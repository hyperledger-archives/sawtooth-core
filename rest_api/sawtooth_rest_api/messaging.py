# Copyright 2017 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ------------------------------------------------------------------------------

import asyncio
from enum import Enum
import logging
import uuid

from google.protobuf.message import DecodeError

import zmq
from zmq.asyncio import Context

from sawtooth_rest_api.protobuf.validator_pb2 import Message

LOGGER = logging.getLogger(__name__)


class _Backoff:
    """Implements a simple backoff mechanism.
    """

    def __init__(self, max_retries=3, interval=100, error=Exception()):
        self.num_retries = 0
        self.max_retries = max_retries
        self.interval = interval
        self.error = error

    async def do_backoff(self, err_msg=" "):
        if self.num_retries == self.max_retries:
            LOGGER.warning("Failed sending message to the Validator. No more "
                           "retries left. Backoff terminated: %s",
                           err_msg)
            raise self.error

        self.num_retries += 1
        LOGGER.warning("Sleeping for %s ms after failed attempt %s of %s to "
                       "send message to the Validator: %s",
                       str(self.num_retries),
                       str(self.max_retries),
                       str(self.interval / 1000),
                       err_msg)

        await asyncio.sleep(self.interval / 1000)
        self.interval *= 2


class _MessageRouter:
    """Manages message, routing them either to an incoming queue or to the
    futures for expected replies.
    """

    def __init__(self):
        self._queue = asyncio.Queue()
        self._futures = {}

    async def _push_incoming(self, msg):
        return await self._queue.put(msg)

    async def incoming(self):
        """Returns the next incoming message.
        """
        msg = await self._queue.get()
        self._queue.task_done()
        return msg

    def expect_reply(self, correlation_id):
        """Informs the router that a reply to the given correlation_id is
        expected.
        """
        self._futures[correlation_id] = asyncio.Future()

    def expected_replies(self):
        """Returns the correlation ids for the expected replies.
        """
        return (c_id for c_id in self._futures)

    async def await_reply(self, correlation_id, timeout=None):
        """Wait for a reply to a given correlation id.  If a timeout is
        provided, it will raise a asyncio.TimeoutError.
        """
        try:
            result = await asyncio.wait_for(
                self._futures[correlation_id], timeout=timeout)

            return result
        finally:
            del self._futures[correlation_id]

    def _set_reply(self, correlation_id, msg):
        if correlation_id in self._futures:
            try:
                self._futures[correlation_id].set_result(msg)
            except asyncio.InvalidStateError as e:
                LOGGER.error(
                    'Attempting to set result on already-resolved future: %s',
                    str(e))

    def _fail_reply(self, correlation_id, err):
        if correlation_id in self._futures and \
                not self._futures[correlation_id].done():
            try:
                self._futures[correlation_id].set_exception(err)
            except asyncio.InvalidStateError as e:
                LOGGER.error(
                    'Attempting to set exception on already-resolved future: '
                    '%s',
                    str(e))

    def fail_all(self, err):
        """Fail all the expected replies with a given error.
        """
        for c_id in self._futures:
            self._fail_reply(c_id, err)

    async def route_msg(self, msg):
        """Given a message, route it either to the incoming queue, or to the
        future associated with its correlation_id.
        """
        if msg.correlation_id in self._futures:
            self._set_reply(msg.correlation_id, msg)
        else:
            await self._push_incoming(msg)


class _Receiver:
    """Receives messages and forwards them to a _MessageRouter.
    """

    def __init__(self, socket, msg_router):
        self._socket = socket
        self._msg_router = msg_router

        self._is_running = False

    async def start(self):
        """Starts receiving messages on the underlying socket and passes them
        to the message router.
        """
        self._is_running = True

        while self._is_running:
            try:
                zmq_msg = await self._socket.recv_multipart()

                message = Message()
                message.ParseFromString(zmq_msg[-1])

                await self._msg_router.route_msg(message)
            except DecodeError as e:
                LOGGER.warning('Unable to decode: %s', e)
            except zmq.ZMQError as e:
                LOGGER.warning('Unable to receive: %s', e)
                return
            except asyncio.CancelledError:
                self._is_running = False

    def cancel(self):
        self._is_running = False


class _Sender:
    """Manages Sending messages over a ZMQ socket.
    """

    def __init__(self, socket, msg_router):
        self._msg_router = msg_router
        self._socket = socket

    async def send(self, message_type, message_content, timeout=None):
        correlation_id = uuid.uuid4().hex

        self._msg_router.expect_reply(correlation_id)

        message = Message(
            correlation_id=correlation_id,
            content=message_content,
            message_type=message_type)

        # Send the message. Backoff and retry in case of an error
        # We want a short backoff and retry attempt, so use the defaults
        # of 3 retries with 200ms of backoff
        backoff = _Backoff(max_retries=3,
                           interval=200,
                           error=SendBackoffTimeoutError())

        while True:
            try:
                await self._socket.send_multipart(
                    [message.SerializeToString()])
                break
            except asyncio.CancelledError:  # pylint: disable=try-except-raise
                raise
            except zmq.error.Again as e:
                await backoff.do_backoff(err_msg=repr(e))

        return await self._msg_router.await_reply(correlation_id,
                                                  timeout=timeout)


class DisconnectError(Exception):
    """Raised when a connection disconnects.
    """

    def __init__(self):
        super().__init__("The connection was lost")


class SendBackoffTimeoutError(Exception):
    """Raised when the send times out.
    """

    def __init__(self):
        super().__init__("Timed out sending message over ZMQ")


class ConnectionEvent(Enum):
    """Event types that indicate a state change in a connection.

    Attributes:
        DISCONNECTED (int): Event fired when a disconnect occurs
        RECONNECTED (int) Event fired on reconnect
    """
    DISCONNECTED = 1
    RECONNECTED = 2


class Connection:
    """A connection, over which validator Message objects may be sent.
    """

    def __init__(self, url):
        self._url = url

        self._ctx = Context.instance()
        self._socket = self._ctx.socket(zmq.DEALER)
        self._socket.identity = uuid.uuid4().hex.encode()[0:16]

        self._msg_router = _MessageRouter()
        self._receiver = _Receiver(self._socket, self._msg_router)
        self._sender = _Sender(self._socket, self._msg_router)

        self._connection_state_listeners = {}

        self._recv_task = None

        # Monitoring properties
        self._monitor_sock = None
        self._monitor_fd = None
        self._monitor_task = None

    @property
    def url(self):
        return self._url

    def open(self):
        """Opens the connection.

        An open connection will monitor for disconnects from the remote end.
        Messages are either received as replies to outgoing messages, or
        received from an incoming queue.
        """
        LOGGER.info('Connecting to %s', self._url)
        asyncio.ensure_future(self._do_start())

    def on_connection_state_change(self, event_type, callback):
        """Register a callback for a specific connection state change.

        Register a callback to be triggered when the connection changes to
        the specified state, signified by a ConnectionEvent.

        The callback must be a coroutine.

        Args:
            event_type (ConnectionEvent): the connection event to listen for
            callback (coroutine): a coroutine to call on the event occurrence
        """
        listeners = self._connection_state_listeners.get(event_type, [])
        listeners.append(callback)
        self._connection_state_listeners[event_type] = listeners

    def _notify_listeners(self, event_type):
        listeners = self._connection_state_listeners.get(event_type, [])
        for coroutine_fn in listeners:
            asyncio.ensure_future(coroutine_fn())

    async def _do_start(self, reconnect=False):
        self._socket.connect(self._url)

        self._monitor_fd = "inproc://monitor.s-{}".format(
            uuid.uuid4().hex[0:5])
        self._monitor_sock = self._socket.get_monitor_socket(
            zmq.EVENT_DISCONNECTED,
            addr=self._monitor_fd)

        self._recv_task = asyncio.ensure_future(self._receiver.start())

        if reconnect:
            self._notify_listeners(ConnectionEvent.RECONNECTED)

        self._monitor_task = asyncio.ensure_future(self._monitor_disconnects())

    async def send(self, message_type, message_content, timeout=None):
        """Sends a message and returns a future for the response.
        """
        return await self._sender.send(
            message_type, message_content, timeout=timeout)

    async def receive(self):
        """Returns a future for an incoming message.
        """
        return await self._msg_router.incoming()

    def close(self):
        """Closes the connection.

        All outstanding futures for replies will be sent a DisconnectError.
        """
        if self._recv_task:
            self._recv_task.cancel()

        self._disable_monitoring()

        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()

        self._receiver.cancel()
        self._socket.close(linger=0)

        self._msg_router.fail_all(DisconnectError())

    def _disable_monitoring(self):
        if self._socket.closed:
            return

        self._socket.disable_monitor()

        if self._monitor_sock:
            self._monitor_sock.disconnect(self._monitor_fd)
            self._monitor_sock.close(linger=0)

            self._monitor_fd = None
            self._monitor_sock = None

    async def _monitor_disconnects(self):
        try:
            cancelled = False
            try:
                await self._monitor_sock.recv_multipart()
            except asyncio.CancelledError:
                cancelled = True

            # Only message received will be a disconnect event
            self._disable_monitoring()

            if not self._socket.closed:
                self._socket.disconnect(self._url)

            # Inform the msg router that all replies failed.
            self._msg_router.fail_all(DisconnectError())

            self._recv_task.cancel()
            self._recv_task = None

            self._notify_listeners(ConnectionEvent.DISCONNECTED)

            if cancelled:
                return

            # start it back up, but first wait a bit to give the other end time
            # to reappear
            try:
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                # We've been cancelled, so let's just exit
                return

            asyncio.ensure_future(self._do_start(reconnect=True))
        except zmq.ZMQError as e:
            # The monitor socket was probably closed
            LOGGER.warning('Error occurred while monitoring the socket: %s', e)

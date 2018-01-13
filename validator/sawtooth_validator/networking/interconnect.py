# Copyright 2016 Intel Corporation
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
from concurrent.futures import CancelledError
from functools import partial
import hashlib
import logging
import queue
from threading import Event
from threading import Lock
import time
import uuid
from collections import namedtuple
from enum import Enum

import zmq
import zmq.auth
from zmq.auth.asyncio import AsyncioAuthenticator
import zmq.asyncio

from sawtooth_validator.concurrent.threadpool import \
    InstrumentedThreadPoolExecutor
from sawtooth_validator.concurrent.thread import InstrumentedThread
from sawtooth_validator.exceptions import LocalConfigurationError
from sawtooth_validator.protobuf import validator_pb2
from sawtooth_validator.networking import future
from sawtooth_validator.protobuf.authorization_pb2 import ConnectionRequest
from sawtooth_validator.protobuf.authorization_pb2 import ConnectionResponse
from sawtooth_validator.protobuf.authorization_pb2 import \
    AuthorizationTrustRequest
from sawtooth_validator.protobuf.authorization_pb2 import \
    AuthorizationChallengeRequest
from sawtooth_validator.protobuf.authorization_pb2 import \
    AuthorizationChallengeResponse
from sawtooth_validator.protobuf.authorization_pb2 import \
    AuthorizationChallengeSubmit
from sawtooth_validator.protobuf.authorization_pb2 import RoleType
from sawtooth_validator.metrics.wrappers import TimerWrapper
from sawtooth_validator.metrics.wrappers import CounterWrapper

LOGGER = logging.getLogger(__name__)

# pylint: disable=too-many-lines


class ConnectionType(Enum):
    OUTBOUND_CONNECTION = 1
    ZMQ_IDENTITY = 2


class ConnectionStatus(Enum):
    CONNECTED = 1
    CONNECTION_REQUEST = 2
    AUTH_CHALLENGE_REQUEST = 3


class AuthorizationType(Enum):
    TRUST = 1
    CHALLENGE = 2


ConnectionInfo = namedtuple('ConnectionInfo',
                            ['connection_type', 'connection', 'uri',
                             'status', 'public_key'])


def _generate_id():
    return uuid.uuid4().hex.encode()


def get_enum_name(enum_value):
    return validator_pb2.Message.MessageType.Name(enum_value)


_STARTUP_COMPLETE_SENTINEL = 1


class _SendReceive(object):
    def __init__(self, connection, address, futures, connections,
                 zmq_identity=None, dispatcher=None, secured=False,
                 server_public_key=None, server_private_key=None,
                 heartbeat=False, heartbeat_interval=10,
                 connection_timeout=60, monitor=False,
                 metrics_registry=None):
        """
        Constructor for _SendReceive.

        Args:
            connection (str): A locally unique identifier for this
                thread's connection. Used to identify the connection
                in the dispatcher for transmitting responses.
            futures (future.FutureCollection): A Map of correlation ids to
                futures
            connections (dict): A dictionary that uses a
                sha512 hash as the keys and either an OutboundConnection
                or string identity as values.
            zmq_identity (bytes): Used to identify the dealer socket
            address (str): The endpoint to bind or connect to.
            dispatcher (dispatcher.Dispather): Used to handle messages in a
                coordinated way.
            secured (bool): Whether or not to start the socket in
                secure mode -- using zmq auth.
            server_public_key (bytes): A public key to use in verifying
                server identity as part of the zmq auth handshake.
            server_private_key (bytes): A private key corresponding to
                server_public_key used by the server socket to sign
                messages are part of the zmq auth handshake.
            heartbeat (bool): Whether or not to send ping messages.
            heartbeat_interval (int): Number of seconds between ping
                messages on an otherwise quiet connection.
            connection_timeout (int): Number of seconds after which a
                connection is considered timed out.
        """
        self._connection = connection
        self._dispatcher = dispatcher
        self._futures = futures
        self._address = address
        self._zmq_identity = zmq_identity
        self._secured = secured
        self._server_public_key = server_public_key
        self._server_private_key = server_private_key
        self._heartbeat = heartbeat
        self._heartbeat_interval = heartbeat_interval
        self._connection_timeout = connection_timeout

        self._event_loop = None
        self._context = None
        self._socket = None
        self._auth = None
        self._ready = Event()

        # The last time a message was received over an outbound
        # socket we established.
        self._last_message_time = None

        # A map of zmq identities to last message received times
        # for inbound connections to our zmq.ROUTER socket.
        self._last_message_times = {}

        self._connections = connections
        self._identities_to_connection_ids = {}
        self._monitor = monitor

        self._check_connections = None
        self._monitor_fd = None
        self._monitor_sock = None

        self._metrics_registry = metrics_registry
        self._received_message_counters = {}
        self._dispatcher_queue = None

    @property
    def connection(self):
        return self._connection

    def _is_connection_lost(self, last_timestamp):
        return (time.time() - last_timestamp >
                self._connection_timeout)

    def _identity_to_connection_id(self, zmq_identity):
        if zmq_identity not in self._identities_to_connection_ids:
            self._identities_to_connection_ids[zmq_identity] = \
                hashlib.sha512(zmq_identity).hexdigest()

        return self._identities_to_connection_ids[zmq_identity]

    def _get_received_message_counter(self, tag):
        if tag not in self._received_message_counters:
            if self._metrics_registry:
                self._received_message_counters[tag] = CounterWrapper(
                    self._metrics_registry.counter(
                        'interconnect_received_message_count', tags=[
                            'message_type={}'.format(tag)]))
            else:
                self._received_message_counters[tag] = CounterWrapper()
        return self._received_message_counters[tag]

    @asyncio.coroutine
    def _do_heartbeat(self):
        while True:
            try:
                if self._socket.getsockopt(zmq.TYPE) == zmq.ROUTER:
                    yield from self._do_router_heartbeat()
                elif self._socket.getsockopt(zmq.TYPE) == zmq.DEALER:
                    yield from self._do_dealer_heartbeat()
                yield from asyncio.sleep(self._heartbeat_interval)
            except CancelledError:
                # The concurrent.futures.CancelledError is caught by asyncio
                # when the Task associated with the coroutine is cancelled.
                # The raise is required to stop this component.
                raise
            except Exception as e:  # pylint: disable=broad-except
                LOGGER.exception(
                    "An error occurred while sending heartbeat: %s", e)

    @asyncio.coroutine
    def _do_router_heartbeat(self):
        check_time = time.time()
        expired = \
            [(ident, check_time - timestamp)
             for ident, timestamp
             in self._last_message_times.items()
             if check_time - timestamp > self._heartbeat_interval]
        for zmq_identity, elapsed in expired:
            if self._is_connection_lost(
                    self._last_message_times[zmq_identity]):
                LOGGER.info("No response from %s in %s seconds"
                            " - removing connection.",
                            self._identity_to_connection_id(
                                zmq_identity),
                            elapsed)
                self.remove_connected_identity(zmq_identity)
            else:
                # This should only log the start of the heartbeat interval, so
                # as to keep the message from  occurring
                # _connection_timeout / _heartbeat_interval # times
                if elapsed < 2 * self._heartbeat_interval:
                    LOGGER.debug("No response from %s in %s seconds"
                                 " - beginning heartbeat pings.",
                                 self._identity_to_connection_id(
                                     zmq_identity),
                                 elapsed)
                message = validator_pb2.Message(
                    correlation_id=_generate_id(),
                    # Ping request is an empty message, so an empty byte string
                    # here is an optimization
                    content=b'',
                    message_type=validator_pb2.Message.PING_REQUEST
                )
                fut = future.Future(
                    message.correlation_id,
                    message.content,
                )
                self._futures.put(fut)
                message_frame = [
                    bytes(zmq_identity),
                    message.SerializeToString()
                ]
                yield from self._send_message_frame(message_frame)

    @asyncio.coroutine
    def _do_dealer_heartbeat(self):
        if self._last_message_time and \
                self._is_connection_lost(self._last_message_time):
            LOGGER.info("No response from %s in %s seconds"
                        " - removing connection.",
                        self._connection,
                        self._last_message_time)
            connection_id = hashlib.sha512(
                self.connection.encode()).hexdigest()
            if connection_id in self._connections:
                del self._connections[connection_id]
            yield from self._stop()

    def remove_connected_identity(self, zmq_identity):
        if zmq_identity in self._last_message_times:
            del self._last_message_times[zmq_identity]
        if zmq_identity in self._identities_to_connection_ids:
            del self._identities_to_connection_ids[zmq_identity]
        connection_id = self._identity_to_connection_id(zmq_identity)
        if connection_id in self._connections:
            del self._connections[connection_id]

    def _received_from_identity(self, zmq_identity):
        self._last_message_times[zmq_identity] = time.time()
        connection_id = self._identity_to_connection_id(zmq_identity)
        if connection_id not in self._connections:
            self._connections[connection_id] = \
                ConnectionInfo(ConnectionType.ZMQ_IDENTITY,
                               zmq_identity,
                               None,
                               None,
                               None)

    @asyncio.coroutine
    def _dispatch_message(self):
        while True:
            try:
                queue_size = self._dispatcher_queue.qsize()
                if queue_size > 10:
                    LOGGER.debug("Dispatch queue size: %s", queue_size)

                zmq_identity, msg_bytes = \
                    yield from self._dispatcher_queue.get()
                message = validator_pb2.Message()
                message.ParseFromString(msg_bytes)

                tag = get_enum_name(message.message_type)
                self._get_received_message_counter(tag).inc()

                if zmq_identity is not None:
                    connection_id = \
                        self._identity_to_connection_id(zmq_identity)
                else:
                    connection_id = \
                        self._identity_to_connection_id(
                            self._connection.encode())
                try:
                    self._futures.set_result(
                        message.correlation_id,
                        future.FutureResult(
                            message_type=message.message_type,
                            content=message.content,
                            connection_id=connection_id))
                except future.FutureCollectionKeyError:
                    self._dispatcher.dispatch(self._connection,
                                              message,
                                              connection_id)
                else:
                    my_future = self._futures.get(message.correlation_id)
                    my_future.timer_stop()
                    self._futures.remove(message.correlation_id)

            except CancelledError:
                # The concurrent.futures.CancelledError is caught by asyncio
                # when the Task associated with the coroutine is cancelled.
                # The raise is required to stop this component.
                raise
            except Exception as e:  # pylint: disable=broad-except
                LOGGER.exception("Received a message on address %s that "
                                 "caused an error: %s", self._address, e)

    @asyncio.coroutine
    def _receive_message(self):
        """
        Internal coroutine for receiving messages
        """
        while True:
            try:
                if self._socket.getsockopt(zmq.TYPE) == zmq.ROUTER:
                    zmq_identity, msg_bytes = \
                        yield from self._socket.recv_multipart()
                    self._received_from_identity(zmq_identity)
                    self._dispatcher_queue.put_nowait(
                        (zmq_identity, msg_bytes))
                else:
                    msg_bytes = yield from self._socket.recv()
                    self._last_message_time = time.time()
                    self._dispatcher_queue.put_nowait((None, msg_bytes))

            except CancelledError:
                # The concurrent.futures.CancelledError is caught by asyncio
                # when the Task associated with the coroutine is cancelled.
                # The raise is required to stop this component.
                raise
            except Exception as e:  # pylint: disable=broad-except
                LOGGER.exception("Received a message on address %s that "
                                 "caused an error: %s", self._address, e)

    @asyncio.coroutine
    def _send_message_frame(self, message_frame):
        yield from self._socket.send_multipart(message_frame)

    def send_message(self, msg, connection_id=None):
        """
        :param msg: protobuf validator_pb2.Message
        """
        zmq_identity = None
        if connection_id is not None and self._connections is not None:
            if connection_id in self._connections:
                connection_info = self._connections.get(connection_id)
                if connection_info.connection_type == \
                        ConnectionType.ZMQ_IDENTITY:
                    zmq_identity = connection_info.connection
            else:
                LOGGER.debug("Can't send to %s, not in self._connections",
                             connection_id)

        self._ready.wait()

        if zmq_identity is None:
            message_bundle = [msg.SerializeToString()]
        else:
            message_bundle = [bytes(zmq_identity),
                              msg.SerializeToString()]

        try:
            asyncio.run_coroutine_threadsafe(
                self._send_message_frame(message_bundle),
                self._event_loop)
        except RuntimeError:
            # run_coroutine_threadsafe will throw a RuntimeError if
            # the eventloop is closed. This occurs on shutdown.
            pass

    @asyncio.coroutine
    def _send_last_message(self, identity, msg):
        LOGGER.debug("%s sending last message %s to %s",
                     self._connection,
                     get_enum_name(msg.message_type),
                     identity if identity else self._address)

        if identity is None:
            message_bundle = [msg.SerializeToString()]
        else:
            message_bundle = [bytes(identity),
                              msg.SerializeToString()]

        yield from self._socket.send_multipart(message_bundle)
        if identity is None:
            if self._connection != "ServerThread":
                self.shutdown()
        else:
            self.remove_connected_identity(identity)

    def send_last_message(self, msg, connection_id=None):
        """
        Should be used instead of send_message, when you want to close the
        connection once the message is sent.

        :param msg: protobuf validator_pb2.Message
        """
        zmq_identity = None
        if connection_id is not None and self._connections is not None:
            if connection_id in self._connections:
                connection_info = self._connections.get(connection_id)
                if connection_info.connection_type == \
                        ConnectionType.ZMQ_IDENTITY:
                    zmq_identity = connection_info.connection
                del self._connections[connection_id]

            else:
                LOGGER.debug("Can't send to %s, not in self._connections",
                             connection_id)
                return

        self._ready.wait()

        try:
            asyncio.run_coroutine_threadsafe(
                self._send_last_message(zmq_identity, msg),
                self._event_loop)
        except RuntimeError:
            # run_coroutine_threadsafe will throw a RuntimeError if
            # the eventloop is closed. This occurs on shutdown.
            pass

    def setup(self, socket_type, complete_or_error_queue):
        """Setup the asyncio event loop.

        Args:
            socket_type (int from zmq.*): One of zmq.DEALER or zmq.ROUTER
            complete_or_error_queue (queue.Queue): A way to propagate errors
                back to the calling thread. Needed since this function is
                directly used in Thread.

        Returns:
            None
        """
        try:
            if self._secured:
                if self._server_public_key is None or \
                        self._server_private_key is None:
                    raise LocalConfigurationError(
                        "Attempting to start socket in secure mode, "
                        "but complete server keys were not provided")

            self._event_loop = zmq.asyncio.ZMQEventLoop()
            asyncio.set_event_loop(self._event_loop)
            self._context = zmq.asyncio.Context()
            self._socket = self._context.socket(socket_type)

            if socket_type == zmq.DEALER:
                self._socket.identity = "{}-{}".format(
                    self._zmq_identity,
                    hashlib.sha512(uuid.uuid4().hex.encode()
                                   ).hexdigest()[:23]).encode('ascii')

                if self._secured:
                    # Generate ephemeral certificates for this connection

                    public_key, secretkey = zmq.curve_keypair()
                    self._socket.curve_publickey = public_key
                    self._socket.curve_secretkey = secretkey
                    self._socket.curve_serverkey = self._server_public_key

                self._socket.connect(self._address)
            elif socket_type == zmq.ROUTER:
                if self._secured:
                    auth = AsyncioAuthenticator(self._context)
                    self._auth = auth
                    auth.start()
                    auth.configure_curve(domain='*',
                                         location=zmq.auth.CURVE_ALLOW_ANY)

                    self._socket.curve_secretkey = self._server_private_key
                    self._socket.curve_publickey = self._server_public_key
                    self._socket.curve_server = True

                try:
                    self._socket.bind(self._address)
                except zmq.error.ZMQError as e:
                    raise LocalConfigurationError(
                        "Can't bind to {}: {}".format(self._address,
                                                      str(e)))
                else:
                    LOGGER.info("Listening on %s", self._address)

            self._dispatcher.add_send_message(self._connection,
                                              self.send_message)
            self._dispatcher.add_send_last_message(self._connection,
                                                   self.send_last_message)

            asyncio.ensure_future(self._receive_message(),
                                  loop=self._event_loop)

            asyncio.ensure_future(self._dispatch_message(),
                                  loop=self._event_loop)

            self._dispatcher_queue = asyncio.Queue()

            if self._monitor:
                self._monitor_fd = "inproc://monitor.s-{}".format(
                    _generate_id()[0:5])
                self._monitor_sock = self._socket.get_monitor_socket(
                    zmq.EVENT_DISCONNECTED,
                    addr=self._monitor_fd)
                asyncio.ensure_future(self._monitor_disconnects(),
                                      loop=self._event_loop)

        except Exception as e:
            # Put the exception on the queue where in start we are waiting
            # for it.
            complete_or_error_queue.put_nowait(e)
            raise

        if self._heartbeat:
            asyncio.ensure_future(self._do_heartbeat(), loop=self._event_loop)

        # Put a 'complete with the setup tasks' sentinel on the queue.
        complete_or_error_queue.put_nowait(_STARTUP_COMPLETE_SENTINEL)

        asyncio.ensure_future(self._notify_started(), loop=self._event_loop)

        self._event_loop.run_forever()
        # event_loop.stop called elsewhere will cause the loop to break out
        # of run_forever then it can be closed and the context destroyed.
        self._event_loop.close()
        self._socket.close(linger=0)
        if self._monitor:
            self._monitor_sock.close(linger=0)
        self._context.destroy(linger=0)

    @asyncio.coroutine
    def _monitor_disconnects(self):
        while True:
            try:
                yield from self._monitor_sock.recv_multipart()
                self._check_connections()
            except CancelledError:
                # The concurrent.futures.CancelledError is caught by asyncio
                # when the Task associated with the coroutine is cancelled.
                # The raise is required to stop this component.
                raise
            except Exception as e:  # pylint: disable=broad-except
                LOGGER.exception(
                    "An error occurred while sending heartbeat: %s", e)

    def set_check_connections(self, function):
        self._check_connections = function

    @asyncio.coroutine
    def _stop_auth(self):
        if self._auth is not None:
            self._auth.stop()

    @asyncio.coroutine
    def _stop_event_loop(self):
        self._event_loop.stop()

    @asyncio.coroutine
    def _stop(self):
        self._dispatcher.remove_send_message(self._connection)
        self._dispatcher.remove_send_last_message(self._connection)
        yield from self._stop_auth()
        tasks = list(asyncio.Task.all_tasks(self._event_loop).copy())
        for task in tasks:
            task.cancel()

        asyncio.ensure_future(self._stop_event_loop())

    @asyncio.coroutine
    def _notify_started(self):
        self._ready.set()

    def shutdown(self):
        self._dispatcher.remove_send_message(self._connection)
        self._dispatcher.remove_send_last_message(self._connection)
        if self._event_loop is None:
            return
        if self._event_loop.is_closed():
            return

        if self._event_loop.is_running():
            if self._auth is not None:
                self._event_loop.call_soon_threadsafe(self._auth.stop)
        else:
            # event loop was never started, so the only Task that is running
            # is the Auth Task.
            self._event_loop.run_until_complete(self._stop_auth())
        # Cancel all running tasks
        tasks = list(asyncio.Task.all_tasks(self._event_loop).copy())
        for task in tasks:
            self._event_loop.call_soon_threadsafe(task.cancel)
        while tasks:
            for task in tasks.copy():
                if task.done() is True:
                    tasks.remove(task)
            time.sleep(.2)
        if self._event_loop is not None:
            try:
                self._event_loop.call_soon_threadsafe(self._event_loop.stop)
            except RuntimeError:
                # Depending on the timing of shutdown, the event loop may
                # already be shutdown from _stop(). If it is,
                # call_soon_threadsafe will raise a RuntimeError,
                # which can safely be ignored.
                pass


class Interconnect(object):
    def __init__(self,
                 endpoint,
                 dispatcher,
                 zmq_identity=None,
                 secured=False,
                 server_public_key=None,
                 server_private_key=None,
                 heartbeat=False,
                 public_endpoint=None,
                 connection_timeout=60,
                 max_incoming_connections=100,
                 monitor=False,
                 max_future_callback_workers=10,
                 roles=None,
                 authorize=False,
                 signer=None,
                 metrics_registry=None
                 ):
        """
        Constructor for Interconnect.

        Args:
            secured (bool): Whether or not to start the 'server' socket
                and associated Connection sockets in secure mode --
                using zmq auth.
            server_public_key (bytes): A public key to use in verifying
                server identity as part of the zmq auth handshake.
            server_private_key (bytes): A private key corresponding to
                server_public_key used by the server socket to sign
                messages are part of the zmq auth handshake.
            heartbeat (bool): Whether or not to send ping messages.
            max_future_callback_workers (int): max number of workers for future
                callbacks, defaults to 10
            signer (:obj:`Signer`): cryptographic signer for the validator
        """
        self._endpoint = endpoint
        self._public_endpoint = public_endpoint
        self._future_callback_threadpool = InstrumentedThreadPoolExecutor(
            max_workers=max_future_callback_workers,
            name='FutureCallback')
        self._futures = future.FutureCollection(
            resolving_threadpool=self._future_callback_threadpool)
        self._dispatcher = dispatcher
        self._zmq_identity = zmq_identity
        self._secured = secured
        self._server_public_key = server_public_key
        self._server_private_key = server_private_key
        self._heartbeat = heartbeat
        self._connection_timeout = connection_timeout
        self._connections_lock = Lock()
        self._connections = {}
        self.outbound_connections = {}
        self._max_incoming_connections = max_incoming_connections
        self._roles = {}
        # if roles are None, default to AuthorizationType.TRUST
        if roles is None:
            self._roles["network"] = AuthorizationType.TRUST
        else:
            self._roles = {}
            for role in roles:
                if roles[role] == "challenge":
                    self._roles[role] = AuthorizationType.CHALLENGE
                else:
                    self._roles[role] = AuthorizationType.TRUST

        self._authorize = authorize
        self._signer = signer

        self._send_receive_thread = _SendReceive(
            "ServerThread",
            connections=self._connections,
            address=endpoint,
            dispatcher=dispatcher,
            futures=self._futures,
            secured=secured,
            server_public_key=server_public_key,
            server_private_key=server_private_key,
            heartbeat=heartbeat,
            connection_timeout=connection_timeout,
            monitor=monitor,
            metrics_registry=metrics_registry)

        self._thread = None

        self._metrics_registry = metrics_registry
        self._send_response_timers = {}

    @property
    def roles(self):
        return self._roles

    @property
    def endpoint(self):
        return self._endpoint

    def _get_send_response_timer(self, tag):
        if tag not in self._send_response_timers:
            if self._metrics_registry:
                self._send_response_timers[tag] = TimerWrapper(
                    self._metrics_registry.timer(
                        'interconnect_send_response_time', tags=[
                            'message_type={}'.format(tag)]))
            else:
                self._send_response_timers[tag] = TimerWrapper()
        return self._send_response_timers[tag]

    def connection_id_to_public_key(self, connection_id):
        """
        Get stored public key for a connection.
        """
        if connection_id in self._connections:
            connection_info = self._connections[connection_id]
            return connection_info.public_key
        return None

    def connection_id_to_endpoint(self, connection_id):
        """
        Get stored public key for a connection.
        """
        if connection_id in self._connections:
            connection_info = self._connections[connection_id]
            return connection_info.uri
        return None

    def get_connection_status(self, connection_id):
        """
        Get status of the connection during Role enforcement.
        """
        if connection_id in self._connections:
            connection_info = self._connections[connection_id]
            return connection_info.status
        return None

    def set_check_connections(self, function):
        self._send_receive_thread.set_check_connections(function)

    def allow_inbound_connection(self):
        """Determines if an additional incoming network connection
        should be permitted.

        Returns:
            bool
        """
        LOGGER.debug("Determining whether inbound connection should "
                     "be allowed. num connections: %s max %s",
                     len(self._connections),
                     self._max_incoming_connections)
        return self._max_incoming_connections >= len(self._connections)

    def add_outbound_connection(self, uri):
        """Adds an outbound connection to the network.

        Args:
            uri (str): The zmq-style (e.g. tcp://hostname:port) uri
                to attempt to connect to.
        """
        LOGGER.debug("Adding connection to %s", uri)
        conn = OutboundConnection(
            connections=self._connections,
            endpoint=uri,
            dispatcher=self._dispatcher,
            zmq_identity=self._zmq_identity,
            secured=self._secured,
            server_public_key=self._server_public_key,
            server_private_key=self._server_private_key,
            future_callback_threadpool=self._future_callback_threadpool,
            heartbeat=True,
            connection_timeout=self._connection_timeout,
            metrics_registry=self._metrics_registry)

        self.outbound_connections[uri] = conn
        conn.start()

        self._add_connection(conn, uri)

        connect_message = ConnectionRequest(endpoint=self._public_endpoint)
        conn.send(
            validator_pb2.Message.NETWORK_CONNECT,
            connect_message.SerializeToString(),
            callback=partial(
                self._connect_callback,
                connection=conn,
            ))

        return conn

    def send_connect_request(self, connection_id):
        """
        Send ConnectionRequest to an inbound connection. This allows
        the validator to be authorized by the incoming connection.
        """
        connect_message = ConnectionRequest(endpoint=self._public_endpoint)
        self._safe_send(
            validator_pb2.Message.NETWORK_CONNECT,
            connect_message.SerializeToString(),
            connection_id,
            callback=partial(
                self._inbound_connection_request_callback,
                connection_id=connection_id))

    def _connect_callback(self, request, result, connection=None):
        connection_response = ConnectionResponse()
        connection_response.ParseFromString(result.content)

        if connection_response.status == connection_response.ERROR:
            LOGGER.debug("Received an error response to the NETWORK_CONNECT "
                         "we sent. Removing connection: %s",
                         connection.connection_id)
            self.remove_connection(connection.connection_id)
        elif connection_response.status == connection_response.OK:

            LOGGER.debug("Connection to %s was acknowledged",
                         connection.connection_id)
            if self._authorize:
                # Send correct Authorization Request for network role
                auth_type = {"trust": [], "challenge": []}
                for role_entry in connection_response.roles:
                    if role_entry.auth_type == connection_response.TRUST:
                        auth_type["trust"].append(role_entry.role)
                    elif role_entry.auth_type == connection_response.CHALLENGE:
                        auth_type["challenge"].append(role_entry.role)

                if auth_type["trust"]:
                    auth_trust_request = AuthorizationTrustRequest(
                        roles=auth_type["trust"],
                        public_key=self._signer.get_public_key().as_hex())

                    connection.send(
                        validator_pb2.Message.AUTHORIZATION_TRUST_REQUEST,
                        auth_trust_request.SerializeToString(),
                        callback=partial(
                            self._check_trust_success,
                            connection_id=connection.connection_id))

                if auth_type["challenge"]:
                    auth_challenge_request = AuthorizationChallengeRequest()
                    connection.send(
                        validator_pb2.Message.AUTHORIZATION_CHALLENGE_REQUEST,
                        auth_challenge_request.SerializeToString(),
                        callback=partial(
                            self._challenge_authorization_callback,
                            connection=connection))

    def _inbound_connection_request_callback(self, request, result,
                                             connection_id=None):
        connection_response = ConnectionResponse()
        connection_response.ParseFromString(result.content)
        if connection_response.status == connection_response.ERROR:
            LOGGER.debug("Received an error response to the NETWORK_CONNECT "
                         "we sent. Removing connection: %s",
                         connection_id)
            self.remove_connection(connection_id)

        # Send correct Authorization Request for network role
        auth_type = {"trust": [], "challenge": []}
        for role_entry in connection_response.roles:
            if role_entry.auth_type == connection_response.TRUST:
                auth_type["trust"].append(role_entry.role)
            elif role_entry.auth_type == connection_response.CHALLENGE:
                auth_type["challenge"].append(role_entry.role)

        if auth_type["trust"]:
            auth_trust_request = AuthorizationTrustRequest(
                roles=[RoleType.Value("NETWORK")],
                public_key=self._signer.get_public_key().as_hex())
            self._safe_send(
                validator_pb2.Message.AUTHORIZATION_TRUST_REQUEST,
                auth_trust_request.SerializeToString(),
                connection_id,
                callback=partial(self._check_trust_success,
                                 connection_id=connection_id)
            )

        if auth_type["challenge"]:
            auth_challenge_request = AuthorizationChallengeRequest()
            self._safe_send(
                validator_pb2.Message.AUTHORIZATION_CHALLENGE_REQUEST,
                auth_challenge_request.SerializeToString(),
                connection_id,
                callback=partial(
                    self._inbound_challenge_authorization_callback,
                    connection_id=connection_id)
            )

    def _challenge_authorization_callback(self, request, result,
                                          connection=None,
                                          ):
        if result.message_type != \
                validator_pb2.Message.AUTHORIZATION_CHALLENGE_RESPONSE:
            LOGGER.debug("Unable to complete Challenge Authorization.")
            self.remove_connection(connection.connection_id)
            return

        auth_challenge_response = AuthorizationChallengeResponse()
        auth_challenge_response.ParseFromString(result.content)
        payload = auth_challenge_response.payload
        signature = self._signer.sign(payload)

        auth_challenge_submit = AuthorizationChallengeSubmit(
            public_key=self._signer.get_public_key().as_hex(),
            signature=signature,
            roles=[RoleType.Value("NETWORK")]
        )

        connection.send(
            validator_pb2.Message.AUTHORIZATION_CHALLENGE_SUBMIT,
            auth_challenge_submit.SerializeToString(),
            callback=partial(self._check_challenge_success,
                             connection_id=connection.connection_id))

    def _inbound_challenge_authorization_callback(self, request, result,
                                                  connection_id=None):
        if result.message_type != \
                validator_pb2.Message.AUTHORIZATION_CHALLENGE_RESPONSE:
            LOGGER.debug("Unable to complete Challenge Authorization.")
            self.remove_connection(connection_id)
            return

        auth_challenge_response = AuthorizationChallengeResponse()
        auth_challenge_response.ParseFromString(result.content)
        payload = auth_challenge_response.payload
        signature = self._signer.sign(payload)

        auth_challenge_submit = AuthorizationChallengeSubmit(
            public_key=self._signer.get_public_key().as_hex(),
            signature=signature,
            roles=[RoleType.Value("NETWORK")])

        self._safe_send(
            validator_pb2.Message.AUTHORIZATION_CHALLENGE_SUBMIT,
            auth_challenge_submit.SerializeToString(),
            connection_id,
            callback=partial(self._check_challenge_success,
                             connection_id=connection_id))

    def _check_trust_success(self, request, result, connection_id=None):
        if result.message_type != \
                validator_pb2.Message.AUTHORIZATION_TRUST_RESPONSE:
            LOGGER.debug("Unable to complete Trust Authorization.")
            self.remove_connection(connection_id)

    def _check_challenge_success(self, request, result, connection_id=None):
        if result.message_type != \
                validator_pb2.Message.AUTHORIZATION_CHALLENGE_RESULT:
            LOGGER.debug("Unable to complete Challenge Authorization.")
            self.remove_connection(connection_id)

    def send(self, message_type, data, connection_id, callback=None,
             one_way=False):
        """
        Send a message of message_type
        :param connection_id: the identity for the connection to send to
        :param message_type: validator_pb2.Message.* enum value
        :param data: bytes serialized protobuf
        :return: future.Future
        """
        if connection_id not in self._connections:
            raise ValueError("Unknown connection id: {}".format(connection_id))
        connection_info = self._connections.get(connection_id)
        if connection_info.connection_type == \
                ConnectionType.ZMQ_IDENTITY:
            message = validator_pb2.Message(
                correlation_id=_generate_id(),
                content=data,
                message_type=message_type)

            timer_tag = get_enum_name(message.message_type)
            timer_ctx = self._get_send_response_timer(timer_tag).time()
            fut = future.Future(
                message.correlation_id,
                message.content,
                callback,
                timer_ctx=timer_ctx)
            if not one_way:
                self._futures.put(fut)

            self._send_receive_thread.send_message(msg=message,
                                                   connection_id=connection_id)
            return fut

        return connection_info.connection.send(
            message_type,
            data,
            callback=callback,
            one_way=one_way)

    def start(self):
        complete_or_error_queue = queue.Queue()
        self._thread = InstrumentedThread(
            target=self._send_receive_thread.setup,
            args=(zmq.ROUTER, complete_or_error_queue))
        self._thread.name = self.__class__.__name__ + self._thread.name
        self._thread.start()
        # Blocking in startup until the background thread has made it to
        # running the event loop or error.
        err = complete_or_error_queue.get(block=True)
        if err != _STARTUP_COMPLETE_SENTINEL:
            raise err

    def stop(self):
        self._send_receive_thread.shutdown()
        for conn in self.outbound_connections.values():
            conn.stop()
        self._future_callback_threadpool.shutdown(wait=True)

    def get_connection_id_by_endpoint(self, endpoint):
        """Returns the connection id associated with a publically
        reachable endpoint or raises KeyError if the endpoint is not
        found.

        Args:
            endpoint (str): A zmq-style uri which identifies a publically
                reachable endpoint.
        """
        for connection_id in self._connections:
            connection_info = self._connections[connection_id]
            if connection_info.uri == endpoint:
                return connection_id
        raise KeyError()

    def update_connection_endpoint(self, connection_id, endpoint):
        """Adds the endpoint to the connection definition. When the
        connection is created by the send/receive thread, we do not
        yet have the endpoint of the remote node. That is not known
        until we process the incoming ConnectRequest.

        Args:
            connection_id (str): The identifier for the connection.
            endpoint (str): A zmq-style uri which identifies a publically
                reachable endpoint.
        """
        if connection_id in self._connections:
            connection_info = self._connections[connection_id]
            self._connections[connection_id] = \
                ConnectionInfo(connection_info.connection_type,
                               connection_info.connection,
                               endpoint,
                               connection_info.status,
                               connection_info.public_key)

        else:
            LOGGER.debug("Could not update the endpoint %s for "
                         "connection_id %s. The connection does not "
                         "exist.",
                         endpoint,
                         connection_id)

    def update_connection_public_key(self, connection_id, public_key):
        """Adds the public_key to the connection definition.

        Args:
            connection_id (str): The identifier for the connection.
            public_key (str): The public key used to enforce permissions on
                connections.

        """
        if connection_id in self._connections:
            connection_info = self._connections[connection_id]
            self._connections[connection_id] = \
                ConnectionInfo(connection_info.connection_type,
                               connection_info.connection,
                               connection_info.uri,
                               connection_info.status,
                               public_key)
        else:
            LOGGER.debug("Could not update the public key %s for "
                         "connection_id %s. The connection does not "
                         "exist.",
                         public_key,
                         connection_id)

    def update_connection_status(self, connection_id, status):
        """Adds a status to the connection definition. This allows the handlers
        to ensure that the connection is following the steps in order for
        authorization enforement.

        Args:
            connection_id (str): The identifier for the connection.
            status (ConnectionStatus): An enum value for the stage of
                authortization the connection is at.

        """
        if connection_id in self._connections:
            connection_info = self._connections[connection_id]
            self._connections[connection_id] = \
                ConnectionInfo(connection_info.connection_type,
                               connection_info.connection,
                               connection_info.uri,
                               status,
                               connection_info.public_key)
        else:
            LOGGER.debug("Could not update the status to %s for "
                         "connection_id %s. The connection does not "
                         "exist.",
                         status,
                         connection_id)

    def _add_connection(self, connection, uri=None):
        with self._connections_lock:
            connection_id = connection.connection_id
            if connection_id not in self._connections:
                self._connections[connection_id] = \
                    ConnectionInfo(ConnectionType.OUTBOUND_CONNECTION,
                                   connection,
                                   uri,
                                   None,
                                   None)

    def remove_connection(self, connection_id):
        with self._connections_lock:
            LOGGER.debug("Removing connection: %s", connection_id)
            if connection_id in self._connections:
                connection_info = self._connections[connection_id]

                if connection_info.connection_type == \
                        ConnectionType.OUTBOUND_CONNECTION:
                    connection_info.connection.stop()
                    del self._connections[connection_id]

                elif connection_info.connection_type == \
                        ConnectionType.ZMQ_IDENTITY:
                    self._send_receive_thread.remove_connected_identity(
                        connection_info.connection)

    def send_last_message(self, message_type, data,
                          connection_id, callback=None, one_way=False):
        """
        Send a message of message_type and close the connection.
        :param connection_id: the identity for the connection to send to
        :param message_type: validator_pb2.Message.* enum value
        :param data: bytes serialized protobuf
        :return: future.Future
        """
        if connection_id not in self._connections:
            raise ValueError("Unknown connection id: {}".format(connection_id))
        connection_info = self._connections.get(connection_id)
        if connection_info.connection_type == \
                ConnectionType.ZMQ_IDENTITY:
            message = validator_pb2.Message(
                correlation_id=_generate_id(),
                content=data,
                message_type=message_type)

            fut = future.Future(message.correlation_id, message.content,
                                callback)

            if not one_way:
                self._futures.put(fut)

            self._send_receive_thread.send_last_message(
                msg=message,
                connection_id=connection_id)
            return fut

        del self._connections[connection_id]
        return connection_info.connection.send_last_message(
            message_type,
            data,
            callback=callback)

    def has_connection(self, connection_id):
        if connection_id in self._connections:
            return True
        return False

    def is_outbound_connection(self, connection_id):
        connection_info = self._connections[connection_id]
        if connection_info.connection_type == \
                ConnectionType.OUTBOUND_CONNECTION:
            return True
        return False

    def _safe_send(self, message_type, message, connection_id, callback=None):
        try:
            self.send(
                message_type,
                message,
                connection_id,
                callback=callback
            )
        except ValueError:
            LOGGER.debug("Connection disconnected: %s", connection_id)


class OutboundConnection(object):
    def __init__(self,
                 connections,
                 endpoint,
                 dispatcher,
                 zmq_identity,
                 secured,
                 server_public_key,
                 server_private_key,
                 future_callback_threadpool,
                 heartbeat=True,
                 connection_timeout=60,
                 metrics_registry=None):
        self._futures = future.FutureCollection(
            resolving_threadpool=future_callback_threadpool)
        self._zmq_identity = zmq_identity
        self._endpoint = endpoint
        self._dispatcher = dispatcher
        self._secured = secured
        self._server_public_key = server_public_key
        self._server_private_key = server_private_key
        self._heartbeat = heartbeat
        self._connection_timeout = connection_timeout
        self._connection_id = None

        self._send_receive_thread = _SendReceive(
            "OutboundConnectionThread-{}".format(self._endpoint),
            endpoint,
            connections=connections,
            dispatcher=self._dispatcher,
            futures=self._futures,
            zmq_identity=zmq_identity,
            secured=secured,
            server_public_key=server_public_key,
            server_private_key=server_private_key,
            heartbeat=heartbeat,
            connection_timeout=connection_timeout,
            metrics_registry=metrics_registry)

        self._thread = None
        self._metrics_registry = metrics_registry

    @property
    def connection_id(self):
        if not self._connection_id:
            self._connection_id = hashlib.sha512(
                self._send_receive_thread.connection.encode()).hexdigest()

        return self._connection_id

    def send(self, message_type, data, callback=None, one_way=False):
        """Sends a message of message_type

        Args:
            message_type (validator_pb2.Message): enum value
            data (bytes): serialized protobuf
            callback (function): a callback function to call when a
                response to this message is received

        Returns:
            future.Future
        """
        message = validator_pb2.Message(
            correlation_id=_generate_id(),
            content=data,
            message_type=message_type)

        fut = future.Future(message.correlation_id, message.content,
                            callback)
        if not one_way:
            self._futures.put(fut)

        self._send_receive_thread.send_message(message)
        return fut

    def send_last_message(self, message_type, data, callback=None,
                          one_way=False):
        """Sends a message of message_type and then close the connection.

        Args:
            message_type (validator_pb2.Message): enum value
            data (bytes): serialized protobuf
            callback (function): a callback function to call when a
                response to this message is received

        Returns:
            future.Future
        """
        message = validator_pb2.Message(
            correlation_id=_generate_id(),
            content=data,
            message_type=message_type)

        fut = future.Future(message.correlation_id, message.content,
                            callback)

        if not one_way:
            self._futures.put(fut)

        self._send_receive_thread.send_last_message(message)
        return fut

    def start(self):
        complete_or_error_queue = queue.Queue()
        self._thread = InstrumentedThread(
            target=self._send_receive_thread.setup,
            args=(zmq.DEALER, complete_or_error_queue))
        self._thread.name = self.__class__.__name__ + self._thread.name

        self._thread.start()
        err = complete_or_error_queue.get(block=True)
        if err != _STARTUP_COMPLETE_SENTINEL:
            raise err

    def stop(self):
        self._send_receive_thread.shutdown()

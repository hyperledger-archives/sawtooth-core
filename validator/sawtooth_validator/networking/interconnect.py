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
import hashlib
import logging
from threading import Condition
from threading import Thread
import uuid

import zmq
import zmq.auth
from zmq.auth.asyncio import AsyncioAuthenticator
import zmq.asyncio

from sawtooth_validator.exceptions import LocalConfigurationError
from sawtooth_validator.protobuf import validator_pb2
from sawtooth_validator.networking import future


LOGGER = logging.getLogger(__name__)


def _generate_id():
    return hashlib.sha512(uuid.uuid4().hex.encode()).hexdigest()


def get_enum_name(enum_value):
    return validator_pb2.Message.MessageType.Name(enum_value)


class _SendReceive(object):
    def __init__(self, address, futures, identity=None,
                 dispatcher=None, secured=False,
                 server_public_key=None, server_private_key=None):
        """
        Constructor for _SendReceive.

        Args:
            secured (bool): Whether or not to start the socket in
                secure mode -- using zmq auth.
            server_public_key (bytes): A public key to use in verifying
                server identity as part of the zmq auth handshake.
            server_private_key (bytes): A private key corresponding to
                server_public_key used by the server socket to sign
                messages are part of the zmq auth handshake.
        """
        self._dispatcher = dispatcher
        self._futures = futures
        self._address = address
        self._identity = identity
        self._secured = secured
        self._server_public_key = server_public_key
        self._server_private_key = server_private_key
        self._event_loop = None
        self._context = None
        self._recv_queue = None
        self._socket = None
        self._condition = Condition()

    @asyncio.coroutine
    def _receive_message(self):
        """
        Internal coroutine for receiving messages
        """
        with self._condition:
            self._condition.wait_for(lambda: self._socket is not None)
        while True:
            if self._socket.getsockopt(zmq.TYPE) == zmq.ROUTER:
                identity, msg_bytes = yield from self._socket.recv_multipart()
            else:
                msg_bytes = yield from self._socket.recv()

            message = validator_pb2.Message()
            message.ParseFromString(msg_bytes)

            LOGGER.debug("receiving %s message",
                         get_enum_name(message.message_type))
            try:
                self._futures.set_result(
                    message.correlation_id,
                    future.FutureResult(message_type=message.message_type,
                                        content=message.content))
            except future.FutureCollectionKeyError:
                if self._socket.getsockopt(zmq.TYPE) == zmq.ROUTER:
                    self._dispatcher.dispatch(identity, message)
                else:
                    LOGGER.info(
                        "received a first message on the zmq dealer.")
            else:
                my_future = self._futures.get(message.correlation_id)
                LOGGER.debug("message round "
                             "trip: %s %s",
                             get_enum_name(message.message_type),
                             my_future.get_duration())
                self._futures.remove(message.correlation_id)

    @asyncio.coroutine
    def _send_message(self, identity, msg):
        LOGGER.debug("sending %s to %s",
                     get_enum_name(msg.message_type),
                     identity)

        if identity is None:
            message_bundle = [msg.SerializeToString()]
        else:
            message_bundle = [bytes(identity),
                              msg.SerializeToString()]
        yield from self._socket.send_multipart(message_bundle)

    def send_message(self, msg, identity=None):
        """
        :param msg: protobuf validator_pb2.Message
        """
        with self._condition:
            self._condition.wait_for(lambda: self._event_loop is not None)
        asyncio.run_coroutine_threadsafe(self._send_message(identity, msg),
                                         self._event_loop)

    def setup(self, socket_type):
        """
        :param socket_type: zmq.DEALER or zmq.ROUTER
        """
        if self._secured:
            if self._server_public_key is None or \
                    self._server_private_key is None:
                raise LocalConfigurationError("Attempting to start socket "
                                              "in secure mode, but complete "
                                              "server keys were not provided")

        self._event_loop = zmq.asyncio.ZMQEventLoop()
        asyncio.set_event_loop(self._event_loop)
        self._context = zmq.asyncio.Context()

        if socket_type == zmq.DEALER:
            self._socket = self._context.socket(socket_type)

            self._socket.identity = "{}-{}".format(
                self._identity,
                hashlib.sha512(uuid.uuid4().hex.encode()
                               ).hexdigest()[:23]).encode('ascii')

            if self._secured:
                # Generate ephemeral certificates for this connection
                self._socket.curve_publickey, self._socket.curve_secretkey = \
                    zmq.curve_keypair()

                self._socket.curve_serverkey = self._server_public_key

            self._socket.connect(self._address)
        elif socket_type == zmq.ROUTER:
            self._socket = self._context.socket(socket_type)

            if self._secured:
                auth = AsyncioAuthenticator(self._context)
                auth.start()
                auth.configure_curve(domain='*',
                                     location=zmq.auth.CURVE_ALLOW_ANY)

                self._socket.curve_secretkey = self._server_private_key
                self._socket.curve_publickey = self._server_public_key
                self._socket.curve_server = True

            self._dispatcher.set_send_message(self.send_message)
            self._socket.bind(self._address)

        self._recv_queue = asyncio.Queue()
        asyncio.ensure_future(self._receive_message(), loop=self._event_loop)
        with self._condition:
            self._condition.notify_all()
        self._event_loop.run_forever()

    def stop(self):
        self._event_loop.stop()
        self._socket.close()
        self._context.term()


class Interconnect(object):
    def __init__(self,
                 endpoint,
                 dispatcher,
                 identity=None,
                 peer_connections=None,
                 secured=False,
                 server_public_key=None,
                 server_private_key=None):
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
        """
        self._futures = future.FutureCollection()
        self._send_receive_thread = _SendReceive(
            address=endpoint,
            dispatcher=dispatcher,
            futures=self._futures,
            secured=secured,
            server_public_key=server_public_key,
            server_private_key=server_private_key)

        self._thread = None

        if peer_connections is not None:
            self.connections = [
                Connection(
                    endpoint=addr,
                    identity=identity,
                    secured=secured,
                    server_public_key=server_public_key,
                    server_private_key=server_private_key)
                for addr in peer_connections]
        else:
            self.connections = []

    def send(self, message_type, data, identity, has_callback=False):
        """
        Send a message of message_type
        :param identity: the zmq identity of the dealer to send to or None
        :param message_type: validator_pb2.Message.* enum value
        :param data: bytes serialized protobuf
        :return: future.Future
        """
        message = validator_pb2.Message(
            correlation_id=_generate_id(),
            content=data,
            message_type=message_type)

        fut = future.Future(message.correlation_id, message.content,
                            has_callback=has_callback)
        self._futures.put(fut)

        self._send_receive_thread.send_message(msg=message,
                                               identity=identity)
        return fut

    def start(self, daemon=False):
        self._thread = Thread(target=self._send_receive_thread.setup,
                              args=(zmq.ROUTER,))
        self._thread.daemon = daemon
        self._thread.start()

    def stop(self):
        self._thread.join()


class Connection(object):
    def __init__(self,
                 endpoint,
                 identity,
                 secured,
                 server_public_key,
                 server_private_key):
        self._futures = future.FutureCollection()
        self._identity = identity
        self._endpoint = endpoint
        self._secured = secured
        self._server_public_key = server_public_key
        self._server_private_key = server_private_key
        self._send_receive_thread = _SendReceive(
            endpoint,
            futures=self._futures,
            identity=identity,
            secured=secured,
            server_public_key=server_public_key,
            server_private_key=server_private_key)

        self._thread = None

    def send(self, message_type, data):
        """
        Send a message of message_type
        :param message_type: validator_pb2.Message.* enum value
        :param data: bytes serialized protobuf
        :return: future.Future
        """
        message = validator_pb2.Message(
            correlation_id=_generate_id(),
            content=data,
            message_type=message_type)

        fut = future.Future(message.correlation_id, message.content)
        self._futures.put(fut)

        self._send_receive_thread.send_message(message)
        return fut

    def start(self, daemon=False):
        self._thread = Thread(target=self._send_receive_thread.setup,
                              args=(zmq.DEALER,))
        self._thread.daemon = daemon

        self._thread.start()

    def stop(self):
        self._thread.join()

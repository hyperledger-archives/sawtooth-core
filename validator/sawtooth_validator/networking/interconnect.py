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

import sys
import asyncio
import hashlib
import logging
from threading import Condition
from threading import Thread
import uuid
import time

import zmq
import zmq.auth
from zmq.auth.asyncio import AsyncioAuthenticator
import zmq.asyncio

from sawtooth_validator.exceptions import LocalConfigurationError
from sawtooth_validator.protobuf import validator_pb2
from sawtooth_validator.networking import future
from sawtooth_validator.protobuf.network_pb2 import PingRequest


LOGGER = logging.getLogger(__name__)


def _generate_id():
    return hashlib.sha512(uuid.uuid4().hex.encode()).hexdigest()


def get_enum_name(enum_value):
    return validator_pb2.Message.MessageType.Name(enum_value)


class _SendReceive(object):
    def __init__(self, connection, address, futures, connections,
                 zmq_identity=None, dispatcher=None, secured=False,
                 server_public_key=None, server_private_key=None,
                 heartbeat=False, heartbeat_interval=10):
        """
        Constructor for _SendReceive.

        Args:
            connection (str): A locally unique identifier for this
                thread's connection. Used to identify the connection
                in the dispatcher for transmitting responses.
            futures (future.FutureCollection): A Map of correlation ids to
                futures
            connections (dict): A dictionary that uses a sha512 hash as
                the keys and either an OutboundConnection or string
                identity as values.
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
        self._last_message_time = None

        self._event_loop = None
        self._context = None
        self._recv_queue = None
        self._socket = None
        self._condition = Condition()

        self._connected_identities = {}
        self._connections = connections

    @property
    def connection(self):
        return self._connection

    @asyncio.coroutine
    def _do_heartbeat(self):
        with self._condition:
            self._condition.wait_for(lambda: self._socket is not None)

        ping = PingRequest()

        while True:
            if self._socket.getsockopt(zmq.TYPE) == zmq.ROUTER:
                expired = [ident for ident in self._connected_identities
                           if time.time() - self._connected_identities[ident] >
                           self._heartbeat_interval]
                for zmq_identity in expired:
                    if time.time() - \
                            self._connected_identities[zmq_identity] > \
                            self._heartbeat_interval * 2:
                        LOGGER.debug("No response from %s in twice the "
                                     "heartbeat interval - removing "
                                     "connection.",
                                     zmq_identity)
                        self._remove_connected_identity(zmq_identity)
                    else:
                        message = validator_pb2.Message(
                            correlation_id=_generate_id(),
                            content=ping.SerializeToString(),
                            message_type=validator_pb2.Message.NETWORK_PING)
                        fut = future.Future(message.correlation_id,
                                            message.content,
                                            has_callback=False)
                        self._futures.put(fut)
                        yield from self._send_message(zmq_identity, message)
            elif self._socket.getsockopt(zmq.TYPE) == zmq.DEALER:
                if self._last_message_time:
                    if time.time() - self._last_message_time > \
                            self._heartbeat_interval * 2:
                        LOGGER.debug("No response from %s in twice the "
                                     "heartbeat interval - removing "
                                     "connection.",
                                     self._connection)
                        self.stop()
            yield from asyncio.sleep(self._heartbeat_interval)

    def _remove_connected_identity(self, zmq_identity):
        if zmq_identity in self._connected_identities:
            del self._connected_identities[zmq_identity]
        connection_id = hashlib.sha512(zmq_identity).hexdigest()
        if connection_id in self._connections:
            del self._connections[connection_id]

    def _received_from_identity(self, zmq_identity):
        self._connected_identities[zmq_identity] = time.time()
        connection_id = hashlib.sha512(zmq_identity).hexdigest()
        if connection_id not in self._connections:
            self._connections[connection_id] = ("ZMQ_Identity", zmq_identity)

    @asyncio.coroutine
    def _receive_message(self):
        """
        Internal coroutine for receiving messages
        """
        zmq_identity = None
        with self._condition:
            self._condition.wait_for(lambda: self._socket is not None)
        while True:
            if self._socket.getsockopt(zmq.TYPE) == zmq.ROUTER:
                zmq_identity, msg_bytes = \
                    yield from self._socket.recv_multipart()
                self._received_from_identity(zmq_identity)
            else:
                msg_bytes = yield from self._socket.recv()
                self._last_message_time = time.time()

            message = validator_pb2.Message()
            message.ParseFromString(msg_bytes)
            LOGGER.debug("%s receiving %s message: %s bytes",
                         self._connection,
                         get_enum_name(message.message_type),
                         sys.getsizeof(msg_bytes))

            try:
                self._futures.set_result(
                    message.correlation_id,
                    future.FutureResult(message_type=message.message_type,
                                        content=message.content))
            except future.FutureCollectionKeyError:
                if zmq_identity is not None:
                    connection_id = hashlib.sha512(zmq_identity).hexdigest()
                else:
                    connection_id = \
                        hashlib.sha512(self._connection.encode()).hexdigest()
                self._dispatcher.dispatch(self._connection,
                                          message,
                                          connection_id)
            else:
                my_future = self._futures.get(message.correlation_id)

                LOGGER.debug("message round "
                             "trip: %s %s",
                             get_enum_name(message.message_type),
                             my_future.get_duration())

                self._futures.remove(message.correlation_id)

    @asyncio.coroutine
    def _send_message(self, identity, msg):
        LOGGER.debug("%s sending %s to %s",
                     self._connection,
                     get_enum_name(msg.message_type),
                     identity if identity else self._address)

        if identity is None:
            message_bundle = [msg.SerializeToString()]
        else:
            message_bundle = [bytes(identity),
                              msg.SerializeToString()]
        yield from self._socket.send_multipart(message_bundle)

    def send_message(self, msg, connection_id=None):
        """
        :param msg: protobuf validator_pb2.Message
        """
        zmq_identity = None
        if connection_id is not None:
            connection_type, connection = self._connections.get(connection_id)
            if connection_type == "ZMQ_Identity":
                zmq_identity = connection

        with self._condition:
            self._condition.wait_for(lambda: self._event_loop is not None)
        asyncio.run_coroutine_threadsafe(
            self._send_message(zmq_identity, msg),
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
        self._socket = self._context.socket(socket_type)

        if socket_type == zmq.DEALER:
            self._socket.identity = "{}-{}".format(
                self._zmq_identity,
                hashlib.sha512(uuid.uuid4().hex.encode()
                               ).hexdigest()[:23]).encode('ascii')

            if self._secured:
                # Generate ephemeral certificates for this connection
                self._socket.curve_publickey, self._socket.curve_secretkey = \
                    zmq.curve_keypair()

                self._socket.curve_serverkey = self._server_public_key

            self._dispatcher.add_send_message(self._connection,
                                              self.send_message)
            self._socket.connect(self._address)
        elif socket_type == zmq.ROUTER:
            if self._secured:
                auth = AsyncioAuthenticator(self._context)
                auth.start()
                auth.configure_curve(domain='*',
                                     location=zmq.auth.CURVE_ALLOW_ANY)

                self._socket.curve_secretkey = self._server_private_key
                self._socket.curve_publickey = self._server_public_key
                self._socket.curve_server = True

            self._dispatcher.add_send_message(self._connection,
                                              self.send_message)
            self._socket.bind(self._address)

        self._recv_queue = asyncio.Queue()

        asyncio.ensure_future(self._receive_message(), loop=self._event_loop)

        if self._heartbeat:
            asyncio.ensure_future(self._do_heartbeat(), loop=self._event_loop)

        with self._condition:
            self._condition.notify_all()
        self._event_loop.run_forever()

    def stop(self):
        self._dispatcher.remove_send_message(self._connection)
        self._event_loop.stop()
        self._socket.close()
        self._context.term()


class Interconnect(object):
    def __init__(self,
                 endpoint,
                 dispatcher,
                 zmq_identity=None,
                 secured=False,
                 server_public_key=None,
                 server_private_key=None,
                 heartbeat=False,
                 max_incoming_connections=100):
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
        """
        self._futures = future.FutureCollection()
        self._dispatcher = dispatcher
        self._zmq_identity = zmq_identity
        self._secured = secured
        self._server_public_key = server_public_key
        self._server_private_key = server_private_key
        self._heartbeat = heartbeat
        self._connections = {}
        self.outbound_connections = {}
        self._max_incoming_connections = max_incoming_connections

        self._send_receive_thread = _SendReceive(
            "ServerThread",
            connections=self._connections,
            address=endpoint,
            dispatcher=dispatcher,
            futures=self._futures,
            secured=secured,
            server_public_key=server_public_key,
            server_private_key=server_private_key,
            heartbeat=heartbeat)

        self._thread = None

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
        if len(self._connections) > self._max_incoming_connections:
            return False
        else:
            return True

    def add_outbound_connection(self, uri):
        """Adds an outbound connection to the network.

        Args:
            connection (OutboundConnection): The connection to add.
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
            heartbeat=True)

        self.outbound_connections[uri] = conn
        conn.start(daemon=True)

        self._add_connection(conn)
        return conn

    def send(self, message_type, data, connection_id, callback=None):
        """
        Send a message of message_type
        :param connection_id: the identity for the connection to send to
        :param message_type: validator_pb2.Message.* enum value
        :param data: bytes serialized protobuf
        :return: future.Future
        """
        connection_type, connection = self._connections.get(connection_id)
        if connection_type == "ZMQ_Identity":
            message = validator_pb2.Message(
                correlation_id=_generate_id(),
                content=data,
                message_type=message_type)

            fut = future.Future(message.correlation_id, message.content,
                                has_callback=True if callback is not None
                                else False)

            if callback is not None:
                fut.add_callback(callback)

            self._futures.put(fut)

            self._send_receive_thread.send_message(msg=message,
                                                   connection_id=connection_id)
            return fut
        else:
            return connection.send(message_type, data, callback=callback)

    def start(self, daemon=False):
        self._thread = Thread(target=self._send_receive_thread.setup,
                              args=(zmq.ROUTER,))
        self._thread.daemon = daemon
        self._thread.start()

    def stop(self):
        self._thread.join()

    def _add_connection(self, connection):
        connection_id = connection.connection_id
        if connection_id not in self._connections:
            self._connections[connection_id] = \
                ("OutboundConnection", connection)

    def _remove_connection(self, connection):
        connection_id = connection.connection_id
        if connection_id in self._connections:
            del self._connections[connection_id]


class OutboundConnection(object):
    def __init__(self,
                 connections,
                 endpoint,
                 dispatcher,
                 zmq_identity,
                 secured,
                 server_public_key,
                 server_private_key,
                 heartbeat=True):
        self._futures = future.FutureCollection()
        self._zmq_identity = zmq_identity
        self._endpoint = endpoint
        self._dispatcher = dispatcher
        self._secured = secured
        self._server_public_key = server_public_key
        self._server_private_key = server_private_key
        self._heartbeat = heartbeat

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
            heartbeat=heartbeat)

        self._thread = None

    @property
    def connection_id(self):
        return hashlib.sha512(
            self._send_receive_thread.connection.encode()).hexdigest()

    def send(self, message_type, data, callback=None):
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
                            has_callback=True if callback is not None
                            else False)

        if callback is not None:
            fut.add_callback(callback)

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

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

import os
import asyncio
import queue
import socket
import logging
import random
import hashlib
import string
from threading import Thread
from threading import Condition

import zmq
import zmq.asyncio

from sawtooth_validator.server import future
from sawtooth_validator.server.signature_verifier import SignatureVerifier
from sawtooth_validator.protobuf import validator_pb2
from sawtooth_validator.protobuf import batch_pb2
from sawtooth_validator.protobuf import block_pb2
from sawtooth_validator.protobuf.network_pb2 import PeerRegisterRequest
from sawtooth_validator.protobuf.network_pb2 import PeerUnregisterRequest
from sawtooth_validator.protobuf.network_pb2 import PingRequest
from sawtooth_validator.protobuf.network_pb2 import GossipMessage
from sawtooth_validator.protobuf.network_pb2 import NetworkAcknowledgement

LOGGER = logging.getLogger(__name__)


class FauxNetwork(object):
    def __init__(self, dispatcher):
        self._dispatcher = dispatcher

    def _verify_batch(self, batch):
        pass

    def load(self, data):
        batch_list = batch_pb2.BatchList()
        batch_list.ParseFromString(data)

        for batch in batch_list.batches:
            self._verify_batch(batch)
            self._dispatcher.on_batch_received(batch)


def _generate_id():
    return hashlib.sha512(''.join(
        [random.choice(string.ascii_letters)
            for _ in range(0, 1024)]).encode()).hexdigest()


class DefaultHandler(object):
    def handle(self, message, responder):
        LOGGER.info("invalid message %s: %s", message.message_type,
                    message.correlation_id)


class Connection(object):
    def __init__(self, identity, url, ingest_message_func):
        LOGGER.debug("Network %s initiating "
                     "a connection to %s", identity, url)
        self._identity = identity
        self._stream = Stream(url, ingest_message_func)
        self.start()

    def start(self):
        futures = []

        fut = self._stream.send(
            message_type=validator_pb2.Message.GOSSIP_REGISTER,
            content=PeerRegisterRequest().SerializeToString())
        futures.append(fut)

    @asyncio.coroutine
    def send_message(self, message):
        # pylint: disable=not-an-iterable
        yield from self._stream.send_message(message)

    def stop(self):
        self._stream.send(
            message_type=validator_pb2.Message.GOSSIP_UNREGISTER,
            content=PeerUnregisterRequest().SerializeToString())
        self._stream.close()


class Stream(object):
    def __init__(self, url, ingest_message_func):
        self._url = url
        self._futures = future.FutureCollection()
        self._handlers = {}

        self.add_handler(validator_pb2.Message.DEFAULT, DefaultHandler())
        self.add_handler(validator_pb2.Message.GOSSIP_MESSAGE,
                         GossipMessageHandler(ingest_message_func))
        self.add_handler(validator_pb2.Message.GOSSIP_PING,
                         PingHandler(self))

        self._send_receive_thread = _ClientSendReceiveThread(url,
                                                             self._handlers,
                                                             self._futures)

        self._send_receive_thread.daemon = True
        self._send_receive_thread.start()

    def add_handler(self, message_type, handler):
        LOGGER.debug("Client stream adding "
                     "handler for %s", message_type)
        self._handlers[message_type] = handler

    @asyncio.coroutine
    def send_message(self, message):
        LOGGER.debug("Client sending message %s", message)
        my_future = future.Future(message.correlation_id)
        self._futures.put(my_future)
        self._send_receive_thread.send_message(message)
        return my_future

    def send(self, message_type, content):
        LOGGER.debug("Client sending %s: %s", message_type, content)
        message = validator_pb2.Message(
            message_type=message_type,
            correlation_id=_generate_id(),
            content=content)
        my_future = future.Future(message.correlation_id)
        self._futures.put(my_future)

        self._send_receive_thread.send_message(message)
        return my_future

    def receive(self):
        """
        Used for receiving messages that are not responses

        """
        return self._send_receive_thread.get_message()

    def close(self):
        self._send_receive_thread.join()


class _ClientSendReceiveThread(Thread):
    def __init__(self, url, handlers, futures):
        super(_ClientSendReceiveThread, self).__init__()
        self._handlers = handlers
        self._futures = futures
        self._url = url
        self._event_loop = None
        self._context = None
        self._recv_queue = None
        self._send_queue = None
        self._proc_sock = None
        self._condition = Condition()

    @asyncio.coroutine
    def _receive_message(self):
        """
        Internal coroutine for receiving messages from the
        zmq processor DEALER interface
        """
        with self._condition:
            self._condition.wait_for(lambda: self._proc_sock is not None)
        while True:
            msg_bytes = yield from self._proc_sock.recv()
            LOGGER.debug("Client received message: %s", msg_bytes)
            message = validator_pb2.Message()
            message.ParseFromString(msg_bytes)
            try:
                self._futures.set_result(
                    message.correlation_id,
                    future.FutureResult(message_type=message.message_type,
                                        content=message.content))
            except future.FutureCollectionKeyError:
                # if we are getting an initial message, not a response
                if message.message_type in self._handlers:
                    handler = self._handlers[message.message_type]
                else:
                    handler = self._handlers[validator_pb2.Message.DEFAULT]

                handler.handle(message, _Responder(self.send_message))
                self._recv_queue.put_nowait(message)
            else:
                my_future = self._futures.get(message.correlation_id)
                LOGGER.debug("Message round "
                             "trip: %s", my_future.get_duration())

    @asyncio.coroutine
    def _send_message(self):
        with self._condition:
            self._condition.wait_for(lambda: self._send_queue is not None
                                     and self._proc_sock is not None)
        while True:
            msg = yield from self._send_queue.get()
            LOGGER.debug("Client sending %s "
                         "message", msg.message_type)
            yield from self._proc_sock.send_multipart(
                [msg.SerializeToString()])

    @asyncio.coroutine
    def _put_message(self, message):
        with self._condition:
            self._condition.wait_for(lambda: self._send_queue is not None)
        yield from self._send_queue.put_nowait(message)

    def send_message(self, msg):
        """
        :param msg: protobuf validator_pb2.Message
        """
        with self._condition:
            self._condition.wait_for(lambda: self._event_loop is not None)

        asyncio.run_coroutine_threadsafe(self._put_message(msg),
                                         self._event_loop)

    @asyncio.coroutine
    def _get_message(self):
        with self._condition:
            self._condition.wait_for(lambda: self._recv_queue is not None)
        msg = yield from self._recv_queue.get()

        return msg

    def get_message(self):
        """
        :return message:
        """
        with self._condition:
            self._condition.wait_for(lambda: self._event_loop is not None)
        return asyncio.run_coroutine_threadsafe(self._get_message(),
                                                self._event_loop).result()

    def run(self):
        self._event_loop = zmq.asyncio.ZMQEventLoop()
        asyncio.set_event_loop(self._event_loop)
        self._context = zmq.asyncio.Context()
        self._proc_sock = self._context.socket(zmq.DEALER)
        self._proc_sock.identity = "{}-{}".format(socket.gethostname(),
                                                  os.getpid()).encode('ascii')

        self._proc_sock.connect(self._url)
        self._send_queue = asyncio.Queue()
        self._recv_queue = asyncio.Queue()
        asyncio.ensure_future(self._receive_message(), loop=self._event_loop)
        asyncio.ensure_future(self._send_message(), loop=self._event_loop)
        with self._condition:
            self._condition.notify_all()
        self._event_loop.run_forever()

    def stop(self):
        self._event_loop.stop()
        self._proc_sock.close()
        self._context.term()


class _ServerSendReceiveThread(Thread):
    """
    A background thread for zmq communication with asyncio.Queues
    To interact with the queues in a threadsafe manner call send_message()
    """
    def __init__(self, url, handlers, futures, ingest_message_func):
        super(_ServerSendReceiveThread, self).__init__()
        self._handlers = handlers
        self._futures = futures
        self._url = url
        self._event_loop = None
        self._send_queue = None
        self._proc_sock = None
        self._connections = []
        self._broadcast_queue = None
        self._ingest_message_func = ingest_message_func
        self._condition = Condition()

    @asyncio.coroutine
    def _receive_message(self):
        """
        Internal coroutine for receiving messages from the
        zmq processor ROUTER interface
        """
        with self._condition:
            self._condition.wait_for(lambda: self._proc_sock is not None)
        while True:
            ident, result = yield from self._proc_sock.recv_multipart()
            LOGGER.debug("Server received message "
                         "from %s: %s", ident, result)
            message = validator_pb2.Message()
            message.ParseFromString(result)
            message.sender = ident
            try:
                # if there is a future, then we are getting a response
                self._futures.set_result(
                    message.correlation_id,
                    future.FutureResult(content=message.content,
                                        message_type=message.message_type))
            except future.FutureCollectionKeyError:
                # if there isn't a future, we are getting an initial message
                if message.message_type in self._handlers:
                    handler = self._handlers[message.message_type]
                else:
                    handler = self._handlers[validator_pb2.Message.DEFAULT]

                handler.handle(message, _Responder(self.send_message))

    @asyncio.coroutine
    def _send_message(self):
        with self._condition:
            self._condition.wait_for(lambda: self._send_queue is not None
                                     and self._proc_sock is not None)
        while True:
            msg = yield from self._send_queue.get()
            LOGGER.debug("Server sending %s "
                         "message to %s", msg.message_type, msg.sender)
            yield from self._proc_sock.send_multipart(
                [bytes(msg.sender, 'UTF-8'),
                 msg.SerializeToString()])

    @asyncio.coroutine
    def _put_message(self, message):
        with self._condition:
            self._condition.wait_for(lambda: self._send_queue is not None)
        yield from self._send_queue.put_nowait(message)

    def send_message(self, msg):
        """
        :param msg: protobuf validator_pb2.Message
        """
        with self._condition:
            self._condition.wait_for(lambda: self._event_loop is not None)

        asyncio.run_coroutine_threadsafe(self._put_message(msg),
                                         self._event_loop)

    @asyncio.coroutine
    def _broadcast_message(self):
        with self._condition:
            self._condition.wait_for(lambda: self._broadcast_queue is not None
                                     and self._proc_sock is not None)
        while True:
            msg = yield from self._broadcast_queue.get()
            LOGGER.debug("Server broadcasting %s "
                         "message to connected peers", msg.message_type)
            for connection in self._connections:
                yield from connection.send_message(msg)

    @asyncio.coroutine
    def _put_broadcast_message(self, message):
        with self._condition:
            self._condition.wait_for(lambda: self._broadcast_queue is not None)
        yield from self._broadcast_queue.put_nowait(message)

    def broadcast_message(self, msg):
        with self._condition:
            self._condition.wait_for(lambda: self._event_loop is not None)

        asyncio.run_coroutine_threadsafe(self._put_broadcast_message(msg),
                                         self._event_loop)

    def add_connection(self, server_identity, url):
        LOGGER.debug("Adding connection for %s, %s", server_identity, url)
        self._connections.append(Connection(server_identity,
                                            url,
                                            self._ingest_message_func))

    def close_connections(self):
        for connection in self._connections:
            connection.stop()

    def run(self):
        self._event_loop = zmq.asyncio.ZMQEventLoop()
        asyncio.set_event_loop(self._event_loop)
        context = zmq.asyncio.Context()
        self._proc_sock = context.socket(zmq.ROUTER)
        LOGGER.debug("Network service binding to %s", self._url)
        self._proc_sock.bind(self._url)
        self._send_queue = asyncio.Queue()
        self._broadcast_queue = asyncio.Queue()
        asyncio.ensure_future(self._receive_message(), loop=self._event_loop)
        asyncio.ensure_future(self._send_message(), loop=self._event_loop)
        asyncio.ensure_future(self._broadcast_message(), loop=self._event_loop)
        with self._condition:
            self._condition.notify_all()
        self._event_loop.run_forever()


class PeerRegisterHandler(object):
    def __init__(self, service):
        self._service = service

    def handle(self, message, peer):
        request = PeerRegisterRequest()
        request.ParseFromString(message.content)

        self._service.register_peer(
            message.sender,
            request.identity)

        LOGGER.debug("Got peer register message "
                     "from %s. Sending ack", message.sender)

        ack = NetworkAcknowledgement()
        ack.status = ack.OK

        peer.send(validator_pb2.Message(
            sender=message.sender,
            message_type=validator_pb2.Message.GOSSIP_ACK,
            correlation_id=message.correlation_id,
            content=ack.SerializeToString()))


class PeerUnregisterHandler(object):
    def __init__(self, service):
        self._service = service

    def handle(self, message, peer):
        request = PeerUnregisterRequest()
        request.ParseFromString(message.content)

        self._service.unregister_peer(
            message.sender,
            request.identity)

        LOGGER.debug("Got peer unregister message "
                     "from %s. Sending ack", message.sender)

        ack = NetworkAcknowledgement()
        ack.status = ack.OK

        peer.send(validator_pb2.Message(
            sender=message.sender,
            message_type=validator_pb2.Message.GOSSIP_ACK,
            correlation_id=message.correlation_id,
            content=ack.SerializeToString()))


class GossipMessageHandler(object):
    def __init__(self, ingest_message_func):
        self._ingest_message = ingest_message_func

    def handle(self, message, peer):
        LOGGER.debug("GossipMessageHandler message: %s", message.sender)

        LOGGER.debug("Got gossip message %s "
                     "from %s. sending ack",
                     message.content,
                     message.sender)

        self._ingest_message(message)

        ack = NetworkAcknowledgement()
        ack.status = ack.OK

        peer.send(validator_pb2.Message(
            sender=message.sender,
            message_type=validator_pb2.Message.GOSSIP_ACK,
            correlation_id=message.correlation_id,
            content=ack.SerializeToString()))


class PingHandler(object):
    def __init__(self, service):
        self._service = service

    def handle(self, message, peer):
        LOGGER.debug("PingHandler message: %s", message)
        request = PingRequest()
        request.ParseFromString(message.content)

        LOGGER.debug("Got ping message %s "
                     "from %s. sending ack",
                     message.content,
                     message.sender)

        ack = NetworkAcknowledgement()
        ack.status = ack.OK

        peer.send(validator_pb2.Message(
            sender=message.sender,
            message_type=validator_pb2.Message.GOSSIP_ACK,
            correlation_id=message.correlation_id,
            content=ack.SerializeToString()))


class Network(object):
    def __init__(self, identity, endpoint, peer_list, dispatcher):
        LOGGER.debug("Initializing Network service")
        self._identity = identity
        self._dispatcher = dispatcher
        self._handlers = {}
        self._peered_with_us = {}
        self.inbound_queue = queue.Queue()
        self.dispatcher_queue = queue.Queue()
        self._signature_condition = Condition()
        self._dispatcher_condition = Condition()
        self._futures = future.FutureCollection()
        self._send_receive_thread = _ServerSendReceiveThread(
            endpoint,
            self._handlers,
            self._futures,
            self._put_on_inbound)

        self._send_receive_thread.daemon = True

        self._signature_verifier = SignatureVerifier(
            self.inbound_queue, self.dispatcher_queue,
            self._signature_condition, self._dispatcher_condition,
            self.broadcast_message)
        self._dispatcher.set_incoming_msg_queue(self.dispatcher_queue)
        self._dispatcher.set_condition(self._dispatcher_condition)
        self.add_handler(validator_pb2.Message.DEFAULT, DefaultHandler())
        self.add_handler(validator_pb2.Message.GOSSIP_REGISTER,
                         PeerRegisterHandler(self))
        self.add_handler(validator_pb2.Message.GOSSIP_UNREGISTER,
                         PeerUnregisterHandler(self))
        self.add_handler(validator_pb2.Message.GOSSIP_MESSAGE,
                         GossipMessageHandler(self._put_on_inbound))
        self.start()
        self._dispatcher.start()

        if peer_list is not None:
            for peer in peer_list:
                self._send_receive_thread.add_connection(self._identity, peer)

    def add_handler(self, message_type, handler):
        LOGGER.debug("Network service adding "
                     "handler for %s", message_type)
        self._handlers[message_type] = handler

    def _put_on_inbound(self, item):
        self.inbound_queue.put_nowait(item)
        with self._signature_condition:
            self._signature_condition.notify_all()

    def send_message(self, data):
        if isinstance(data, str):
            msg = GossipMessage(content_type="BlockRequest",
                                content=data.encode("utf-8"))
        elif isinstance(data, block_pb2.Block):
            msg = GossipMessage(content_type="Block",
                                content=data.SerializeToString())
        elif isinstance(data, batch_pb2.Batch):
            msg = GossipMessage(content_type="Batch",
                                content=data.SerializeToString())

        content = msg.SerializeToString()
        message = validator_pb2.Message(
            message_type=validator_pb2.Message.GOSSIP_MESSAGE,
            correlation_id=_generate_id(),
            content=content)

        self._put_on_inbound(message)

    def broadcast_message(self, message):
        self._send_receive_thread.broadcast_message(message)
        fut = future.Future(message.correlation_id)
        self._futures.put(fut)
        return fut

    def register_peer(self, sender, identity):
        data = sender

        LOGGER.debug("Registering peer: "
                     "sender %s, identity %s", sender, identity)

        if sender not in self._peered_with_us.keys():
            self._peered_with_us[sender] = []
        self._peered_with_us[sender].append(data)

        LOGGER.debug("Peers: %s", self._peered_with_us)

    def unregister_peer(self, sender, identity):

        LOGGER.debug("Unregistering peer: "
                     "sender %s, identity %s", sender, identity)

        if sender in self._peered_with_us.keys():
            del self._peered_with_us[sender]

        LOGGER.debug("Peers: %s", self._peered_with_us)

    def start(self):
        self._send_receive_thread.start()
        self._signature_verifier.start()

    def stop(self):
        self._signature_verifier.stop()
        self._dispatcher.stop()
        with self._signature_condition:
            self._signature_condition.notify_all()

        with self._dispatcher_condition:
            self._dispatcher_condition.notify_all()

        self._send_receive_thread.join()


class _Responder(object):
    def __init__(self, func):
        """
        :param func: a function,
                    specifically _ServerSendReceiveThread.send_message
        """
        self._func = func

    def send(self, message):
        """
        Send a response
        :param message: protobuf validator_pb2.Message
        """
        self._func(message)

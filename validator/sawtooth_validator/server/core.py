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

import logging
import os
import socket
from threading import Condition
from threading import Thread

import asyncio
import zmq
import zmq.asyncio

from sawtooth_validator.context_manager import ContextManager
from sawtooth_validator.database.lmdb_nolock_database import LMDBNoLockDatabase
from sawtooth_validator.journal.consensus.dev_mode import dev_mode_consensus
from sawtooth_validator.journal.journal import Journal
from sawtooth_validator.protobuf import validator_pb2
from sawtooth_validator.server import future
from sawtooth_validator.server.dispatch import Dispatcher
from sawtooth_validator.server.executor import TransactionExecutor
from sawtooth_validator.server.loader import SystemLoadHandler
from sawtooth_validator.server.network import FauxNetwork
from sawtooth_validator.server.network import Network
from sawtooth_validator.server import state
from sawtooth_validator.server.processor import ProcessorRegisterHandler
from sawtooth_validator.server import processor_iterator

LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.StreamHandler())
LOGGER.setLevel(logging.DEBUG)


class _SendReceiveThread(Thread):
    """
    A background thread for zmq communication with asyncio.Queues
    To interact with the queues in a threadsafe manner call send_message()
    """
    def __init__(self, url, handlers, futures):
        super(_SendReceiveThread, self).__init__()
        self._handlers = handlers
        self._futures = futures
        self._url = url
        self._event_loop = None
        self._send_queue = None
        self._proc_sock = None
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
                    handler = self._handlers['default']

                handler.handle(message, _Responder(self.send_message))

    @asyncio.coroutine
    def _send_message(self):
        """
        internal coroutine for sending messages through the
        zmq Router interface
        """
        with self._condition:
            self._condition.wait_for(lambda: self._send_queue is not None
                                     and self._proc_sock is not None)
        while True:
            msg = yield from self._send_queue.get()
            yield from self._proc_sock.send_multipart(
                [bytes(msg.sender, 'UTF-8'),
                 validator_pb2.MessageList(messages=[msg]
                                           ).SerializeToString()])

    @asyncio.coroutine
    def _put_message(self, message):
        """
        put a message on the send_queue. Not to be accessed directly.
        :param message:
        :return:
        """
        with self._condition:
            self._condition.wait_for(lambda: self._send_queue is not None)
        self._send_queue.put_nowait(message)

    def send_message(self, msg):
        """
        :param msg: protobuf validator_pb2.Message
        """
        with self._condition:
            self._condition.wait_for(lambda: self._event_loop is not None)

        asyncio.run_coroutine_threadsafe(self._put_message(msg),
                                         self._event_loop)

    def run(self):
        self._event_loop = zmq.asyncio.ZMQEventLoop()
        asyncio.set_event_loop(self._event_loop)
        context = zmq.asyncio.Context()
        self._proc_sock = context.socket(zmq.ROUTER)
        self._proc_sock.bind('tcp://' + self._url)
        self._send_queue = asyncio.Queue()
        with self._condition:
            self._condition.notify_all()
        asyncio.ensure_future(self._receive_message(), loop=self._event_loop)
        asyncio.ensure_future(self._send_message(), loop=self._event_loop)
        self._event_loop.run_forever()


class ValidatorService(object):
    def __init__(self, url):
        self._handlers = {}
        self._processors = processor_iterator.ProcessorIteratorCollection(
            processor_iterator.RoundRobinProcessorIterator)

        self._futures = future.FutureCollection()
        self._send_receive_thread = _SendReceiveThread(url,
                                                       self._handlers,
                                                       self._futures)

    def add_handler(self, message_type, handler):
        self._handlers[message_type] = handler

    def send_txn(self, header, message):
        print(repr(header))
        family_name = header.family_name
        family_version = header.family_version
        encoding = header.payload_encoding
        processor_type = processor_iterator.ProcessorType(family_name,
                                                          family_version,
                                                          encoding)
        print(repr(processor_type))
        print(repr(self._processors))
        if processor_type not in self._processors:
            raise Exception("internal error, no processor available")
        processor = self._processors[processor_type]
        message.sender = processor.sender

        fut = future.Future(message.correlation_id)
        self._futures.put(fut)

        self._send_receive_thread.send_message(message)

        return fut

    def register_transaction_processor(self, sender, family, version,
                                       encoding, namespaces):
        processor_type = processor_iterator.ProcessorType(
            family,
            version,
            encoding)
        processor = processor_iterator.Processor(sender, namespaces)
        self._processors[processor_type] = processor

    def start(self):
        self._send_receive_thread.start()

    def stop(self):
        self._send_receive_thread.join()


class _Responder(object):
    def __init__(self, func):
        """
        :param func: a function,
                    specifically _SendReceiveThread.send_message
        """
        self._func = func

    def send(self, message):
        """
        Send a response
        :param message: protobuf validator_pb2.Message
        """
        self._func(message)


class DefaultHandler(object):
    def handle(self, message, responder):
        print("invalid message {}".format(message.message_type))


class Validator(object):
    def __init__(self, network_endpoint, component_endpoint, peer_list):
        db_filename = os.path.join(os.path.expanduser('~'), 'merkle.lmdb')
        LOGGER.debug('database file is %s', db_filename)

        lmdb = LMDBNoLockDatabase(db_filename, 'n')
        context_manager = ContextManager(lmdb)

        block_db_filename = os.path.join(os.path.expanduser('~'), 'block.lmdb')
        LOGGER.debug('block store file is %s', block_db_filename)
        block_store = LMDBNoLockDatabase(block_db_filename, 'n')

        self._service = ValidatorService(component_endpoint)

        # setup network
        dispatcher = Dispatcher()
        faux_network = FauxNetwork(dispatcher=dispatcher)

        identity = "{}-{}".format(socket.gethostname(),
                                  os.getpid()).encode('ascii')
        self._network = Network(identity,
                                network_endpoint,
                                peer_list,
                                dispatcher=dispatcher)

        # Create and configure journal
        executor = TransactionExecutor(self._service, context_manager)
        self._journal = Journal(
            consensus=dev_mode_consensus,
            block_store={},  # FIXME - block_store=block_store
            # -- need to serialize blocks to dicts
            send_message=faux_network.send_message,
            transaction_executor=executor,
            squash_handler=context_manager.get_squash_handler(),
            first_state_root=context_manager.get_first_root())

        dispatcher.on_batch_received = \
            self._journal.on_batch_received
        dispatcher.on_block_received = \
            self._journal.on_block_received
        dispatcher.on_block_request = \
            self._journal.on_block_request

        self._service.add_handler('default', DefaultHandler())
        self._service.add_handler('state/getrequest',
                                  state.GetHandler(context_manager))
        self._service.add_handler('state/setrequest',
                                  state.SetHandler(context_manager))
        self._service.add_handler('tp/register',
                                  ProcessorRegisterHandler(self._service))
        self._service.add_handler('system/load',
                                  SystemLoadHandler(faux_network))

    def start(self):
        self._service.start()
        self._journal.start()

    def stop(self):
        self._service.stop()
        self._journal.stop()

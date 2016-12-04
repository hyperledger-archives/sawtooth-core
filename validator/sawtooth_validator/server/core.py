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
import random
import queue

from threading import Thread
from concurrent.futures import ThreadPoolExecutor

import grpc

from sawtooth_validator.database.lmdb_nolock_database import LMDBNoLockDatabase
from sawtooth_validator.context_manager import ContextManager
from sawtooth_validator.server.dispatch import Dispatcher
from sawtooth_validator.server.executor import TransactionExecutor
from sawtooth_validator.server.message import Message
from sawtooth_validator.server.loader import SystemLoadHandler
from sawtooth_validator.server.journal import FauxJournal
from sawtooth_validator.server.network import FauxNetwork
from sawtooth_validator.server import state
from sawtooth_validator.server.processor import ProcessorRegisterHandler
from sawtooth_validator.server import future

import sawtooth_validator.protobuf.validator_pb2 as validator_pb2


LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.StreamHandler())
LOGGER.setLevel(logging.DEBUG)


class RecvThread(Thread):
    def __init__(self, response_iterator, handlers, responder, context):
        super(RecvThread, self).__init__()
        self._response_iterator = response_iterator
        self._handlers = handlers
        self._responder = responder
        self._disconnect = False
        self._context = context

    @property
    def disconnect(self):
        return self._disconnect

    def run(self):
        for response_list in self._response_iterator:
            for response_message in response_list.messages:
                message = Message.from_pb2(response_message)
                message.sender = self._context.peer()

                if message.message_type == 'system/disconnect':
                    self._disconnect = True
                    break
                elif message.message_type in self._handlers:
                    handler = self._handlers[message.message_type]
                else:
                    handler = self._handlers['default']

                handler.handle(message, self._responder)


class ValidatorService(validator_pb2.ValidatorServicer):
    def __init__(self):
        self._handlers = {}
        self._send_queues = {}
        self._processors = {}
        self._futures = future.FutureCollection()

    def add_handler(self, message_type, handler):
        self._handlers[message_type] = handler

    def send_txn(self, header, message):
        print(repr(header))
        family_name = header.family_name
        family_version = header.family_version
        encoding = header.payload_encoding
        key = (family_name, family_version, encoding)
        print(repr(key))
        print(repr(self._processors.keys()))
        if key not in self._processors.keys():
            raise Exception("internal error, no processor available")

        # Choose a random processor of the type
        processor = random.choice(self._processors[key])
        peer = processor[0]

        if peer not in self._send_queues:
            raise Exception("internal error, no send queue available")

        self._send_queues[peer].put(message)
        fut = future.Future(message.correlation_id)
        self._futures.put(fut)
        return fut

    def set_future(self, correlation_id, result):
        self._futures.set_result(correlation_id=correlation_id,
                                 result=result)

    def register_transaction_processor(self, sender, family, version,
                                       encoding, namespaces):
        key = (family, version, encoding)
        data = (sender, namespaces)

        if key not in self._processors.keys():
            self._processors[key] = []
        self._processors[key].append(data)

    def Connect(self, response_iterator, context):
        peer = context.peer()
        LOGGER.info("connections from peer %s", peer)

        send_queue = queue.Queue()

        self._send_queues[context.peer()] = send_queue

        responder = Responder(send_queue)
        recv_thread = RecvThread(
            response_iterator,
            self._handlers.copy(),
            responder,
            context)
        recv_thread.start()

        while not recv_thread.disconnect:
            message = None
            while message is None and not recv_thread.disconnect:
                try:
                    message = send_queue.get(True, 1)
                    print("sending {}".format(message.message_type))
                except queue.Empty:
                    message = None
            if recv_thread.disconnect:
                break
            yield validator_pb2.MessageList(messages=[message.to_pb2()])

        recv_thread.join()


class Responder(object):
    def __init__(self, queue):
        self._queue = queue

    def send(self, message):
        self._queue.put(message)


class DefaultHandler(object):
    def handle(self, message, responder):
        print("invalid message {}".format(message.message_type))


class ResponseHandler(object):
    def __init__(self, service):
        self._service = service

    def handle(self, message, responder):
        self._service.set_future(message.correlation_id,
                                 future.FutureResult(
                                     content=message.content,
                                     message_type=message.message_type))


class Validator(object):
    def __init__(self, url):
        db_filename = os.path.join(os.path.expanduser('~'), 'merkle.lmdb')
        LOGGER.debug('database file is %s', db_filename)

        lmdb = LMDBNoLockDatabase(db_filename, 'n')
        context_manager = ContextManager(lmdb)
        service = ValidatorService()

        executor = TransactionExecutor(service, context_manager)
        journal = FauxJournal(executor)
        dispatcher = Dispatcher()
        dispatcher.on_batch_received = journal.get_on_batch_received_handler()
        network = FauxNetwork(dispatcher=dispatcher)

        service.add_handler('default', DefaultHandler())
        service.add_handler('state/getrequest',
                            state.GetHandler(context_manager))
        service.add_handler('state/setrequest',
                            state.SetHandler(context_manager))
        service.add_handler('tp/register', ProcessorRegisterHandler(service))
        service.add_handler('tp/response', ResponseHandler(service))
        service.add_handler('system/load', SystemLoadHandler(network))

        self._server = grpc.server(ThreadPoolExecutor(max_workers=10))

        validator_pb2.add_ValidatorServicer_to_server(service, self._server)

        port_spec = url
        LOGGER.debug('listening on port %s', port_spec)
        self._server.add_insecure_port(port_spec)

    def start(self):
        self._server.start()

    def stop(self):
        self._server.stop(0)

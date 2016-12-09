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

import queue

from threading import Thread

import hashlib
import random
import string
import time

import grpc

import sawtooth_protobuf.validator_pb2 as validator_pb2

from sawtooth_sdk.client.future import Future
from sawtooth_sdk.client.future import FutureCollection
from sawtooth_sdk.client.future import FutureCollectionKeyError
from sawtooth_sdk.client.future import FutureResult


def _generate_id():
    return hashlib.sha512(''.join(
        [random.choice(string.ascii_letters)
            for _ in range(0, 1024)]).encode()).hexdigest()


class RecvThread(Thread):
    def __init__(self, handle, futures, recv_queue):
        super(RecvThread, self).__init__()
        self._handle = handle
        self._futures = futures
        self._recv_queue = recv_queue

    def run(self):
        try:
            for message_list in self._handle:
                for message in message_list.messages:
                    try:
                        self._futures.set_result(
                            message.correlation_id,
                            FutureResult(message_type=message.message_type,
                                         content=message.content))
                        self._futures.remove(message.correlation_id)
                    except FutureCollectionKeyError:
                        self._recv_queue.put(message)
        except grpc.RpcError:
            # Ignore RpcError here, as handling an RpcError is handled in
            # the call's done_callback.
            pass


class MessageType(object):
    """
    This datastructure is the message_type used in the Stream().send() method
    """
    DEFAULT = 'default'
    STATE_GET = 'state/getrequest'
    STATE_SET = 'state/setrequest'
    STATE_DELETE = 'state/deleterequest'
    TP_REGISTER = 'tp/register'
    TP_RESPONSE = 'tp/response'


class Stream(object):
    def __init__(self, url):
        self._url = url
        self._send_queue = queue.Queue()
        self._recv_queue = queue.Queue()

        self._futures = FutureCollection()

        self._channel = None
        self._stub = None
        self._handle = None

        def send_generator():
            disconnect = False
            while not disconnect:
                message = None
                while message is None and not disconnect:
                    try:
                        message = self._send_queue.get(True, 1)
                        if message.message_type == 'system/disconnect':
                            disconnect = True
                    except queue.Empty:
                        message = None

                yield validator_pb2.MessageList(messages=[message])

                if disconnect:
                    break
        self._send_generator = send_generator()

    def connect(self):
        self._channel = grpc.insecure_channel(self._url)
        self._stub = validator_pb2.ValidatorStub(self._channel)
        self._handle = self._stub.Connect(self._send_generator)

        def done_callback(call):
            if call.code() != grpc.StatusCode.OK:
                print("ERROR: Connect() failed with status code: "
                      "{}: {}".format(str(call.code()), call.details()))

        self._handle.add_done_callback(done_callback)

        recv_thread = RecvThread(
            self._handle,
            self._futures,
            self._recv_queue)
        recv_thread.start()

    def send(self, message_type, content):
        message = validator_pb2.Message(
            message_type=message_type,
            correlation_id=_generate_id(),
            content=content)

        future = Future(message.correlation_id)
        self._futures.put(future)

        self._send_queue.put(message)

        return future

    def send_back(self, message_type, correlation_id, content):
        message = validator_pb2.Message(
            message_type=message_type,
            correlation_id=correlation_id,
            content=content)
        self._send_queue.put(message)

    def receive(self):
        return self._recv_queue.get()

    def close(self):
        message = validator_pb2.Message(
            message_type='system/disconnect',
            correlation_id=_generate_id(),
            content=''.encode())
        self._send_queue.put(message)

        while not self._handle.done():
            time.sleep(1)

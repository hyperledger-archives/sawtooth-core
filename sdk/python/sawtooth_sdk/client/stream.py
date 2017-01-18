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
import os
import random
import string
from threading import Thread
from threading import Condition

import zmq
import zmq.asyncio

import sawtooth_protobuf.validator_pb2 as validator_pb2

from sawtooth_sdk.client.future import Future
from sawtooth_sdk.client.future import FutureCollection
from sawtooth_sdk.client.future import FutureCollectionKeyError
from sawtooth_sdk.client.future import FutureResult


LOGGER = logging.getLogger(__file__)


def _generate_id():
    return hashlib.sha512(''.join(
        [random.choice(string.ascii_letters)
            for _ in range(0, 1024)]).encode('ascii')).hexdigest()


class _SendReceiveThread(Thread):
    """
    Internal thread to Stream class that runs the asyncio event loop.
    """

    def __init__(self, url, futures):
        super(_SendReceiveThread, self).__init__()
        self._futures = futures
        self._url = url

        self._event_loop = None
        self._sock = None
        self._recv_queue = None
        self._send_queue = None
        self._context = None

        self._condition = Condition()

    @asyncio.coroutine
    def _receive_message(self):
        """
        internal coroutine that receives messages and puts
        them on the recv_queue
        """
        with self._condition:
            self._condition.wait_for(lambda: self._sock is not None)
        while True:
            msg_bytes = yield from self._sock.recv()
            message_list = validator_pb2.MessageList()
            message_list.ParseFromString(msg_bytes)
            for message in message_list.messages:
                if message.correlation_id:
                    try:
                        self._futures.set_result(
                            message.correlation_id,
                            FutureResult(message_type=message.message_type,
                                         content=message.content))
                    except FutureCollectionKeyError:
                        # if we are getting an initial message, not a response
                        self._recv_queue.put_nowait(message)
                else:
                    self._recv_queue.put_nowait(message)

    @asyncio.coroutine
    def _send_message(self):
        """
        internal coroutine that sends messages from the send_queue
        """
        with self._condition:
            self._condition.wait_for(lambda: self._send_queue is not None
                                     and self._sock is not None)
        while True:
            msg = yield from self._send_queue.get()
            yield from self._sock.send_multipart([msg.SerializeToString()])

    @asyncio.coroutine
    def _put_message(self, message):
        """
        puts a message on the send_queue. Not to be accessed directly.
        :param message: protobuf generated validator_pb2.Message
        """
        with self._condition:
            self._condition.wait_for(lambda: self._send_queue is not None)
        self._send_queue.put_nowait(message)

    @asyncio.coroutine
    def _get_message(self):
        """
        get a message from the recv_queue. Not to be accessed directly.
        """
        with self._condition:
            self._condition.wait_for(lambda: self._recv_queue is not None)
        msg = yield from self._recv_queue.get()

        return msg

    def put_message(self, message):
        """
        :param message: protobuf generated validator_pb2.Message
        """
        with self._condition:
            self._condition.wait_for(lambda: self._event_loop is not None)
        asyncio.run_coroutine_threadsafe(self._put_message(message),
                                         self._event_loop)

    def get_message(self):
        """
        :return message: protobuf generated validator_pb2.Message
        """
        with self._condition:
            self._condition.wait_for(lambda: self._event_loop is not None)
        return asyncio.run_coroutine_threadsafe(self._get_message(),
                                                self._event_loop).result()

    def _exit_tasks(self):
        for task in asyncio.Task.all_tasks(self._event_loop):
            task.cancel()

    def shutdown(self):
        self._exit_tasks()
        self._event_loop.call_soon_threadsafe(self._event_loop.stop)
        self._sock.close()
        self._context.destroy()

    def run(self):
        self._event_loop = zmq.asyncio.ZMQEventLoop()
        asyncio.set_event_loop(self._event_loop)
        self._context = zmq.asyncio.Context()
        self._sock = self._context.socket(zmq.DEALER)
        self._sock.identity = "{}-{}".format(self.__class__.__name__,
                                             os.getpid()).encode('ascii')
        self._sock.connect('tcp://' + self._url)
        self._send_queue = asyncio.Queue(loop=self._event_loop)
        self._recv_queue = asyncio.Queue(loop=self._event_loop)
        with self._condition:
            self._condition.notify_all()
        asyncio.ensure_future(self._send_message(), loop=self._event_loop)
        asyncio.ensure_future(self._receive_message(), loop=self._event_loop)
        self._event_loop.run_forever()


class Stream(object):
    def __init__(self, url):
        self._url = url
        self._futures = FutureCollection()
        self._send_recieve_thread = _SendReceiveThread(url, self._futures)
        self._send_recieve_thread.daemon = True
        self._send_recieve_thread.start()

    def send(self, message_type, content):
        message = validator_pb2.Message(
            message_type=message_type,
            correlation_id=_generate_id(),
            content=content)
        future = Future(message.correlation_id)
        self._futures.put(future)

        self._send_recieve_thread.put_message(message)
        return future

    def send_back(self, message_type, correlation_id, content):
        """
        Return a response to a message.
        :param message_type: validator_pb2.Message.MessageType enum value
        :param correlation_id: a random str internal to the validator
        :param content: protobuf bytes
        """
        message = validator_pb2.Message(
            message_type=message_type,
            correlation_id=correlation_id,
            content=content)
        self._send_recieve_thread.put_message(message)

    def receive(self):
        """
        Used for receiving messages that are not responses

        """
        return self._send_recieve_thread.get_message()

    def close(self):
        self._send_recieve_thread.shutdown()

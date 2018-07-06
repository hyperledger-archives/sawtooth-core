# Copyright 2018 Intel Corporation
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
# -----------------------------------------------------------------------------

import logging
import threading
import random
import string
import unittest
import queue

import zmq

from sawtooth_sdk.consensus.engine import Engine
from sawtooth_sdk.consensus.zmq_driver import ZmqDriver
from sawtooth_sdk.protobuf import consensus_pb2
from sawtooth_sdk.protobuf.validator_pb2 import Message


LOGGER = logging.getLogger(__name__)


class MockEngine(Engine):
    def __init__(self):
        self.updates = []
        self.exit = False

    def start(self, updates, service, startup_state):
        while not self.exit:
            try:
                update = updates.get(timeout=1)
            except queue.Empty:
                pass
            else:
                self.updates.append(update)

    def stop(self):
        self.exit = True

    def name(self):
        return 'test-name'

    def version(self):
        return 'test-version'


class TestDriver(unittest.TestCase):
    def setUp(self):
        self.ctx = zmq.Context.instance()
        self.socket = self.ctx.socket(zmq.ROUTER)
        self.socket.bind('tcp://127.0.0.1:*')
        self.url = self.socket.getsockopt_string(zmq.LAST_ENDPOINT)
        self.connection_id = None

        self.engine = MockEngine()
        self.driver = ZmqDriver(self.engine)

    def tearDown(self):
        self.socket.close()

    def recv_rep(self, request_type, response, response_type):
        # pylint: disable=unbalanced-tuple-unpacking
        connection_id, message_bytes = self.socket.recv_multipart(0)

        self.connection_id = connection_id

        message = Message()
        message.ParseFromString(message_bytes)

        request = request_type()
        request.ParseFromString(message.content)

        reply = Message(
            message_type=response_type,
            content=response.SerializeToString(),
            correlation_id=message.correlation_id)

        self.socket.send_multipart(
            [self.connection_id, reply.SerializeToString()],
            0)

        return request

    def send_req_rep(self, request, request_type):
        message = Message(
            message_type=request_type,
            correlation_id=generate_correlation_id(),
            content=request.SerializeToString())

        self.socket.send_multipart(
            [self.connection_id, message.SerializeToString()],
            0)

        # pylint: disable=unbalanced-tuple-unpacking
        _, reply_bytes = self.socket.recv_multipart(0)

        reply = Message()
        reply.ParseFromString(reply_bytes)

        self.assertEqual(
            reply.message_type,
            Message.CONSENSUS_NOTIFY_ACK)

        return reply.content

    def test_driver(self):
        # Start the driver in a separate thread to simulate the
        # validator and the driver
        driver_thread = threading.Thread(
            target=self.driver.start,
            args=(self.url,))

        driver_thread.start()

        response = consensus_pb2.ConsensusRegisterResponse(
            status=consensus_pb2.ConsensusRegisterResponse.OK)

        request = self.recv_rep(
            consensus_pb2.ConsensusRegisterRequest,
            response,
            Message.CONSENSUS_REGISTER_RESPONSE)

        self.assertEqual(request.name, 'test-name')
        self.assertEqual(request.version, 'test-version')

        self.send_req_rep(
            consensus_pb2.ConsensusNotifyPeerConnected(),
            Message.CONSENSUS_NOTIFY_PEER_CONNECTED)

        self.send_req_rep(
            consensus_pb2.ConsensusNotifyPeerDisconnected(),
            Message.CONSENSUS_NOTIFY_PEER_DISCONNECTED)

        self.send_req_rep(
            consensus_pb2.ConsensusNotifyPeerMessage(),
            Message.CONSENSUS_NOTIFY_PEER_MESSAGE)

        self.send_req_rep(
            consensus_pb2.ConsensusNotifyBlockNew(),
            Message.CONSENSUS_NOTIFY_BLOCK_NEW)

        self.send_req_rep(
            consensus_pb2.ConsensusNotifyBlockValid(),
            Message.CONSENSUS_NOTIFY_BLOCK_VALID)

        self.send_req_rep(
            consensus_pb2.ConsensusNotifyBlockInvalid(),
            Message.CONSENSUS_NOTIFY_BLOCK_INVALID)

        self.send_req_rep(
            consensus_pb2.ConsensusNotifyBlockCommit(),
            Message.CONSENSUS_NOTIFY_BLOCK_COMMIT)

        self.assertEqual(
            [msg_type for (msg_type, data) in self.engine.updates],
            [
                Message.CONSENSUS_NOTIFY_PEER_CONNECTED,
                Message.CONSENSUS_NOTIFY_PEER_DISCONNECTED,
                Message.CONSENSUS_NOTIFY_PEER_MESSAGE,
                Message.CONSENSUS_NOTIFY_BLOCK_NEW,
                Message.CONSENSUS_NOTIFY_BLOCK_VALID,
                Message.CONSENSUS_NOTIFY_BLOCK_INVALID,
                Message.CONSENSUS_NOTIFY_BLOCK_COMMIT,
            ])

        self.driver.stop()
        driver_thread.join()


def generate_correlation_id():
    return ''.join(random.choice(string.ascii_letters) for _ in range(16))

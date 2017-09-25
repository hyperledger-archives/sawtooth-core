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

import unittest

from rpc_client import RpcClient
from mock_validator import MockValidator

from sawtooth_sdk.protobuf.validator_pb2 import Message
from sawtooth_sdk.protobuf.client_pb2 import ClientBlockListRequest
from sawtooth_sdk.protobuf.client_pb2 import ClientBlockListResponse
from sawtooth_sdk.protobuf.block_pb2 import Block
from sawtooth_sdk.protobuf.block_pb2 import BlockHeader


class SethRpcTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validator = MockValidator()
        cls.validator.listen("tcp://eth0:4004")
        cls.url = 'http://seth-rpc:3030/'
        cls.rpc = RpcClient(cls.url)
        cls.rpc.wait_for_service()

    # Network tests
    def test_net_version(self):
        """Test that the network id 19 is returned."""
        self.assertEqual("19", self.rpc.call("net_version"))

    def test_net_peerCount(self):
        """Test that 0 is returned as hex."""
        self.assertEqual("0x0", self.rpc.call("net_peerCount"))

    def test_net_listening(self):
        """Test that the True is returned."""
        self.assertEqual(True, self.rpc.call("net_listening"))

    # Block tests
    def test_block_number(self):
        """Test that the block number is extracted correctly and returned as
        hex."""
        self.rpc.acall("eth_blockNumber")
        msg = self.validator.receive()
        self.assertEqual(msg.message_type, Message.CLIENT_BLOCK_LIST_REQUEST)
        self.validator.respond(
            Message.CLIENT_BLOCK_LIST_RESPONSE,
            ClientBlockListResponse(
                status=ClientBlockListResponse.OK,
                blocks=[Block(
                    header=BlockHeader(block_num=15).SerializeToString(),
                )]),
            msg)
        self.assertEqual("0xf", self.rpc.get_result())

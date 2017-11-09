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

from sawtooth_validator.protobuf.network_pb2 import GossipMessage
from sawtooth_validator.protobuf.block_pb2 import Block
from sawtooth_validator.gossip.gossip_handlers import \
    GossipMessageHaveBlockHandler
from test_has_block_handler.mock import MockCompleter
from test_has_block_handler.mock import MockChainController
from sawtooth_validator.networking.dispatch import HandlerStatus


class TestHasBlockHandle(unittest.TestCase):
    def setUp(self):
        self.completer = MockCompleter()
        self.chain = MockChainController()
        self.handler = GossipMessageHaveBlockHandler(
            self.completer, self.chain.has_block)

    def test_no_block(self):
        """
        Test that if the block does not exist yet in the completer or the
        chain controller, the gossip message is passed.
        """
        block = Block(header_signature="Block1")
        message = GossipMessage(content_type=GossipMessage.BLOCK,
                                content=block.SerializeToString())
        handler_status = self.handler.handle(
            "connection_id", message.SerializeToString())
        self.assertEqual(handler_status.status, HandlerStatus.PASS)

    def test_completer_has_block(self):
        """
        Test that if the block does not exist yet in the completer or the
        chain controller, the gossip message is passed.
        """
        block = Block(header_signature="Block1")
        self.completer.add_block("Block1")
        message = GossipMessage(content_type=GossipMessage.BLOCK,
                                content=block.SerializeToString())
        handler_status = self.handler.handle(
            "connection_id", message.SerializeToString())
        self.assertEqual(handler_status.status, HandlerStatus.DROP)

    def test_chain_has_block(self):
        """
        Test that if the block does not exist yet in the completer or the
        chain controller, the gossip message is passed.
        """
        block = Block(header_signature="Block1")
        self.chain.add_block("Block1")
        message = GossipMessage(content_type=GossipMessage.BLOCK,
                                content=block.SerializeToString())
        handler_status = self.handler.handle(
            "connection_id", message.SerializeToString())
        self.assertEqual(handler_status.status, HandlerStatus.DROP)

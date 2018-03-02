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
from sawtooth_validator.protobuf.batch_pb2 import Batch
from sawtooth_validator.networking.dispatch import HandlerStatus
from sawtooth_validator.gossip.gossip_handlers import \
    GossipMessageDuplicateHandler

from test_duplicate_handler.mock import MockCompleter
from test_duplicate_handler.mock import MockChainController
from test_duplicate_handler.mock import MockPublisher


class TestDuplicateHandler(unittest.TestCase):
    def setUp(self):
        self.completer = MockCompleter()
        self.chain = MockChainController()
        self.publisher = MockPublisher()
        self.handler = GossipMessageDuplicateHandler(
            self.completer, self.chain.has_block, self.publisher.has_batch)

    def test_no_block(self):
        """
        Test that if the block does not exist yet in the completer or the
        chain controller, the gossip message is passed.
        """
        block = Block(header_signature="Block1")
        handler_status = self.handler.handle(
            "connection_id", (block, GossipMessage.BLOCK, 2))
        self.assertEqual(handler_status.status, HandlerStatus.PASS)

    def test_no_batch(self):
        """
        Test that if the block does not exist yet in the completer or the
        chain controller, the gossip message is passed.
        """
        batch = Batch(header_signature="Batch1")
        handler_status = self.handler.handle(
            "connection_id", (batch, GossipMessage.BATCH, 2))
        self.assertEqual(handler_status.status, HandlerStatus.PASS)

    def test_completer_has_block(self):
        """
        Test that if the block does not exist yet in the completer or the
        chain controller, the gossip message is passed.
        """
        block = Block(header_signature="Block1")
        self.completer.add_block("Block1")
        handler_status = self.handler.handle(
            "connection_id", (block, GossipMessage.BLOCK, 2))
        self.assertEqual(handler_status.status, HandlerStatus.DROP)

    def test_completer_has_batch(self):
        """
        Test that if the block does not exist yet in the completer or the
        chain controller, the gossip message is passed.
        """
        batch = Batch(header_signature="Batch1")
        self.completer.add_batch("Batch1")
        handler_status = self.handler.handle(
            "connection_id", (batch, GossipMessage.BATCH, 2))
        self.assertEqual(handler_status.status, HandlerStatus.DROP)

    def test_chain_has_block(self):
        """
        Test that if the block does not exist yet in the completer or the
        chain controller, the gossip message is passed.
        """
        block = Block(header_signature="Block1")
        self.chain.add_block("Block1")
        handler_status = self.handler.handle(
            "connection_id", (block, GossipMessage.BLOCK, 2))
        self.assertEqual(handler_status.status, HandlerStatus.DROP)

    def test_publisher_has_block(self):
        """
        Test that if the block does not exist yet in the completer or the
        chain controller, the gossip message is passed.
        """
        batch = Batch(header_signature="Batch1")
        self.publisher.add_batch("Batch1")
        handler_status = self.handler.handle(
            "connection_id", (batch, GossipMessage.BATCH, 2))
        self.assertEqual(handler_status.status, HandlerStatus.DROP)

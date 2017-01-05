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
import pprint
import time
import unittest

from sawtooth_validator.journal.consensus.test_mode \
    import test_mode_consensus
from sawtooth_validator.journal.journal import Journal
from sawtooth_validator.protobuf.batch_pb2 import Batch
from tests.unit3.gossip_mock import GossipMock
from tests.unit3.transaction_executor_mock import TransactionExecutorMock
from tests.unit3.utils import TimeOut

LOGGER = logging.getLogger(__name__)

pp = pprint.PrettyPrinter(indent=4)


class TestJournal(unittest.TestCase):
    def setUp(self):
        self.gossip = GossipMock()
        self.txn_executor = TransactionExecutorMock()

    def test_publish_block(self):
        """
        Test that the Journal will produce blocks and consume those blocks
        to extend the chain.
        :return:
        """
        # construction and wire the journal to the
        # gossip layer.

        LOGGER.info("test_publish_block")
        block_store = {}
        journal = None
        try:
            journal = Journal(
                consensus=test_mode_consensus,
                block_store=block_store,
                send_message=self.gossip.send_message,
                transaction_executor=self.txn_executor,
                squash_handler=None,
                first_state_root="000000")

            self.gossip.on_batch_received = \
                journal.on_batch_received
            self.gossip.on_block_received = \
                journal.on_block_received
            self.gossip.on_block_request = \
                journal.on_block_request

            journal.start()

            # feed it a batch
            batch = Batch()
            journal.on_batch_received(batch)

            # wait for a block message to arrive should be soon
            to = TimeOut(2)
            while len(self.gossip.messages) == 0:
                time.sleep(0.1)

            LOGGER.info("Batches: %s", self.gossip.messages)
            self.assertTrue(len(self.gossip.messages) != 0)

            block = self.gossip.messages[0].block
            # dispatch the message
            self.gossip.dispatch_messages()

            # wait for the chain_head to be updated.
            to = TimeOut(2)
            while block_store['chain_head_id'] != block.header_signature:
                time.sleep(0.1)

            self.assertTrue(block_store['chain_head_id'] ==
                            block.header_signature)

        finally:
            if journal is not None:
                journal.stop()

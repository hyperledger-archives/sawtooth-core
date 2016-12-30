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
import sys
import unittest

from sawtooth_validator.journal.journal import \
    BlockPublisher
from sawtooth_validator.journal.consensus.test_mode.test_mode_consensus \
    import \
    BlockPublisher as TestModePublisher
from sawtooth_validator.protobuf.batch_pb2 import Batch
from tests.unit3.block_tree_manager import BlockTreeManager
from tests.unit3.gossip_mock import GossipMock
from tests.unit3.transaction_executor_mock import TransactionExecutorMock

LOGGER = logging.getLogger(__name__)


class TestBlockPublisher(unittest.TestCase):
    def setUp(self):
        self.blocks = BlockTreeManager()

    def test_publish(self, args=sys.argv[1:]):

        gossip = GossipMock()

        LOGGER.info(self.blocks)
        publisher = BlockPublisher(
            consensus=TestModePublisher(),
            transaction_executor=TransactionExecutorMock(),
            send_message=gossip.send_message,
            squash_handler=None)

        LOGGER.info("1")

        # initial load of existing state
        publisher.on_chain_updated(self.blocks.chain_head.block, [], [])

        LOGGER.info("2")
        # repeat as necessary
        batch = Batch()
        publisher.on_batch_received(batch)
        LOGGER.info("3")
        # current dev_mode consensus always claims blocks when asked.
        # this will be called on a polling every so often or possibly triggered
        # by events in the consensus it's self ... TBD
        publisher.on_check_publish_block()
        LOGGER.info("4")
        LOGGER.info(self.blocks)

        # repeat as necessary
        batch = Batch()
        publisher.on_batch_received(batch)

        publisher.on_check_publish_block()

        LOGGER.info(self.blocks)

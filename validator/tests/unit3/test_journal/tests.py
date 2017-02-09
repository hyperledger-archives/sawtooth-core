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

from sawtooth_validator.journal.publisher import BlockPublisher
from sawtooth_validator.journal.chain import ChainController
from sawtooth_validator.journal.journal import Journal
from sawtooth_validator.journal.block_wrapper import BlockWrapper
from sawtooth_validator.journal.consensus.test_mode.test_mode_consensus \
    import \
    BlockPublisher as TestModePublisher
from sawtooth_validator.journal.consensus.test_mode.test_mode_consensus \
    import \
    BlockVerifier as TestModeVerifier
from sawtooth_validator.journal.consensus.test_mode \
    import test_mode_consensus
from sawtooth_validator.protobuf.batch_pb2 import Batch
from sawtooth_validator.protobuf.block_pb2 import BlockHeader
from test_journal.block_tree_manager import BlockTreeManager
from test_journal.mock import MockBlockSender
from test_journal.mock import MockNetwork
from test_journal.mock import MockTransactionExecutor
from test_journal.mock import SynchronousExecutor
from test_journal.utils import wait_until


LOGGER = logging.getLogger(__name__)

class TestBlockCache(unittest.TestCase):
    def test_load_from_block_store(self):
        """ Test that misses will load from the block store.
        """
        bs = {}
        bs["test"] = "value"
        bs["test2"] = "value"
        bc = BlockCache(bs)

        self.assertTrue("test" in bc)
        self.assertTrue(bc["test2"] == "value")

        with self.assertRaises(KeyError):
            bc["test-missing"]



class TestBlockPublisher(unittest.TestCase):
    def setUp(self):
        self.blocks = BlockTreeManager()
        self.block_sender = MockBlockSender()

    def test_publish(self):

        LOGGER.info(self.blocks)
        publisher = BlockPublisher(
            consensus=TestModePublisher(),
            transaction_executor=MockTransactionExecutor(),
            block_sender=self.block_sender,
            squash_handler=None,
            chain_head=self.blocks.chain_head)

        # initial load of existing state
        publisher.on_chain_updated(self.blocks.chain_head, [], [])

        # repeat as necessary
        batch = Batch()
        publisher.on_batch_received(batch)
        # current dev_mode consensus always claims blocks when asked.
        # this will be called on a polling every so often or possibly triggered
        # by events in the consensus it's self ... TBD
        publisher.on_check_publish_block()
        LOGGER.info(self.blocks)

        # repeat as necessary
        batch = Batch()
        publisher.on_batch_received(batch)

        publisher.on_check_publish_block()

        LOGGER.info(self.blocks)


class TestChainController(unittest.TestCase):
    def setUp(self):
        self.blocks = BlockTreeManager()
        self.gossip = MockNetwork()
        self.executor = SynchronousExecutor()
        self.txn_executor = MockTransactionExecutor()
        self.block_sender = MockBlockSender()

        def chain_updated(head):
            pass

        self.chain_ctrl = ChainController(
            consensus=TestModeVerifier(),
            block_cache=self.blocks.block_cache,
            block_sender=self.block_sender,
            executor=self.executor,
            transaction_executor=MockTransactionExecutor(),
            on_chain_updated=chain_updated,
            squash_handler=None)

    def test_simple_case(self):
        # TEST Run the simple case
        block_1 = self.blocks.generate_block(self.blocks.chain_head)
        self.chain_ctrl.on_block_received(block_1)
        self.executor.process_all()
        assert(self.chain_ctrl.chain_head.block.header_signature ==
               block_1.header_signature)

    def test_alternate_genesis(self):
        # TEST Run generate and alternate genesis block
        head = self.chain_ctrl.chain_head
        other_genesis = self.blocks.generate_block(add_to_store=True)
        for b in self.blocks.generate_chain(other_genesis, 5):
            self.chain_ctrl.on_block_received(b)
            self.executor.process_all()
        assert(self.chain_ctrl.chain_head.block.header_signature ==
               head.block.header_signature)

    def test_bad_block_signature(self):
        # TEST Bad block extending current chain
        # Bad due to signature
        head = self.blocks.chain_head
        block_bad = self.blocks.generate_block(self.blocks.chain_head.block,
                                               invalid_signature=True)
        self.chain_ctrl.on_block_received(block_bad)
        assert (self.chain_ctrl.chain_head.block.header_signature ==
                head.block.header_signature)

    def test_bad_block_consensus(self):
        # Bad due to consensus
        pass

    def test_bad_block_transaction(self):
        # Bad due to transaction
        pass

    # TESTS TBD
    # TEST Missing block never sent G->missing->B
    # validate waiting time out....

    # TEST Run generate a fork -- current chain valid

    # TEST Run generate a fork -- fork chain valid

    # TEST variable block weights

    # TEST Run generate a fork -- fork with missing block in chain

    # TEST Run generate a fork -- bad block in middle of fork

    # TEST Run generate a fork - chain advances before fork resolves

    # TEST Run generate a fork - fork advances before fork resolves

    # TEST Run random cases thru - 2-3 forks extending at random,
    # then pick a winner

    # block arrives that extends block being validated. --
    # should be keeping a
    # fork state?

    # next multi threaded
    # next add block publisher
    # next batch lists
    # integrate with LMDB
    # early vs late binding ( class member of consensus BlockPublisher)

    # print(journal.chain_head, new_block)


class TestJournal(unittest.TestCase):
    def setUp(self):
        self.gossip = MockNetwork()
        self.txn_executor = MockTransactionExecutor()
        self.block_sender = MockBlockSender()

    def test_publish_block(self):
        """
        Test that the Journal will produce blocks and consume those blocks
        to extend the chain.
        :return:
        """
        # construction and wire the journal to the
        # gossip layer.

        LOGGER.info("test_publish_block")
        btm = BlockTreeManager()
        journal = None
        try:
            journal = Journal(
                consensus=test_mode_consensus,
                block_store=btm.block_store.store,
                block_cache=btm.block_cache,
                block_sender=self.block_sender,
                transaction_executor=self.txn_executor,
                squash_handler=None
            )

            self.gossip.on_batch_received = \
                journal.on_batch_received
            self.gossip.on_block_received = \
                journal.on_block_received

            journal.start()

            # feed it a batch
            batch = Batch()
            journal.on_batch_received(batch)

            wait_until(lambda: self.block_sender.new_block is not None, 2)
            self.assertTrue(self.block_sender.new_block is not None)

            block = BlockWrapper(self.block_sender.new_block)
            journal.on_block_received(block)

            # wait for the chain_head to be updated.
            wait_until(lambda: btm.chain_head.identifier ==
                       block.identifier, 2)
            self.assertTrue(btm.chain_head.identifier ==
                            block.identifier)
        finally:
            if journal is not None:
                journal.stop()

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
import unittest

from sawtooth_signing import pbct as signing

from sawtooth_validator.database.dict_database import DictDatabase

from sawtooth_validator.journal.block_cache import BlockCache
from sawtooth_validator.journal.block_wrapper import BlockStatus
from sawtooth_validator.journal.block_wrapper import BlockWrapper

from sawtooth_validator.journal.chain import BlockValidator
from sawtooth_validator.journal.chain import ChainController
from sawtooth_validator.journal.journal import Journal
from sawtooth_validator.journal.publisher import BlockPublisher
from sawtooth_validator.journal.timed_cache import TimedCache

from sawtooth_validator.protobuf.batch_pb2 import Batch

from sawtooth_validator.state.state_view import StateViewFactory

from test_journal.block_tree_manager import BlockTreeManager

from test_journal.mock import MockBlockSender
from test_journal.mock import MockNetwork
from test_journal.mock import MockStateViewFactory
from test_journal.mock import MockTransactionExecutor
from test_journal.mock import SynchronousExecutor
from test_journal.utils import wait_until

from test_journal import mock_consensus


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


class TestBlockCache(unittest.TestCase):
    def test_load_from_block_store(self):
        """ Test that misses will load from the block store.
        """
        bs = {}
        bs["test"] = "value"
        bc = BlockCache(bs)

        self.assertTrue("test" in bc)
        self.assertTrue(bc["test"] == "value")


class TestBlockPublisher(unittest.TestCase):
    def setUp(self):
        self.blocks = BlockTreeManager()
        self.block_sender = MockBlockSender()
        self.state_view_factory = MockStateViewFactory({})

    def test_publish(self):

        LOGGER.info(self.blocks)
        publisher = BlockPublisher(
            transaction_executor=MockTransactionExecutor(),
            block_cache=self.blocks.block_cache,
            state_view_factory=self.state_view_factory,
            block_sender=self.block_sender,
            squash_handler=None,
            chain_head=self.blocks.chain_head,
            identity_signing_key=self.blocks.identity_signing_key)

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


class TestBlockValidator(unittest.TestCase):
    def setUp(self):
        self.btm = BlockTreeManager()
        self.state_view_factory = MockStateViewFactory()

    def create_block_validator(self, new_block, on_block_validated):
        return BlockValidator(
            consensus_module=mock_consensus,
            new_block=new_block,
            chain_head=self.btm.chain_head,
            state_view_factory=self.state_view_factory,
            block_cache=self.btm.block_cache,
            done_cb=on_block_validated,
            executor=MockTransactionExecutor(),
            squash_handler=None)

    class BlockValidationHandler(object):
        def __init__(self):
            self.result = None

        def on_block_validated(self, commit_new_block, result):
            result["commit_new_block"] = commit_new_block
            self.result = result

        def has_result(self):
            return self.result is not None

    # fork based tests
    def test_fork_simple(self):
        """
        Test a simple case of a new block extending the current root.
        """
        bvh = self.BlockValidationHandler()
        new_block = self.btm.generate_block(previous_block=self.btm.chain_head,
                                            add_to_store=True)

        bv = self.create_block_validator(new_block, bvh.on_block_validated)
        bv.run()

        self.assertTrue(bvh.has_result())
        self.assertTrue(new_block.status == BlockStatus.Valid)
        self.assertTrue(bvh.result["commit_new_block"])

    def test_good_fork_lower(self):
        """
        Test case of a new block extending on a valid chain but not as long
        as the current chain.
        """
        bvh = self.BlockValidationHandler()

        root = self.btm.chain_head

        # create a new valid chain 5 long from the current root
        new_head = self.btm.generate_chain(root, 5,
                                           {'add_to_store': True})
        self.btm.set_chain_head(new_head[-1])
        # generate candidate chain 3 long from the same root
        new_block = self.btm.generate_chain(root, 3,
                                            {'add_to_cache': True})

        bv = self.create_block_validator(new_block[-1], bvh.on_block_validated)
        bv.run()

        self.assertTrue(bvh.has_result())
        self.assertTrue(new_block[-1].status == BlockStatus.Valid)
        self.assertFalse(bvh.result["commit_new_block"])

    def test_good_fork_higher(self):
        """
        Test case of a new block extending on a valid chain but longer
        than the current chain. ( similar to test_good_fork_lower but uses
        a different code path when finding the common root )
        """
        bvh = self.BlockValidationHandler()

        root = self.btm.chain_head

        # create a new valid chain 5 long from the current root
        new_head = self.btm.generate_chain(root, 5,
                                           {'add_to_store': True})
        self.btm.set_chain_head(new_head[-1])
        # generate candidate chain 8 long from the same root
        new_block = self.btm.generate_chain(root, 8,
                                            {'add_to_cache': True})
        bv = self.create_block_validator(new_block[-1], bvh.on_block_validated)
        bv.run()

        self.assertTrue(bvh.has_result())
        self.assertTrue(new_block[-1].status == BlockStatus.Valid)
        self.assertTrue(bvh.result["commit_new_block"])

    def test_fork_different_genesis(self):
        """"
        Test the case where new block is from a different genesis
        """
        bvh = self.BlockValidationHandler()

        # create a new valid chain 5 long from the current root
        new_head = self.btm.generate_chain(self.btm.chain_head, 5,
                                           {'add_to_store': True})
        self.btm.set_chain_head(new_head[-1])

        # generate candidate chain 5 long from it's own genesis
        new_block = self.btm.generate_chain(None, 5,
                                            {'add_to_cache': True})

        bv = self.create_block_validator(new_block[-1], bvh.on_block_validated)
        bv.run()

        self.assertTrue(bvh.has_result())
        self.assertTrue(new_block[-1].status == BlockStatus.Invalid)
        self.assertFalse(bvh.result["commit_new_block"])

    def test_fork_missing_predecessor(self):
        """"
        Test the case where new block is missing the a predecessor
        """
        bvh = self.BlockValidationHandler()

        root = self.btm.chain_head

        # generate candidate chain 3 long off the current head.
        new_block = self.btm.generate_chain(root, 3,
                                            {'add_to_cache': True})
        # remove one of the new blocks
        del self.btm.block_cache[new_block[1].identifier]

        bv = self.create_block_validator(new_block[-1], bvh.on_block_validated)
        bv.run()

        self.assertTrue(bvh.has_result())
        self.assertTrue(new_block[-1].status == BlockStatus.Invalid)
        self.assertFalse(bvh.result["commit_new_block"])

    def test_fork_invalid_predecessor(self):
        """"
        Test the case where new block has an invalid predecessor
        """
        bvh = self.BlockValidationHandler()

        root = self.btm.chain_head

        # generate candidate chain 3 long off the current head.
        new_block = self.btm.generate_chain(root, 3,
                                            {'add_to_cache': True})
        # Mark a predecessor as invalid
        new_block[1].status = BlockStatus.Invalid

        bv = self.create_block_validator(new_block[-1], bvh.on_block_validated)
        bv.run()

        self.assertTrue(bvh.has_result())
        self.assertTrue(new_block[-1].status == BlockStatus.Invalid)
        self.assertFalse(bvh.result["commit_new_block"])

    # block based tests
    def test_block_bad_signature(self):
        """
        Test the case where the new block has a bad signature.
        """
        pass

    def test_block_missing_batch(self):
        """
        Test the case where the new block is missing a batch.
        """
        pass

    def test_block_extra_batch(self):
        """
        Test the case where the new block has a batch.
        """
        pass

    def test_block_batches_order(self):
        """
        Test the case where the new block has batches that are
        out of order.
        """
        pass

    def test_block_bad_batch(self):
        """
        Test the case where the new block has a bad batch
        """
        pass

    def test_block_missing_batch_dependency(self):
        """
        Test the case where the new block has a batch that is missing a
        dependency.
        """
        pass

    def test_block_bad_state(self):
        """
        Test the case where the new block has a bad batch
        """
        pass

    def test_block_bad_consensus(self):
        """
        Test the case where the new block has a bad batch
        """
        pass


class TestChainController(unittest.TestCase):
    def setUp(self):
        self.blocks = BlockTreeManager()
        self.gossip = MockNetwork()
        self.executor = SynchronousExecutor()
        self.txn_executor = MockTransactionExecutor()
        self.block_sender = MockBlockSender()
        self.state_view_factory = MockStateViewFactory()

        def chain_updated(head, committed_batches=None,
                          uncommitted_batches=None):
            pass

        self.chain_ctrl = ChainController(
            block_cache=self.blocks.block_cache,
            state_view_factory=self.state_view_factory,
            block_sender=self.block_sender,
            executor=self.executor,
            transaction_executor=MockTransactionExecutor(),
            on_chain_updated=chain_updated,
            squash_handler=None,
            chain_id_manager=None)

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
        for b in self.blocks.generate_chain(None, 5,
                                            {"add_to_cache": True}):
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

        btm = BlockTreeManager()
        journal = None
        try:
            journal = Journal(
                block_store=btm.block_store,
                block_cache=btm.block_cache,
                state_view_factory=StateViewFactory(DictDatabase()),
                block_sender=self.block_sender,
                transaction_executor=self.txn_executor,
                squash_handler=None,
                identity_signing_key=btm.identity_signing_key,
                chain_id_manager=None
            )

            self.gossip.on_batch_received = journal.on_batch_received
            self.gossip.on_block_received = journal.on_block_received

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
            self.assertTrue(btm.chain_head.identifier == block.identifier)
        finally:
            if journal is not None:
                journal.stop()


class TestTimedCache(unittest.TestCase):
    def test_cache(self):
        bc = TimedCache(keep_time=1)

        with self.assertRaises(KeyError):
            bc["test"]

        bc["test"] = "value"

        self.assertEqual(len(bc), 1)

        del bc["test"]
        self.assertFalse("test" in bc)

    def test_evict_expired(self):
        """ Test that values will be evicted from the
        cache as they time out.
        """

        # use an invasive technique so that we don't have to sleep for
        # the item to expire

        bc = TimedCache(keep_time=1)

        bc["test"] = "value"
        bc["test2"] = "value2"
        self.assertEqual(len(bc), 2)

        # test that expired item i
        bc.cache["test"].timestamp = bc.cache["test"].timestamp - 2
        bc.purge_expired()
        self.assertEqual(len(bc), 1)
        self.assertFalse("test" in bc)
        self.assertTrue("test2" in bc)

    def test_access_update(self):

        bc = TimedCache(keep_time=1)

        bc["test"] = "value"
        bc["test2"] = "value2"
        self.assertEqual(len(bc), 2)

        bc["test"] = "value"
        bc.cache["test"].timestamp = bc.cache["test"].timestamp - 2
        bc["test"]  # access to update timestamp
        bc.purge_expired()
        self.assertEqual(len(bc), 2)
        self.assertTrue("test" in bc)
        self.assertTrue("test2" in bc)

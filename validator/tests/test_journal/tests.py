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

# pylint: disable=too-many-lines
# pylint: disable=pointless-statement
# pylint: disable=protected-access
# pylint: disable=unbalanced-tuple-unpacking

import logging
from threading import RLock
import unittest
from unittest.mock import patch

from sawtooth_validator.database.dict_database import DictDatabase

from sawtooth_validator.journal.block_cache import BlockCache
from sawtooth_validator.journal.block_wrapper import BlockStatus
from sawtooth_validator.journal.block_wrapper import BlockWrapper

from sawtooth_validator.journal.block_store import BlockStore
from sawtooth_validator.journal.chain import BlockValidator
from sawtooth_validator.journal.chain import ChainController
from sawtooth_validator.journal.chain_commit_state import ChainCommitState
from sawtooth_validator.journal.publisher import BlockPublisher
from sawtooth_validator.journal.timed_cache import TimedCache
from sawtooth_validator.journal.event_extractors \
    import BlockEventExtractor
from sawtooth_validator.journal.event_extractors \
    import ReceiptEventExtractor
from sawtooth_validator.journal.batch_injector import \
    DefaultBatchInjectorFactory

from sawtooth_validator.server.events.subscription import EventSubscription
from sawtooth_validator.server.events.subscription import EventFilterFactory

from sawtooth_validator.protobuf.batch_pb2 import Batch
from sawtooth_validator.protobuf.block_pb2 import Block
from sawtooth_validator.protobuf.block_pb2 import BlockHeader
from sawtooth_validator.protobuf.transaction_receipt_pb2 import \
    TransactionReceipt
from sawtooth_validator.protobuf.transaction_receipt_pb2 import StateChange
from sawtooth_validator.protobuf.transaction_receipt_pb2 import StateChangeList
from sawtooth_validator.protobuf.events_pb2 import Event
from sawtooth_validator.protobuf.events_pb2 import EventFilter

from sawtooth_validator.state.settings_view import SettingsViewFactory
from sawtooth_validator.state.settings_cache import SettingsCache

from test_journal.block_tree_manager import BlockTreeManager

from test_journal.mock import MockChainIdManager
from test_journal.mock import MockBlockSender
from test_journal.mock import MockBatchSender
from test_journal.mock import MockNetwork
from test_journal.mock import MockStateViewFactory, CreateSetting
from test_journal.mock import MockTransactionExecutor
from test_journal.mock import MockPermissionVerifier
from test_journal.mock import SynchronousExecutor
from test_journal.mock import MockBatchInjectorFactory
from test_journal.utils import wait_until

from test_journal import mock_consensus


LOGGER = logging.getLogger(__name__)


class TestBlockCache(unittest.TestCase):
    def test_load_from_block_store(self):
        """ Test that misses will load from the block store.
        """
        bs = {}
        block1 = Block(
            header=BlockHeader(previous_block_id="000").SerializeToString(),
            header_signature="test")
        bs["test"] = BlockWrapper(block1)
        block2 = Block(
            header=BlockHeader(previous_block_id="000").SerializeToString(),
            header_signature="test2")
        blkw2 = BlockWrapper(block2)
        bs["test2"] = blkw2
        bc = BlockCache(bs)

        self.assertTrue("test" in bc)
        self.assertTrue(bc["test2"] == blkw2)

        with self.assertRaises(KeyError):
            bc["test-missing"]


class TestBlockPublisher(unittest.TestCase):
    '''
    The block publisher has three main functions, and in these tests
    those functions are given the following wrappers for convenience:
        * on_batch_received -> receive_batches
        * on_chain_updated -> update_chain_head
        * on_check_publish_block -> publish_block

    After publishing a block, publish_block sends its block to the
    mock block sender, and that block is named result_block. This block
    is what is checked by the test assertions.

    The basic pattern for the publisher tests (with variations) is:
        0) make a list of batches (usually in setUp);
        1) receive the batches;
        2) publish a block;
        3) verify the block (checking that it contains the correct batches,
           or checking that it doesn't exist, or whatever).

    The publisher chain head might be updated several times in a test.
    '''

    def setUp(self):
        self.block_tree_manager = BlockTreeManager()
        self.block_sender = MockBlockSender()
        self.batch_sender = MockBatchSender()
        self.state_view_factory = MockStateViewFactory({})
        self.permission_verifier = MockPermissionVerifier()

        self.publisher = BlockPublisher(
            transaction_executor=MockTransactionExecutor(),
            block_cache=self.block_tree_manager.block_cache,
            state_view_factory=self.state_view_factory,
            settings_cache=SettingsCache(
                SettingsViewFactory(
                    self.block_tree_manager.state_view_factory),
            ),
            block_sender=self.block_sender,
            batch_sender=self.batch_sender,
            squash_handler=None,
            chain_head=self.block_tree_manager.chain_head,
            identity_signer=self.block_tree_manager.identity_signer,
            data_dir=None,
            config_dir=None,
            check_publish_block_frequency=0.1,
            batch_observers=[],
            permission_verifier=self.permission_verifier)

        self.init_chain_head = self.block_tree_manager.chain_head

        self.result_block = None

        # A list of batches is created at the beginning of each test.
        # The test assertions and the publisher function wrappers
        # take these batches as a default argument.
        self.batch_count = 8
        self.batches = self.make_batches()

    def test_publish(self):
        '''
        Publish a block with several batches
        '''
        self.receive_batches()

        self.publish_block()

        self.verify_block()

    def test_reject_duplicate_batches_from_receive(self):
        '''
        Test that duplicate batches from on_batch_received are rejected
        '''
        for _ in range(5):
            self.receive_batches()

        self.publish_block()

        self.verify_block()

    def test_reject_duplicate_batches_from_store(self):
        '''
        Test that duplicate batches from block store are rejected
        '''
        self.update_chain_head(None)

        self.update_chain_head(
            head=self.init_chain_head,
            uncommitted=self.batches)

        self.receive_batches()

        self.publish_block()

        self.verify_block()

    def test_no_chain_head(self):
        '''
        Test that nothing gets published with a null chain head,
        then test that publishing resumes after updating
        '''
        self.update_chain_head(None)

        self.receive_batches()

        # try to publish block (failing)
        self.publish_block()

        self.assert_no_block_published()

        # reset chain head several times,
        # making sure batches remain queued
        for _ in range(3):
            self.update_chain_head(None)
            self.update_chain_head(self.init_chain_head)

        # try to publish block (succeeding)
        self.publish_block()

        self.verify_block()

    def test_committed_batches(self):
        '''
        Test that batches committed upon updating the chain head
        are not included in the next block.
        '''
        self.update_chain_head(None)

        self.update_chain_head(
            head=self.init_chain_head,
            committed=self.batches)

        new_batches = self.make_batches(batch_count=12)

        self.receive_batches(new_batches)

        self.publish_block()

        self.verify_block(new_batches)

    def test_uncommitted_batches(self):
        '''
        Test that batches uncommitted upon updating the chain head
        are included in the next block.
        '''
        self.update_chain_head(None)

        self.update_chain_head(
            head=self.init_chain_head,
            uncommitted=self.batches)

        self.publish_block()

        self.verify_block()

    def test_empty_pending_queue(self):
        '''
        Test that no block is published if the pending queue is empty
        '''
        # try to publish with no pending queue (failing)
        self.publish_block()

        self.assert_no_block_published()

        # receive batches, then try again (succeeding)
        self.receive_batches()

        self.publish_block()

        self.verify_block()

    def test_missing_dependencies(self):
        '''
        Test that no block is published with missing dependencies
        '''
        self.batches = self.make_batches(
            missing_deps=True)

        self.receive_batches()

        self.publish_block()

        self.assert_no_block_published()

    def test_batches_rejected_by_scheduler(self):
        '''
        Test that no block is published with
        batches rejected by the scheduler
        '''
        self.publisher = BlockPublisher(
            transaction_executor=MockTransactionExecutor(
                batch_execution_result=False),
            block_cache=self.block_tree_manager.block_cache,
            state_view_factory=self.state_view_factory,
            settings_cache=SettingsCache(
                SettingsViewFactory(
                    self.block_tree_manager.state_view_factory),
            ),
            block_sender=self.block_sender,
            batch_sender=self.batch_sender,
            squash_handler=None,
            chain_head=self.block_tree_manager.chain_head,
            identity_signer=self.block_tree_manager.identity_signer,
            data_dir=None,
            config_dir=None,
            check_publish_block_frequency=0.1,
            batch_observers=[],
            permission_verifier=self.permission_verifier)

        self.receive_batches()

        self.publish_block()

        self.assert_no_block_published()

    def test_max_block_size(self):
        '''
        Test block publisher obeys the block size limits
        '''
        # Create a publisher that has a state view
        # with a batch limit
        addr, value = CreateSetting(
            'sawtooth.publisher.max_batches_per_block', 1)
        self.state_view_factory = MockStateViewFactory(
            {addr: value})

        self.publisher = BlockPublisher(
            transaction_executor=MockTransactionExecutor(),
            block_cache=self.block_tree_manager.block_cache,
            state_view_factory=self.state_view_factory,
            settings_cache=SettingsCache(
                SettingsViewFactory(
                    self.state_view_factory),
            ),
            block_sender=self.block_sender,
            batch_sender=self.batch_sender,
            squash_handler=None,
            chain_head=self.block_tree_manager.chain_head,
            identity_signer=self.block_tree_manager.identity_signer,
            data_dir=None,
            config_dir=None,
            check_publish_block_frequency=0.1,
            batch_observers=[],
            permission_verifier=self.permission_verifier)

        self.assert_no_block_published()

        # receive batches, then try again (succeeding)
        self.receive_batches()

        # try to publish with no pending queue (failing)
        for i in range(self.batch_count):
            self.publish_block()
            self.assert_block_published()
            self.update_chain_head(BlockWrapper(self.result_block))
            self.verify_block([self.batches[i]])

    def test_duplicate_transactions(self):
        '''
        Test discards batches that have duplicate transactions in them.
        '''
        # receive batches, then try again (succeeding)
        self.batches = self.batches[1:2]
        self.receive_batches()
        self.publish_block()
        self.assert_block_published()
        self.update_chain_head(BlockWrapper(self.result_block))
        self.verify_block()

        # build a new set of batches with the same transactions in them
        self.batches = self.make_batches_with_duplicate_txn()
        self.receive_batches()
        self.publish_block()
        self.assert_no_block_published()  # block should be empty after batch
        # with duplicate transaction is dropped.

    def test_batch_injection_start_block(self):
        '''
        Test that the batch is injected at the beginning of the block.
        '''

        injected_batch = self.make_batch()

        self.publisher = BlockPublisher(
            transaction_executor=MockTransactionExecutor(),
            block_cache=self.block_tree_manager.block_cache,
            state_view_factory=self.state_view_factory,
            settings_cache=SettingsCache(
                SettingsViewFactory(
                    self.block_tree_manager.state_view_factory),
            ),
            block_sender=self.block_sender,
            batch_sender=self.batch_sender,
            squash_handler=None,
            chain_head=self.block_tree_manager.chain_head,
            identity_signer=self.block_tree_manager.identity_signer,
            data_dir=None,
            config_dir=None,
            permission_verifier=self.permission_verifier,
            check_publish_block_frequency=0.1,
            batch_observers=[],
            batch_injector_factory=MockBatchInjectorFactory(injected_batch))

        self.receive_batches()

        self.publish_block()

        self.assert_batch_in_block(injected_batch)

    # assertions
    def assert_block_published(self):
        self.assertIsNotNone(
            self.result_block,
            'Block should have been published')

    def assert_no_block_published(self):
        self.assertIsNone(
            self.result_block,
            'Block should not have been published')

    def assert_batch_in_block(self, batch):
        self.assertIn(
            batch,
            tuple(self.result_block.batches),
            'Batch not in block')

    def assert_batches_in_block(self, batches=None):
        if batches is None:
            batches = self.batches

        for batch in batches:
            self.assert_batch_in_block(batch)

    def assert_block_batch_count(self, batch_count=None):
        if batch_count is None:
            batch_count = self.batch_count

        self.assertEqual(
            len(self.result_block.batches),
            batch_count,
            'Wrong batch count in block')

    def verify_block(self, batches=None):
        if batches is None:
            batches = self.batches

        batch_count = None if batches is None else len(batches)

        self.assert_block_published()
        self.assert_batches_in_block(batches)
        self.assert_block_batch_count(batch_count)

        self.result_block = None

    # publisher functions

    def receive_batch(self, batch):
        self.publisher.on_batch_received(batch)

    def receive_batches(self, batches=None):
        if batches is None:
            batches = self.batches

        for batch in batches:
            self.receive_batch(batch)

    def publish_block(self):
        self.publisher.on_check_publish_block()
        self.result_block = self.block_sender.new_block
        self.block_sender.new_block = None

    def update_chain_head(self, head, committed=None, uncommitted=None):
        if head:
            self.block_tree_manager.block_store.update_chain([head])
        self.publisher.on_chain_updated(
            chain_head=head,
            committed_batches=committed,
            uncommitted_batches=uncommitted)

    # batches
    def make_batch(self, missing_deps=False):
        return self.block_tree_manager.generate_batch(
            missing_deps=missing_deps)

    def make_batches(self, batch_count=None, missing_deps=False):
        if batch_count is None:
            batch_count = self.batch_count

        return [self.make_batch(missing_deps=missing_deps)
                for _ in range(batch_count)]

    def make_batches_with_duplicate_txn(self):
        txns = [self.batches[0].transactions[0],
                self.block_tree_manager.generate_transaction("nonce")]
        return [self.block_tree_manager.generate_batch(txns=txns)]


class TestBlockValidator(unittest.TestCase):
    def setUp(self):
        self.state_view_factory = MockStateViewFactory()

        self.block_tree_manager = BlockTreeManager()
        self.root = self.block_tree_manager.chain_head

        self.block_validation_handler = self.BlockValidationHandler()
        self.permission_verifier = MockPermissionVerifier()

    # fork based tests
    def test_fork_simple(self):
        """
        Test a simple case of a new block extending the current root.
        """

        new_block = self.block_tree_manager.generate_block(
            previous_block=self.root,
            add_to_cache=True)

        self.validate_block(new_block)

        self.assert_valid_block(new_block)
        self.assert_new_block_committed()

    def test_good_fork_lower(self):
        """
        Test case of a new block extending on a valid chain but not as long
        as the current chain.
        """
        # create a new valid chain 5 long from the current root
        _, head = self.generate_chain_with_head(
            self.root, 5, {'add_to_store': True})

        self.block_tree_manager.set_chain_head(head)

        # generate candidate chain 3 long from the same root
        _, new_head = self.generate_chain_with_head(
            self.root, 3, {'add_to_cache': True})

        self.validate_block(new_head)

        self.assert_valid_block(new_head)
        self.assert_new_block_not_committed()

    def test_good_fork_higher(self):
        """
        Test case of a new block extending on a valid chain but longer
        than the current chain. ( similar to test_good_fork_lower but uses
        a different code path when finding the common root )
        """
        # create a new valid chain 5 long from the current root
        _, head = self.generate_chain_with_head(
            self.root, 5, {'add_to_store': True})

        self.block_tree_manager.set_chain_head(head)

        # generate candidate chain 8 long from the same root
        _, new_head = self.generate_chain_with_head(
            head, 8, {'add_to_cache': True})

        self.validate_block(new_head)

        self.assert_valid_block(new_head)
        self.assert_new_block_committed()

    def test_fork_different_genesis(self):
        """"
        Test the case where new block is from a different genesis
        """
        # create a new valid chain 5 long from the current root
        _, head = self.generate_chain_with_head(
            self.root, 5, {'add_to_store': True})

        self.block_tree_manager.set_chain_head(head)

        # generate candidate chain 5 long from its own genesis
        _, new_head = self.generate_chain_with_head(
            None, 5, {'add_to_cache': True})

        self.validate_block(new_head)

        self.assert_invalid_block(new_head)
        self.assert_new_block_not_committed()

    def test_fork_missing_predecessor(self):
        """"
        Test the case where new block is missing the a predecessor
        """
        # generate candidate chain 5 long off the current head.
        chain, head = self.generate_chain_with_head(
            self.root, 5, {'add_to_cache': True})

        # remove one of the new blocks
        del self.block_tree_manager.block_cache[chain[1].identifier]

        self.validate_block(head)

        self.assert_invalid_block(head)
        self.assert_new_block_not_committed()

    def test_fork_invalid_predecessor(self):
        """"
        Test the case where new block has an invalid predecessor
        """
        # generate candidate chain 5 long off the current head.
        chain, head = self.generate_chain_with_head(
            self.root, 5, {'add_to_cache': True})

        # Mark a predecessor as invalid
        chain[1].status = BlockStatus.Invalid

        self.validate_block(head)

        self.assert_invalid_block(head)
        self.assert_new_block_not_committed()

    def test_block_bad_consensus(self):
        """
        Test the case where the new block has a bad batch
        """
        _, head = self.generate_chain_with_head(
            self.root, 5, {'add_to_store': True})

        new_block = self.block_tree_manager.generate_block(
            previous_block=head,
            add_to_cache=True,
            invalid_consensus=True)

        self.validate_block(new_block)

        self.assert_invalid_block(new_block)
        self.assert_new_block_not_committed()

    def test_block_bad_batch(self):
        """
        Test the case where the new block has a bad batch
        """
        _, head = self.generate_chain_with_head(
            self.root, 5, {'add_to_store': True})

        new_block = self.block_tree_manager.generate_block(
            previous_block=head,
            add_to_cache=True,
            invalid_batch=True)

        self.validate_block(new_block)

        self.assert_invalid_block(new_block)
        self.assert_new_block_not_committed()

    def test_block_missing_batch_dependency(self):
        """
        Test the case where the new block has a batch that is missing a
        dependency.
        """
        _, head = self.generate_chain_with_head(
            self.root, 5, {'add_to_store': True})

        txn = self.block_tree_manager.generate_transaction(deps=["missing"])
        batch = self.block_tree_manager.generate_batch(txns=[txn])
        new_block = self.block_tree_manager.generate_block(
            previous_block=head,
            add_to_cache=True,
            invalid_batch=True,
            batches=[batch])

        self.validate_block(new_block)

        self.assert_invalid_block(new_block)
        self.assert_new_block_not_committed()

    def test_block_duplicate_batch(self):
        """
        Test the case where the new block has a batch that already committed to
        the chain.
        """
        _, head = self.generate_chain_with_head(
            self.root, 5, {'add_to_store': True})

        batch = self.block_tree_manager.generate_batch()
        new_block = self.block_tree_manager.generate_block(
            previous_block=head,
            add_to_cache=True,
            invalid_batch=True,
            batches=[batch])
        self.validate_block(new_block)

        new_block = self.block_tree_manager.generate_block(
            previous_block=head,
            add_to_cache=True,
            invalid_batch=True,
            batches=[batch])
        self.validate_block(new_block)

        self.assert_invalid_block(new_block)
        self.assert_new_block_not_committed()

    def test_block_duplicate_batch_in_block(self):
        """
        Test the case where the new block has a duplicate batches.
        """
        _, head = self.generate_chain_with_head(
            self.root, 5, {'add_to_store': True})

        batch = self.block_tree_manager.generate_batch()

        new_block = self.block_tree_manager.generate_block(
            previous_block=head,
            add_to_cache=True,
            invalid_batch=True,
            batches=[batch, batch])
        self.validate_block(new_block)

        self.assert_invalid_block(new_block)
        self.assert_new_block_not_committed()

    def test_block_duplicate_transaction(self):
        """
        Test the case where the new block has a transaction that is already
        committed.
        """
        _, head = self.generate_chain_with_head(
            self.root, 5, {'add_to_store': True})

        txn = self.block_tree_manager.generate_transaction()
        batch = self.block_tree_manager.generate_batch(txns=[txn])
        new_block = self.block_tree_manager.generate_block(
            previous_block=head,
            add_to_cache=True,
            invalid_batch=True,
            batches=[batch])
        self.validate_block(new_block)

        txn2 = self.block_tree_manager.generate_transaction()
        batch = self.block_tree_manager.generate_batch(txns=[txn, txn2])
        new_block = self.block_tree_manager.generate_block(
            previous_block=new_block,
            add_to_cache=True,
            invalid_batch=True,
            batches=[batch])
        self.validate_block(new_block)

        self.assert_invalid_block(new_block)
        self.assert_new_block_not_committed()

    def test_block_duplicate_transaction_in_batch(self):
        """
        Test the case where the new block has a batch that contains duplicate
        transactions.
        """
        _, head = self.generate_chain_with_head(
            self.root, 5, {'add_to_store': True})

        txn = self.block_tree_manager.generate_transaction()
        batch = self.block_tree_manager.generate_batch(txns=[txn, txn])
        new_block = self.block_tree_manager.generate_block(
            previous_block=head,
            add_to_cache=True,
            invalid_batch=True,
            batches=[batch])
        self.validate_block(new_block)

        self.assert_invalid_block(new_block)
        self.assert_new_block_not_committed()

    # assertions

    def assert_valid_block(self, block):
        self.assertEqual(
            block.status, BlockStatus.Valid,
            "Block should be valid")

    def assert_invalid_block(self, block):
        self.assertEqual(
            block.status, BlockStatus.Invalid,
            "Block should be invalid")

    def assert_new_block_committed(self):
        self.assert_handler_has_result()
        self.assertTrue(
            self.block_validation_handler.result["commit_new_block"],
            "New block not committed, should be")

    def assert_new_block_not_committed(self):
        self.assert_handler_has_result()
        self.assertFalse(
            self.block_validation_handler.result["commit_new_block"],
            "New block committed, shouldn't be")

    def assert_handler_has_result(self):
        msg = "Validation handler doesn't have result"
        self.assertTrue(self.block_validation_handler.has_result(), msg)

    # block validation

    def validate_block(self, block):
        validator = self.create_block_validator(
            block,
            self.block_validation_handler.on_block_validated)

        validator.run()

    def create_block_validator(self, new_block, on_block_validated):
        return BlockValidator(
            consensus_module=mock_consensus,
            new_block=new_block,
            state_view_factory=self.state_view_factory,
            block_cache=self.block_tree_manager.block_cache,
            done_cb=on_block_validated,
            executor=MockTransactionExecutor(batch_execution_result=None),
            squash_handler=None,
            identity_signer=self.block_tree_manager.identity_signer,
            data_dir=None,
            config_dir=None,
            permission_verifier=self.permission_verifier)

    class BlockValidationHandler(object):
        def __init__(self):
            self.result = None

        def on_block_validated(self, commit_new_block, result):
            result["commit_new_block"] = commit_new_block
            self.result = result

        def has_result(self):
            return self.result is not None

    # block tree manager interface

    def generate_chain_with_head(self, root_block, num_blocks, params=None):
        chain = self.block_tree_manager.generate_chain(
            root_block, num_blocks, params)

        head = chain[-1]

        return chain, head


class TestChainController(unittest.TestCase):
    def setUp(self):
        self.block_tree_manager = BlockTreeManager()
        self.gossip = MockNetwork()
        self.executor = SynchronousExecutor()
        self.txn_executor = MockTransactionExecutor()
        self.block_sender = MockBlockSender()
        self.chain_id_manager = MockChainIdManager()
        self._chain_head_lock = RLock()
        self.permission_verifier = MockPermissionVerifier()

        def chain_updated(head, committed_batches=None,
                          uncommitted_batches=None):
            pass

        self.chain_ctrl = ChainController(
            block_cache=self.block_tree_manager.block_cache,
            state_view_factory=MockStateViewFactory(
                self.block_tree_manager.state_db),
            block_sender=self.block_sender,
            thread_pool=self.executor,
            transaction_executor=MockTransactionExecutor(
                batch_execution_result=None),
            chain_head_lock=self._chain_head_lock,
            on_chain_updated=chain_updated,
            squash_handler=None,
            chain_id_manager=self.chain_id_manager,
            identity_signer=self.block_tree_manager.identity_signer,
            data_dir=None,
            config_dir=None,
            permission_verifier=self.permission_verifier,
            chain_observers=[],
            metrics_registry=None)

        init_root = self.chain_ctrl.chain_head
        self.assert_is_chain_head(init_root)

        # create a chain of length 5 extending the root
        _, head = self.generate_chain(init_root, 5)
        self.receive_and_process_blocks(head)
        self.assert_is_chain_head(head)

        self.init_head = head

    def test_simple_case(self):
        new_block = self.generate_block(self.init_head)
        self.receive_and_process_blocks(new_block)
        self.assert_is_chain_head(new_block)

    def test_alternate_genesis(self):
        '''Tests a fork extending an alternate genesis block
        '''
        chain, _ = self.generate_chain(None, 5)

        for block in chain:
            self.receive_and_process_blocks(block)

        # make sure initial head is still chain head
        self.assert_is_chain_head(self.init_head)

    def test_bad_blocks(self):
        '''Tests bad blocks extending current chain
        '''
        # Bad due to consensus
        bad_consen = self.generate_block(
            previous_block=self.init_head,
            invalid_consensus=True)

        # chain head should be the same
        self.receive_and_process_blocks(bad_consen)
        self.assert_is_chain_head(self.init_head)

        # Bad due to transaction
        bad_batch = self.generate_block(
            previous_block=self.init_head,
            invalid_batch=True)

        # chain head should be the same
        self.receive_and_process_blocks(bad_batch)
        self.assert_is_chain_head(self.init_head)

        # # Ensure good block works
        good_block = self.generate_block(
            previous_block=self.init_head)

        # chain head should be good_block
        self.receive_and_process_blocks(good_block)
        self.assert_is_chain_head(good_block)

    def test_fork_weights(self):
        '''Tests extending blocks of different weights
        '''
        weight_4 = self.generate_block(
            previous_block=self.init_head,
            weight=4)

        weight_7 = self.generate_block(
            previous_block=self.init_head,
            weight=7)

        weight_8 = self.generate_block(
            previous_block=self.init_head,
            weight=8)

        self.receive_and_process_blocks(
            weight_7,
            weight_4,
            weight_8)

        self.assert_is_chain_head(weight_8)

    def test_fork_lengths(self):
        '''Tests competing forks of different lengths
        '''
        _, head_2 = self.generate_chain(self.init_head, 2)
        _, head_7 = self.generate_chain(self.init_head, 7)
        _, head_5 = self.generate_chain(self.init_head, 5)

        self.receive_and_process_blocks(
            head_2,
            head_7,
            head_5)

        self.assert_is_chain_head(head_7)

    def test_advancing_chain(self):
        '''Tests the chain being advanced between a fork's
        creation and validation
        '''
        _, fork_5 = self.generate_chain(self.init_head, 5)
        _, fork_3 = self.generate_chain(self.init_head, 3)

        self.receive_and_process_blocks(fork_3)
        self.assert_is_chain_head(fork_3)

        # fork_5 is longer than fork_3, so it should be accepted
        self.receive_and_process_blocks(fork_5)
        self.assert_is_chain_head(fork_5)

    def test_fork_missing_block(self):
        '''Tests a fork with a missing block
        '''
        # make new chain
        new_chain, new_head = self.generate_chain(self.init_head, 5)

        self.chain_ctrl.on_block_received(new_head)

        # delete a block from the new chain
        del self.chain_ctrl._block_cache[new_chain[3].identifier]

        self.executor.process_all()

        # chain shouldn't advance
        self.assert_is_chain_head(self.init_head)

        # try again, chain still shouldn't advance
        self.receive_and_process_blocks(new_head)

        self.assert_is_chain_head(self.init_head)

    def test_fork_bad_block(self):
        '''Tests a fork with a bad block in the middle
        '''
        # make two chains extending chain
        _, good_head = self.generate_chain(self.init_head, 5)
        bad_chain, bad_head = self.generate_chain(self.init_head, 5)

        self.chain_ctrl.on_block_received(bad_head)
        self.chain_ctrl.on_block_received(good_head)

        # invalidate block in the middle of bad_chain
        bad_chain[3].status = BlockStatus.Invalid

        self.executor.process_all()

        # good_chain should be accepted
        self.assert_is_chain_head(good_head)

    def test_advancing_fork(self):
        '''Tests a fork advancing before getting validated
        '''
        _, fork_head = self.generate_chain(self.init_head, 5)

        self.chain_ctrl.on_block_received(fork_head)

        # advance fork before it gets accepted
        _, ext_head = self.generate_chain(fork_head, 3)

        self.executor.process_all()

        self.assert_is_chain_head(fork_head)

        self.receive_and_process_blocks(ext_head)

        self.assert_is_chain_head(ext_head)

    def test_block_extends_in_validation(self):
        '''Tests a block getting extended while being validated
        '''
        # create candidate block
        candidate = self.block_tree_manager.generate_block(
            previous_block=self.init_head)

        self.assert_is_chain_head(self.init_head)

        # queue up the candidate block, but don't process
        self.chain_ctrl.on_block_received(candidate)

        # create a new block extending the candidate block
        extending_block = self.block_tree_manager.generate_block(
            previous_block=candidate)

        self.assert_is_chain_head(self.init_head)

        # queue and process the extending block,
        # which should be the new head
        self.receive_and_process_blocks(extending_block)
        self.assert_is_chain_head(extending_block)

    def test_multiple_extended_forks(self):
        '''A more involved example of competing forks

        Three forks of varying lengths a_0, b_0, and c_0
        are created extending the existing chain, with c_0
        being the longest initially. The chains are extended
        in the following sequence:

        1. Extend all forks by 2. The c fork should remain the head.
        2. Extend forks by lenths such that the b fork is the
           longest. It should be the new head.
        3. Extend all forks by 8. The b fork should remain the head.
        4. Create a new fork of the initial chain longer than
           any of the other forks. It should be the new head.
        '''

        # create forks of various lengths
        _, a_0 = self.generate_chain(self.init_head, 3)
        _, b_0 = self.generate_chain(self.init_head, 5)
        _, c_0 = self.generate_chain(self.init_head, 7)

        self.receive_and_process_blocks(a_0, b_0, c_0)
        self.assert_is_chain_head(c_0)

        # extend every fork by 2
        _, a_1 = self.generate_chain(a_0, 2)
        _, b_1 = self.generate_chain(b_0, 2)
        _, c_1 = self.generate_chain(c_0, 2)

        self.receive_and_process_blocks(a_1, b_1, c_1)
        self.assert_is_chain_head(c_1)

        # extend the forks by different lengths
        _, a_2 = self.generate_chain(a_1, 1)
        _, b_2 = self.generate_chain(b_1, 6)
        _, c_2 = self.generate_chain(c_1, 3)

        self.receive_and_process_blocks(a_2, b_2, c_2)
        self.assert_is_chain_head(b_2)

        # extend every fork by 2
        _, a_3 = self.generate_chain(a_2, 8)
        _, b_3 = self.generate_chain(b_2, 8)
        _, c_3 = self.generate_chain(c_2, 8)

        self.receive_and_process_blocks(a_3, b_3, c_3)
        self.assert_is_chain_head(b_3)

        # create a new longest chain
        _, wow = self.generate_chain(self.init_head, 30)
        self.receive_and_process_blocks(wow)
        self.assert_is_chain_head(wow)

    # next multi threaded
    # next add block publisher
    # next batch lists
    # integrate with LMDB
    # early vs late binding ( class member of consensus BlockPublisher)

    # helpers

    def assert_is_chain_head(self, block):
        chain_head_sig = self.chain_ctrl.chain_head.header_signature
        block_sig = block.header_signature

        self.assertEqual(
            chain_head_sig[:8],
            block_sig[:8],
            'Not chain head')

    def generate_chain(self, root_block, num_blocks, params=None):
        '''Returns (chain, chain_head).
        Usually only the head is needed,
        but occasionally the chain itself is used.
        '''
        if params is None:
            params = {'add_to_cache': True}

        chain = self.block_tree_manager.generate_chain(
            root_block, num_blocks, params)

        head = chain[-1]

        return chain, head

    def generate_block(self, *args, **kwargs):
        return self.block_tree_manager.generate_block(
            *args, **kwargs)

    def receive_and_process_blocks(self, *blocks):
        for block in blocks:
            self.chain_ctrl.on_block_received(block)
        self.executor.process_all()


class TestChainControllerGenesisPeer(unittest.TestCase):
    def setUp(self):
        self.block_tree_manager = BlockTreeManager(with_genesis=False)
        self.gossip = MockNetwork()
        self.executor = SynchronousExecutor()
        self.txn_executor = MockTransactionExecutor()
        self.block_sender = MockBlockSender()
        self.chain_id_manager = MockChainIdManager()
        self.chain_head_lock = RLock()
        self.permission_verifier = MockPermissionVerifier()

        def chain_updated(head, committed_batches=None,
                          uncommitted_batches=None):
            pass

        self.chain_ctrl = ChainController(
            block_cache=self.block_tree_manager.block_cache,
            state_view_factory=MockStateViewFactory(
                self.block_tree_manager.state_db),
            block_sender=self.block_sender,
            thread_pool=self.executor,
            transaction_executor=MockTransactionExecutor(),
            chain_head_lock=self.chain_head_lock,
            on_chain_updated=chain_updated,
            squash_handler=None,
            chain_id_manager=self.chain_id_manager,
            identity_signer=self.block_tree_manager.identity_signer,
            data_dir=None,
            config_dir=None,
            permission_verifier=self.permission_verifier,
            chain_observers=[],
            metrics_registry=None)

        self.assertIsNone(self.chain_ctrl.chain_head)

    def test_genesis_block_mismatch(self):
        '''Test mismatch block chain id will drop genesis block.
        Given a ChainController with an empty chain
        mismatches the block-chain-id stored on disk.
        '''
        self.chain_id_manager.save_block_chain_id('my_chain_id')
        some_other_genesis_block = \
            self.block_tree_manager.generate_genesis_block()
        self.chain_ctrl.on_block_received(some_other_genesis_block)

        self.assertIsNone(self.chain_ctrl.chain_head)

    def test_genesis_block_matches_block_chain_id(self):
        '''Test that a validator with no chain will accept a valid genesis
        block that matches the block-chain-id stored on disk.
        '''
        my_genesis_block = self.block_tree_manager.generate_genesis_block()
        chain_id = my_genesis_block.header_signature
        self.chain_id_manager.save_block_chain_id(chain_id)

        with patch.object(BlockValidator,
                          'validate_block',
                          return_value=True):
            self.chain_ctrl.on_block_received(my_genesis_block)

        self.assertIsNotNone(self.chain_ctrl.chain_head)
        chain_head_sig = self.chain_ctrl.chain_head.header_signature

        self.assertEqual(
            chain_head_sig[:8],
            chain_id[:8],
            'Chain id does not match')

        self.assertEqual(chain_id,
                         self.chain_id_manager.get_block_chain_id())

    def test_invalid_genesis_block_matches_block_chain_id(self):
        '''Test that a validator with no chain will drop an invalid genesis
        block that matches the block-chain-id stored on disk.
        '''
        my_genesis_block = self.block_tree_manager.generate_genesis_block()
        chain_id = my_genesis_block.header_signature
        self.chain_id_manager.save_block_chain_id(chain_id)

        with patch.object(BlockValidator,
                          'validate_block',
                          return_value=False):
            self.chain_ctrl.on_block_received(my_genesis_block)

        self.assertIsNone(self.chain_ctrl.chain_head)


class TestJournal(unittest.TestCase):
    def setUp(self):
        self.gossip = MockNetwork()
        self.txn_executor = MockTransactionExecutor()
        self.block_sender = MockBlockSender()
        self.batch_sender = MockBatchSender()
        self.permission_verifier = MockPermissionVerifier()

    def test_publish_block(self):
        """
        Test that the Journal will produce blocks and consume those blocks
        to extend the chain.
        :return:
        """
        # construction and wire the journal to the
        # gossip layer.

        btm = BlockTreeManager()
        block_publisher = None
        chain_controller = None
        try:
            block_publisher = BlockPublisher(
                transaction_executor=self.txn_executor,
                block_cache=btm.block_cache,
                state_view_factory=MockStateViewFactory(btm.state_db),
                settings_cache=SettingsCache(
                    SettingsViewFactory(
                        btm.state_view_factory),
                ),
                block_sender=self.block_sender,
                batch_sender=self.batch_sender,
                squash_handler=None,
                chain_head=btm.block_store.chain_head,
                identity_signer=btm.identity_signer,
                data_dir=None,
                config_dir=None,
                permission_verifier=self.permission_verifier,
                check_publish_block_frequency=0.1,
                batch_observers=[],
                batch_injector_factory=DefaultBatchInjectorFactory(
                    block_store=btm.block_store,
                    state_view_factory=MockStateViewFactory(btm.state_db),
                    signer=btm.identity_signer))

            chain_controller = ChainController(
                block_sender=self.block_sender,
                block_cache=btm.block_cache,
                state_view_factory=MockStateViewFactory(btm.state_db),
                transaction_executor=self.txn_executor,
                chain_head_lock=block_publisher.chain_head_lock,
                on_chain_updated=block_publisher.on_chain_updated,
                squash_handler=None,
                chain_id_manager=None,
                identity_signer=btm.identity_signer,
                data_dir=None,
                config_dir=None,
                permission_verifier=self.permission_verifier,
                chain_observers=[])

            self.gossip.on_batch_received = block_publisher.queue_batch
            self.gossip.on_block_received = chain_controller.queue_block

            block_publisher.start()
            chain_controller.start()

            # feed it a batch
            batch = Batch()
            block_publisher.queue_batch(batch)

            wait_until(lambda: self.block_sender.new_block is not None, 2)
            self.assertTrue(self.block_sender.new_block is not None)

            block = BlockWrapper(self.block_sender.new_block)
            chain_controller.queue_block(block)

            # wait for the chain_head to be updated.
            wait_until(lambda: btm.chain_head.identifier ==
                       block.identifier, 2)
            self.assertTrue(btm.chain_head.identifier == block.identifier)
        finally:
            if block_publisher is not None:
                block_publisher.stop()
            if chain_controller is not None:
                chain_controller.stop()


class TestTimedCache(unittest.TestCase):
    def test_cache(self):
        bc = TimedCache(keep_time=1, purge_frequency=0)

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

        bc = TimedCache(keep_time=1, purge_frequency=0)

        bc["test"] = "value"
        bc["test2"] = "value2"
        self.assertEqual(len(bc), 2)

        # test that expired item i
        bc.cache["test"].timestamp = bc.cache["test"].timestamp - 2
        bc["test2"] = "value2"  # set value to activate purge
        self.assertEqual(len(bc), 1)
        self.assertFalse("test" in bc)
        self.assertTrue("test2" in bc)

    def test_access_update(self):

        bc = TimedCache(keep_time=1, purge_frequency=0)

        bc["test"] = "value"
        bc["test2"] = "value2"
        self.assertEqual(len(bc), 2)

        bc["test"] = "value"
        bc.cache["test"].timestamp = bc.cache["test"].timestamp - 2
        bc["test"]  # access to update timestamp
        bc["test2"] = "value2"  # set value to activate purge
        self.assertEqual(len(bc), 2)
        self.assertTrue("test" in bc)
        self.assertTrue("test2" in bc)


class TestChainCommitState(unittest.TestCase):
    def setUp(self):
        self.commit_state = None
        self.block_tree_manager = BlockTreeManager()

    def test_fall_thru(self):
        """ Test that the requests correctly fall thru to the
        underlying BlockStore.
        """
        blocks = self.generate_chain(1)
        commit_state = self.create_chain_commit_state(blocks)
        self.commit_state = commit_state

        self.assert_block_present(blocks[0])

        self.assert_missing()

    def test_uncommitted_blocks(self):
        """ Test that the ChainCommitState can simulate blocks being
        uncommited from the BlockStore
        """
        blocks = self.generate_chain(2)
        block, uncommitted_block = blocks
        commit_state = self.create_chain_commit_state(
            blocks=blocks,
            uncommitted_blocks=[uncommitted_block],
        )
        self.commit_state = commit_state

        # the first block is still present
        self.assert_block_present(block)
        # batch from the uncommited block should not be present
        self.assert_block_not_present(uncommitted_block)

        self.assert_missing()

    def test_add_remove_batch(self):
        """ Test that we can incrementatlly build the commit state and
        roll it back
        """
        blocks = self.generate_chain(2)
        block, uncommitted_block = blocks
        commit_state = self.create_chain_commit_state(
            blocks=blocks,
            uncommitted_blocks=[uncommitted_block],
        )
        self.commit_state = commit_state

        # the first block is still present
        self.assert_block_present(block)
        # batch from the uncommited block should not be present
        self.assert_block_not_present(uncommitted_block)

        batch = uncommitted_block.batches[0]
        commit_state.add_batch(batch)

        # the batch should appear present
        self.assert_batch_present(batch)

        # check that we can remove the batch again.
        commit_state.remove_batch(batch)
        self.assert_batch_not_present(batch)

        # Do an incremental add of the batch
        for txn in batch.transactions:
            commit_state.add_txn(txn.header_signature)
            self.assert_txn_present(txn)
        self.assertFalse(commit_state.has_batch(
            batch.header_signature))

        commit_state.add_batch(batch, add_transactions=False)
        self.assert_batch_present(batch)

        # check that we can remove the batch again.
        commit_state.remove_batch(batch)
        self.assert_batch_not_present(batch)

    def generate_chain(self, block_count):
        return self.block_tree_manager.generate_chain(
            None, [{} for _ in range(block_count)])

    def create_chain_commit_state(self, blocks, uncommitted_blocks=None,
                                  chain_head=None):
        block_store = BlockStore(DictDatabase(
            indexes=BlockStore.create_index_configuration()))
        block_store.update_chain(blocks)
        if chain_head is None:
            chain_head = block_store.chain_head.identifier
        if uncommitted_blocks is None:
            uncommitted_blocks = []
        return ChainCommitState(block_store, uncommitted_blocks)

    def assert_txn_present(self, txn):
        self.assertTrue(self.commit_state.has_transaction(
            txn.header_signature))

    def assert_batch_present(self, batch):
        self.assertTrue(self.commit_state.has_batch(
            batch.header_signature))
        for txn in batch.transactions:
            self.assert_txn_present(txn)

    def assert_block_present(self, block):
        for batch in block.batches:
            self.assert_batch_present(batch)

    def assert_txn_not_present(self, txn):
        self.assertFalse(self.commit_state.has_transaction(
            txn.header_signature))

    def assert_batch_not_present(self, batch):
        self.assertFalse(self.commit_state.has_batch(
            batch.header_signature))
        for txn in batch.transactions:
            self.assert_txn_not_present(txn)

    def assert_block_not_present(self, block):
        for batch in block.batches:
            self.assert_batch_not_present(batch)

    def assert_missing(self):
        """check missing keys behave as expected.
        """
        self.assertFalse(self.commit_state.has_batch("missing"))
        self.assertFalse(self.commit_state.has_transaction("missing"))


class TestBlockEventExtractor(unittest.TestCase):
    def test_block_event_extractor(self):
        """Test that a sawtooth/block-commit event is generated correctly."""
        block_header = BlockHeader(
            block_num=85,
            state_root_hash="0987654321fedcba",
            previous_block_id="0000000000000000")
        block = BlockWrapper(Block(
            header_signature="abcdef1234567890",
            header=block_header.SerializeToString()))
        extractor = BlockEventExtractor(block)
        events = extractor.extract([EventSubscription(
            event_type="sawtooth/block-commit")])
        self.assertEqual(events, [
            Event(
                event_type="sawtooth/block-commit",
                attributes=[
                    Event.Attribute(key="block_id", value="abcdef1234567890"),
                    Event.Attribute(key="block_num", value="85"),
                    Event.Attribute(
                        key="state_root_hash", value="0987654321fedcba"),
                    Event.Attribute(
                        key="previous_block_id",
                        value="0000000000000000")])])


class TestReceiptEventExtractor(unittest.TestCase):
    def test_tf_events(self):
        """Test that tf events are generated correctly."""
        gen_data = [
            ["test1", "test2"],
            ["test3"],
            ["test4", "test5", "test6"],
        ]
        event_sets = [
            [
                Event(event_type=event_type)
                for event_type in events
            ] for events in gen_data
        ]
        receipts = [
            TransactionReceipt(events=events)
            for events in event_sets
        ]
        extractor = ReceiptEventExtractor(receipts)

        events = extractor.extract([])
        self.assertEqual([], events)

        events = extractor.extract([
            EventSubscription(event_type="test1"),
            EventSubscription(event_type="test5"),
        ])
        self.assertEqual(events, [event_sets[0][0], event_sets[2][1]])

    def test_state_delta_events(self):
        """Test that sawtooth/state-delta events are generated correctly."""
        gen_data = [
            [("a", b"a", StateChange.SET), ("b", b"b", StateChange.DELETE)],
            [("a", b"a", StateChange.DELETE), ("d", b"d", StateChange.SET)],
            [("e", b"e", StateChange.SET)],
        ]
        change_sets = [
            [
                StateChange(address=address, value=value, type=change_type)
                for address, value, change_type in state_changes
            ] for state_changes in gen_data
        ]
        receipts = [
            TransactionReceipt(state_changes=state_changes)
            for state_changes in change_sets
        ]
        extractor = ReceiptEventExtractor(receipts)

        factory = EventFilterFactory()
        events = extractor.extract([
            EventSubscription(
                event_type="sawtooth/state-delta",
                filters=[factory.create("address", "a")]),
            EventSubscription(
                event_type="sawtooth/state-delta",
                filters=[factory.create(
                    "address", "[ce]", EventFilter.REGEX_ANY)],
            )
        ])
        self.assertEqual(events, [Event(
            event_type="sawtooth/state-delta",
            attributes=[
                Event.Attribute(key="address", value=address)
                for address in ["e", "d", "a", "b"]
            ],
            data=StateChangeList(state_changes=[
                change_sets[2][0], change_sets[1][1],
                change_sets[1][0], change_sets[0][1],
            ]).SerializeToString(),
        )])

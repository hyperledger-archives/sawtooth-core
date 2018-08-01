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
# pylint: disable=arguments-differ

import logging
import os
import shutil
import tempfile
from time import sleep
import unittest
from unittest.mock import patch

from sawtooth_validator.consensus.handlers import BlockInProgress
from sawtooth_validator.consensus.handlers import BlockEmpty
from sawtooth_validator.consensus.handlers import BlockNotInitialized

from sawtooth_validator.database.dict_database import DictDatabase
from sawtooth_validator.database.native_lmdb import NativeLmdbDatabase

from sawtooth_validator.journal.block_cache import BlockCache
from sawtooth_validator.journal.block_wrapper import BlockStatus
from sawtooth_validator.journal.block_wrapper import BlockWrapper
from sawtooth_validator.journal.block_wrapper import NULL_BLOCK_IDENTIFIER

from sawtooth_validator.journal.block_store import BlockStore
from sawtooth_validator.journal.block_validator import BlockValidator
from sawtooth_validator.journal.block_validator import BlockValidationFailure
from sawtooth_validator.journal.chain import ChainController
from sawtooth_validator.journal.chain_id_manager import ChainIdManager
from sawtooth_validator.journal.chain_commit_state import ChainCommitState
from sawtooth_validator.journal.chain_commit_state import DuplicateTransaction
from sawtooth_validator.journal.chain_commit_state import DuplicateBatch
from sawtooth_validator.journal.chain_commit_state import MissingDependency
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

from sawtooth_validator.protobuf.transaction_pb2 import Transaction
from sawtooth_validator.protobuf.transaction_pb2 import TransactionHeader
from sawtooth_validator.protobuf.batch_pb2 import Batch
from sawtooth_validator.protobuf.block_pb2 import Block
from sawtooth_validator.protobuf.block_pb2 import BlockHeader
from sawtooth_validator.protobuf.transaction_receipt_pb2 import \
    TransactionReceipt
from sawtooth_validator.protobuf.transaction_receipt_pb2 import StateChange
from sawtooth_validator.protobuf.transaction_receipt_pb2 import StateChangeList
from sawtooth_validator.protobuf.events_pb2 import Event
from sawtooth_validator.protobuf.events_pb2 import EventFilter

from sawtooth_validator.state.merkle import MerkleDatabase
from sawtooth_validator.state.settings_view import SettingsViewFactory
from sawtooth_validator.state.settings_cache import SettingsCache

from test_journal.block_tree_manager import BlockTreeManager

from test_journal.mock import MockBlockSender
from test_journal.mock import MockBlockValidator
from test_journal.mock import MockBatchSender
from test_journal.mock import MockConsensusNotifier
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


@unittest.skip(
    'These tests no longer take into account underlying FFI threads')
class TestBlockPublisher(unittest.TestCase):
    '''
    The block publisher has five main functions, and in these tests
    those functions are given the following wrappers for convenience:
        * on_batch_received -> receive_batches
        * on_chain_updated -> update_chain_head
        * initialize_block -> initialize_block
        * summarize_block -> summarize_block
        * finalize_block -> finalize_block
    Additionally, the publish_block is provided to call both initialize_block
    and finalize_block.

    After finalizing a block, finalize_block sends its block
    to the mock block sender, and that block is named result_block. This block
    is what is checked by the test assertions.

    The basic pattern for the publisher tests (with variations) is:
        0) make a list of batches (usually in setUp);
        1) receive the batches;
        2) initialize a block;
        3) finalize a block;
        4) verify the block (checking that it contains the correct batches,
           or checking that it doesn't exist, etc.).
    '''

    @unittest.mock.patch('test_journal.mock.MockBatchInjectorFactory')
    def setUp(self, mock_batch_injector_factory):

        mock_batch_injector_factory.create_injectors.return_value = []

        self.block_tree_manager = BlockTreeManager()
        self.block_sender = MockBlockSender()
        self.batch_sender = MockBatchSender()
        self.state_view_factory = MockStateViewFactory({})
        self.permission_verifier = MockPermissionVerifier()

        self.publisher = BlockPublisher(
            transaction_executor=MockTransactionExecutor(),
            get_block=lambda block: self.block_tree_manager.block_cache[block],
            transaction_committed=(
                self.block_tree_manager.block_store.has_transaction
            ),
            batch_committed=self.block_tree_manager.block_store.has_batch,
            state_view_factory=self.state_view_factory,
            settings_cache=SettingsCache(
                SettingsViewFactory(
                    self.block_tree_manager.state_view_factory),
            ),
            block_sender=self.block_sender,
            batch_sender=self.batch_sender,
            chain_head=self.block_tree_manager.chain_head,
            identity_signer=self.block_tree_manager.identity_signer,
            data_dir=None,
            config_dir=None,
            batch_observers=[],
            permission_verifier=self.permission_verifier,
            batch_injector_factory=mock_batch_injector_factory)

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

    def test_receive_after_initialize(self):
        '''
        Receive batches after initialization
        '''
        self.initialize_block()
        self.receive_batches()
        self.finalize_block()
        self.verify_block()

    def test_summarize_block(self):
        '''
        Initialize a block and summarize it
        '''
        self.receive_batches()
        self.initialize_block()
        self.assertIsNotNone(self.summarize_block(),
                             'Expected block summary')

    def test_reject_double_initialization(self):
        '''
        Test that you can't initialize a candidate block twice
        '''
        self.initialize_block()
        with self.assertRaises(
                BlockInProgress,
                msg='Second initialization should have rejected'):
            self.initialize_block()

    def test_reject_finalize_without_initialize(self):
        '''
        Test that no block is published if the block hasn't been initialized
        '''
        self.receive_batches()
        with self.assertRaises(
                BlockNotInitialized,
                msg='Block should not be finalized'):
            self.finalize_block()

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
        self.update_chain_head(
            head=self.init_chain_head,
            uncommitted=self.batches)

        self.receive_batches()

        self.publish_block()

        self.verify_block()

    def test_committed_batches(self):
        '''
        Test that batches committed upon updating the chain head
        are not included in the next block.
        '''
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
        with self.assertRaises(
                BlockEmpty, msg='Block should not be published'):
            self.publish_block()

        self.assert_no_block_published()

        # receive batches, then try again (succeeding)
        self.receive_batches()

        self.finalize_block()

        self.verify_block()

    def test_missing_dependencies(self):
        '''
        Test that no block is published with missing dependencies
        '''
        self.batches = self.make_batches(
            missing_deps=True)

        self.receive_batches()

        # Block should be empty, since batches with missing deps aren't added
        with self.assertRaises(BlockEmpty, msg='Block should be empty'):
            self.publish_block()

        self.assert_no_block_published()

    @unittest.mock.patch('test_journal.mock.MockBatchInjectorFactory')
    def test_batches_rejected_by_scheduler(self, mock_batch_injector_factory):
        '''
        Test that no block is published with
        batches rejected by the scheduler
        '''

        mock_batch_injector_factory.create_injectors.return_value = []
        self.publisher = BlockPublisher(
            transaction_executor=MockTransactionExecutor(
                batch_execution_result=False),
            get_block=lambda block: self.block_tree_manager.block_cache[block],
            transaction_committed=(
                self.block_tree_manager.block_store.has_transaction
            ),
            batch_committed=self.block_tree_manager.block_store.has_batch,
            state_view_factory=self.state_view_factory,
            settings_cache=SettingsCache(
                SettingsViewFactory(
                    self.block_tree_manager.state_view_factory),
            ),
            block_sender=self.block_sender,
            batch_sender=self.batch_sender,
            chain_head=self.block_tree_manager.chain_head,
            identity_signer=self.block_tree_manager.identity_signer,
            data_dir=None,
            config_dir=None,
            batch_observers=[],
            permission_verifier=self.permission_verifier,
            batch_injector_factory=mock_batch_injector_factory)

        self.receive_batches()

        # Block should be empty since all batches are rejected
        with self.assertRaises(BlockEmpty, msg='Block should be empty'):
            self.publish_block()

        self.assert_no_block_published()

    @unittest.mock.patch('test_journal.mock.MockBatchInjectorFactory')
    def test_max_block_size(self, mock_batch_injector_factory):
        '''
        Test block publisher obeys the block size limits
        '''

        mock_batch_injector_factory.create_injectors.return_value = []

        # Create a publisher that has a state view
        # with a batch limit
        addr, value = CreateSetting(
            'sawtooth.publisher.max_batches_per_block', 1)
        self.state_view_factory = MockStateViewFactory(
            {addr: value})

        self.publisher = BlockPublisher(
            transaction_executor=MockTransactionExecutor(),
            get_block=lambda block: self.block_tree_manager.block_cache[block],
            transaction_committed=(
                self.block_tree_manager.block_store.has_transaction
            ),
            batch_committed=self.block_tree_manager.block_store.has_batch,
            state_view_factory=self.state_view_factory,
            settings_cache=SettingsCache(
                SettingsViewFactory(
                    self.state_view_factory),
            ),
            block_sender=self.block_sender,
            batch_sender=self.batch_sender,
            chain_head=self.block_tree_manager.chain_head,
            identity_signer=self.block_tree_manager.identity_signer,
            data_dir=None,
            config_dir=None,
            batch_observers=[],
            permission_verifier=self.permission_verifier,
            batch_injector_factory=mock_batch_injector_factory)

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
        with self.assertRaises(BlockEmpty, msg='Block should be empty'):
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
            get_block=lambda block: self.block_tree_manager.block_cache[block],
            transaction_committed=(
                self.block_tree_manager.block_store.has_transaction
            ),
            batch_committed=self.block_tree_manager.block_store.has_batch,
            state_view_factory=self.state_view_factory,
            settings_cache=SettingsCache(
                SettingsViewFactory(
                    self.block_tree_manager.state_view_factory),
            ),
            block_sender=self.block_sender,
            batch_sender=self.batch_sender,
            chain_head=self.block_tree_manager.chain_head,
            identity_signer=self.block_tree_manager.identity_signer,
            data_dir=None,
            config_dir=None,
            permission_verifier=self.permission_verifier,
            batch_observers=[],
            batch_injector_factory=MockBatchInjectorFactory(injected_batch))

        self.receive_batches()

        self.publish_block()

        self.assert_batch_in_block(injected_batch)

    @unittest.mock.patch('test_journal.mock.MockBatchInjectorFactory')
    def test_validation_rules_reject_batches(self,
                                             mock_batch_injector_factory):
        """Test that a batch is not added to the block if it will violate the
        block validation rules.

        It does the following:

        - Sets the block_validation_rules to limit the number of 'test'
          transactions to 1
        - creates two batches, limited to 1 transaction each, and receives
          them
        - verifies that only the first batch was committed to the block
        """
        addr, value = CreateSetting(
            'sawtooth.validator.block_validation_rules', 'NofX:1,test')
        self.state_view_factory = MockStateViewFactory(
            {addr: value})

        mock_batch_injector_factory.create_injectors.return_value = []

        batch1 = self.make_batch(txn_count=1)
        batch2 = self.make_batch(txn_count=1)

        self.publisher = BlockPublisher(
            transaction_executor=MockTransactionExecutor(),
            get_block=lambda block: self.block_tree_manager.block_cache[block],
            transaction_committed=(
                self.block_tree_manager.block_store.has_transaction
            ),
            batch_committed=self.block_tree_manager.block_store.has_batch,
            state_view_factory=self.state_view_factory,
            settings_cache=SettingsCache(
                SettingsViewFactory(
                    self.state_view_factory),
            ),
            block_sender=self.block_sender,
            batch_sender=self.batch_sender,
            chain_head=self.block_tree_manager.chain_head,
            identity_signer=self.block_tree_manager.identity_signer,
            data_dir=None,
            config_dir=None,
            batch_observers=[],
            permission_verifier=self.permission_verifier,
            batch_injector_factory=mock_batch_injector_factory)

        self.receive_batches(batches=[batch1, batch2])

        self.publish_block()

        self.assert_block_batch_count(1)
        self.assert_batch_in_block(batch1)

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

    def initialize_block(self):
        self.publisher.initialize_block(self.block_tree_manager.chain_head)

    def summarize_block(self):
        return self.publisher.summarize_block()

    def finalize_block(self):
        self.publisher.finalize_block("")
        self.result_block = self.block_sender.new_block
        self.block_sender.new_block = None

    def publish_block(self):
        self.initialize_block()
        self.finalize_block()

    def update_chain_head(self, head, committed=None, uncommitted=None):
        if head:
            self.block_tree_manager.block_store.update_chain([head])
        self.publisher.on_chain_updated(
            chain_head=head,
            committed_batches=committed,
            uncommitted_batches=uncommitted)

    # batches
    def make_batch(self, missing_deps=False, txn_count=2):
        return self.block_tree_manager.generate_batch(
            txn_count=txn_count,
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


@unittest.skip(
    'These tests no longer reflect the behaviour of block validator')
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

        self.assert_unknown_block(head)
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
            self.root, 5, {'add_to_store': True}, False)

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
            self.root, 5, {'add_to_store': True}, False)

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
            self.root, 5, {'add_to_store': True}, False)

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
            self.root, 5, {'add_to_store': True}, False)

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
            self.root, 5, {'add_to_store': True}, False)

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
            self.root, 5, {'add_to_store': True}, False)

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
            self.root, 5, {'add_to_store': True}, False)

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

    def assert_unknown_block(self, block):
        self.assertEqual(
            block.status, BlockStatus.Unknown,
            "Block should be unknown")

    def assert_new_block_committed(self):
        self.assert_handler_has_result()
        self.assertTrue(
            self.block_validation_handler.commit_new_block,
            "New block not committed, should be")

    def assert_new_block_not_committed(self):
        self.assert_handler_has_result()
        self.assertFalse(
            self.block_validation_handler.commit_new_block,
            "New block committed, shouldn't be")

    def assert_handler_has_result(self):
        msg = "Validation handler doesn't have result"
        self.assertTrue(self.block_validation_handler.has_result(), msg)

    # block validation

    def validate_block(self, block):
        validator = self.create_block_validator()
        validator._load_consensus = lambda block: mock_consensus
        validator.process_block_verification(
            block,
            self.block_validation_handler.on_block_validated)

    def create_block_validator(self):
        return BlockValidator(
            state_view_factory=self.state_view_factory,
            block_cache=self.block_tree_manager.block_cache,
            transaction_executor=MockTransactionExecutor(
                batch_execution_result=None),
            identity_signer=self.block_tree_manager.identity_signer,
            data_dir=None,
            config_dir=None,
            permission_verifier=self.permission_verifier)

    class BlockValidationHandler:
        def __init__(self):
            self.validated_block = None

        def on_block_validated(self, block):
            self.validated_block = block

        def has_result(self):
            return self.validated_block is not None

    # block tree manager interface

    def generate_chain_with_head(self, root_block, num_blocks, params=None,
                                 exclude_head=True):
        chain = self.block_tree_manager.generate_chain(
            root_block, num_blocks, params, exclude_head)

        head = chain[-1]

        return chain, head


class TestChainController(unittest.TestCase):
    @unittest.mock.patch('test_journal.mock.MockBatchInjectorFactory')
    def setUp(self, mock_batch_injector_factory):
        mock_batch_injector_factory.create_injectors.return_value = []

        self.dir = tempfile.mkdtemp()

        self.state_database = NativeLmdbDatabase(
            os.path.join(self.dir, 'merkle.lmdb'),
            indexes=MerkleDatabase.create_index_configuration(),
            _size=120 * 1024 * 1024)

        self.block_tree_manager = BlockTreeManager()
        self.permission_verifier = MockPermissionVerifier()
        self.state_view_factory = MockStateViewFactory(
            self.block_tree_manager.state_db)
        self.transaction_executor = MockTransactionExecutor(
            batch_execution_result=None)
        self.executor = SynchronousExecutor()
        self.consensus_notifier = MockConsensusNotifier()

        self.block_validator = MockBlockValidator(
            state_view_factory=self.state_view_factory,
            block_cache=self.block_tree_manager.block_cache,
            transaction_executor=self.transaction_executor,
            identity_signer=self.block_tree_manager.identity_signer,
            data_dir=self.dir,
            config_dir=None,
            permission_verifier=self.permission_verifier,
            thread_pool=self.executor)

        self.publisher = BlockPublisher(
            transaction_executor=MockTransactionExecutor(),
            get_block=lambda block: self.block_tree_manager.block_cache[block],
            transaction_committed=(
                self.block_tree_manager.block_store.has_transaction
            ),
            batch_committed=self.block_tree_manager.block_store.has_batch,
            state_view_factory=self.state_view_factory,
            settings_cache=SettingsCache(
                SettingsViewFactory(
                    self.block_tree_manager.state_view_factory),
            ),
            block_sender=MockBlockSender(),
            batch_sender=MockBatchSender(),
            chain_head=self.block_tree_manager.chain_head,
            identity_signer=self.block_tree_manager.identity_signer,
            data_dir=None,
            config_dir=None,
            batch_observers=[],
            permission_verifier=self.permission_verifier,
            batch_injector_factory=mock_batch_injector_factory)

        self.chain_ctrl = ChainController(
            self.block_tree_manager.block_store,
            self.block_tree_manager.block_cache,
            self.block_validator,
            self.state_database,
            self.publisher.chain_head_lock,
            self.consensus_notifier,
            data_dir=self.dir)

        self.chain_ctrl.start()

        self.init_head = self.chain_ctrl.chain_head

    def tearDown(self):
        shutil.rmtree(self.dir)

    def test_chain_head(self):
        self.assert_is_chain_head(self.init_head)

    def test_receive_block(self):
        new_block = self.generate_block(self.init_head)
        self.receive_block(new_block)
        self.assert_block_received(new_block)

    def test_commit_block(self):
        new_block = self.generate_block(self.init_head)
        self.commit_block(new_block)
        self.assert_block_committed(new_block)
        self.assert_is_chain_head(new_block)

    def test_has_block(self):
        # Block in block cache
        new_block = self.generate_block(self.init_head)
        self.commit_block(new_block)
        self.assert_block_committed(new_block)
        self.assert_has_block(new_block)

        # Block in block validator
        self.block_validator = MockBlockValidator(
            state_view_factory=self.state_view_factory,
            block_cache=self.block_tree_manager.block_cache,
            transaction_executor=self.transaction_executor,
            identity_signer=self.block_tree_manager.identity_signer,
            data_dir=self.dir,
            config_dir=None,
            permission_verifier=self.permission_verifier,
            thread_pool=self.executor,
            has_block=True)
        self.chain_ctrl = ChainController(
            self.block_tree_manager.block_store,
            self.block_tree_manager.block_cache,
            self.block_validator,
            self.state_database,
            self.publisher.chain_head_lock,
            self.consensus_notifier,
            data_dir=self.dir)

        self.chain_ctrl.start()

        new_block = self.generate_block(self.chain_ctrl.chain_head)
        self.assert_has_block(new_block)

    def test_on_block_validated(self):
        chain, head = self.generate_chain(self.init_head, 2)
        chain[0].status = BlockStatus.Valid
        self.receive_block(chain[0])
        self.receive_block(head)
        self.executor.process_all()
        self.assert_new_block_notified(head)

    @unittest.skip('Currently not implemented in the chain controller')
    def test_ignore_block(self):
        pass

    def test_fail_block(self):
        new_block = self.generate_block(self.init_head)
        self.chain_ctrl.fail_block(new_block)
        self.assert_block_invalid(new_block)

    # helpers

    def assert_is_chain_head(self, block):
        chain_head_sig = self.chain_ctrl.chain_head.header_signature
        block_sig = block.header_signature

        self.assertEqual(
            chain_head_sig,
            block_sig,
            'Not chain head')

    def assert_block_received(self, block):
        while not self.block_validator.submitted_blocks:
            sleep(1)
        submitted_blocks = [b.header_signature
                            for b in self.block_validator.submitted_blocks]

        self.assertIn(
            block.header_signature,
            submitted_blocks,
            'Block not received')

    def assert_block_committed(self, block):
        while not self.consensus_notifier.committed_block:
            sleep(1)
        commited_block = self.consensus_notifier.committed_block
        block_id = block.header_signature

        self.assertEqual(
            commited_block,
            block_id,
            'Block not committed')

    def assert_has_block(self, block):
        self.assertTrue(
            self.chain_ctrl.has_block(block.header_signature),
            'Block not found')

    def assert_block_invalid(self, block):
        block = self.block_tree_manager.block_cache.get(block.header_signature)
        self.assertEqual(
            block.status, BlockStatus.Invalid, 'Block not invalid')

    def assert_new_block_notified(self, block):
        while not self.consensus_notifier.new_block:
            sleep(1)
        new_block_id = self.consensus_notifier.new_block.header_signature
        block_id = block.header_signature

        self.assertEqual(
            new_block_id,
            block_id,
            'New block not notified')

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

    def receive_block(self, block):
        self.chain_ctrl.on_block_received(block)

    def commit_block(self, block):
        self.chain_ctrl.commit_block(block)


@unittest.skip(
    'These tests no longer take into account underlying FFI threads')
class TestChainControllerGenesisPeer(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.block_tree_manager = BlockTreeManager(with_genesis=False)
        self.gossip = MockNetwork()
        self.txn_executor = MockTransactionExecutor()
        self.chain_id_manager = ChainIdManager(self.dir)
        self.permission_verifier = MockPermissionVerifier()
        self.state_view_factory = MockStateViewFactory(
            self.block_tree_manager.state_db)
        self.transaction_executor = MockTransactionExecutor(
            batch_execution_result=None)
        self.executor = SynchronousExecutor()

        self.state_database = NativeLmdbDatabase(
            os.path.join(self.dir, 'merkle.lmdb'),
            indexes=MerkleDatabase.create_index_configuration(),
            _size=120 * 1024 * 1024)
        self.block_sender = MockBlockSender()
        self.batch_sender = MockBatchSender()
        self.consensus_notifier = MockConsensusNotifier()

        self.publisher = BlockPublisher(
            transaction_executor=self.txn_executor,
            get_block=lambda block: self.block_tree_manager.block_cache[block],
            transaction_committed=(
                self.block_tree_manager.block_store.has_transaction
            ),
            batch_committed=self.block_tree_manager.block_store.has_batch,
            state_view_factory=MockStateViewFactory(
                self.block_tree_manager.state_db),
            settings_cache=SettingsCache(
                SettingsViewFactory(
                    self.block_tree_manager.state_view_factory),
            ),
            block_sender=self.block_sender,
            batch_sender=self.batch_sender,
            chain_head=self.block_tree_manager.block_store.chain_head,
            identity_signer=self.block_tree_manager.identity_signer,
            data_dir=None,
            config_dir=None,
            permission_verifier=self.permission_verifier,
            batch_observers=[],
            batch_injector_factory=DefaultBatchInjectorFactory(
                state_view_factory=MockStateViewFactory(
                    self.block_tree_manager.state_db),
                signer=self.block_tree_manager.identity_signer))

        self.block_validator = None
        self.chain_ctrl = None

    def setup_chain_controller(self):

        self.block_validator = BlockValidator(
            state_view_factory=self.state_view_factory,
            block_cache=self.block_tree_manager.block_cache,
            transaction_executor=self.transaction_executor,
            identity_signer=self.block_tree_manager.identity_signer,
            data_dir=self.dir,
            config_dir=None,
            permission_verifier=self.permission_verifier,
            thread_pool=self.executor)

        self.chain_ctrl = ChainController(
            self.block_tree_manager.block_store,
            self.block_tree_manager.block_cache,
            self.block_validator,
            self.state_database,
            self.publisher.chain_head_lock,
            consensus_notifier=self.consensus_notifier,
            data_dir=self.dir,
            observers=[])

        self.assertIsNone(self.chain_ctrl.chain_head)

    def tearDown(self):
        shutil.rmtree(self.dir)

    def test_genesis_block_mismatch(self):
        '''Test mismatch block chain id will drop genesis block.
        Given a ChainController with an empty chain
        mismatches the block-chain-id stored on disk.
        '''
        self.setup_chain_controller()
        self.chain_id_manager.save_block_chain_id('my_chain_id')
        some_other_genesis_block = \
            self.block_tree_manager.generate_genesis_block()
        self.chain_ctrl.on_block_received(some_other_genesis_block)

        self.assertIsNone(self.chain_ctrl.chain_head)

    def test_genesis_block_matches_block_chain_id(self):
        '''Test that a validator with no chain will accept a valid genesis
        block that matches the block-chain-id stored on disk.
        '''
        with patch.object(BlockValidator,
                          'validate_block',
                          return_value=True):
            self.setup_chain_controller()

        my_genesis_block = self.block_tree_manager.generate_genesis_block()
        chain_id = my_genesis_block.header_signature
        self.chain_id_manager.save_block_chain_id(chain_id)

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
        self.setup_chain_controller()
        my_genesis_block = self.block_tree_manager.generate_genesis_block()
        chain_id = my_genesis_block.header_signature
        self.chain_id_manager.save_block_chain_id(chain_id)

        with patch.object(BlockValidator,
                          'validate_block',
                          side_effect=BlockValidationFailure):
            self.chain_ctrl.on_block_received(my_genesis_block)

        self.assertIsNone(self.chain_ctrl.chain_head)


@unittest.skip(
    'These tests no longer take into account underlying FFI threads')
class TestJournal(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.gossip = MockNetwork()
        self.txn_executor = MockTransactionExecutor()
        self.block_sender = MockBlockSender()
        self.batch_sender = MockBatchSender()
        self.permission_verifier = MockPermissionVerifier()

    def tearDown(self):
        shutil.rmtree(self.dir)

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
        block_validator = None
        chain_controller = None
        try:
            block_publisher = BlockPublisher(
                transaction_executor=self.txn_executor,
                get_block=lambda block: btm.block_cache[block],
                transaction_committed=btm.block_store.has_transaction,
                batch_committed=btm.block_store.has_batch,
                state_view_factory=MockStateViewFactory(btm.state_db),
                settings_cache=SettingsCache(
                    SettingsViewFactory(
                        btm.state_view_factory),
                ),
                block_sender=self.block_sender,
                batch_sender=self.batch_sender,
                chain_head=btm.block_store.chain_head,
                identity_signer=btm.identity_signer,
                data_dir=None,
                config_dir=None,
                permission_verifier=self.permission_verifier,
                batch_observers=[],
                batch_injector_factory=DefaultBatchInjectorFactory(
                    state_view_factory=MockStateViewFactory(btm.state_db),
                    signer=btm.identity_signer))

            block_validator = BlockValidator(
                state_view_factory=MockStateViewFactory(btm.state_db),
                block_cache=btm.block_cache,
                transaction_executor=self.txn_executor,
                identity_signer=btm.identity_signer,
                data_dir=None,
                config_dir=None,
                permission_verifier=self.permission_verifier)

            state_database = NativeLmdbDatabase(
                os.path.join(self.dir, 'merkle.lmdb'),
                indexes=MerkleDatabase.create_index_configuration(),
                _size=120 * 1024 * 1024)

            chain_controller = ChainController(
                btm.block_store,
                btm.block_cache,
                block_validator,
                state_database,
                block_publisher.chain_head_lock,
                consensus_notifier=MockConsensusNotifier(),
                data_dir=None,
                observers=[])

            self.gossip.on_batch_received = block_publisher.batch_sender().send
            self.gossip.on_block_received = chain_controller.queue_block

            block_publisher.start()
            chain_controller.start()

            # feed it a batch
            batch = Batch()
            block_publisher.batch_sender().send(batch)

            wait_until(lambda: self.block_sender.new_block is not None, 2)
            self.assertTrue(self.block_sender.new_block is not None)

            block = BlockWrapper.wrap(self.block_sender.new_block)
            chain_controller.queue_block(block)

            # wait for the chain_head to be updated.
            wait_until(
                lambda: btm.chain_head.identifier == block.identifier, 2)
            self.assertTrue(btm.chain_head.identifier == block.identifier)
        finally:
            if block_publisher is not None:
                block_publisher.stop()
            if chain_controller is not None:
                chain_controller.stop()
            if block_validator is not None:
                block_validator.stop()


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
    """Test for:
    - No duplicates found for batches
    - No duplicates found for transactions
    - Duplicate batch found in current chain
    - Duplicate batch found in fork
    - Duplicate transaction found in current chain
    - Duplicate transaction found in fork
    - Missing dependencies caught
    - Dependencies found for transactions in current chain
    - Dependencies found for transactions in fork
    """

    def gen_block(self, block_id, prev_id, num, batches):
        return BlockWrapper(
            Block(
                header_signature=block_id,
                batches=batches,
                header=BlockHeader(
                    block_num=num,
                    previous_block_id=prev_id).SerializeToString()))

    def gen_batch(self, batch_id, transactions):
        return Batch(header_signature=batch_id, transactions=transactions)

    def gen_txn(self, txn_id, deps=None):
        return Transaction(
            header_signature=txn_id,
            header=TransactionHeader(dependencies=deps).SerializeToString())

    # Batches
    def test_no_duplicate_batch_found(self):
        """Verify that DuplicateBatch is not raised for a completely new
        batch.
        """
        _, _, committed_blocks, uncommitted_blocks =\
            self.create_new_chain()

        commit_state = self.create_chain_commit_state(
            committed_blocks, uncommitted_blocks, 'B6')

        commit_state.check_for_duplicate_batches([self.gen_batch('b10', [])])

    def test_duplicate_batch_in_both_chains(self):
        """Verify that DuplicateBatch is raised for a batch in both the current
        chain and the fork.
        """
        _, batches, committed_blocks, uncommitted_blocks =\
            self.create_new_chain()

        commit_state = self.create_chain_commit_state(
            committed_blocks, uncommitted_blocks, 'B6')

        with self.assertRaises(DuplicateBatch) as cm:
            commit_state.check_for_duplicate_batches(
                [batches[2]])

        self.assertEqual(cm.exception.batch_id, 'b2')

    def test_duplicate_batch_in_current_chain(self):
        """Verify that DuplicateBatch is raised for a batch in the current
        chain.
        """
        _, batches, committed_blocks, uncommitted_blocks =\
            self.create_new_chain()

        commit_state = self.create_chain_commit_state(
            committed_blocks, uncommitted_blocks, 'B6')

        with self.assertRaises(DuplicateBatch) as cm:
            commit_state.check_for_duplicate_batches(
                [batches[5]])

        self.assertEqual(cm.exception.batch_id, 'b5')

    def test_duplicate_batch_in_fork(self):
        """Verify that DuplicateBatch is raised for a batch in the fork.
        """
        _, batches, committed_blocks, uncommitted_blocks =\
            self.create_new_chain()

        commit_state = self.create_chain_commit_state(
            committed_blocks, uncommitted_blocks, 'B9')

        with self.assertRaises(DuplicateBatch) as cm:
            commit_state.check_for_duplicate_batches(
                [batches[8]])

        self.assertEqual(cm.exception.batch_id, 'b8')

    def test_no_duplicate_batch_in_current_chain(self):
        """Verify that DuplicateBatch is not raised for a batch that is in the
        current chain but not the fork when head is on the fork.
        """
        _, batches, committed_blocks, uncommitted_blocks =\
            self.create_new_chain()

        commit_state = self.create_chain_commit_state(
            committed_blocks, uncommitted_blocks, 'B9')

        commit_state.check_for_duplicate_batches(
            [batches[5]])

    def test_no_duplicate_batch_in_fork(self):
        """Verify that DuplicateBatch is not raised for a batch that is in the
        fork but not the current chain when head is on the current chain.
        """
        _, batches, committed_blocks, uncommitted_blocks =\
            self.create_new_chain()

        commit_state = self.create_chain_commit_state(
            committed_blocks, uncommitted_blocks, 'B6')

        commit_state.check_for_duplicate_batches(
            [batches[8]])

    # Transactions
    def test_no_duplicate_txn_found(self):
        """Verify that DuplicateTransaction is not raised for a completely new
        transaction.
        """
        _, _, committed_blocks, uncommitted_blocks =\
            self.create_new_chain()

        commit_state = self.create_chain_commit_state(
            committed_blocks, uncommitted_blocks, 'B6')

        commit_state.check_for_duplicate_transactions([self.gen_txn('t10')])

    def test_duplicate_txn_in_both_chains(self):
        """Verify that DuplicateTransaction is raised for a transaction in both
        the current chain and the fork.
        """
        transactions, _, committed_blocks, uncommitted_blocks =\
            self.create_new_chain()

        commit_state = self.create_chain_commit_state(
            committed_blocks, uncommitted_blocks, 'B6')

        with self.assertRaises(DuplicateTransaction) as cm:
            commit_state.check_for_duplicate_transactions(
                [transactions[2]])

        self.assertEqual(cm.exception.transaction_id, 't2')

    def test_duplicate_txn_in_current_chain(self):
        """Verify that DuplicateTransaction is raised for a transaction in the
        current chain.
        """
        transactions, _, committed_blocks, uncommitted_blocks =\
            self.create_new_chain()

        commit_state = self.create_chain_commit_state(
            committed_blocks, uncommitted_blocks, 'B6')

        with self.assertRaises(DuplicateTransaction) as cm:
            commit_state.check_for_duplicate_transactions(
                [transactions[5]])

        self.assertEqual(cm.exception.transaction_id, 't5')

    def test_duplicate_txn_in_fork(self):
        """Verify that DuplicateTransaction is raised for a transaction in the
        fork.
        """
        transactions, _, committed_blocks, uncommitted_blocks =\
            self.create_new_chain()

        commit_state = self.create_chain_commit_state(
            committed_blocks, uncommitted_blocks, 'B9')

        with self.assertRaises(DuplicateTransaction) as cm:
            commit_state.check_for_duplicate_transactions(
                [transactions[8]])

        self.assertEqual(cm.exception.transaction_id, 't8')

    def test_no_duplicate_txn_in_current_chain(self):
        """Verify that DuplicateTransaction is not raised for a transaction
        that is in the current chain but not the fork when head is on the fork.
        """
        transactions, _, committed_blocks, uncommitted_blocks =\
            self.create_new_chain()

        commit_state = self.create_chain_commit_state(
            committed_blocks, uncommitted_blocks, 'B9')

        commit_state.check_for_duplicate_transactions(
            [transactions[5]])

    def test_no_duplicate_txn_in_fork(self):
        """Verify that DuplicateTransaction is not raised for a transaction
        that is in the fork but not the current chain when head is on the
        current chain.
        """
        transactions, _, committed_blocks, uncommitted_blocks =\
            self.create_new_chain()

        commit_state = self.create_chain_commit_state(
            committed_blocks, uncommitted_blocks, 'B6')

        commit_state.check_for_duplicate_transactions(
            [transactions[8]])

    # Dependencies
    def test_present_dependency(self):
        """Verify that a present dependency is found."""
        transactions, _, committed_blocks, uncommitted_blocks =\
            self.create_new_chain()

        commit_state = self.create_chain_commit_state(
            committed_blocks, uncommitted_blocks, 'B6')

        commit_state.check_for_transaction_dependencies([
            self.gen_txn('t10', deps=[transactions[2].header_signature])
        ])

    def test_missing_dependency_in_both_chains(self):
        """Verifies that MissingDependency is raised when a dependency is not
        committed anywhere.
        """
        _, _, committed_blocks, uncommitted_blocks =\
            self.create_new_chain()

        commit_state = self.create_chain_commit_state(
            committed_blocks, uncommitted_blocks, 'B6')

        with self.assertRaises(MissingDependency) as cm:
            commit_state.check_for_transaction_dependencies([
                self.gen_txn('t10', deps=['t11'])
            ])

        self.assertEqual(cm.exception.transaction_id, 't11')

    def test_present_dependency_in_current_chain(self):
        """Verify that a dependency present in the current chain is found.
        """
        transactions, _, committed_blocks, uncommitted_blocks =\
            self.create_new_chain()

        commit_state = self.create_chain_commit_state(
            committed_blocks, uncommitted_blocks, 'B6')

        commit_state.check_for_transaction_dependencies([
            self.gen_txn('t10', deps=[transactions[5].header_signature])
        ])

    def test_present_dependency_in_fork(self):
        """Verify that a dependency present in the fork is found.
        """
        transactions, _, committed_blocks, uncommitted_blocks =\
            self.create_new_chain()

        commit_state = self.create_chain_commit_state(
            committed_blocks, uncommitted_blocks, 'B9')

        commit_state.check_for_transaction_dependencies([
            self.gen_txn('t10', deps=[transactions[8].header_signature])
        ])

    def test_missing_dependency_in_current_chain(self):
        """Verify that MissingDependency is raised for a dependency that is
        committed to the current chain but not the fork when head is on the
        fork.
        """
        transactions, _, committed_blocks, uncommitted_blocks =\
            self.create_new_chain()

        commit_state = self.create_chain_commit_state(
            committed_blocks, uncommitted_blocks, 'B9')

        commit_state.check_for_duplicate_transactions(
            [transactions[5]])

    def test_missing_dependency_in_fork(self):
        """Verify that MissingDependency is raised for a dependency that is
        committed to the fork but not the current chain when head is on the
        current chain.
        """
        transactions, _, committed_blocks, uncommitted_blocks =\
            self.create_new_chain()

        commit_state = self.create_chain_commit_state(
            committed_blocks, uncommitted_blocks, 'B6')

        commit_state.check_for_duplicate_transactions(
            [transactions[8]])

    def create_new_chain(self):
        """
        NUM     0  1  2  3  4  5  6
        CURRENT B0-B1-B2-B3-B4-B5-B6
                         |
        FORK             +--B7-B8-B9
        """
        txns = [
            self.gen_txn('t' + format(i, 'x'))
            for i in range(10)
        ]
        batches = [
            self.gen_batch('b' + format(i, 'x'), [txns[i]])
            for i in range(10)
        ]
        committed_blocks = [
            self.gen_block(
                block_id='B0',
                prev_id=NULL_BLOCK_IDENTIFIER,
                num=0,
                batches=[batches[0]])
        ]
        committed_blocks.extend([
            self.gen_block(
                block_id='B' + format(i, 'x'),
                prev_id='B' + format(i - 1, 'x'),
                num=i,
                batches=[batches[i]])
            for i in range(1, 7)
        ])
        uncommitted_blocks = [
            self.gen_block(
                block_id='B7',
                prev_id='B3',
                num=4,
                batches=[batches[0]])
        ]
        uncommitted_blocks.extend([
            self.gen_block(
                block_id='B' + format(i, 'x'),
                prev_id='B' + format(i - 1, 'x'),
                num=5 + (i - 8),
                batches=[batches[i]])
            for i in range(8, 10)
        ])

        return txns, batches, committed_blocks, uncommitted_blocks

    def create_chain_commit_state(
        self,
        committed_blocks,
        uncommitted_blocks,
        head_id,
    ):
        block_store = BlockStore(DictDatabase(
            indexes=BlockStore.create_index_configuration()))
        block_store.update_chain(committed_blocks)

        block_cache = BlockCache(
            block_store=block_store)

        for block in uncommitted_blocks:
            block_cache[block.header_signature] = block

        return ChainCommitState(head_id, block_cache, block_store)


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

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
import unittest.mock

from sawtooth_validator.consensus.handlers import BlockInProgress
from sawtooth_validator.consensus.handlers import BlockEmpty
from sawtooth_validator.consensus.handlers import BlockNotInitialized

from sawtooth_validator.journal.block_cache import BlockCache
from sawtooth_validator.journal.block_wrapper import BlockWrapper
from sawtooth_validator.journal.publisher import BlockPublisher
from sawtooth_validator.journal.timed_cache import TimedCache
from sawtooth_validator.journal.event_extractors \
    import BlockEventExtractor
from sawtooth_validator.journal.event_extractors \
    import ReceiptEventExtractor

from sawtooth_validator.server.events.subscription import EventSubscription
from sawtooth_validator.server.events.subscription import EventFilterFactory

from sawtooth_validator.protobuf.block_pb2 import Block
from sawtooth_validator.protobuf.block_pb2 import BlockHeader
from sawtooth_validator.protobuf.transaction_receipt_pb2 import \
    TransactionReceipt
from sawtooth_validator.protobuf.transaction_receipt_pb2 import StateChange
from sawtooth_validator.protobuf.transaction_receipt_pb2 import StateChangeList
from sawtooth_validator.protobuf.events_pb2 import Event
from sawtooth_validator.protobuf.events_pb2 import EventFilter

from test_journal.block_tree_manager import BlockTreeManager

from test_journal.mock import MockBlockSender
from test_journal.mock import MockBatchSender
from test_journal.mock import MockStateViewFactory, CreateSetting
from test_journal.mock import MockTransactionExecutor
from test_journal.mock import MockPermissionVerifier
from test_journal.mock import MockBatchInjectorFactory


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
            block_store=self.block_tree_manager.block_store,
            block_manager=self.block_tree_manager.block_manager,
            transaction_executor=MockTransactionExecutor(),
            state_view_factory=self.state_view_factory,
            block_sender=self.block_sender,
            batch_sender=self.batch_sender,
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
            block_store=self.block_tree_manager.block_store,
            block_manager=self.block_tree_manager.block_manager,
            transaction_executor=MockTransactionExecutor(
                batch_execution_result=False),
            state_view_factory=self.state_view_factory,
            block_sender=self.block_sender,
            batch_sender=self.batch_sender,
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
            block_store=self.block_tree_manager.block_store,
            block_manager=self.block_tree_manager.block_manager,
            transaction_executor=MockTransactionExecutor(),
            state_view_factory=self.state_view_factory,
            block_sender=self.block_sender,
            batch_sender=self.batch_sender,
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
            block_store=self.block_tree_manager.block_store,
            block_manager=self.block_tree_manager.block_manager,
            transaction_executor=MockTransactionExecutor(),
            state_view_factory=self.state_view_factory,
            block_sender=self.block_sender,
            batch_sender=self.batch_sender,
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
            block_store=self.block_tree_manager.block_store,
            block_manager=self.block_tree_manager.block_manager,
            transaction_executor=MockTransactionExecutor(),
            state_view_factory=self.state_view_factory,
            block_sender=self.block_sender,
            batch_sender=self.batch_sender,
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

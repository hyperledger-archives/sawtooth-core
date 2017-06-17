# Copyright 2016, 2017 Intel Corporation
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
from unittest.mock import Mock
import logging
import hashlib
import os
import threading
import time

import sawtooth_signing as signing

import sawtooth_validator.protobuf.transaction_pb2 as transaction_pb2

from sawtooth_validator.execution.context_manager import ContextManager
from sawtooth_validator.execution.scheduler_exceptions import SchedulerError
from sawtooth_validator.execution.scheduler_serial import SerialScheduler
from sawtooth_validator.execution.scheduler_parallel import ParallelScheduler
from sawtooth_validator.database import dict_database
from sawtooth_validator.execution.scheduler_parallel import PredecessorTree
from sawtooth_validator.state.merkle import MerkleDatabase

from test_scheduler.yaml_scheduler_tester import create_batch
from test_scheduler.yaml_scheduler_tester import create_transaction
from test_scheduler.yaml_scheduler_tester import SchedulerTester


LOGGER = logging.getLogger(__name__)


class TestSchedulersWithYaml(unittest.TestCase):

    def _setup_serial_scheduler(self):
        context_manager = self._context_manager
        squash_handler = context_manager.get_squash_handler()
        first_state_root = context_manager.get_first_root()
        scheduler = SerialScheduler(squash_handler,
                                    first_state_root,
                                    always_persist=False)
        return context_manager, scheduler

    def _setup_parallel_scheduler(self):
        context_manager = self._context_manager
        squash_handler = context_manager.get_squash_handler()
        first_state_root = context_manager.get_first_root()
        scheduler = ParallelScheduler(squash_handler,
                                      first_state_root)
        return context_manager, scheduler

    def test_parallel_simple_scheduler_test(self):
        context_manager, scheduler = self._setup_parallel_scheduler()
        self._single_block_files_individually(
            scheduler=scheduler,
            context_manager=context_manager,
            name='simple_scheduler_test.yaml')

    def test_serial_simple_scheduler_test(self):
        context_manager, scheduler = self._setup_serial_scheduler()
        self._single_block_files_individually(
            scheduler=scheduler,
            context_manager=context_manager,
            name='simple_scheduler_test.yaml')

    def test_parallel_intkey_small_batch(self):
        context_manager, scheduler = self._setup_parallel_scheduler()
        self._single_block_files_individually(
            scheduler=scheduler,
            context_manager=context_manager,
            name='intkey_small_batch.yaml')

    def test_serial_intkey_small_batch(self):
        context_manager, scheduler = self._setup_serial_scheduler()
        self._single_block_files_individually(
            scheduler=scheduler,
            context_manager=context_manager,
            name='intkey_small_batch.yaml')

    def _single_block_files_individually(self,
                                         scheduler,
                                         context_manager,
                                         name):
        """Tests scheduler(s) with yaml files that represent a single
        block.

        Notes:
            Tests that the serial scheduler has the correct batch validity
            and state hash, and that 1 state hash is produced.

        """

        file_name = self._path_to_yaml_file(name)
        tester = SchedulerTester(file_name)
        defined_batch_results_dict = tester.batch_results
        batch_results = tester.run_scheduler(
            scheduler=scheduler,
            context_manager=context_manager)
        self.assert_batch_validity(
            defined_batch_results_dict,
            batch_results)
        self.assert_one_state_hash(batch_results=batch_results)
        sched_state_roots = self._get_state_roots(
            batch_results=batch_results)
        calc_state_hash = tester.compute_state_hashes_wo_scheduler()

        self.assertEquals(
            sched_state_roots,
            calc_state_hash,
            "The state hashes calculated by the scheduler for yaml file {}"
            " must be the same as calculated by the tester".format(name))

    def setUp(self):
        self._context_manager = ContextManager(
            dict_database.DictDatabase(),
            state_delta_store=Mock())

    def tearDown(self):
        self._context_manager.stop()

    def _get_state_roots(self, batch_results):
        return [r.state_hash for _, r in batch_results
                if r.state_hash is not None]

    def assert_batch_validity(self, yaml_results_dict, batch_results):
        """Checks that all of the BatchExecutionResults calculated are the
        same as defined in the yaml file and returned by
        SchedulerTester.create_batches().

        Args:
            yaml_results_dict (dict): batch signature: BatchExecutionResult,
                                      Calculated from the yaml.
            batch_results (list): list of tuples
                                  (batch signature, BatchExecutionResult)
                                  Calculated by the scheduler.

        Raises:
            AssertionError
        """

        for i, b_e in enumerate(batch_results):
            signature, result = b_e
            defined_result = yaml_results_dict[signature]
            self.assertIsNotNone(result.is_valid, "Batch #{} has None as it's "
                                                  "validity".format(i))
            self.assertEquals(
                result.is_valid,
                defined_result.is_valid,
                "Batch #{} was defined in the yaml to be {},"
                "but the scheduler determined "
                "it was {}".format(
                    i + 1,
                    'valid' if defined_result.is_valid else 'invalid',
                    'valid' if result.is_valid else 'invalid'))

    def assert_one_state_hash(self, batch_results):
        """Should be used when only one state hash is expected from the
        scheduler.

        Args:
            batch_results (list): list of tuples
                                  (batch signature, BatchExecutionResult)
        Raises:
            AssertionError
        """

        state_roots = self._get_state_roots(batch_results=batch_results)
        self.assertEquals(len(state_roots), 1,
                          "The scheduler calculated more than one state "
                          "root when only one was expected")

    def _path_to_yaml_file(self, name):
        parent_dir = os.path.dirname(__file__)
        file_name = os.path.join(parent_dir, 'data', name)
        return file_name


def _get_address_from_txn(txn_info):
    txn_header = transaction_pb2.TransactionHeader()
    txn_header.ParseFromString(txn_info.txn.header)
    inputs_or_outputs = list(txn_header.inputs)
    address_b = inputs_or_outputs[0]
    return address_b


class TestSchedulers(unittest.TestCase):

    def _setup_serial_scheduler(self):
        context_manager = ContextManager(dict_database.DictDatabase(),
                                         state_delta_store=Mock())
        squash_handler = context_manager.get_squash_handler()
        first_state_root = context_manager.get_first_root()
        scheduler = SerialScheduler(squash_handler,
                                    first_state_root,
                                    always_persist=False)
        return context_manager, scheduler

    def _setup_parallel_scheduler(self):
        context_manager = ContextManager(dict_database.DictDatabase(),
                                         state_delta_store=Mock())
        squash_handler = context_manager.get_squash_handler()
        first_state_root = context_manager.get_first_root()
        scheduler = ParallelScheduler(squash_handler,
                                      first_state_root)
        return context_manager, scheduler

    def test_serial_completion_on_finalize(self):
        try:
            context_manager, scheduler = self._setup_serial_scheduler()
            self._completion_on_finalize(scheduler)
        finally:
            context_manager.stop()

    def test_parallel_completion_on_finalize(self):
        try:
            context_manager, scheduler = self._setup_parallel_scheduler()
            self._completion_on_finalize(scheduler)
        finally:
            context_manager.stop()

    def _completion_on_finalize(self, scheduler):
        """Tests that iteration will stop when finalized is called on an
        otherwise complete scheduler.
        Adds one batch and transaction, then verifies the iterable returns
        that transaction.  Sets the execution result and then calls finalize.
        Since the the scheduler is complete (all transactions have had
        results set, and it's been finalized), we should get a StopIteration.
        This check is useful in making sure the finalize() can occur after
        all set_transaction_execution_result()s have been performed, because
        in a normal situation, finalize will probably occur prior to those
        calls.

        This test should work for both a serial and parallel scheduler.
        """
        private_key = signing.generate_privkey()
        public_key = signing.generate_pubkey(private_key)

        txn, _ = create_transaction(
            payload='a'.encode(),
            private_key=private_key,
            public_key=public_key)

        batch = create_batch(
            transactions=[txn],
            private_key=private_key,
            public_key=public_key)

        iterable = iter(scheduler)

        scheduler.add_batch(batch)

        scheduled_txn_info = next(iterable)
        self.assertIsNotNone(scheduled_txn_info)
        self.assertEquals(txn.payload, scheduled_txn_info.txn.payload)
        scheduler.set_transaction_execution_result(
            txn.header_signature, False, None)

        scheduler.finalize()

        with self.assertRaises(StopIteration):
            next(iterable)

    def test_serial_completion_on_finalize_only_when_done(self):
        try:
            context_manager, scheduler = self._setup_serial_scheduler()
            self._completion_on_finalize_only_when_done(scheduler)
        finally:
            context_manager.stop()

    def test_parallel_completion_on_finalize_only_when_done(self):
        try:
            context_manager, scheduler = self._setup_parallel_scheduler()
            self._completion_on_finalize_only_when_done(scheduler)
        finally:
            context_manager.stop()

    def _completion_on_finalize_only_when_done(self, scheduler):
        """Tests that iteration will stop when finalized is called on an
        otherwise complete scheduler.
        Adds one batch and transaction, then verifies the iterable returns
        that transaction.  Finalizes then sets the execution result. The
        schedule should not be marked as complete.
        This check is useful in making sure the finalize() can occur after
        all set_transaction_execution_result()s have been performed, because
        in a normal situation, finalize will probably occur prior to those
        calls.

        This test should work for both a serial and parallel scheduler.
        """
        private_key = signing.generate_privkey()
        public_key = signing.generate_pubkey(private_key)

        txn, _ = create_transaction(
            payload='a'.encode(),
            private_key=private_key,
            public_key=public_key)

        batch = create_batch(
            transactions=[txn],
            private_key=private_key,
            public_key=public_key)

        iterable = iter(scheduler)

        scheduler.add_batch(batch)

        scheduled_txn_info = next(iterable)
        self.assertIsNotNone(scheduled_txn_info)
        self.assertEquals(txn.payload, scheduled_txn_info.txn.payload)
        scheduler.finalize()
        self.assertFalse(scheduler.complete(block=False))
        scheduler.set_transaction_execution_result(
            txn.header_signature, False, None)
        self.assertTrue(scheduler.complete(block=False))

        with self.assertRaises(StopIteration):
            next(iterable)

    def test_serial_add_batch_after_empty_iteration(self):
        try:
            context_manager, scheduler = self._setup_serial_scheduler()
            self._add_batch_after_empty_iteration(scheduler)
        finally:
            context_manager.stop()

    def test_parallel_add_batch_after_empty_iteration(self):
        try:
            context_manager, scheduler = self._setup_parallel_scheduler()
            self._add_batch_after_empty_iteration(scheduler)
        finally:
            context_manager.stop()

    def _add_batch_after_empty_iteration(self, scheduler):
        """Tests that iterations will continue as result of add_batch().
        This test calls next() on a scheduler iterator in a separate thread
        called the IteratorThread.  The test waits until the IteratorThread
        is waiting in next(); internal to the scheduler, it will be waiting on
        a condition variable as there are no transactions to return and the
        scheduler is not finalized.  Then, the test continues by running
        add_batch(), which should cause the next() running in the
        IterableThread to return a transaction.
        This demonstrates the scheduler's ability to wait on an empty iterator
        but continue as transactions become available via add_batch.

        This test should work for both a serial and parallel scheduler.
        """
        private_key = signing.generate_privkey()
        public_key = signing.generate_pubkey(private_key)

        # Create a basic transaction and batch.
        txn, _ = create_transaction(
            payload='a'.encode(),
            private_key=private_key,
            public_key=public_key)
        batch = create_batch(
            transactions=[txn],
            private_key=private_key,
            public_key=public_key)

        # This class is used to run the scheduler's iterator.
        class IteratorThread(threading.Thread):
            def __init__(self, iterable):
                threading.Thread.__init__(self)
                self._iterable = iterable
                self.ready = False
                self.condition = threading.Condition()
                self.txn_info = None

            def run(self):
                # Even with this lock here, there is a race condition between
                # exit of the lock and entry into the iterable.  That is solved
                # by sleep later in the test.
                with self.condition:
                    self.ready = True
                    self.condition.notify()
                txn_info = next(self._iterable)
                with self.condition:
                    self.txn_info = txn_info
                    self.condition.notify()

        # This is the iterable we are testing, which we will use in the
        # IteratorThread.  We also use it in this thread below to test
        # for StopIteration.
        iterable = iter(scheduler)

        # Create and startup thread.
        thread = IteratorThread(iterable=iterable)
        thread.start()

        # Pause here to make sure the thread is absolutely as far along as
        # possible; in other words, right before we call next() in it's run()
        # method.  When this returns, there should be very little time until
        # the iterator is blocked on a condition variable.
        with thread.condition:
            while not thread.ready:
                thread.condition.wait()

        # May the daemons stay away during this dark time, and may we be
        # forgiven upon our return.
        time.sleep(1)

        # At this point, the IteratorThread should be waiting next(), so we go
        # ahead and give it a batch.
        scheduler.add_batch(batch)

        # If all goes well, thread.txn_info will get set to the result of the
        # next() call.  If not, it will timeout and thread.txn_info will be
        # empty.
        with thread.condition:
            if thread.txn_info is None:
                thread.condition.wait(5)

        # If thread.txn_info is empty, the test failed as iteration did not
        # continue after add_batch().
        self.assertIsNotNone(thread.txn_info, "iterable failed to return txn")
        self.assertEquals(txn.payload, thread.txn_info.txn.payload)

        # Continue with normal shutdown/cleanup.
        scheduler.finalize()
        scheduler.set_transaction_execution_result(
            txn.header_signature, False, None)
        with self.assertRaises(StopIteration):
            next(iterable)


    def test_serial_valid_batch_invalid_batch(self):
        try:
            context_manager, scheduler = self._setup_serial_scheduler()
            self._add_valid_batch_invalid_batch(scheduler, context_manager)
        finally:
            context_manager.stop()

    def test_parallel_add_valid_batch_invalid_batch(self):
        try:
            context_manager, scheduler = self._setup_parallel_scheduler()
            self._valid_batch_invalid_batch(scheduler, context_manager)
        finally:
            context_manager.stop()

    def _add_valid_batch_invalid_batch(self, scheduler, context_manager):
        """Tests the squash function. That the correct hash is being used
        for each txn and that the batch ending state hash is being set.
         Basically:
            1. Adds two batches, one where all the txns are valid,
               and one where one of the txns is invalid.
            2. Run through the scheduler executor interaction
               as txns are processed.
            3. Verify that the state root obtained through the squash function
               is the same as directly updating the merkle tree.
            4. Verify that correct batch statuses are set

        This test should work for both a serial and parallel scheduler.
        """
        private_key = signing.generate_privkey()
        public_key = signing.generate_pubkey(private_key)

        # 1)
        batch_signatures = []
        for names in [['a', 'b'], ['invalid', 'c'], ['d', 'e']]:
            batch_txns = []
            for name in names:
                txn, _ = create_transaction(
                    payload=name.encode(),
                    private_key=private_key,
                    public_key=public_key)

                batch_txns.append(txn)

            batch = create_batch(
                transactions=batch_txns,
                private_key=private_key,
                public_key=public_key)

            batch_signatures.append(batch.header_signature)
            scheduler.add_batch(batch)
        scheduler.finalize()
        # 2)
        sched1 = iter(scheduler)
        invalid_payload = hashlib.sha512('invalid'.encode()).hexdigest()
        while not scheduler.complete(block=False):
            txn_info = next(sched1)
            txn_header = transaction_pb2.TransactionHeader()
            txn_header.ParseFromString(txn_info.txn.header)
            inputs_or_outputs = list(txn_header.inputs)
            c_id = context_manager.create_context(
                state_hash=txn_info.state_hash,
                inputs=inputs_or_outputs,
                outputs=inputs_or_outputs,
                base_contexts=txn_info.base_context_ids)
            if txn_header.payload_sha512 == invalid_payload:
                scheduler.set_transaction_execution_result(
                    txn_info.txn.header_signature, False, None)
            else:
                context_manager.set(c_id, [{inputs_or_outputs[0]: b"1"}])
                scheduler.set_transaction_execution_result(
                    txn_info.txn.header_signature, True, c_id)

        sched2 = iter(scheduler)
        # 3)
        txn_info_a = next(sched2)
        txn_a_header = transaction_pb2.TransactionHeader()
        txn_a_header.ParseFromString(txn_info_a.txn.header)
        inputs_or_outputs = list(txn_a_header.inputs)
        address_a = inputs_or_outputs[0]

        txn_info_b = next(sched2)
        address_b = _get_address_from_txn(txn_info_b)

        txn_infoInvalid = next(sched2)
        txn_info_c = next(sched2)

        txn_info_d = next(sched2)
        address_d = _get_address_from_txn(txn_info_d)

        txn_info_e = next(sched2)
        address_e = _get_address_from_txn(txn_info_e)

        merkle_database = MerkleDatabase(dict_database.DictDatabase())
        state_root_end = merkle_database.update(
            {address_a: b"1", address_b: b"1",
             address_d: b"1", address_e: b"1"},
            virtual=False)

        # 4)
        batch1_result = scheduler.get_batch_execution_result(
            batch_signatures[0])
        self.assertTrue(batch1_result.is_valid)

        batch2_result = scheduler.get_batch_execution_result(
            batch_signatures[1])
        self.assertFalse(batch2_result.is_valid)

        batch3_result = scheduler.get_batch_execution_result(
            batch_signatures[2])
        self.assertTrue(batch3_result.is_valid)
        self.assertEqual(batch3_result.state_hash, state_root_end)

    def test_serial_sequential_add_batch_after_all_results_set(self):
        """Tests that adding a new batch only after setting all of the
        txn results will produce only expected state roots.
        """

        context_manager, scheduler = self._setup_serial_scheduler()
        self._sequential_add_batch_after_all_results_set(
            scheduler=scheduler,
            context_manager=context_manager)

    def test_parallel_sequential_add_batch_after_all_results_set(self):
        """Tests that adding a new batch only after setting all of the
        txn results will produce only expected state roots.
        """

        context_manager, scheduler = self._setup_parallel_scheduler()
        self._sequential_add_batch_after_all_results_set(
            scheduler=scheduler,
            context_manager=context_manager)

    def _sequential_add_batch_after_all_results_set(self,
                                                    scheduler,
                                                    context_manager):
        """Tests that adding a new batch only after setting all of the
        txn results will produce only expected state roots. Here no state
        roots were specified, so similar to block publishing use of scheduler.
        Basically:
            1) Create 3 batches, the last being marked as having an invalid
               transaction. Add one batch and then while the scheduler keeps
               on returning transactions, set the txn result, and then
               call next_transaction.
            2) Call finalize, and then assert that the scheduler is complete
            3) Assert that the first batch is valid and has no state hash,
               the second batch is valid and since it is the last valid batch
               in the scheduler has a state hash, and that the third batch
               is invalid and consequently has no state hash.
        """

        private_key = signing.generate_privkey()
        public_key = signing.generate_pubkey(private_key)

        # 1)
        batch_signatures = []
        batches = []
        for names in [['a', 'b'], ['d', 'e'], ['invalid', 'c']]:
            batch_txns = []
            for name in names:
                txn, _ = create_transaction(
                    payload=name.encode(),
                    private_key=private_key,
                    public_key=public_key)

                batch_txns.append(txn)

            batch = create_batch(
                transactions=batch_txns,
                private_key=private_key,
                public_key=public_key)
            batches.append(batch)
            batch_signatures.append(batch.header_signature)
        invalid_payload_sha = hashlib.sha512(
            'invalid'.encode()).hexdigest()
        for batch in batches:
            scheduler.add_batch(batch=batch)
            txn_info = scheduler.next_transaction()
            while txn_info is not None:
                txn_header = transaction_pb2.TransactionHeader()
                txn_header.ParseFromString(txn_info.txn.header)
                inputs_outputs = list(txn_header.inputs)
                c_id = context_manager.create_context(
                    state_hash=context_manager.get_first_root(),
                    base_contexts=txn_info.base_context_ids,
                    inputs=list(txn_header.inputs),
                    outputs=list(txn_header.outputs))
                context_manager.set(
                    context_id=c_id,
                    address_value_list=[{inputs_outputs[0]: b'5'}])
                if txn_header.payload_sha512 == invalid_payload_sha:
                    scheduler.set_transaction_execution_result(
                        txn_info.txn.header_signature,
                        is_valid=False,
                        context_id=None)
                else:
                    scheduler.set_transaction_execution_result(
                        txn_info.txn.header_signature,
                        is_valid=True,
                        context_id=c_id)
                txn_info = scheduler.next_transaction()

        # 2)
        scheduler.finalize()
        self.assertTrue(scheduler.complete(block=False),
                        "The scheduler has had all txn results set so after "
                        " calling finalize the scheduler is complete")
        # 3)
        first_batch_id = batch_signatures.pop(0)
        result1 = scheduler.get_batch_execution_result(first_batch_id)
        self.assertEqual(
            result1.is_valid,
            True,
            "The first batch is valid")
        self.assertIsNone(result1.state_hash,
                          "The first batch doesn't produce"
                          " a state hash")
        second_batch_id = batch_signatures.pop(0)
        result2 = scheduler.get_batch_execution_result(second_batch_id)
        self.assertEqual(
            result2.is_valid,
            True,
            "The second batch is valid")
        self.assertIsNotNone(result2.state_hash, "The second batch is the "
                                                 "last valid batch in the "
                                                 "scheduler")

        third_batch_id = batch_signatures.pop(0)
        result3 = scheduler.get_batch_execution_result(third_batch_id)
        self.assertEqual(result3.is_valid, False)
        self.assertIsNone(result3.state_hash,
                          "The last batch is invalid so "
                          "doesn't have a state hash")



class TestSerialScheduler(unittest.TestCase):
    def setUp(self):
        self.context_manager = ContextManager(dict_database.DictDatabase(),
                                              state_delta_store=Mock())
        squash_handler = self.context_manager.get_squash_handler()
        self.first_state_root = self.context_manager.get_first_root()
        self.scheduler = SerialScheduler(squash_handler,
                                         self.first_state_root,
                                         always_persist=False)

    def tearDown(self):
        self.context_manager.stop()

    def test_transaction_order(self):
        """Tests the that transactions are returned in order added.

        Adds three batches with varying number of transactions, then tests
        that they are returned in the appropriate order when using an iterator.

        This test also creates a second iterator and verifies that both
        iterators return the same transactions.

        This test also finalizes the scheduler and verifies that StopIteration
        is thrown by the iterator.
        """
        private_key = signing.generate_privkey()
        public_key = signing.generate_pubkey(private_key)

        txns = []

        for names in [['a', 'b', 'c'], ['d', 'e'], ['f', 'g', 'h', 'i']]:
            batch_txns = []
            for name in names:
                txn, _ = create_transaction(
                    payload=name.encode(),
                    private_key=private_key,
                    public_key=public_key)

                batch_txns.append(txn)
                txns.append(txn)

            batch = create_batch(
                transactions=batch_txns,
                private_key=private_key,
                public_key=public_key)

            self.scheduler.add_batch(batch)

        self.scheduler.finalize()

        iterable1 = iter(self.scheduler)
        iterable2 = iter(self.scheduler)
        for txn in txns:
            scheduled_txn_info = next(iterable1)
            self.assertEqual(scheduled_txn_info, next(iterable2))
            self.assertIsNotNone(scheduled_txn_info)
            self.assertEquals(txn.payload, scheduled_txn_info.txn.payload)
            self.scheduler.set_transaction_execution_result(
                txn.header_signature, False, None)

        with self.assertRaises(StopIteration):
            next(iterable1)

    def test_completion_on_last_result(self):
        """Tests the that the schedule is not marked complete until the last
        result is set.

        Adds three batches with varying number of transactions, then tests
        that they are returned in the appropriate order when using an iterator.
        Test that the value of `complete` is false until the last value.

        This test also finalizes the scheduler and verifies that StopIteration
        is thrown by the iterator, and the complete is true in the at the end.
        """
        private_key = signing.generate_privkey()
        public_key = signing.generate_pubkey(private_key)

        txns = []

        for names in [['a', 'b', 'c'], ['d', 'e'], ['f', 'g', 'h', 'i']]:
            batch_txns = []
            for name in names:
                txn, _ = create_transaction(
                    payload=name.encode(),
                    private_key=private_key,
                    public_key=public_key)

                batch_txns.append(txn)
                txns.append(txn)

            batch = create_batch(
                transactions=batch_txns,
                private_key=private_key,
                public_key=public_key)

            self.scheduler.add_batch(batch)

        self.scheduler.finalize()

        iterable1 = iter(self.scheduler)
        for txn in txns:
            scheduled_txn_info = next(iterable1)
            self.assertFalse(self.scheduler.complete(block=False))
            self.scheduler.set_transaction_execution_result(
                txn.header_signature, False, None)

        self.assertTrue(self.scheduler.complete(block=False))

        with self.assertRaises(StopIteration):
            next(iterable1)

    def test_set_status(self):
        """Tests that set_status() has the correct behavior.

        Basically:
            1. Adds a batch which has two transactions.
            2. Calls next_transaction() to get the first Transaction.
            3. Calls next_transaction() to verify that it returns None.
            4. Calls set_status() to mark the first transaction applied.
            5. Calls next_transaction() to  get the second Transaction.

        Step 3 returns None because the first transaction hasn't been marked
        as applied, and the SerialScheduler will only return one
        not-applied Transaction at a time.

        Step 5 is expected to return the second Transaction, not None,
        since the first Transaction was marked as applied in the previous
        step.
        """
        private_key = signing.generate_privkey()
        public_key = signing.generate_pubkey(private_key)

        txns = []

        for name in ['a', 'b']:
            txn, _ = create_transaction(
                payload=name.encode(),
                private_key=private_key,
                public_key=public_key)

            txns.append(txn)

        batch = create_batch(
            transactions=txns,
            private_key=private_key,
            public_key=public_key)

        self.scheduler.add_batch(batch)

        scheduled_txn_info = self.scheduler.next_transaction()
        self.assertIsNotNone(scheduled_txn_info)
        self.assertEquals('a', scheduled_txn_info.txn.payload.decode())

        self.assertIsNone(self.scheduler.next_transaction())

        self.scheduler.set_transaction_execution_result(
            scheduled_txn_info.txn.header_signature,
            is_valid=False,
            context_id=None)

        scheduled_txn_info = self.scheduler.next_transaction()
        self.assertIsNotNone(scheduled_txn_info)
        self.assertEquals('b', scheduled_txn_info.txn.payload.decode())


class TestParallelScheduler(unittest.TestCase):
    def setUp(self):
        self.context_manager = ContextManager(dict_database.DictDatabase(),
                                              state_delta_store=Mock())
        squash_handler = self.context_manager.get_squash_handler()
        self.first_state_root = self.context_manager.get_first_root()
        self.scheduler = ParallelScheduler(squash_handler,
                                           self.first_state_root)

    def tearDown(self):
        self.context_manager.stop()

    def test_add_to_finalized_scheduler(self):
        """Tests that a finalized scheduler raise exception on add_batch().

        This test creates a scheduler, finalizes it, and calls add_batch().
        The result is expected to be a SchedulerError, since adding a batch
        to a finalized scheduler is invalid.
        """
        private_key = signing.generate_privkey()
        public_key = signing.generate_pubkey(private_key)

        # Finalize prior to attempting to add a batch.
        self.scheduler.finalize()

        txn, _ = create_transaction(
            payload='a'.encode(),
            private_key=private_key,
            public_key=public_key)

        batch = create_batch(
            transactions=[txn],
            private_key=private_key,
            public_key=public_key)

        # scheduler.add_batch(batch) should throw a SchedulerError due to
        # the finalized status of the scheduler.
        self.assertRaises(
            SchedulerError, lambda: self.scheduler.add_batch(batch))

    def test_set_result_on_unscheduled_txn(self):
        """Tests that a scheduler will reject a result on an unscheduled
        transaction.

        Creates a batch with a single transaction, adds the batch to the
        scheduler, then immediately attempts to set the result for the
        transaction without first causing it to be scheduled (by using an
        iterator or calling next_transaction()).
        """
        private_key = signing.generate_privkey()
        public_key = signing.generate_pubkey(private_key)

        txn, _ = create_transaction(
            payload='a'.encode(),
            private_key=private_key,
            public_key=public_key)

        batch = create_batch(
            transactions=[txn],
            private_key=private_key,
            public_key=public_key)

        self.scheduler.add_batch(batch)

        self.assertRaises(
            SchedulerError,
            lambda: self.scheduler.set_transaction_execution_result(
                txn.header_signature, False, None))

    def test_transaction_order(self):
        """Tests the that transactions are returned in order added.

        Adds three batches with varying number of transactions, then tests
        that they are returned in the appropriate order when using an iterator.

        This test also creates a second iterator and verifies that both
        iterators return the same transactions.

        This test also finalizes the scheduler and verifies that StopIteration
        is thrown by the iterator.
        """
        private_key = signing.generate_privkey()
        public_key = signing.generate_pubkey(private_key)

        txns = []

        for names in [['a', 'b', 'c'], ['d', 'e'], ['f', 'g', 'h', 'i']]:
            batch_txns = []
            for name in names:
                txn, _ = create_transaction(
                    payload=name.encode(),
                    private_key=private_key,
                    public_key=public_key)

                batch_txns.append(txn)
                txns.append(txn)

            batch = create_batch(
                transactions=batch_txns,
                private_key=private_key,
                public_key=public_key)

            self.scheduler.add_batch(batch)

        iterable1 = iter(self.scheduler)
        iterable2 = iter(self.scheduler)
        for txn in txns:
            scheduled_txn_info = next(iterable1)
            self.assertEqual(scheduled_txn_info, next(iterable2))
            self.assertIsNotNone(scheduled_txn_info)
            self.assertEquals(txn.payload, scheduled_txn_info.txn.payload)
            self.scheduler.set_transaction_execution_result(
                txn.header_signature, False, None)

        self.scheduler.finalize()
        self.assertTrue(self.scheduler.complete(block=False))
        with self.assertRaises(StopIteration):
            next(iterable1)

    def test_transaction_order_with_dependencies(self):
        """Tests the that transactions are returned in the expected order given
        dependencies implied by state.

        Creates one batch with four transactions.
        """
        private_key = signing.generate_privkey()
        public_key = signing.generate_pubkey(private_key)

        txns = []
        headers = []

        txn, header = create_transaction(
            payload='a'.encode(),
            private_key=private_key,
            public_key=public_key)
        txns.append(txn)
        headers.append(header)

        txn, header = create_transaction(
            payload='b'.encode(),
            private_key=private_key,
            public_key=public_key)
        txns.append(txn)
        headers.append(header)

        txn, header =create_transaction(
            payload='aa'.encode(),
            private_key=private_key,
            public_key=public_key,
            inputs=['000000' + hashlib.sha512('a'.encode()).hexdigest()[:64]],
            outputs=['000000' + hashlib.sha512('a'.encode()).hexdigest()[:64]])
        txns.append(txn)
        headers.append(header)

        txn, header = create_transaction(
            payload='bb'.encode(),
            private_key=private_key,
            public_key=public_key,
            inputs=['000000' + hashlib.sha512('b'.encode()).hexdigest()[:64]],
            outputs=['000000' + hashlib.sha512('b'.encode()).hexdigest()[:64]])
        txns.append(txn)
        headers.append(header)

        batch = create_batch(
            transactions=txns,
            private_key=private_key,
            public_key=public_key)

        self.scheduler.add_batch(batch)
        self.scheduler.finalize()
        self.assertFalse(self.scheduler.complete(block=False))

        iterable = iter(self.scheduler)
        scheduled_txn_info = []

        self.assertEquals(2, self.scheduler.available())
        scheduled_txn_info.append(next(iterable))
        self.assertIsNotNone(scheduled_txn_info[0])
        self.assertEquals(txns[0].payload, scheduled_txn_info[0].txn.payload)
        self.assertFalse(self.scheduler.complete(block=False))

        self.assertEquals(1, self.scheduler.available())
        scheduled_txn_info.append(next(iterable))
        self.assertIsNotNone(scheduled_txn_info[1])
        self.assertEquals(txns[1].payload, scheduled_txn_info[1].txn.payload)
        self.assertFalse(self.scheduler.complete(block=False))

        self.assertEquals(0, self.scheduler.available())
        context_id1 = self.context_manager.create_context(
            state_hash=self.first_state_root,
            inputs=list(headers[1].inputs),
            outputs=list(headers[1].outputs),
            base_contexts=[])
        self.scheduler.set_transaction_execution_result(
            txns[1].header_signature, True, context_id1)

        self.assertEquals(1, self.scheduler.available())
        scheduled_txn_info.append(next(iterable))
        self.assertIsNotNone(scheduled_txn_info[2])
        self.assertEquals(txns[3].payload, scheduled_txn_info[2].txn.payload)
        self.assertFalse(self.scheduler.complete(block=False))

        self.assertEquals(0, self.scheduler.available())
        context_id2 = self.context_manager.create_context(
            state_hash=self.first_state_root,
            inputs=list(headers[0].inputs),
            outputs=list(headers[0].outputs),
            base_contexts=[context_id1])
        self.scheduler.set_transaction_execution_result(
            txns[0].header_signature, True, context_id2)

        self.assertEquals(1, self.scheduler.available())
        scheduled_txn_info.append(next(iterable))
        self.assertIsNotNone(scheduled_txn_info[3])
        self.assertEquals(txns[2].payload, scheduled_txn_info[3].txn.payload)
        self.assertFalse(self.scheduler.complete(block=False))

        self.assertEquals(0, self.scheduler.available())
        context_id3 = self.context_manager.create_context(
            state_hash=self.first_state_root,
            inputs=list(headers[2].inputs),
            outputs=list(headers[2].outputs),
            base_contexts=[context_id2])
        self.scheduler.set_transaction_execution_result(
            txns[2].header_signature, True, context_id3)
        context_id4 = self.context_manager.create_context(
            state_hash=self.first_state_root,
            inputs=list(headers[3].inputs),
            outputs=list(headers[3].outputs),
            base_contexts=[context_id3])
        self.scheduler.set_transaction_execution_result(
            txns[3].header_signature, True, context_id4)

        self.assertEquals(0, self.scheduler.available())
        self.assertTrue(self.scheduler.complete(block=False))
        with self.assertRaises(StopIteration):
            next(iterable)

        result = self.scheduler.get_batch_execution_result(batch.header_signature)
        self.assertIsNotNone(result)
        self.assertTrue(result.is_valid)


class TestPredecessorTree(unittest.TestCase):
    '''
    With an empty tree initialized in setUp, the predecessor tree
    tests generally follow this pattern (repeated several times):

        1) Add some readers or writers. In most cases, a diagram
           will be given in comments to show what the tree should
           look like after the additions.
        2) Assert the readers, writers, and children at all addresses
           in the tree (using assert_rwc_at_addresses). Possibly also
           assert (using assert_no_nodes_at_addresses) that nodes don't
           exist at certain addresses (this is normally done after
           setting a writer).
        3) Assert the total count of readers and writers in the tree
           (using assert_rw_count). This ensures that nothing is in the
           tree that shouldn't be there.
        4) Assert the read and write predecessors for various addresses
           (using assert_rw_preds_at_addresses).

    Although the default token size for the predecessor tree is 2,
    1 is used for most tests because it makes for more natural examples.
    '''

    def setUp(self):
        self.tree = PredecessorTree(token_size=1)

    def tearDown(self):
        self.tree = None

    def test_predecessor_tree(self):
        '''Tests basic predecessor tree functions

        This test is intended to show the evolution of a tree
        over the course of normal use. Apart from testing, it
        can also be used as a reference example.

        Readers and writers are added in the following steps:

        1) Add some readers.
        2) Add readers at addresses that are initial segments
           of existing node addresses.
        3) Add a writer in the middle of the tree.
        4) Add readers to existing nodes.
        5) Add a writer to a new node.
        6) Add writers in the middle of the tree.
        7) Add readers to upper nodes.
        8) Add readers to nodes with writers.
        9) Add readers to new top nodes.
        10) Add writer to top node.
        11) Add readers to upper nodes, then add writers.
        12) Add writer to top node, then add reader.
        13) Add writer to root
        '''

        # 1) Add some readers.

        self.add_readers({
            'radix': 1,
            'radish': 2,
            'radon': 3,
            'razzle': 4,
            'rustic': 5
        })

        # ROOT:
        #   r:
        #     a:
        #       d:
        #         o:
        #           n: Readers: [3]
        #         i:
        #           x: Readers: [1]
        #           s:
        #             h: Readers: [2]
        #       z:
        #         z:
        #           l:
        #             e: Readers: [4]
        #     u:
        #       s:
        #         t:
        #           i:
        #             c: Readers: [5]

        self.assert_rwc_at_addresses({
            'r':        ([], None, {'a', 'u'}),
            'ra':       ([], None, {'z', 'd'}),
            'rad':      ([], None, {'o', 'i'}),
            'radi':     ([], None, {'s', 'x'}),
            'radix':    ([1], None, {}),
            'radish':   ([2], None, {}),
            'radon':    ([3], None, {}),
            'razzle':   ([4], None, {}),
            'ru':       ([], None, {'s'}),
            'rust':     ([], None, {'i'}),
            'rustic':   ([5], None, {}),
        })

        self.assert_rw_count(5, 0)

        self.assert_rw_preds_at_addresses({
            'r':        ({}, {1, 2, 3, 4, 5}),
            'rad':      ({}, {1, 2, 3}),
            'radi':     ({}, {1, 2}),
            'radix':    ({}, {1}),
        })

        # 2) Add readers at addresses that are initial segments
        #    of existing node addresses.

        self.add_readers({
            'rad': 6,
            'rust': 7
        })

        # ROOT:
        #   r:
        #     a:
        #       d: Readers: [6]
        #         o:
        #           n: Readers: [3]
        #         i:
        #           x: Readers: [1]
        #           s:
        #             h: Readers: [2]
        #       z:
        #         z:
        #           l:
        #             e: Readers: [4]
        #     u:
        #       s:
        #         t: Readers: [7]
        #           i:
        #             c: Readers: [5]

        self.assert_rwc_at_addresses({
            'r':        ([], None, {'a', 'u'}),
            'ra':       ([], None, {'z', 'd'}),
            'rad':      ([6], None, {'o', 'i'}),
            'radi':     ([], None, {'s', 'x'}),
            'radix':    ([1], None, {}),
            'radish':   ([2], None, {}),
            'radon':    ([3], None, {}),
            'razzle':   ([4], None, {}),
            'ru':       ([], None, {'s'}),
            'rust':     ([7], None, {'i'}),
            'rustic':   ([5], None, {}),
        })

        self.assert_rw_count(7, 0)

        self.assert_rw_preds_at_addresses({
            'ra':       ({}, {1, 2, 3, 4, 6}),
            'ru':       ({}, {5, 7}),
        })

        # 3) Add a writer in the middle of the tree.

        self.set_writer('radi', 8)

        # ROOT:
        #   r:
        #     u:
        #       s:
        #         t: Readers: [7]
        #           i:
        #             c: Readers: [5]
        #     a:
        #       d: Readers: [6]
        #         o:
        #           n: Readers: [3]
        #         i: Writer: 8
        #       z:
        #         z:
        #           l:
        #             e: Readers: [4]

        self.assert_no_nodes_at_addresses(
            'radix',
            'radish'
        )

        self.assert_rwc_at_addresses({
            'r':        ([], None, {'a', 'u'}),
            'ra':       ([], None, {'z', 'd'}),
            'rad':      ([6], None, {'o', 'i'}),
            'radi':     ([], 8, {}),
            'radon':    ([3], None, {}),
            'razzle':   ([4], None, {}),
            'ru':       ([], None, {'s'}),
            'rust':     ([7], None, {'i'}),
            'rustic':   ([5], None, {}),
        })

        self.assert_rw_count(5, 1)

        self.assert_rw_preds_at_addresses({
            'rad':      ({8}, {3, 6, 8}),
            'radi':     ({8}, {6, 8}),
            'radical':  ({8}, {6, 8}),
        })

        # 4) Add readers to existing nodes.

        self.add_readers({
            'rad': 9,
            'radi': 10,
            'radio': 11,
            'radon': 12,
            'rust': 13
        })

        # ROOT:
        #   r:
        #     u:
        #       s:
        #         t: Readers: [7, 13]
        #           i:
        #             c: Readers: [5]
        #     a:
        #       d: Readers: [6, 9]
        #         o:
        #           n: Readers: [3, 12]
        #         i: Writer: 8 Readers: [10]
        #           o: Readers: [11]
        #       z:
        #         z:
        #           l:
        #             e: Readers: [4]

        self.assert_rwc_at_addresses({
            'r':        ([], None, {'a', 'u'}),
            'ra':       ([], None, {'z', 'd'}),
            'rad':      ([6, 9], None, {'o', 'i'}),
            'radi':     ([10], 8, {'o'}),
            'radio':    ([11], None, {}),
            'radon':    ([3, 12], None, {}),
            'razzle':   ([4], None, {}),
            'ru':       ([], None, {'s'}),
            'rust':     ([7, 13], None, {'i'}),
            'rustic':   ([5], None, {}),
        })

        self.assert_rw_count(10, 1)

        self.assert_rw_preds_at_addresses({
            'rad':      ({8}, {6, 9, 10, 8, 11, 3, 12}),
            'ru':       ({}, {7, 13, 5}),
        })

        # 5) Add a writer to a new node.

        self.set_writer('radii', 14)

        # ROOT:
        #   r:
        #     u:
        #       s:
        #         t: Readers: [7, 13]
        #           i:
        #             c: Readers: [5]
        #     a:
        #       d: Readers: [6, 9]
        #         o:
        #           n: Readers: [3, 12]
        #         i: Writer: 8 Readers: [10]
        #           o: Readers: [11]
        #           i: Writer: 14
        #       z:
        #         z:
        #           l:
        #             e: Readers: [4]

        self.assert_rwc_at_addresses({
            'r':        ([], None, {'a', 'u'}),
            'ra':       ([], None, {'z', 'd'}),
            'rad':      ([6, 9], None, {'o', 'i'}),
            'radi':     ([10], 8, {'o', 'i'}),
            'radii':    ([], 14, {}),
            'radio':    ([11], None, {}),
            'radon':    ([3, 12], None, {}),
            'razzle':   ([4], None, {}),
            'ru':       ([], None, {'s'}),
            'rust':     ([7, 13], None, {'i'}),
            'rustic':   ([5], None, {}),
        })

        self.assert_rw_count(10, 2)

        self.assert_rw_preds_at_addresses({
            'radi':     ({8, 14}, {6, 9, 10, 8, 14, 11}),
            'radii':    ({14}, {6, 9, 10, 14}),
            'radio':    ({8}, {6, 9, 10, 8, 11}),
        })

        # 6) Add writers in the middle of the tree.

        self.set_writers({
            'rust': 15,
            'rad': 16
        })

        # ROOT:
        #   r:
        #     u:
        #       s:
        #         t: Writer: 15
        #     a:
        #       d: Writer: 16
        #       z:
        #         z:
        #           l:
        #             e: Readers: [4]

        self.assert_no_nodes_at_addresses(
            'radi',
            'radii',
            'radio',
            'radon',
            'rustic'
        )

        self.assert_rwc_at_addresses({
            'r':        ([], None, {'a', 'u'}),
            'ra':       ([], None, {'z', 'd'}),
            'rad':      ([], 16, {}),
            'razzle':   ([4], None, {}),
            'ru':       ([], None, {'s'}),
            'rust':     ([], 15, {}),
        })

        self.assert_rw_count(1, 2)

        self.assert_rw_preds_at_addresses({
            'r':        ({16, 15}, {16, 4, 15}),
            'ru':       ({15}, {15}),
            'rust':     ({15}, {15}),
            'rustic':   ({15}, {15}),
        })

        # 7) Add readers to upper nodes.

        self.add_readers({
            'r': 17,
            'ra': 18,
            'ru': 19,
        })

        # ROOT:
        #   r: Readers: [17]
        #     u: Readers: [19]
        #       s:
        #         t: Writer: 15
        #     a: Readers: [18]
        #       d: Writer: 16
        #       z:
        #         z:
        #           l:
        #             e: Readers: [4]

        self.assert_rwc_at_addresses({
            'r':        ([17], None, {'a', 'u'}),
            'ra':       ([18], None, {'z', 'd'}),
            'rad':      ([], 16, {}),
            'razzle':   ([4], None, {}),
            'ru':       ([19], None, {'s'}),
            'rust':     ([], 15, {}),
        })

        self.assert_rw_count(4, 2)

        self.assert_rw_preds_at_addresses({
            'r':        ({15, 16}, {17, 19, 15, 18, 16, 4}),
            'ru':       ({15}, {17, 19, 15}),
        })

        # 8) Add readers to nodes with writers.

        self.add_readers({
            'rad': 20,
            'rust': 21
        })

        # ROOT:
        #   r: Readers: [17]
        #     u: Readers: [19]
        #       s:
        #         t: Writer: 15 Readers: [21]
        #     a: Readers: [18]
        #       d: Writer: 16 Readers: [20]
        #       z:
        #         z:
        #           l:
        #             e: Readers: [4]

        self.assert_rwc_at_addresses({
            '':         ([], None, {'r'}),
            'r':        ([17], None, {'a', 'u'}),
            'ra':       ([18], None, {'z', 'd'}),
            'rad':      ([20], 16, {}),
            'razzle':   ([4], None, {}),
            'ru':       ([19], None, {'s'}),
            'rust':     ([21], 15, {}),
        })

        self.assert_rw_count(6, 2)

        self.assert_rw_preds_at_addresses({
            '':         ({16, 15}, {17, 18, 20, 16, 4, 19, 21, 15}),
            'rad':      ({16}, {17, 18, 20, 16}),
            'rust':     ({15}, {17, 19, 21, 15}),
        })

        # 9) Add readers to new top nodes.

        self.add_readers({
            's': 22,
            't': 23,
        })

        # ROOT:
        #   t: Readers: [23]
        #   s: Readers: [22]
        #   r: Readers: [17]
        #     u: Readers: [19]
        #       s:
        #         t: Writer: 15 Readers: [21]
        #     a: Readers: [18]
        #       d: Writer: 16 Readers: [20]
        #       z:
        #         z:
        #           l:
        #             e: Readers: [4]

        self.assert_rwc_at_addresses({
            '':         ([], None, {'r', 's', 't'}),
            'r':        ([17], None, {'a', 'u'}),
            'ra':       ([18], None, {'z', 'd'}),
            'rad':      ([20], 16, {}),
            'razzle':   ([4], None, {}),
            'ru':       ([19], None, {'s'}),
            'rust':     ([21], 15, {}),
            's':        ([22], None, {}),
            't':        ([23], None, {}),
        })

        self.assert_rw_count(8, 2)

        self.assert_rw_preds_at_addresses({
            's':        ({}, {22}),
            't':        ({}, {23}),
            'r':        ({16, 15}, {17, 18, 20, 16, 4, 19, 21, 15}),
        })

        # 10) Add writer to top node.

        self.set_writer('s', 24)

        # ROOT:
        #   t: Readers: [23]
        #   s: Writer: 24
        #   r: Readers: [17]
        #     u: Readers: [19]
        #       s:
        #         t: Writer: 15 Readers: [21]
        #     a: Readers: [18]
        #       d: Writer: 16 Readers: [20]
        #       z:
        #         z:
        #           l:
        #             e: Readers: [4]

        self.assert_rwc_at_addresses({
            'r':        ([17], None, {'a', 'u'}),
            'ra':       ([18], None, {'z', 'd'}),
            'rad':      ([20], 16, {}),
            'razzle':   ([4], None, {}),
            'ru':       ([19], None, {'s'}),
            'rust':     ([21], 15, {}),
            's':        ([], 24, {}),
            't':        ([23], None, {}),
        })

        self.assert_rw_count(7, 3)

        self.assert_rw_preds_at_addresses({
            's':       ({24}, {24}),
            't':       ({}, {23}),
            'r':       ({16, 15}, {17, 18, 20, 16, 4, 19, 21, 15}),
        })

        # 11) Add readers to upper nodes, then add writers.

        self.add_readers({
            'ra': 25,
            'ru': 26,
        })

        self.set_writers({
            'ra': 27,
            'ru': 28,
        })

        # ROOT:
        #   t: Readers: [23]
        #   s: Writer: 24
        #   r: Readers: [17]
        #     u: Writer: 28
        #     a: Writer: 27

        self.assert_rwc_at_addresses({
            'r':        ([17], None, {'a', 'u'}),
            'ra':       ([], 27, {}),
            'ru':       ([], 28, {}),
            's':        ([], 24, {}),
            't':        ([23], None, {}),
        })

        self.assert_no_nodes_at_addresses(
            'rad',
            'razzle',
            'rust',
        )

        self.assert_rw_preds_at_addresses({
            'r':        ({27, 28}, {17, 27, 28}),
            'ra':       ({27}, {17, 27}),
            'rad':      ({27}, {17, 27}),
        })

        # 12) Add writer to top node, then add reader.

        self.set_writer('r', 29)
        self.add_reader('r', 30)

        # ROOT:
        #   t: Readers: [23]
        #   s: Writer: 24
        #   r: Writer: 29 Readers: [30]

        self.assert_rwc_at_addresses({
            '':         ([], None, {'r', 's', 't'}),
            'r':        ([30], 29, {}),
            's':        ([], 24, {}),
            't':        ([23], None, {}),
        })

        self.assert_no_nodes_at_addresses(
            'ra',
            'ru',
        )

        self.assert_rw_count(2, 2)

        self.assert_rw_preds_at_addresses({
            'r':        ({29}, {30, 29}),
            'roger':    ({29}, {30, 29}),
            'ebert':   ({}, {}),
        })

        # 13) Add writer to root

        self.set_writer('', 0)

        # ROOT: Writer: 0

        self.assert_rwc_at_addresses({
            '':        ([], 0, {})
        })

        self.assert_no_nodes_at_addresses(
            'r',
            's',
            't'
        )

        self.assert_rw_count(0, 1)

        self.assert_rw_preds_at_addresses({
            '':         ({0}, {0}),
            'r':        ({0}, {0}),
            's':        ({0}, {0}),
            'rabbit':   ({0}, {0}),
        })

    def test_initial_segment_addresses(self):
        '''Tests addresses with and without common initial segments
        '''

        expected = (
            ('c', 1),
            ('ca', 2),
            ('cat', 3),
        )

        for address, val in expected:
            self.set_writer(address, val)
            self.add_reader(address, val)

        # ROOT:
        #   c: Writer: 1 Readers: [1]
        #     a: Writer: 2 Readers: [2]
        #       t: Writer: 3 Readers: [3]

        self.assert_rwc_at_addresses({
            '':         ([], None, {'c'}),
            'c':        ([1], 1, {'a'}),
            'ca':       ([2], 2, {'t'}),
            'cat':      ([3], 3, {}),
        })

        self.assert_rw_count(3, 3)

        # 'cath' isn't on the tree, so it should have
        # the same predecessors as 'cat'

        self.assert_rw_preds_at_addresses({
            '':         ({1, 2, 3}, {1, 2, 3}),
            'c':        ({1, 2, 3}, {1, 2, 3}),
            'ca':       ({2, 3}, {1, 2, 3}),
            'cat':      ({3}, {1, 2, 3}),
            'cath':     ({3}, {1, 2, 3}),
        })

        # add reader and writer at an address with a common initial segment

        self.set_writer('carp', 4)
        self.add_reader('carp', 4)

        # ROOT:
        #   c: Writer: 1 Readers: [1]
        #     a: Writer: 2 Readers: [2]
        #       r:
        #         p: Writer: 4 Readers: [4]
        #       t: Writer: 3 Readers: [3]

        self.assert_rwc_at_addresses({
            '':         ([], None, {'c'}),
            'c':        ([1], 1, {'a'}),
            'ca':       ([2], 2, {'t', 'r'}),
            'cat':      ([3], 3, {}),
            'carp':     ([4], 4, {}),
        })

        self.assert_rw_count(4, 4)

        self.assert_rw_preds_at_addresses({
            '':         ({1, 2, 3, 4}, {1, 2, 3, 4}),
            'c':        ({1, 2, 3, 4}, {1, 2, 3, 4}),
            'ca':       ({2, 3, 4}, {1, 2, 3, 4}),
            'cat':      ({3}, {1, 2, 3}),
            'cath':     ({3}, {1, 2, 3}),
            'carp':     ({4}, {1, 2, 4}),
        })

        # add reader and writer at an address with no common initial segment

        self.set_writer('dog', 5)
        self.add_reader('dog', 5)

        # ROOT:
        #   c: Writer: 1 Readers: [1]
        #     a: Writer: 2 Readers: [2]
        #       r:
        #         p: Writer: 4 Readers: [4]
        #       t: Writer: 3 Readers: [3]
        #   d:
        #     o:
        #       g: Writer: 5 Readers: [5]

        self.assert_rwc_at_addresses({
            '':         ([], None, {'c', 'd'}),
            'c':        ([1], 1, {'a'}),
            'ca':       ([2], 2, {'t', 'r'}),
            'cat':      ([3], 3, {}),
            'carp':     ([4], 4, {}),
            'dog':      ([5], 5, {}),
        })

        self.assert_rw_count(5, 5)

        self.assert_rw_preds_at_addresses({
            '':         ({1, 2, 3, 4, 5}, {1, 2, 3, 4, 5}),
            'c':        ({1, 2, 3, 4}, {1, 2, 3, 4}),
            'ca':       ({2, 3, 4}, {1, 2, 3, 4}),
            'cat':      ({3}, {1, 2, 3}),
            'cath':     ({3}, {1, 2, 3}),
            'carp':     ({4}, {1, 2, 4}),
            'dog':      ({5}, {5}),
        })

        # check predecessors of an address that isn't on the tree at all

        self.assert_rw_preds_at_addresses({
            'yak':      ({}, {}),
        })

        # add readers to root and check again

        self.add_reader('', 6)
        self.add_reader('', 7)

        # ROOT: Readers: [6, 7]
        #   c: Writer: 1 Readers: [1]
        #     a: Writer: 2 Readers: [2]
        #       r:
        #         p: Writer: 4 Readers: [4]
        #       t: Writer: 3 Readers: [3]
        #   d:
        #     o:
        #       g: Writer: 5 Readers: [5]

        self.assert_rwc_at_addresses({
            '':         ([6, 7], None, {'c', 'd'}),
            'c':        ([1], 1, {'a'}),
            'ca':       ([2], 2, {'t', 'r'}),
            'cat':      ([3], 3, {}),
            'carp':     ([4], 4, {}),
            'dog':      ([5], 5, {}),
        })

        self.assert_rw_count(7, 5)

        self.assert_rw_preds_at_addresses({
            '':         ({1, 2, 3, 4, 5}, {1, 2, 3, 4, 5, 6, 7}),
            'c':        ({1, 2, 3, 4}, {1, 2, 3, 4, 6, 7}),
            'ca':       ({2, 3, 4}, {1, 2, 3, 4, 6, 7}),
            'cat':      ({3}, {1, 2, 3, 6, 7}),
            'cath':     ({3}, {1, 2, 3, 6, 7}),
            'carp':     ({4}, {1, 2, 4, 6, 7}),
            'dog':      ({5}, {5, 6, 7}),
            'yak':      ({}, {6, 7}),
        })

    def test_add_writers_to_same_node(self):
        '''Adds a series of writers one after the other
        to a single node, verifying after each new writer
        that there is nothing else at that node and that
        there is just one writer in the whole tree.
        '''

        # Set writer num at 'address'
        for num in range(10):
            self.set_writer('plum', num)

            # ROOT:
            #   p:
            #     l:
            #       u:
            #         m: Writer: ,num

            self.assert_rwc_at_addresses({
                '':     ([], None, {'p'}),
                'p':    ([], None, {'l'}),
                'pl':   ([], None, {'u'}),
                'plu':  ([], None, {'m'}),
                'plum': ([], num, {}),
            })

            self.assert_rw_count(0, 1)

            self.assert_rw_preds_at_addresses({
                '':     ({num}, {num}),
                'p':    ({num}, {num}),
                'pl':   ({num}, {num}),
                'plu':  ({num}, {num}),
                'plum': ({num}, {num}),
            })

    def test_add_lists_of_readers(self):
        '''Tests multiple readers at nodes
        '''

        for address in ('p', 'pu', 'pug'):
            self.set_writer(address, 0)
            for i in range(1, 4):
                self.add_reader(address, i)

        # ROOT:
        #   p: Writer: 0 Readers: [1, 2, 3]
        #     u: Writer: 0 Readers: [1, 2, 3]
        #       g: Writer: 0 Readers: [1, 2, 3]

        self.assert_rwc_at_addresses({
            '':         ([], None, {'p'}),
            'p':        ([1, 2, 3], 0, {'u'}),
            'pu':       ([1, 2, 3], 0, {'g'}),
            'pug':      ([1, 2, 3], 0, {}),
        })

        self.assert_no_nodes_at_addresses('pugs')

        self.assert_rw_count(9, 3)

        self.assert_rw_preds_at_addresses({
            '':         ({0}, {0, 1, 2, 3}),
            'p':        ({0}, {0, 1, 2, 3}),
            'pu':       ({0}, {0, 1, 2, 3}),
            'pug':      ({0}, {0, 1, 2, 3}),
            'pugs':     ({0}, {0, 1, 2, 3}),
        })

        # add a writer and verify that downstream readers are gone

        self.set_writer('pu', 4)

        # ROOT:
        #   p: Writer: 0 Readers: [1, 2, 3]
        #     u: Writer: 4

        self.assert_rwc_at_addresses({
            '':         ([], None, {'p'}),
            'p':        ([1, 2, 3], 0, {'u'}),
            'pu':       ([], 4, {}),
        })

        self.assert_no_nodes_at_addresses('pug', 'pugs')

        self.assert_rw_count(3, 2)

        self.assert_rw_preds_at_addresses({
            '':         ({0, 4}, {0, 1, 2, 3, 4}),
            'p':        ({0, 4}, {0, 1, 2, 3, 4}),
            'pu':       ({4}, {1, 2, 3, 4}),
        })

    def test_long_addresses(self):
        """Tests predecessor tree with len-64 addresses and token size 2
        """

        self.tree = PredecessorTree(token_size=2)

        address_a = \
            'ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb'
        address_b = \
            '3e23e8160039594a33894f6564e1b1348bbd7a0088d42c4acb73eeaed59c009d'

        self.add_readers({
            address_a: 'txn1',
            address_b: 'txn2'
        })

        self.assert_rwc_at_addresses({
            address_a:  (['txn1'], None, {}),
            address_b:  (['txn2'], None, {})
        })

        # Set a writer for address_a.
        self.set_writer(address_a, 'txn1')

        # Verify address_a now contains txn1 as the writer, with no
        # readers set.

        # Verify address_b didn't change when address_a was modified.

        self.assert_rwc_at_addresses({
            address_a:  ([], 'txn1', {}),
            address_b:  (['txn2'], None, {})
        })

        # Set a writer for a prefix of address_b.
        address_c = address_b[0:4]

        self.set_writer(address_c, 'txn3')

        # Verify address_c now contains txn3 as the writer, with
        # no readers set and no children.

        # Verify address_a didn't change when address_c was modified.
        self.assert_rwc_at_addresses({
            address_a:  ([], 'txn1', {}),
            address_c:  ([], 'txn3', {})
        })

        # Verify address_b now returns None
        self.assert_no_nodes_at_addresses(address_b)

        # Add readers for address_a, address_b
        self.add_readers({
            address_a: 'txn1',
            address_b: 'txn2'
        })

        # Verify address_c now contains txn3 as the writer, with
        # no readers set and 'e8' as a child.
        self.assert_rwc_at_addresses({
            address_a:  (['txn1'], 'txn1', {}),
            address_b:  (['txn2'], None, {}),
            address_c:  ([], 'txn3', ['e8'])
        })

        self.assert_rw_preds_at_addresses({
            address_a:  ({'txn1'}, {'txn1'}),
            address_b:  ({'txn3'}, {'txn3', 'txn2'}),
            address_c:  ({'txn3'}, {'txn3', 'txn2'}),
        })

        self.assert_rw_count(2, 2)


    # assertions

    def assert_rwc_at_addresses(self, expected_dict):
        '''
        Asserts the readers, writer, and children at an address

        expected_dict = {address: (readers, writer, children)}
        '''

        self.show_tree()


        for address, rwc in expected_dict.items():
            error_msg = 'Address "{}": '.format(address) + 'incorrect {}'

            readers, writer, children = rwc
            node = self.get_node(address)

            self.assertIsNotNone(node)
            self.assertEqual(
                readers,
                node.readers,
                error_msg.format('readers'))
            self.assertEqual(
                writer,
                node.writer,
                error_msg.format('writer'))
            self.assertEqual(
                set(children),
                set(node.children.keys()),
                error_msg.format('children'))

    def assert_no_nodes_at_addresses(self, *addresses):
        for address in addresses:
            node = self.get_node(address)
            self.assertIsNone(
                node,
                'Address "{}": unexpected node'.format(address))

    def assert_rw_count(self, reader_count, writer_count):
        '''
        Asserts the total number of readers and writers in the tree
        '''

        def count_readers(node=None):
            if node is None:
                node = self.get_node('') # root node
            count = len(node.readers)
            for child in node.children:
                next_node = node.children[child]
                count += count_readers(next_node)
            return count

        def count_writers(node=None):
            if node is None:
                node = self.get_node('') # root node
            count = 1 if node.writer is not None else 0
            for child in node.children:
                next_node = node.children[child]
                count += count_writers(next_node)
            return count

        error_msg = 'Incorrect {} count'

        self.assertEqual(reader_count, count_readers(), error_msg.format('reader'))
        self.assertEqual(writer_count, count_writers(), error_msg.format('writer'))

    def assert_rw_preds_at_addresses(self, rw_pred_dict):
        '''
        Asserts the read predecessors and write predecessors at an address

        rw_pred_dict = {address: (read_preds, write_preds)}
        '''

        for address, rw_preds in rw_pred_dict.items():
            error_msg = 'Address "{}": '.format(address) + 'incorrect {} predecesors'

            read_preds, write_preds = rw_preds

            self.assertEqual(
                self.tree.find_read_predecessors(address),
                set(read_preds),
                error_msg.format('read'))

            self.assertEqual(
                self.tree.find_write_predecessors(address),
                set(write_preds),
                error_msg.format('write'))

    # basic tree operations (for convenience)

    def add_readers(self, reader_dict):
        '''
        reader_dict = {address: reader}
        '''
        for address, reader in reader_dict.items():
            self.add_reader(address, reader)

    def set_writers(self, writer_dict):
        '''
        writer_dict = {address: writer}

        The order in which writers are added matters, since they can
        overwrite each other. If a specific order is required,
        an OrderedDict should be used.
        '''
        for address, writer in writer_dict.items():
            self.set_writer(address, writer)

    def add_reader(self, address, txn):
        self.tree.add_reader(address, txn)

    def set_writer(self, address, txn):
        self.tree.set_writer(address, txn)

    def get_node(self, address):
        return self.tree.get(address)

    # display

    def show_tree(self):
        output = tree_to_string(self.tree).split('\n')
        for line in output:
            LOGGER.debug(line)


def tree_to_string(tree):
    return node_to_string(tree._root)

def node_to_string(node, indent=2):
    string = '\nROOT:' if indent == 2 else ''

    writer = node.writer
    if writer is not None:
        string += ' Writer: {}'.format(writer)

    readers = node.readers
    if readers:
        string += ' Readers: {}'.format(readers)

    for child_address in node.children:
        string += '\n' + ' ' * indent
        string += '{}:'.format(child_address)
        child_node = node.children[child_address]
        string += node_to_string(child_node, indent + 2)

    return string

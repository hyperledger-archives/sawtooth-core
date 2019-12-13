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

# pylint: disable=too-many-lines,invalid-name

import unittest
import hashlib
import os
import shutil
import tempfile
import threading
import time

from sawtooth_signing import create_context
from sawtooth_signing import CryptoFactory

from sawtooth_validator.protobuf import transaction_pb2

from sawtooth_validator.execution.context_manager import ContextManager
from sawtooth_validator.execution.scheduler_exceptions import SchedulerError
from sawtooth_validator.execution.scheduler_serial import SerialScheduler
from sawtooth_validator.execution.scheduler_parallel import ParallelScheduler
from sawtooth_validator.database.native_lmdb import NativeLmdbDatabase
from sawtooth_validator.state.merkle import MerkleDatabase

from test_scheduler.yaml_scheduler_tester import create_batch
from test_scheduler.yaml_scheduler_tester import create_transaction


def _get_address_from_txn(txn_info):
    txn_header = transaction_pb2.TransactionHeader()
    txn_header.ParseFromString(txn_info.txn.header)
    inputs_or_outputs = list(txn_header.inputs)
    address_b = inputs_or_outputs[0]
    return address_b


def create_address(payload):
    return hashlib.sha512(payload.encode()).hexdigest()[0:70]


class TestSchedulers(unittest.TestCase):
    def __init__(self, test_name):
        super().__init__(test_name)
        self._temp_dir = None

    def setUp(self):
        self._temp_dir = tempfile.mkdtemp()

        database = NativeLmdbDatabase(
            os.path.join(self._temp_dir, 'test_schedulers.lmdb'),
            indexes=MerkleDatabase.create_index_configuration(),
            _size=10 * 1024 * 1024)

        self._context_manager = ContextManager(database)

        self._context = create_context('secp256k1')
        self._crypto_factory = CryptoFactory(self._context)

    def tearDown(self):
        self._context_manager.stop()
        shutil.rmtree(self._temp_dir)

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
                                      first_state_root,
                                      always_persist=False)
        return context_manager, scheduler

    def test_parallel_dependencies(self):
        """Tests that transactions dependent on other transactions will fail
        their batch, if the dependency fails
        """

        context_manager, scheduler = self._setup_parallel_scheduler()
        self._dependencies(scheduler, context_manager)

    def test_serial_dependencies(self):
        """Tests that transactions dependent on other transactions will fail
        their batch, if the dependency fails
        """

        context_manager, scheduler = self._setup_serial_scheduler()
        self._dependencies(scheduler, context_manager)

    def _dependencies(self, scheduler, context_manager):
        """Tests that transactions dependent on other transactions will fail
        their batch, if the dependency fails.

            1        2    3   4   5
        dependency--> B       D   F
        [A, B, C] [D, E] [F] [G] [H]
               x <------- invalid
        Notes:
            1. Add 5 batches with 8 txns with dependencies as in the diagram.
            2. Run through the scheduler setting all the transaction results,
               including the single invalid txn, C.
            3. Assert the batch validity, that there are 2 valid batches,
               3 and 5.

        """
        private_key = self._context.new_random_private_key()
        signer = self._crypto_factory.new_signer(private_key)

        transaction_validity = {}

        # 1.

        txn_a, _ = create_transaction(
            payload='A'.encode(),
            signer=signer)

        transaction_validity[txn_a.header_signature] = True

        txn_b, _ = create_transaction(
            payload='B'.encode(),
            signer=signer)

        transaction_validity[txn_b.header_signature] = True

        txn_c, _ = create_transaction(
            payload='C'.encode(),
            signer=signer)

        transaction_validity[txn_c.header_signature] = False

        batch_1 = create_batch(
            transactions=[txn_a, txn_b, txn_c],
            signer=signer)

        txn_d, _ = create_transaction(
            payload='D'.encode(),
            signer=signer)

        transaction_validity[txn_d.header_signature] = True

        txn_e, _ = create_transaction(
            payload='E'.encode(),
            signer=signer,
            dependencies=[txn_b.header_signature])

        transaction_validity[txn_e.header_signature] = True

        batch_2 = create_batch(
            transactions=[txn_d, txn_e],
            signer=signer)

        txn_f, _ = create_transaction(
            payload='F'.encode(),
            signer=signer)

        transaction_validity[txn_f.header_signature] = True

        batch_3 = create_batch(
            transactions=[txn_f],
            signer=signer)

        txn_g, _ = create_transaction(
            payload='G'.encode(),
            signer=signer,
            dependencies=[txn_d.header_signature])

        transaction_validity[txn_g.header_signature] = True

        batch_4 = create_batch(
            transactions=[txn_g],
            signer=signer)

        txn_h, _ = create_transaction(
            payload='H'.encode(),
            signer=signer,
            dependencies=[txn_f.header_signature])

        transaction_validity[txn_h.header_signature] = True

        batch_5 = create_batch(
            transactions=[txn_h],
            signer=signer)

        for batch in [batch_1, batch_2, batch_3, batch_4, batch_5]:
            scheduler.add_batch(batch)

        # 2.
        scheduler.finalize()
        scheduler_iter = iter(scheduler)
        while not scheduler.complete(block=False):
            txn_info = next(scheduler_iter)
            context_id = context_manager.create_context(
                state_hash=txn_info.state_hash,
                base_contexts=txn_info.base_context_ids,
                inputs=[_get_address_from_txn(txn_info)],
                outputs=[_get_address_from_txn(txn_info)])
            txn_id = txn_info.txn.header_signature
            validity = transaction_validity[txn_id]

            scheduler.set_transaction_execution_result(
                txn_signature=txn_id,
                is_valid=validity,
                context_id=context_id)

        # 3.
        for i, batch_info in enumerate(
                [(batch_1, False),
                 (batch_2, False),
                 (batch_3, True),
                 (batch_4, False),
                 (batch_5, True)]):
            batch, validity = batch_info[0], batch_info[1]
            batch_id = batch.header_signature
            result = scheduler.get_batch_execution_result(batch_id)
            self.assertEqual(
                result.is_valid,
                validity,
                "Batch {} was {} when it should have been {}".format(
                    i + 1,
                    'valid' if result.is_valid else 'invalid',
                    'valid' if validity else 'invalid'))
            txn_results = scheduler.get_transaction_execution_results(batch_id)
            # Check that a result was returned for every transaction
            result_txn_ids = [result.signature for result in txn_results]
            batch_txn_ids = [txn.header_signature
                             for txn in batch.transactions]
            self.assertEqual(result_txn_ids, batch_txn_ids)
            if validity:
                self.assertTrue(all(txn.is_valid for txn in txn_results))

    def test_serial_fail_fast(self):
        """Tests that transactions that are already determined to be in an
        invalid batch due to a prior transaction being invalid, won't run.
        """

        _, scheduler = self._setup_serial_scheduler()
        self._fail_fast(scheduler)

    def _fail_fast(self, scheduler):
        """Tests that transactions that are already determined to be in an
        invalid batch due to a prior transaction being invalid, won't run.
          x
        [ A B C ] [ D E F]
                    B
        Notes:
             1. Create an invalid transaction, txn A, and put it in a batch
                with txn B. Create a transaction, txn C, that depends on txn B
                and put it in a batch with txn D.

             2. Add the batches to the scheduler and call finalize.

             3. Assert that only txn A is run.
        """

        private_key = self._context.new_random_private_key()
        signer = self._crypto_factory.new_signer(private_key)

        transaction_validity = {}

        txn_a, _ = create_transaction(
            payload='A'.encode(),
            signer=signer)

        transaction_validity[txn_a.header_signature] = False

        txn_b, _ = create_transaction(
            payload='B'.encode(),
            signer=signer)

        txn_c, _ = create_transaction(
            payload='C'.encode(),
            signer=signer)

        batch_1 = create_batch(transactions=[txn_a, txn_b, txn_c],
                               signer=signer)

        txn_d, _ = create_transaction(
            payload='D'.encode(),
            signer=signer,
            dependencies=[txn_b.header_signature])

        txn_e, _ = create_transaction(
            payload='E'.encode(),
            signer=signer)

        txn_f, _ = create_transaction(
            payload='F'.encode(),
            signer=signer)

        batch_2 = create_batch(
            transactions=[txn_d, txn_e, txn_f],
            signer=signer)

        scheduler.add_batch(batch_1)
        scheduler.add_batch(batch_2)
        scheduler.finalize()

        scheduler_iter = iter(scheduler)
        while not scheduler.complete(block=False):
            try:
                txn_from_scheduler = next(scheduler_iter)
            except StopIteration:
                break
            txn_id = txn_from_scheduler.txn.header_signature

            self.assertEqual(txn_id,
                             txn_a.header_signature,
                             "Only Transaction A is run, not txn {}"
                             "".format(txn_from_scheduler.txn.payload))

            validity = transaction_validity[txn_id]
            scheduler.set_transaction_execution_result(
                txn_signature=txn_id,
                is_valid=validity,
                context_id=None)

        scheduler_iter2 = iter(scheduler)
        txn_info_from_2 = next(scheduler_iter2)
        txn_id_from_2 = txn_info_from_2.txn.header_signature
        self.assertEqual(txn_id_from_2, txn_a.header_signature,
                         "Only Transaction A is run, not "
                         "txn {}".format(txn_info_from_2.txn.payload))
        with self.assertRaises(StopIteration):
            next(scheduler_iter2)

    def test_serial_wildcarded_unschedule(self):
        context_manager, scheduler = self._setup_serial_scheduler()

        self._test_wildcarded_unschedule(
            scheduler=scheduler,
            context_manager=context_manager)

    def test_parallel_wildcarded_unschedule(self):
        context_manager, scheduler = self._setup_parallel_scheduler()

        self._test_wildcarded_unschedule(
            scheduler=scheduler,
            context_manager=context_manager)

    def _test_wildcarded_unschedule(self, scheduler, context_manager):
        """Tests interaction of the context manager and scheduler when
        addresses are wildcarded. The error condition is that this
        will raise a KeyError.

        Notes:
            1) Add two batches, each with one transaction, with wildcarded
               inputs and outputs.
            2) Create a context.
            3) Set the transaction result as valid.
            4) Get the next transaction and create a context.
            5) Unschedule the schedule.
            6) Make a Get on the context manager.

        """

        private_key = self._context.new_random_private_key()
        signer = self._crypto_factory.new_signer(private_key)

        txn1, _ = create_transaction(
            payload='A'.encode(),
            signer=signer,
            inputs=[create_address('A')[0:40]],
            outputs=[create_address('A')[0:40]])

        batch_1 = create_batch(
            [txn1],
            signer=signer)

        txn2, _ = create_transaction(
            payload='A'.encode(),
            signer=signer,
            inputs=[create_address('A')[0:40]])

        batch_2 = create_batch(
            [txn2],
            signer=signer)

        # 1
        scheduler.add_batch(batch=batch_1)
        scheduler.add_batch(batch=batch_2)

        # 2
        txn_info = scheduler.next_transaction()

        header = transaction_pb2.TransactionHeader()
        header.ParseFromString(txn_info.txn.header)
        inputs = list(header.inputs)
        outputs = list(header.outputs)

        ctx_id1 = context_manager.create_context(
            state_hash=txn_info.state_hash,
            base_contexts=txn_info.base_context_ids,
            inputs=inputs,
            outputs=outputs)

        # 3
        scheduler.set_transaction_execution_result(
            txn_signature=txn_info.txn.header_signature,
            is_valid=True,
            context_id=ctx_id1)

        # 4
        txn_info_2 = scheduler.next_transaction()

        header = transaction_pb2.TransactionHeader()
        header.ParseFromString(txn_info_2.txn.header)
        inputs = list(header.inputs)
        outputs = list(header.outputs)

        ctx_id2 = context_manager.create_context(
            state_hash=txn_info_2.state_hash,
            base_contexts=txn_info_2.base_context_ids,
            inputs=inputs,
            outputs=outputs)

        # 5
        scheduler.unschedule_incomplete_batches()
        scheduler.finalize()
        scheduler.complete(block=True)

        # 6
        context_manager.get(ctx_id2, address_list=[create_address('A')])

    def test_serial_unschedule(self):
        context_manager, scheduler = self._setup_serial_scheduler()

        self._test_unschedule(
            scheduler=scheduler,
            context_manager=context_manager)

    def test_parallel_unschedule(self):
        context_manager, scheduler = self._setup_parallel_scheduler()

        self._test_unschedule(
            scheduler=scheduler,
            context_manager=context_manager)

    def _test_unschedule(self, scheduler, context_manager):
        """Tests that each of the top level methods on scheduler can be
        called after unscheduling.

        Notes:

        - The test creates two batches, the first containing one txn,
          the second containing two.
        - The first batch's txn is completed, and therefore should be
          included in the final result.
        - The second batch's first txn is marked as "in-flight", and therefore
          a response is expected.
        - With a cancel before receiving the result, setting the txn result
          should not cause any errors (it should be ignored).
        """

        private_key = self._context.new_random_private_key()
        signer = self._crypto_factory.new_signer(private_key)

        txn1a, _ = create_transaction(
            payload='A'.encode(),
            signer=signer,
            inputs=[create_address('A')[0:40]],
            outputs=[create_address('A')[0:40]])

        batch_1 = create_batch(
            [txn1a],
            signer=signer)

        txn2a, _ = create_transaction(
            payload='A'.encode(),
            signer=signer,
            inputs=[create_address('A')[0:40]])

        txn2B, _ = create_transaction(
            payload='B'.encode(),
            signer=signer,
            inputs=[create_address('B')[0:40]])

        batch_2 = create_batch(
            [txn2a, txn2B],
            signer=signer)

        # 1
        scheduler.add_batch(batch=batch_1)
        scheduler.add_batch(batch=batch_2)

        sched_iter = iter(scheduler)

        # 2
        txn_info1a = next(sched_iter)
        header = transaction_pb2.TransactionHeader()
        header.ParseFromString(txn_info1a.txn.header)
        inputs = list(header.inputs)
        outputs = list(header.outputs)

        ctx_id1a = context_manager.create_context(
            state_hash=txn_info1a.state_hash,
            inputs=inputs,
            outputs=outputs,
            base_contexts=txn_info1a.base_context_ids)

        # 3
        scheduler.set_transaction_execution_result(
            txn_info1a.txn.header_signature,
            False,
            ctx_id1a)

        # 4
        txn_info2a = next(sched_iter)
        header = transaction_pb2.TransactionHeader()
        header.ParseFromString(txn_info2a.txn.header)
        inputs = list(header.inputs)
        outputs = list(header.outputs)

        ctx_id2a = context_manager.create_context(
            state_hash=txn_info2a.state_hash,
            inputs=inputs,
            outputs=outputs,
            base_contexts=txn_info2a.base_context_ids)

        # 5
        scheduler.unschedule_incomplete_batches()
        scheduler.set_transaction_execution_result(
            txn_info2a.txn.header_signature,
            True,
            ctx_id2a)

    def test_serial_completion_on_finalize(self):
        """Tests that iteration will stop when finalized is called on an
        otherwise complete serial scheduler.
        """

        _, scheduler = self._setup_serial_scheduler()
        self._completion_on_finalize(scheduler)

    def test_parallel_completion_on_finalize(self):
        """Tests that iteration will stop when finalized is called on an
        otherwise complete parallel scheduler.
        """

        _, scheduler = self._setup_parallel_scheduler()
        self._completion_on_finalize(scheduler)

    def _completion_on_finalize(self, scheduler):
        """Tests that iteration will stop when finalized is called on an
        otherwise complete scheduler.

        Notes:
            Adds one batch and transaction, then verifies the iterable
            returns that transaction. Sets the execution result and
            then calls finalize. Since the the scheduler is complete
            (all transactions have had results set, and it's been
            finalized), we should get a StopIteration. This check is
            useful in making sure the finalize() can occur after all
            set_transaction_execution_result()s have been performed,
            because in a normal situation, finalize will probably
            occur prior to those calls.

        This test should work for both a serial and parallel scheduler.

        """

        private_key = self._context.new_random_private_key()
        signer = self._crypto_factory.new_signer(private_key)

        txn, _ = create_transaction(
            payload='a'.encode(),
            signer=signer)

        batch = create_batch(
            transactions=[txn],
            signer=signer)

        iterable = iter(scheduler)

        scheduler.add_batch(batch)

        scheduled_txn_info = next(iterable)
        self.assertIsNotNone(scheduled_txn_info)
        self.assertEqual(txn.payload, scheduled_txn_info.txn.payload)
        scheduler.set_transaction_execution_result(
            txn.header_signature, False, None)

        scheduler.finalize()

        with self.assertRaises(StopIteration):
            next(iterable)

    def test_serial_completion_on_finalize_only_when_done(self):
        """Tests that complete will only be true when the serial scheduler
        has had finalize called and all txns have execution result set.
        """

        _, scheduler = self._setup_serial_scheduler()
        self._completion_on_finalize_only_when_done(scheduler)

    def test_parallel_completion_on_finalize_only_when_done(self):
        """Tests that complete will only be true when the parallel scheduler
        has had finalize called and all txns have execution result set.
        """

        _, scheduler = self._setup_parallel_scheduler()
        self._completion_on_finalize_only_when_done(scheduler)

    def _completion_on_finalize_only_when_done(self, scheduler):
        """Tests that complete will only be true when the scheduler
        has had finalize called and all txns have execution result set.

        Notes:
            Adds one batch and transaction, then verifies the iterable returns
            that transaction.  Finalizes then sets the execution result. The
            schedule should not be marked as complete until after the
            execution result is set.

            This check is useful in making sure the finalize() can
            occur after all set_transaction_execution_result()s have
            been performed, because in a normal situation, finalize
            will probably occur prior to those calls.

        This test should work for both a serial and parallel scheduler.

        """
        private_key = self._context.new_random_private_key()
        signer = self._crypto_factory.new_signer(private_key)

        txn, _ = create_transaction(
            payload='a'.encode(),
            signer=signer)

        batch = create_batch(
            transactions=[txn],
            signer=signer)

        iterable = iter(scheduler)

        scheduler.add_batch(batch)

        scheduled_txn_info = next(iterable)
        self.assertIsNotNone(scheduled_txn_info)
        self.assertEqual(txn.payload, scheduled_txn_info.txn.payload)
        scheduler.finalize()
        self.assertFalse(scheduler.complete(block=False))
        scheduler.set_transaction_execution_result(
            txn.header_signature, False, None)
        self.assertTrue(scheduler.complete(block=False))

        with self.assertRaises(StopIteration):
            next(iterable)

    def test_serial_add_batch_after_empty_iteration(self):
        """Tests that iterations of the serial scheduler will continue
        as result of add_batch().
        """

        _, scheduler = self._setup_serial_scheduler()
        self._add_batch_after_empty_iteration(scheduler)

    def test_parallel_add_batch_after_empty_iteration(self):
        """Tests that iterations of the parallel scheduler will continue
        as result of add_batch().
        """

        _, scheduler = self._setup_parallel_scheduler()
        self._add_batch_after_empty_iteration(scheduler)

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
        private_key = self._context.new_random_private_key()
        signer = self._crypto_factory.new_signer(private_key)

        # Create a basic transaction and batch.
        txn, _ = create_transaction(
            payload='a'.encode(),
            signer=signer)
        batch = create_batch(
            transactions=[txn],
            signer=signer)

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
        self.assertEqual(txn.payload, thread.txn_info.txn.payload)

        # Continue with normal shutdown/cleanup.
        scheduler.finalize()
        scheduler.set_transaction_execution_result(
            txn.header_signature, False, None)
        with self.assertRaises(StopIteration):
            next(iterable)

    def test_serial_valid_batch_invalid_batch(self):
        """Tests the squash function. That the correct state hash is found
        at the end of valid and invalid batches, similar to block publishing.
        """

        context_manager, scheduler = self._setup_serial_scheduler()
        self._add_valid_batch_invalid_batch(scheduler, context_manager)

    def test_parallel_add_valid_batch_invalid_batch(self):
        """Tests the squash function. That the correct state hash is found
        at the end of valid and invalid batches, similar to block publishing.
        """

        context_manager, scheduler = self._setup_parallel_scheduler()
        self._add_valid_batch_invalid_batch(scheduler, context_manager)

    def _add_valid_batch_invalid_batch(self, scheduler, context_manager):
        """Tests the squash function. That the correct state hash is found
        at the end of valid and invalid batches, similar to block publishing.

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
        private_key = self._context.new_random_private_key()
        signer = self._crypto_factory.new_signer(private_key)

        # 1)
        batch_signatures = []
        for names in [['a', 'b'], ['invalid', 'c'], ['d', 'e']]:
            batch_txns = []
            for name in names:
                txn, _ = create_transaction(
                    payload=name.encode(),
                    signer=signer)

                batch_txns.append(txn)

            batch = create_batch(
                transactions=batch_txns,
                signer=signer)

            batch_signatures.append(batch.header_signature)
            scheduler.add_batch(batch)
        scheduler.finalize()
        # 2)
        sched1 = iter(scheduler)
        invalid_payload = hashlib.sha512('invalid'.encode()).hexdigest()
        while not scheduler.complete(block=False):
            try:
                txn_info = next(sched1)
            except StopIteration:
                break
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

        address_a = _get_address_from_txn(txn_info_a)

        txn_info_b = next(sched2)
        address_b = _get_address_from_txn(txn_info_b)

        next(sched2)

        txn_info_d = next(sched2)
        address_d = _get_address_from_txn(txn_info_d)

        txn_info_e = next(sched2)
        address_e = _get_address_from_txn(txn_info_e)

        database = NativeLmdbDatabase(
            os.path.join(self._temp_dir,
                         '_add_valid_batch_invalid_batch.lmdb'),
            indexes=MerkleDatabase.create_index_configuration(),
            _size=10 * 1024 * 1024)
        merkle_database = MerkleDatabase(database)
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

        private_key = self._context.new_random_private_key()
        signer = self._crypto_factory.new_signer(private_key)

        # 1)
        batch_signatures = []
        batches = []
        for names in [['a', 'b'], ['d', 'e'], ['invalid', 'c']]:
            batch_txns = []
            for name in names:
                txn, _ = create_transaction(
                    payload=name.encode(),
                    signer=signer)

                batch_txns.append(txn)

            batch = create_batch(
                transactions=batch_txns,
                signer=signer)
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
    def __init__(self, test_name):
        super().__init__(test_name)
        self._temp_dir = None

    def setUp(self):
        self._temp_dir = tempfile.mkdtemp()

        database = NativeLmdbDatabase(
            os.path.join(self._temp_dir, 'test_serial_schedulers.lmdb'),
            indexes=MerkleDatabase.create_index_configuration(),
            _size=10 * 1024 * 1024)

        self.context_manager = ContextManager(database)
        squash_handler = self.context_manager.get_squash_handler()
        self.first_state_root = self.context_manager.get_first_root()
        self.scheduler = SerialScheduler(squash_handler,
                                         self.first_state_root,
                                         always_persist=False)

        self._context = create_context('secp256k1')
        self._crypto_factory = CryptoFactory(self._context)

    def tearDown(self):
        self.context_manager.stop()
        shutil.rmtree(self._temp_dir)

    def test_transaction_order(self):
        """Tests the that transactions are returned in order added.

        Adds three batches with varying number of transactions, then tests
        that they are returned in the appropriate order when using an iterator.

        This test also creates a second iterator and verifies that both
        iterators return the same transactions.

        This test also finalizes the scheduler and verifies that StopIteration
        is thrown by the iterator.
        """
        private_key = self._context.new_random_private_key()
        signer = self._crypto_factory.new_signer(private_key)

        txns = []

        for names in [['a', 'b', 'c'], ['d', 'e'], ['f', 'g', 'h', 'i']]:
            batch_txns = []
            for name in names:
                txn, _ = create_transaction(
                    payload=name.encode(),
                    signer=signer)

                batch_txns.append(txn)
                txns.append(txn)

            batch = create_batch(
                transactions=batch_txns,
                signer=signer)

            self.scheduler.add_batch(batch)

        self.scheduler.finalize()

        iterable1 = iter(self.scheduler)
        iterable2 = iter(self.scheduler)
        for txn in txns:
            scheduled_txn_info = next(iterable1)
            self.assertEqual(scheduled_txn_info, next(iterable2))
            self.assertIsNotNone(scheduled_txn_info)
            self.assertEqual(txn.payload, scheduled_txn_info.txn.payload)
            c_id = self.context_manager.create_context(
                self.first_state_root,
                base_contexts=scheduled_txn_info.base_context_ids,
                inputs=[],
                outputs=[])
            self.scheduler.set_transaction_execution_result(
                txn.header_signature, True, c_id)

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
        private_key = self._context.new_random_private_key()
        signer = self._crypto_factory.new_signer(private_key)

        txns = []

        for names in [['a', 'b', 'c'], ['d', 'e'], ['f', 'g', 'h', 'i']]:
            batch_txns = []
            for name in names:
                txn, _ = create_transaction(
                    payload=name.encode(),
                    signer=signer)

                batch_txns.append(txn)
                txns.append(txn)

            batch = create_batch(
                transactions=batch_txns,
                signer=signer)

            self.scheduler.add_batch(batch)

        self.scheduler.finalize()

        iterable1 = iter(self.scheduler)
        for txn in txns:
            scheduled_txn_info = next(iterable1)
            self.assertFalse(self.scheduler.complete(block=False))

            c_id = self.context_manager.create_context(
                self.first_state_root,
                base_contexts=scheduled_txn_info.base_context_ids,
                inputs=[],
                outputs=[])
            self.scheduler.set_transaction_execution_result(
                txn.header_signature, True, c_id)

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
        private_key = self._context.new_random_private_key()
        signer = self._crypto_factory.new_signer(private_key)

        txns = []

        for name in ['a', 'b']:
            txn, _ = create_transaction(
                payload=name.encode(),
                signer=signer)

            txns.append(txn)

        batch = create_batch(
            transactions=txns,
            signer=signer)

        self.scheduler.add_batch(batch)

        scheduled_txn_info = self.scheduler.next_transaction()
        self.assertIsNotNone(scheduled_txn_info)
        self.assertEqual('a', scheduled_txn_info.txn.payload.decode())

        self.assertIsNone(self.scheduler.next_transaction())
        c_id = self.context_manager.create_context(
            self.first_state_root,
            base_contexts=scheduled_txn_info.base_context_ids,
            inputs=[],
            outputs=[])

        self.scheduler.set_transaction_execution_result(
            scheduled_txn_info.txn.header_signature,
            is_valid=True,
            context_id=c_id)

        scheduled_txn_info = self.scheduler.next_transaction()
        self.assertIsNotNone(scheduled_txn_info)
        self.assertEqual('b', scheduled_txn_info.txn.payload.decode())

    def test_unschedule_incomplete_transactions(self):
        """Tests that unschedule_incomplete_batches will remove
        batches above the mimimum.

        Given a schedule with two batches, ensure that a call to
        unschedule_incomplete_batches will leave one batch in the schedule.
        """
        private_key = self._context.new_random_private_key()
        signer = self._crypto_factory.new_signer(private_key)

        txn_a, _ = create_transaction(
            payload='A'.encode(),
            signer=signer)

        txn_b, _ = create_transaction(
            payload='B'.encode(),
            signer=signer)

        batch_1 = create_batch(transactions=[txn_a],
                               signer=signer)
        batch_2 = create_batch(transactions=[txn_b],
                               signer=signer)

        self.scheduler.add_batch(batch_1)
        self.scheduler.add_batch(batch_2)

        self.scheduler.unschedule_incomplete_batches()
        self.scheduler.finalize()
        self.assertFalse(self.scheduler.complete(block=False))

        scheduled_txn_info = self.scheduler.next_transaction()
        self.assertIsNotNone(scheduled_txn_info)
        self.assertEqual('A', scheduled_txn_info.txn.payload.decode())

        c_id = self.context_manager.create_context(
            self.first_state_root,
            base_contexts=scheduled_txn_info.base_context_ids,
            inputs=[],
            outputs=[])

        self.scheduler.set_transaction_execution_result(
            scheduled_txn_info.txn.header_signature,
            is_valid=True,
            context_id=c_id)

        with self.assertRaises(StopIteration):
            scheduled_txn_info = self.scheduler.next_transaction()


class TestParallelScheduler(unittest.TestCase):
    def __init__(self, test_name):
        super().__init__(test_name)
        self._temp_dir = None

    def setUp(self):
        self._temp_dir = tempfile.mkdtemp()

        database = NativeLmdbDatabase(
            os.path.join(self._temp_dir, 'test_serial_schedulers.lmdb'),
            indexes=MerkleDatabase.create_index_configuration(),
            _size=10 * 1024 * 1024)

        self.context_manager = ContextManager(database)
        squash_handler = self.context_manager.get_squash_handler()
        self.first_state_root = self.context_manager.get_first_root()
        self.scheduler = ParallelScheduler(squash_handler,
                                           self.first_state_root,
                                           always_persist=False)

        self._context = create_context('secp256k1')
        self._crypto_factory = CryptoFactory(self._context)

    def tearDown(self):
        self.context_manager.stop()
        shutil.rmtree(self._temp_dir)

    def test_add_to_finalized_scheduler(self):
        """Tests that a finalized scheduler raise exception on add_batch().

        This test creates a scheduler, finalizes it, and calls add_batch().
        The result is expected to be a SchedulerError, since adding a batch
        to a finalized scheduler is invalid.
        """
        private_key = self._context.new_random_private_key()
        signer = self._crypto_factory.new_signer(private_key)

        # Finalize prior to attempting to add a batch.
        self.scheduler.finalize()

        txn, _ = create_transaction(
            payload='a'.encode(),
            signer=signer)

        batch = create_batch(
            transactions=[txn],
            signer=signer)

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
        private_key = self._context.new_random_private_key()
        signer = self._crypto_factory.new_signer(private_key)

        txn, _ = create_transaction(
            payload='a'.encode(),
            signer=signer)

        batch = create_batch(
            transactions=[txn],
            signer=signer)

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
        private_key = self._context.new_random_private_key()
        signer = self._crypto_factory.new_signer(private_key)

        txns = []

        for names in [['a', 'b', 'c'], ['d', 'e'], ['f', 'g', 'h', 'i']]:
            batch_txns = []
            for name in names:
                txn, _ = create_transaction(
                    payload=name.encode(),
                    signer=signer)

                batch_txns.append(txn)
                txns.append(txn)

            batch = create_batch(
                transactions=batch_txns,
                signer=signer)

            self.scheduler.add_batch(batch)

        iterable1 = iter(self.scheduler)
        iterable2 = iter(self.scheduler)
        for txn in txns:
            scheduled_txn_info = next(iterable1)
            self.assertEqual(scheduled_txn_info, next(iterable2))
            self.assertIsNotNone(scheduled_txn_info)
            self.assertEqual(txn.payload, scheduled_txn_info.txn.payload)
            c_id = self.context_manager.create_context(
                self.first_state_root,
                base_contexts=scheduled_txn_info.base_context_ids,
                inputs=[],
                outputs=[])
            self.scheduler.set_transaction_execution_result(
                txn.header_signature, True, c_id)

        self.scheduler.finalize()
        self.assertTrue(self.scheduler.complete(block=False))
        with self.assertRaises(StopIteration):
            next(iterable1)

    def test_transaction_order_with_dependencies(self):
        """Tests the that transactions are returned in the expected order given
        dependencies implied by state.

        Creates one batch with four transactions.
        """
        private_key = self._context.new_random_private_key()
        signer = self._crypto_factory.new_signer(private_key)

        txns = []
        headers = []

        txn, header = create_transaction(
            payload='a'.encode(),
            signer=signer)
        txns.append(txn)
        headers.append(header)

        txn, header = create_transaction(
            payload='b'.encode(),
            signer=signer)
        txns.append(txn)
        headers.append(header)

        txn, header = create_transaction(
            payload='aa'.encode(),
            signer=signer,
            inputs=['000000' + hashlib.sha512('a'.encode()).hexdigest()[:64]],
            outputs=['000000' + hashlib.sha512('a'.encode()).hexdigest()[:64]])
        txns.append(txn)
        headers.append(header)

        txn, header = create_transaction(
            payload='bb'.encode(),
            signer=signer,
            inputs=['000000' + hashlib.sha512('b'.encode()).hexdigest()[:64]],
            outputs=['000000' + hashlib.sha512('b'.encode()).hexdigest()[:64]])
        txns.append(txn)
        headers.append(header)

        batch = create_batch(
            transactions=txns,
            signer=signer)

        self.scheduler.add_batch(batch)
        self.scheduler.finalize()
        self.assertFalse(self.scheduler.complete(block=False))

        iterable = iter(self.scheduler)
        scheduled_txn_info = []

        self.assertEqual(2, self.scheduler.available())
        scheduled_txn_info.append(next(iterable))
        self.assertIsNotNone(scheduled_txn_info[0])
        self.assertEqual(txns[0].payload, scheduled_txn_info[0].txn.payload)
        self.assertFalse(self.scheduler.complete(block=False))

        self.assertEqual(1, self.scheduler.available())
        scheduled_txn_info.append(next(iterable))
        self.assertIsNotNone(scheduled_txn_info[1])
        self.assertEqual(txns[1].payload, scheduled_txn_info[1].txn.payload)
        self.assertFalse(self.scheduler.complete(block=False))

        self.assertEqual(0, self.scheduler.available())
        context_id1 = self.context_manager.create_context(
            state_hash=self.first_state_root,
            inputs=list(headers[1].inputs),
            outputs=list(headers[1].outputs),
            base_contexts=[])
        self.scheduler.set_transaction_execution_result(
            txns[1].header_signature, True, context_id1)

        self.assertEqual(1, self.scheduler.available())
        scheduled_txn_info.append(next(iterable))
        self.assertIsNotNone(scheduled_txn_info[2])
        self.assertEqual(txns[3].payload, scheduled_txn_info[2].txn.payload)
        self.assertFalse(self.scheduler.complete(block=False))

        self.assertEqual(0, self.scheduler.available())
        context_id2 = self.context_manager.create_context(
            state_hash=self.first_state_root,
            inputs=list(headers[0].inputs),
            outputs=list(headers[0].outputs),
            base_contexts=[context_id1])
        self.scheduler.set_transaction_execution_result(
            txns[0].header_signature, True, context_id2)

        self.assertEqual(1, self.scheduler.available())
        scheduled_txn_info.append(next(iterable))
        self.assertIsNotNone(scheduled_txn_info[3])
        self.assertEqual(txns[2].payload, scheduled_txn_info[3].txn.payload)
        self.assertFalse(self.scheduler.complete(block=False))

        self.assertEqual(0, self.scheduler.available())
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

        self.assertEqual(0, self.scheduler.available())
        self.assertTrue(self.scheduler.complete(block=False))
        with self.assertRaises(StopIteration):
            next(iterable)

        result = self.scheduler.get_batch_execution_result(
            batch.header_signature)
        self.assertIsNotNone(result)
        self.assertTrue(result.is_valid)

    def test_unschedule_incomplete_transactions(self):
        """Tests that unschedule_incomplete_batches will remove
        batches above the mimimum.

        Given a schedule with two batches, ensure that a call to
        unschedule_incomplete_batches will leave one batch in the schedule.
        """
        private_key = self._context.new_random_private_key()
        signer = self._crypto_factory.new_signer(private_key)

        txn_a, _ = create_transaction(
            payload='A'.encode(),
            signer=signer)

        txn_b, _ = create_transaction(
            payload='B'.encode(),
            signer=signer)

        batch_1 = create_batch(transactions=[txn_a],
                               signer=signer)
        batch_2 = create_batch(transactions=[txn_b],
                               signer=signer)

        self.scheduler.add_batch(batch_1)
        self.scheduler.add_batch(batch_2)

        self.scheduler.unschedule_incomplete_batches()
        self.scheduler.finalize()
        self.assertFalse(self.scheduler.complete(block=False))

        scheduled_txn_info = self.scheduler.next_transaction()
        self.assertIsNotNone(scheduled_txn_info)
        self.assertEqual('A', scheduled_txn_info.txn.payload.decode())

        c_id = self.context_manager.create_context(
            self.first_state_root,
            base_contexts=scheduled_txn_info.base_context_ids,
            inputs=[],
            outputs=[])

        self.scheduler.set_transaction_execution_result(
            scheduled_txn_info.txn.header_signature,
            is_valid=True,
            context_id=c_id)

        scheduled_txn_info = self.scheduler.next_transaction()
        self.assertIsNone(scheduled_txn_info)

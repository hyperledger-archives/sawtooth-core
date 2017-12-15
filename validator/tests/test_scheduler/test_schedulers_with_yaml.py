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
# ----------------------------------------------------------------------------

import unittest

import os

from sawtooth_validator.database import dict_database
from sawtooth_validator.execution.context_manager import ContextManager
from sawtooth_validator.execution.scheduler_parallel import ParallelScheduler
from sawtooth_validator.execution.scheduler_serial import SerialScheduler

from test_scheduler.yaml_scheduler_tester import SchedulerTester


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
                                      first_state_root,
                                      always_persist=False)
        return context_manager, scheduler

    def test_complex_batches_multiple_failures(self):
        """Tests the schedulers against the
        test_scheduler/data/complex_batches_multiple_failures.yaml file.

        Notes:
            This yaml file has 33 batches with several txns per batch,
            multiple implicit dependencies per txn, and several
            failed batches.
        """

        context_manager, scheduler = self._setup_parallel_scheduler()
        self._single_block_files_individually(
            scheduler=scheduler,
            context_manager=context_manager,
            name='complex_batches_multiple_failures.yaml')

        context_manager, scheduler = self._setup_parallel_scheduler()
        self._single_block_files_individually(
            scheduler=scheduler,
            context_manager=context_manager,
            name='complex_batches_multiple_failures.yaml',
            lifo=True)

        context_manager, scheduler = self._setup_parallel_scheduler()
        self._single_block_files_individually_alt(
            scheduler=scheduler,
            context_manager=context_manager,
            name='complex_batches_multiple_failures.yaml')

        context_manager, scheduler = self._setup_parallel_scheduler()
        self._single_block_files_individually_alt(
            scheduler=scheduler,
            context_manager=context_manager,
            name='complex_batches_multiple_failures.yaml',
            lifo=True)

        context_manager, scheduler = self._setup_serial_scheduler()
        self._single_block_files_individually(
            scheduler=scheduler,
            context_manager=context_manager,
            name='complex_batches_multiple_failures.yaml')

        context_manager, scheduler = self._setup_serial_scheduler()
        self._single_block_files_individually_alt(
            scheduler=scheduler,
            context_manager=context_manager,
            name='complex_batches_multiple_failures.yaml')

    def test_enclosing_writer_fails(self):
        """Tests the schedulers against the
        test_scheduler/data/enclosing_writer_fails.yaml file.

        Notes:
            This yaml file has failed batches that have txns that implicitly
            depend on multiple prior txns because they have the
            whole tree ('') in the inputs and outputs, and also are
            the implicit dependency of several subsequent txns. When
            the batch fails, those dependent txns need to be replayed with
            a different state.
        """

        context_manager, scheduler = self._setup_parallel_scheduler()
        self._single_block_files_individually(
            scheduler=scheduler,
            context_manager=context_manager,
            name='enclosing_writer_fails.yaml')

        context_manager, scheduler = self._setup_parallel_scheduler()
        self._single_block_files_individually(
            scheduler=scheduler,
            context_manager=context_manager,
            name='enclosing_writer_fails.yaml',
            lifo=True)

        context_manager, scheduler = self._setup_parallel_scheduler()
        self._single_block_files_individually_alt(
            scheduler=scheduler,
            context_manager=context_manager,
            name='enclosing_writer_fails.yaml')

        context_manager, scheduler = self._setup_parallel_scheduler()
        self._single_block_files_individually_alt(
            scheduler=scheduler,
            context_manager=context_manager,
            name='enclosing_writer_fails.yaml',
            lifo=True)

        context_manager, scheduler = self._setup_serial_scheduler()
        self._single_block_files_individually(
            scheduler=scheduler,
            context_manager=context_manager,
            name='enclosing_writer_fails.yaml')

        context_manager, scheduler = self._setup_serial_scheduler()
        self._single_block_files_individually_alt(
            scheduler=scheduler,
            context_manager=context_manager,
            name='enclosing_writer_fails.yaml')

    def test_dependencies(self):
        """Tests the schedulers against the
        test_scheduler/data/dependencies.yaml file.

        Notes:
            This yaml file has batches with transactions that have implicit
            dependencies, explicit dependencies, and multiple failed batches.
        """

        context_manager, scheduler = self._setup_parallel_scheduler()
        self._single_block_files_individually(
            scheduler=scheduler,
            context_manager=context_manager,
            name='dependencies.yaml')

        context_manager, scheduler = self._setup_parallel_scheduler()
        self._single_block_files_individually(
            scheduler=scheduler,
            context_manager=context_manager,
            name='dependencies.yaml',
            lifo=True)

        context_manager, scheduler = self._setup_parallel_scheduler()
        self._single_block_files_individually_alt(
            scheduler=scheduler,
            context_manager=context_manager,
            name='dependencies.yaml')

        context_manager, scheduler = self._setup_parallel_scheduler()
        self._single_block_files_individually_alt(
            scheduler=scheduler,
            context_manager=context_manager,
            name='dependencies.yaml',
            lifo=True)

        context_manager, scheduler = self._setup_serial_scheduler()
        self._single_block_files_individually(
            scheduler=scheduler,
            context_manager=context_manager,
            name='dependencies.yaml')

        context_manager, scheduler = self._setup_serial_scheduler()
        self._single_block_files_individually_alt(
            scheduler=scheduler,
            context_manager=context_manager,
            name='dependencies.yaml')

    def test_deletes(self):
        """Tests the schedulers against the
        test_scheduler/data/deletes_test.yaml file.

        Notes:
            This yaml file has complex batches with failures and transactions
            with deletes from the context manager.
        """

        context_manager, scheduler = self._setup_parallel_scheduler()
        self._single_block_files_individually(
            scheduler=scheduler,
            context_manager=context_manager,
            name='deletes_test.yaml')

        context_manager, scheduler = self._setup_parallel_scheduler()
        self._single_block_files_individually(
            scheduler=scheduler,
            context_manager=context_manager,
            name='deletes_test.yaml',
            lifo=True)

        context_manager, scheduler = self._setup_parallel_scheduler()
        self._single_block_files_individually_alt(
            scheduler=scheduler,
            context_manager=context_manager,
            name='deletes_test.yaml')

        context_manager, scheduler = self._setup_parallel_scheduler()
        self._single_block_files_individually_alt(
            scheduler=scheduler,
            context_manager=context_manager,
            name='deletes_test.yaml',
            lifo=True)

        context_manager, scheduler = self._setup_serial_scheduler()
        self._single_block_files_individually(
            scheduler=scheduler,
            context_manager=context_manager,
            name='deletes_test.yaml')

        context_manager, scheduler = self._setup_serial_scheduler()
        self._single_block_files_individually_alt(
            scheduler=scheduler,
            context_manager=context_manager,
            name='deletes_test.yaml')

    def test_complex_dependency_failures(self):
        """Tests the schedulers against the
        test_scheduler/data/complex_dependency_failures.yaml file.

        Notes:
            This yaml file has complex batches with failures and transactions
            with deletes from the context manager.
        """

        context_manager, scheduler = self._setup_parallel_scheduler()
        self._single_block_files_individually(
            scheduler=scheduler,
            context_manager=context_manager,
            name='complex_dependency_failures.yaml')

        context_manager, scheduler = self._setup_parallel_scheduler()
        self._single_block_files_individually(
            scheduler=scheduler,
            context_manager=context_manager,
            name='complex_dependency_failures.yaml',
            lifo=True)

        context_manager, scheduler = self._setup_parallel_scheduler()
        self._single_block_files_individually_alt(
            scheduler=scheduler,
            context_manager=context_manager,
            name='complex_dependency_failures.yaml')

        context_manager, scheduler = self._setup_parallel_scheduler()
        self._single_block_files_individually_alt(
            scheduler=scheduler,
            context_manager=context_manager,
            name='complex_dependency_failures.yaml',
            lifo=True)

        context_manager, scheduler = self._setup_serial_scheduler()
        self._single_block_files_individually(
            scheduler=scheduler,
            context_manager=context_manager,
            name='complex_dependency_failures.yaml')

        context_manager, scheduler = self._setup_serial_scheduler()
        self._single_block_files_individually_alt(
            scheduler=scheduler,
            context_manager=context_manager,
            name='complex_dependency_failures.yaml')

    def _single_block_files_individually_alt(self,
                                             scheduler,
                                             context_manager,
                                             name,
                                             lifo=False):
        """Tests scheduler(s) with yaml files that represent a single
        block.

        Notes:
            Tests that the serial scheduler has the correct batch validity
            and state hash, and that 1 state hash is produced.

        """

        file_name = self._path_to_yaml_file(name)
        tester = SchedulerTester(file_name)
        defined_batch_results_dict = tester.batch_results
        batch_results, txns_to_assert_state = tester.run_scheduler_alternating(
            scheduler=scheduler,
            context_manager=context_manager,
            txns_executed_fifo=not lifo)

        self._assertions(tester, defined_batch_results_dict,
                         batch_results,
                         txns_to_assert_state, name)

    def _single_block_files_individually(self,
                                         scheduler,
                                         context_manager,
                                         name,
                                         lifo=False):
        """Tests scheduler(s) with yaml files that represent a single
        block.

        Notes:
            Tests that the serial scheduler has the correct batch validity
            and state hash, and that 1 state hash is produced.

        """

        file_name = self._path_to_yaml_file(name)
        tester = SchedulerTester(file_name)
        defined_batch_results_dict = tester.batch_results
        batch_results, txns_to_assert_state = tester.run_scheduler(
            scheduler=scheduler,
            context_manager=context_manager,
            txns_executed_fifo=not lifo)

        self._assertions(tester, defined_batch_results_dict,
                         batch_results,
                         txns_to_assert_state, name)

    def _assertions(self, tester, defined_batch_results_dict,
                    batch_results, txns_to_assert_state, name):
        self.assert_batch_validity(
            defined_batch_results_dict,
            batch_results)

        for t_id in txns_to_assert_state:
            state_and_txn_context = txns_to_assert_state.get(t_id)
            if state_and_txn_context is not None:
                txn_context, state_found, state_assert = state_and_txn_context

                self.assertEqual(state_found, state_assert,
                                 "Transaction {} in batch {} has the wrong "
                                 "state in the context".format(
                                     txn_context.txn_num,
                                     txn_context.batch_num))

        self.assert_one_state_hash(batch_results=batch_results)

        sched_state_roots = self._get_state_roots(
            batch_results=batch_results)

        calc_state_hash = tester.compute_state_hashes_wo_scheduler()

        self.assertEqual(
            sched_state_roots,
            calc_state_hash,
            "The state hashes calculated by the scheduler for yaml file {}"
            " must be the same as calculated by the tester".format(name))

    def setUp(self):
        self._context_manager = ContextManager(dict_database.DictDatabase())

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
            self.assertEqual(
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
        self.assertEqual(len(state_roots), 1,
                         "The scheduler calculated more than one state "
                         "root when only one was expected")

    def _path_to_yaml_file(self, name):
        parent_dir = os.path.dirname(__file__)
        file_name = os.path.join(parent_dir, 'data', name)
        return file_name

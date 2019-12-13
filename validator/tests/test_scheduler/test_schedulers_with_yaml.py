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
import logging
import os
import shutil
import tempfile

from sawtooth_validator.database.native_lmdb import NativeLmdbDatabase
from sawtooth_validator.state.merkle import MerkleDatabase
from sawtooth_validator.execution.context_manager import ContextManager
from sawtooth_validator.execution.scheduler_parallel import ParallelScheduler
from sawtooth_validator.execution.scheduler_serial import SerialScheduler

from test_scheduler.yaml_scheduler_tester import SchedulerTester


LOGGER = logging.getLogger(__name__)


class TestSchedulersWithYaml(unittest.TestCase):
    def __init__(self, test_name):
        super().__init__(test_name)
        self._temp_dir = None

    def setUp(self):
        self._temp_dir = tempfile.mkdtemp()

        database = NativeLmdbDatabase(
            os.path.join(self._temp_dir, 'test_state_view.lmdb'),
            indexes=MerkleDatabase.create_index_configuration(),
            _size=10 * 1024 * 1024)

        self._context_manager = ContextManager(database)

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

    def _get_filenames(self):
        base_dir = os.path.abspath(os.path.dirname(__file__))
        data_dir = os.path.join(base_dir, 'data')

        filepaths = []
        for root, _, filenames in os.walk(data_dir):
            filepaths.extend(
                map(
                    lambda f, r=root: os.path.join(r, f),
                    filter(
                        lambda f: f.endswith('.yml') or f.endswith('.yaml'),
                        filenames)))
        return filepaths

    def test_all_yaml_files(self):
        """Tests the schedulers against each of the yaml files in the
        test_scheduler/data directory"""

        for file_path in self._get_filenames():
            try:
                context_manager, scheduler = self._setup_parallel_scheduler()
                self._single_block_files_individually(
                    scheduler=scheduler,
                    context_manager=context_manager,
                    name=file_path)

                context_manager, scheduler = self._setup_parallel_scheduler()
                self._single_block_files_individually(
                    scheduler=scheduler,
                    context_manager=context_manager,
                    name=file_path,
                    lifo=True)

                context_manager, scheduler = self._setup_parallel_scheduler()
                self._single_block_files_individually_alt(
                    scheduler=scheduler,
                    context_manager=context_manager,
                    name=file_path)

                context_manager, scheduler = self._setup_parallel_scheduler()
                self._single_block_files_individually_alt(
                    scheduler=scheduler,
                    context_manager=context_manager,
                    name=file_path,
                    lifo=True)

                context_manager, scheduler = self._setup_serial_scheduler()
                self._single_block_files_individually(
                    scheduler=scheduler,
                    context_manager=context_manager,
                    name=file_path)

                context_manager, scheduler = self._setup_serial_scheduler()
                self._single_block_files_individually_alt(
                    scheduler=scheduler,
                    context_manager=context_manager,
                    name=file_path)
            except AssertionError:
                LOGGER.warning("Failure on file %s", file_path)
                raise

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

        file_name = name
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

        file_name = name
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

        calc_state_hash = tester.compute_state_hashes_wo_scheduler(
            self._temp_dir)

        self.assertEqual(
            sched_state_roots,
            calc_state_hash,
            "The state hashes calculated by the scheduler for yaml file {}"
            " must be the same as calculated by the tester".format(name))

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

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
# ------------------------------------------------------------------------------

import unittest

from sawtooth_validator.database import dict_database
from sawtooth_validator.execution import context_manager
from sawtooth_validator.state.merkle import MerkleDatabase
from sawtooth_validator.state.state_delta_store import StateDeltaStore
from sawtooth_validator.protobuf.state_delta_pb2 import StateChange


class TestContextManager(unittest.TestCase):

    def setUp(self):
        self.database_of_record = dict_database.DictDatabase()
        self.state_delta_store = StateDeltaStore(dict_database.DictDatabase())
        self.context_manager = context_manager.ContextManager(
            self.database_of_record, self.state_delta_store)
        self.first_state_hash = self.context_manager.get_first_root()

        # used for replicating state hash through direct merkle tree updates
        self.database_results = dict_database.DictDatabase()

    def tearDown(self):
        self.context_manager.stop()

    def _create_address(self, value=None):
        """
        Args:
            value: (str)

        Returns: (str) sha512 of value or random

        """
        if value is None:
            value = time.time().hex()
        return hashlib.sha512(value.encode()).hexdigest()[:70]

    def _setup_context(self):
        # 1) Create transaction data
        first_transaction = {'inputs': [self._create_address(a) for a in
                                        ['aaaa', 'bbbb', 'cccc']],
                             'outputs': [self._create_address(a) for a in
                                         ['llaa', 'aall', 'nnnn']]}
        second_transaction = {
            'inputs': [self._create_address(a) for a in
                       ['aaaa', 'dddd']],
            'outputs': [self._create_address(a) for a in
                        ['zzzz', 'yyyy', 'tttt', 'qqqq']]
        }
        third_transaction = {
            'inputs': [self._create_address(a) for a in
                       ['eeee', 'dddd', 'ffff']],
            'outputs': [self._create_address(a) for a in
                        ['oooo', 'oozz', 'zzoo', 'ppoo', 'aeio']]
        }
        # 2) Create contexts based on that data
        context_id_1 = self.context_manager.create_context(
            state_hash=self.first_state_hash,
            base_contexts=[],
            inputs=first_transaction['inputs'],
            outputs=first_transaction['outputs'])
        context_id_2 = self.context_manager.create_context(
            state_hash=self.first_state_hash,
            base_contexts=[],
            inputs=second_transaction['inputs'],
            outputs=second_transaction['outputs'])
        context_id_3 = self.context_manager.create_context(
            state_hash=self.first_state_hash,
            base_contexts=[],
            inputs=third_transaction['inputs'],
            outputs=third_transaction['outputs'])

        # 3) Set addresses with values
        self.context_manager.set(context_id_1, [{self._create_address(a): v}
                                                for a, v in [('llaa', b'1'),
                                                             ('aall', b'2'),
                                                             ('nnnn', b'3')]])
        self.context_manager.set(context_id_2, [{self._create_address(a): v}
                                                for a, v in [('zzzz', b'9'),
                                                             ('yyyy', b'11'),
                                                             ('tttt', b'12'),
                                                             ('qqqq', b'13')]])
        self.context_manager.set(context_id_3, [{self._create_address(a): v}
                                                for a, v in [('oooo', b'25'),
                                                             ('oozz', b'26'),
                                                             ('zzoo', b'27'),
                                                             ('ppoo', b'28'),
                                                             ('aeio', b'29')]])

        # 4)
        context_id = self.context_manager.create_context(
            state_hash=self.first_state_hash,
            base_contexts=[context_id_1, context_id_2, context_id_3],
            inputs=[self._create_address(a)
                    for a in ['llaa', 'yyyy', 'tttt', 'zzoo']],
            outputs=[self._create_address(a)
                     for a in ['llaa', 'yyyy', 'tttt', 'zzoo', 'aeio']])
        return context_id

    def test_create_context_with_prior_state(self):
        """Tests context creation with prior state from base contexts.

        Notes:
            Set up the context:
                Create 3 prior contexts each with 3-5 addresses to set to.
                Make set calls to those addresses.
                Create 1 new context based on those three prior contexts.
                this test method:
            Test:
                Make a get call on addresses that are from prior state,
                making assertions about the correct values.
        """
        context_id = self._setup_context()

        self.assertEqual(self.context_manager.get(
            context_id,
            [self._create_address(a) for a in
             ['llaa', 'yyyy', 'tttt', 'zzoo']]),
            [(self._create_address(a), v) for a, v in
             [('llaa', b'1'),
             ('yyyy', b'11'),
             ('tttt', b'12'),
             ('zzoo', b'27')]])

    def test_squash(self):
        """Tests that squashing a context based on state from other
        contexts will result in the same merkle hash as updating the
        merkle tree with the same data.

        Notes:
            Set up the context

            Test:
                1) Make set calls on several of the addresses.
                2) Squash the context to get a new state hash.
                3) Apply all of the aggregate sets from all
                of the contexts, to another database with a merkle tree.
                4) Assert that the state hashes are the same.
                5) Assert that the state deltas have been stored
        """
        # 1)
        context_id = self._setup_context()
        self.context_manager.set(
            context_id,
            [{self._create_address(a): v} for a, v in
             [('yyyy', b'2'),
              ('tttt', b'4')]])

        # 2)
        squash = self.context_manager.get_squash_handler()
        resulting_state_hash = squash(self.first_state_hash, [context_id],
                                      persist=True)

        # 3)
        final_state_to_update = {self._create_address(a): v for a, v in
                                 [('llaa', b'1'),
                                  ('aall', b'2'),
                                  ('nnnn', b'3'),
                                  ('zzzz', b'9'),
                                  ('yyyy', b'2'),
                                  ('tttt', b'4'),
                                  ('qqqq', b'13'),
                                  ('oooo', b'25'),
                                  ('oozz', b'26'),
                                  ('zzoo', b'27'),
                                  ('ppoo', b'28'),
                                  ('aeio', b'29')]}

        test_merkle_tree = MerkleDatabase(self.database_results)
        test_resulting_state_hash = test_merkle_tree.update(
            final_state_to_update, virtual=False)
        # 4)
        self.assertEqual(resulting_state_hash, test_resulting_state_hash)
        state_changes = self.state_delta_store.get_state_deltas(
            resulting_state_hash)

        # 5)
        for addr, value in final_state_to_update.items():
            expected_state_change = StateChange(
                address=addr,
                value=value,
                type=StateChange.SET)

            self.assertTrue(expected_state_change in state_changes)

    def test_squash_no_updates(self):
        """Tests that squashing a context that has no state updates will return
           the starting state root hash.

        Notes:
            Set up the context

            Test:
                1) Squash the context.
                2) Assert that the state hash is the same as the starting
                hash.
                3) Assert that the state deltas have not been overwritten
        """
        self.state_delta_store.save_state_deltas(
            self.first_state_hash,
            [StateChange(address='aaa', value=b'xyz', type=StateChange.SET)])

        context_id = self.context_manager.create_context(
            state_hash=self.first_state_hash,
            base_contexts=[],
            inputs=[],
            outputs=[])
        # 1)
        squash = self.context_manager.get_squash_handler()
        resulting_state_hash = squash(self.first_state_hash, [context_id],
                                      persist=True)
        # 2
        self.assertIsNotNone(resulting_state_hash)
        self.assertEquals(resulting_state_hash, self.first_state_hash)

        # 3
        changes = self.state_delta_store.get_state_deltas(resulting_state_hash)

        self.assertEqual(
            [StateChange(address='aaa', value=b'xyz', type=StateChange.SET)],
            [c for c in changes])

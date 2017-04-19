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


class TestContextManager(unittest.TestCase):

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
            ['aaaa', 'bbbb', 'cccc', 'dddd']),
            [('aaaa', b'25'),
             ('bbbb', b'26'),
             ('cccc', b'27'),
             ('dddd', b'28')])

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
        """
        # 1)
        context_id = self._setup_context()
        self.context_manager.set(
            context_id,
            [{'bbbb': b'2'},
             {'eeee': b'4'}])

        # 2)
        squash = self.context_manager.get_squash_handler()
        resulting_state_hash = squash(self.first_state_hash, [context_id],
                                      persist=True)

        # 3)
        final_state_to_update = {
            'aaaa': b'25',
            'bbbb': b'2',
            'cccc': b'27',
            'dddd': b'28',
            'eeee': b'4'
        }

        test_merkle_tree = MerkleDatabase(self.database_results)
        test_resulting_state_hash = test_merkle_tree.update(
            final_state_to_update, virtual=False)
        # 4)
        self.assertEqual(resulting_state_hash, test_resulting_state_hash)

    def _setup_context(self):
        # 1) Create transaction data
        first_transaction = {'inputs': ['aaaa', 'bbbb', 'cccc'],
                             'outputs': ['aaaa', 'cccc', 'dddd']}
        second_transaction = {
            'inputs': ['aaaa', 'dddd'],
            'outputs': ['aaaa', 'bbbb', 'cccc', 'dddd']
        }
        third_transaction = {
            'inputs': ['eeee', 'dddd', 'ffff'],
            'outputs': ['aaaa', 'bbbb', 'cccc', 'dddd', 'eeee']
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
        self.context_manager.set(context_id_1, [{'aaaa': b'1'},
                                                {'cccc': b'2'},
                                                {'dddd': b'3'}])
        self.context_manager.set(context_id_2, [{'aaaa': b'9',
                                                 'bbbb': b'11',
                                                 'cccc': b'12',
                                                 'dddd': b'13'}])
        self.context_manager.set(context_id_3, [{'aaaa': b'25'},
                                                {'bbbb': b'26'},
                                                {'cccc': b'27'},
                                                {'dddd': b'28'},
                                                {'eeee': b'29'}])

        # 4)
        context_id = self.context_manager.create_context(
            state_hash=self.first_state_hash,
            base_contexts=[context_id_1, context_id_2, context_id_3],
            inputs=['aaaa', 'bbbb', 'cccc', 'dddd'],
            outputs=['aaaa', 'bbbb', 'cccc', 'dddd', 'eeee'])
        return context_id

    def setUp(self):
        self.database_of_record = dict_database.DictDatabase()
        self.context_manager = context_manager.ContextManager(
            self.database_of_record)
        self.first_state_hash = self.context_manager.get_first_root()

        # used for replicating state hash through direct merkle tree updates
        self.database_results = dict_database.DictDatabase()

    def tearDown(self):
        self.context_manager.stop()

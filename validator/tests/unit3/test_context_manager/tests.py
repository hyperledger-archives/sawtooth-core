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

from collections import namedtuple
import hashlib
import time

from sawtooth_validator.database import dict_database
from sawtooth_validator.execution import context_manager
from sawtooth_validator.state.merkle import MerkleDatabase
from sawtooth_validator.state.state_delta_store import StateDeltaStore
from sawtooth_validator.protobuf.state_delta_pb2 import StateChange


TestAddresses = namedtuple('TestAddresses',
                              ['inputs', 'outputs', 'reads', 'writes'])


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

    def _create_txn_inputs_outputs(self, start=None):
        """Create unique addresses that make up the inputs, outputs,
         reads, and writes that are involved in a context.

         Venn Diagram of relationship of disjoint sets that make up the
         inputs, outputs, reads, and writes.

         Knowledge of which disjoint set an address is a part of
         may give knowledge about a test failure in the context
         manager.

                    Inputs                      Outputs
            +----------+--------------------------+-----------+
            |          |                          |           |
            |  i___    |Reads       io__        Writes  _o__  |
            |          |                          |           |
            |    +-----------+-----------+---------------+    |
            |    |     |     |           |        |      |    |
            |    |     |     |           |        |      |    |
            |    |     |     |           |        |      |    |
            |    |     |     |           |        |      |    |
            |    |i_r_ | ior_|  iorw     |  io_w  | _o_w |    |
            |    |     |     |           |        |      |    |
            |    |     |     |           |        |      |    |
            |    |     |     |           |        |      |    |
            |    +-----------+-----------+---------------+    |
            |          |                          |           |
            |          |                          |           |
            +----------+--------------------------+-----------+

        Args:
            start (int): An integer to start the sequence of integers being
            hashed to addresses.

        Returns (namedtuple): An object that holds inputs, outputs, reads,
            and writes.

        """
        if start is None:
            start = 0
        iorw = [self._create_address(str(i)) for i in range(start,
                                                            start + 10)]
        i_r_ = [self._create_address(str(i)) for i in range(start + 10,
                                                            start + 20)]
        ior_ = [self._create_address(str(i)) for i in range(start + 20,
                                                            start + 30)]
        io__ = [self._create_address(str(i)) for i in range(start + 30,
                                                            start + 40)]
        io_w = [self._create_address(str(i)) for i in range(start + 40,
                                                            start + 50)]
        _o_w = [self._create_address(str(i)) for i in range(start + 50,
                                                            start + 60)]
        _o__ = [self._create_address(str(i)) for i in range(start + 60,
                                                            start + 70)]
        i___ = [self._create_address(str(i)) for i in range(start + 70,
                                                            start + 80)]
        addresses = TestAddresses(
            inputs=iorw + ior_ + io__ + io_w + i___,
            outputs=ior_ + io__ + io_w + _o__ + _o_w,
            reads=i_r_ + ior_,
            writes=io_w + _o_w
        )
        return addresses

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

    @unittest.skip("Support for context manager parallelization")
    def test_reads_from_context_w_several_writes(self):
        """Tests that those context values that have been written to the
        Merkle tree, or that have been set to a base_context, will have the
        correct value at the address for a given context.

                                               ->context_id_a1
                                               |              |
                                               |              |
                                               |              |
        sh0-->context_id1-->sh1-->context_a-----              -->context_id_b
                                               |              |
                                               |              |
                                               |              |
                                               |              |
                                               -->context_id_a2

        Notes:

            Test:
                1. From a Merkle Tree with only the root node in it, create a
                   context and set several values, and then squash that context
                   upon the first state hash.
                2. Create a context with no base context, based on
                   the merkle root computed from the first squash.
                   Assert that gets from this context will provide
                   values that were set in the first context.
                3. Write to all of the available outputs
                4. Create a new context based on context_a, from #2,
                5. Assert that gets from this context equal the values set
                   to Context A.
                6. Create a new context based on context_a and set values to
                   this context.
                7. Create a new context based on the 2 contexts made in 4 and 6
                8. From this context assert that gets equal the correct values
                   set in the prior contexts.
        """

        squash = self.context_manager.get_squash_handler()
        test_addresses = self._create_txn_inputs_outputs()
        # 1)
        context_id1 = self.context_manager.create_context(
            state_hash=self.first_state_hash,
            inputs=test_addresses.inputs,
            outputs=test_addresses.outputs,
            base_contexts=[])

        values1 = [bytes(i) for i in range(len(test_addresses.writes))]
        self.context_manager.set(
            context_id1,
            [{a: v} for a, v in zip(test_addresses.writes, values1)])
        sh1 = squash(
            state_root=self.first_state_hash,
            context_ids=[context_id1],
            persist=True)
        # 2)
        context_a = self.context_manager.create_context(
            state_hash=sh1,
            inputs=test_addresses.writes,  # read from every address written to
            outputs=test_addresses.outputs,
            base_contexts=[]
        )

        address_values = self.context_manager.get(
                context_a,
                test_addresses.writes
            )
        self.assertEquals(
            address_values,
            [(a, v) for a, v in zip(test_addresses.writes, values1)]
            )

        # 3)
        values2 = [bytes(v.encode()) for v in test_addresses.outputs]
        self.context_manager.set(
            context_id=context_a,
            address_value_list=[{a: v} for
                                a, v in zip(test_addresses.outputs, values2)])

        # 4)
        context_id_a1 = self.context_manager.create_context(
            state_hash=sh1,
            inputs=test_addresses.outputs,
            outputs=test_addresses.outputs,
            base_contexts=[context_a]
        )
        # 5)
        c_ida1_address_values = self.context_manager.get(
            context_id=context_id_a1,
            address_list=test_addresses.outputs
        )
        self.assertEquals(
            c_ida1_address_values,
            [(a, v) for a, v in zip(test_addresses.outputs, values2)]
        )

        # 6)
        test_addresses2 = self._create_txn_inputs_outputs(80)
        context_id_a2 = self.context_manager.create_context(
            state_hash=sh1,
            inputs=test_addresses2.inputs,
            outputs=test_addresses2.outputs,
            base_contexts=[context_a]
        )
        values3 = [bytes(v.encode()) for v in test_addresses2.writes]
        self.context_manager.set(
            context_id=context_id_a2,
            address_value_list=[{a: v} for
                                a, v in zip(test_addresses2.writes, values3)],
        )
        # 7)
        context_id_b = self.context_manager.create_context(
            state_hash=sh1,
            inputs=test_addresses2.writes + test_addresses.outputs,
            outputs=[],
            base_contexts=[context_id_a1, context_id_a2]
        )

        # 8)
        self.assertEquals(
            self.context_manager.get(
                context_id_b,
                test_addresses2.writes + test_addresses.outputs
            ),
            [(a, v) for a, v in zip(
                test_addresses2.writes + test_addresses.outputs,
                values3 + values2)]
        )

    @unittest.skip("Support for context manager parallelization")
    def test_state_root_after_parallel_ctx(self):
        """Tests that the correct state root is calculated after basing one
        context off of multiple contexts.

                              i=abcd
                              o=aaaa
                           +>context_1+
                           |  aaaa=1  |
                           |          |
               i=llll      |   i=bacd |      i=bbbb,aaaa
               o=llll      |   o=bbbb |      o=cccc,llll
        sh0--->ctx_0-->sh1>|-->context_2-+---->context_n---->sh2
               llll=5      |   bbbb=2 |      cccc=4
                           |          |      llll=8
                           |   i=abcd |
                           |   o=cccc |
                           +>context_3+
                               cccc=3

        Notes:
            Test:
                1. Create a context, set a value in it and squash it into a new
                   state hash.
                2. Create 3 contexts based off of the state root from #1.
                3. Set values at addresses to all three contexts.
                4. Base another context off of the contexts from #2.
                5. Set a value to an address in this context that has already
                   been set to in the non-base context.
                6. Squash the contexts producing a state hash and assert
                   that it equals a state hash obtained by manually updating
                   the merkle tree.
        """

        sh0 = self.first_state_hash
        # 1)
        squash = self.context_manager.get_squash_handler()
        ctx_1 = self.context_manager.create_context(
            state_hash=sh0,
            base_contexts=[],
            inputs=[self._create_address('llll')],
            outputs=[self._create_address('llll')]
        )
        self.context_manager.set(
            context_id=ctx_1,
            address_value_list=[{self._create_address('llll'): b'5'}]
        )

        sh1 = squash(
            state_root=sh0,
            context_ids=[ctx_1],
            persist=True
        )

        # 2)
        context_1 = self.context_manager.create_context(
            state_hash=sh1,
            base_contexts=[],
            inputs=[self._create_address('abcd')],
            outputs=[self._create_address('aaaa')]
        )
        context_2 = self.context_manager.create_context(
            state_hash=sh1,
            base_contexts=[],
            inputs=[self._create_address('bacd')],
            outputs=[self._create_address('bbbb')]
        )
        context_3 = self.context_manager.create_context(
            state_hash=sh1,
            base_contexts=[],
            inputs=[self._create_address('abcd')],
            outputs=[self._create_address('cccc'),
                     self._create_address('dddd')]
        )

        # 3)
        self.context_manager.set(
            context_id=context_1,
            address_value_list=[{self._create_address('aaaa'): b'1'}]
        )
        self.context_manager.set(
            context_id=context_2,
            address_value_list=[{self._create_address('bbbb'): b'2'}]
        )
        self.context_manager.set(
            context_id=context_3,
            address_value_list=[{self._create_address('cccc'): b'3'}]
        )

        # 4)
        context_n = self.context_manager.create_context(
            state_hash=sh1,
            base_contexts=[context_1, context_2, context_3],
            inputs=[self._create_address('bbbb'), self._create_address('aaaa')],
            outputs=[self._create_address('cccc'), self._create_address('llll')]
        )

        # 5)
        self.context_manager.set(
            context_id=context_n,
            address_value_list=[{self._create_address('cccc'): b'4',
                                 self._create_address('llll'): b'8'}]
        )

        # 6)
        cm_state_root = squash(
            state_root=sh1,
            context_ids=[context_n],
            persist=False)

        tree = MerkleDatabase(self.database_results)
        calc_state_root = tree.update({self._create_address('aaaa'): b'1',
                                       self._create_address('bbbb'): b'2',
                                       self._create_address('cccc'): b'4'})
        self.assertEquals(calc_state_root, cm_state_root)

    @unittest.skip("Support for context manager parallelization")
    def test_complex_basecontext_squash(self):
        """Tests complex context basing and squashing.
                                            i=qq,dd dd=0
                                            o=dd,pp pp=1
                                i=cc,aa  +->context_3_2a_1+|
                                o=dd,ll  |                 |
               i=aa,ab      +->context_2a|  i=aa    aa=0   |
               o=cc,ab      |   dd=10    |  o=aa,ll ll=1   |
        sh0->context_1-->sh1|   ll=11    +->context_3_2a_2+|->sh1
               cc=0         |   i=cc,aa  +->context_3_2b_1+|
               ab=1         |   o=nn,mm  |  i=nn,ba mm=0   |
                            +->context_2b|  o=mm,ba ba=1   |
                                nn=0     |                 |
                                mm=1     +->context_3_2b_2+|
                                            i=nn,oo ab=0
                                            o=ab,oo oo=1

        Notes:
            Test:
                1. Create a context off of the first state hash, set
                   addresses in it, and squash that context, getting a new
                   merkle root.
                2. Create 2 contexts with the context in # 1 as the base, and
                   for each of these contexts set addresses to values where the
                   outputs for each are disjoint.
                3. For each of these 2 contexts create 2 more contexts each
                   having one of the contexts in # 2 as the base context, and
                   set addresses to values.
                4. Squash the 4 contexts from #3 and assert the state hash
                   is equal to a manually computed state hash.
        """

        squash = self.context_manager.get_squash_handler()
        # 1)
        inputs_1 = [self._create_address('aa'),
                    self._create_address('ab')]
        outputs_1 = [self._create_address('cc'),
                     self._create_address('ab')]
        context_1 = self.context_manager.create_context(
            state_hash=self.first_state_hash,
            base_contexts=[],
            inputs=inputs_1,
            outputs=outputs_1)
        self.context_manager.set(
            context_id=context_1,
            address_value_list=[{a: v} for a, v in zip(
                outputs_1, [bytes(i) for i in range(len(outputs_1))])])

        sh1 = squash(
            state_root=self.first_state_hash,
            context_ids=[context_1],
            persist=True)

        # 2)
        inputs_2a = [self._create_address('cc'),
                     self._create_address('aa')]
        outputs_2a = [self._create_address('dd'),
                      self._create_address('ll')]
        context_2a = self.context_manager.create_context(
            state_hash=self.first_state_hash,
            base_contexts=[],
            inputs=inputs_2a,
            outputs=outputs_2a)

        inputs_2b = [self._create_address('cc'),
                     self._create_address('aa')]
        outputs_2b = [self._create_address('nn'),
                      self._create_address('mm')]
        context_2b = self.context_manager.create_context(
            state_hash=sh1,
            base_contexts=[],
            inputs=inputs_2b,
            outputs=outputs_2b)

        self.context_manager.set(
            context_id=context_2a,
            address_value_list=[{a: bytes(v)}
                                for a, v in zip(outputs_2a,
                                                range(10,
                                                      10 + len(outputs_2a)))]
        )
        self.context_manager.set(
            context_id=context_2b,
            address_value_list=[{a: bytes(v)}
                                for a, v in zip(outputs_2b,
                                                range(len(outputs_2b)))]
        )

        # 3)
        inputs_3_2a_1 = [self._create_address('qq'),
                         self._create_address('dd')]
        outputs_3_2a_1 = [self._create_address('dd'),
                          self._create_address('pp')]
        context_3_2a_1 = self.context_manager.create_context(
            state_hash=sh1,
            base_contexts=[context_2a],
            inputs=inputs_3_2a_1,
            outputs=outputs_3_2a_1
        )
        inputs_3_2a_2 = [self._create_address('aa')]
        outputs_3_2a_2 = [self._create_address('aa'),
                          self._create_address('ll')]
        context_3_2a_2 = self.context_manager.create_context(
            state_hash=sh1,
            base_contexts=[context_2a],
            inputs=inputs_3_2a_2,
            outputs=outputs_3_2a_2)

        inputs_3_2b_1 = [self._create_address('nn'),
                         self._create_address('ab')]
        outputs_3_2b_1 = [self._create_address('mm'),
                          self._create_address('ba')]
        context_3_2b_1 = self.context_manager.create_context(
            state_hash=sh1,
            base_contexts=[context_2b],
            inputs=inputs_3_2b_1,
            outputs=outputs_3_2b_1)

        inputs_3_2b_2 = [self._create_address('nn'),
                         self._create_address('oo')]
        outputs_3_2b_2 = [self._create_address('ab'),
                          self._create_address('oo')]
        context_3_2b_2 = self.context_manager.create_context(
            state_hash=sh1,
            base_contexts=[context_2b],
            inputs=inputs_3_2b_2,
            outputs=outputs_3_2b_2)

        self.context_manager.set(
            context_id=context_3_2a_1,
            address_value_list=[{a: bytes(v)}
                                for a, v in zip(outputs_3_2a_1,
                                                range(len(outputs_3_2a_1)))])
        self.context_manager.set(
            context_id=context_3_2a_2,
            address_value_list=[{a: bytes(v)}
                                for a, v in zip(outputs_3_2a_2,
                                                range(len(outputs_3_2a_2)))])
        self.context_manager.set(
            context_id=context_3_2b_1,
            address_value_list=[{a: bytes(v)}
                                for a, v in zip(outputs_3_2b_1,
                                                range(len(outputs_3_2b_1)))])
        self.context_manager.set(
            context_id=context_3_2b_2,
            address_value_list=[{a: bytes(v)}
                                for a, v in zip(outputs_3_2b_2,
                                                range(len(outputs_3_2b_2)))])

        # 4)
        sh2 = squash(
            state_root=sh1,
            context_ids=[context_3_2a_1, context_3_2a_2,
                         context_3_2b_1, context_3_2b_2],
            persist=False)

        tree = MerkleDatabase(self.database_results)
        state_hash_from_1 = tree.update(
            set_items={a: v for a, v in zip(outputs_1,
                                        [bytes(i)
                                         for i in range(len(outputs_1))])},
                                        virtual=False)
        self.assertEquals(state_hash_from_1, sh1,
                          "The manually calculated state hash from the first "
                          "context and the one calculated by squashing that "
                          "state hash should be the same")
        tree.set_merkle_root(state_hash_from_1)
        test_sh2 = tree.update(set_items={self._create_address('aa'): b'0',
                                          self._create_address('ab'): b'0',
                                          self._create_address('ba'): b'1',
                                          self._create_address('dd'): b'0',
                                          self._create_address('ll'): b'1',
                                          self._create_address('mm'): b'0',
                                          self._create_address('oo'): b'1',
                                          self._create_address('pp'): b'1',
                                          self._create_address('nn'): b'0',
                                          self._create_address('cc'): b'0'})

        self.assertEquals(sh2, test_sh2, "Manually calculated and context "
                                         "manager calculated merkle hashes "
                                         "are the same")

    def test_check_for_bad_combination(self):
        """Tests that the context manager will raise
        an exception if asked to combine contexts, either via base contexts 
        in create_context or via squash that shouldn't be
        combined because they share addresses that can't be determined by the
        scheduler to not have been parallel. This is a check on scheduler bugs.

        Examples where the context manager should raise an exception on
        duplicate addresses:
        1. Success
              i=a
              o=b
           +>ctx_1+
        dup|->b=3 |
           |      |
        sh0|      ----->state hash or context
           |  i=q |
           |  o=b |
           +>ctx_2+
        dup-->b=2
        2.
                      i=b
                      o=d
                   +>ctx_1a_1+
                   |  d=4    |
             i=a   |         |
             o=b   |         |
           +>ctx_1a|         |
           | b=2   |  i=b    |
           |       |  o=c    |
        sh0|       +>ctx_1a_2|
           |     dup-> c=7   |------>state hash or context
           |  i=a  +>ctx_1b_1|
           |  o=c  |         |
           +>ctx_1b|         |
        dup-->c=5  |  i=t    |
                   |  o=p    |
                   +>ctx_1b_2+
                      p=8

        3.
                      i=b
                      o=d
                   +>ctx_1a_1+
                   |  d=4    |   i=d,c
             i=a   |         |   o=n
             o=b   |         <>ctx_3a+
           +>ctx_1a|         |   n=5 |
           | b=2   |  i=b    |       |
           |       |  o=c    |       |
        sh0|       +>ctx_1a_2+       <----->state hash or context
           |   dup--> c=7            |
           |  i=a  +>ctx_1b_1+       |
           |  o=c  |         |  i=c  |
           +>ctx_1b|         |  o=q  |
              c=5  |  i=c    <>ctx_3b+
                   |  o=c    |  q=5
                   +>ctx_1b_2+
               dup--> c=1

        """

        # 1.
        squash = self.context_manager.get_squash_handler()
        sh0 = self.first_state_hash
        inputs_1 = [self._create_address('a')]
        outputs_1 = [self._create_address('b')]
        ctx_1 = self.context_manager.create_context(
            state_hash=sh0,
            base_contexts=[],
            inputs=inputs_1,
            outputs=outputs_1
        )
        self.context_manager.set(
            context_id=ctx_1,
            address_value_list=[{self._create_address('b'): b'3'}]
        )

        inputs_2 = [self._create_address('q')]
        outputs_2 = [self._create_address('b')]
        ctx_2 = self.context_manager.create_context(
            state_hash=sh0,
            base_contexts=[],
            inputs=inputs_2,
            outputs=outputs_2
        )
        self.context_manager.set(
            context_id=ctx_2,
            address_value_list=[{self._create_address('b'): b'2'}]
        )

        try:
            sh1 = squash(
                state_root=sh0,
                context_ids=[ctx_1, ctx_2],
                persist=True)
            self.fail("squash of two contexts with a duplicate address")
        except Exception:
            pass

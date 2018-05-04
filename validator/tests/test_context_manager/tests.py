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

# pylint: disable=too-many-lines,broad-except

import unittest

from collections import namedtuple
import hashlib
import os
import shutil
import tempfile
import time

from sawtooth_validator.database.native_lmdb import NativeLmdbDatabase
from sawtooth_validator.execution import context_manager
from sawtooth_validator.state.merkle import MerkleDatabase
from sawtooth_validator.protobuf.events_pb2 import Event


TestAddresses = namedtuple('TestAddresses',
                           ['inputs', 'outputs', 'reads', 'writes'])


class TestContextManager(unittest.TestCase):
    def __init__(self, test_name):
        super().__init__(test_name)
        self._temp_dir = None

    def setUp(self):
        self._temp_dir = tempfile.mkdtemp()

        self.database_of_record = NativeLmdbDatabase(
            os.path.join(self._temp_dir, 'db_of_record.lmdb'),
            indexes=MerkleDatabase.create_index_configuration(),
            _size=10 * 1024 * 1024)

        self.context_manager = context_manager.ContextManager(
            self.database_of_record)
        self.first_state_hash = self.context_manager.get_first_root()

        # used for replicating state hash through direct merkle tree updates
        self.database_results = NativeLmdbDatabase(
            os.path.join(self._temp_dir, 'db_results.lmdb'),
            indexes=MerkleDatabase.create_index_configuration(),
            _size=10 * 1024 * 1024)

    def tearDown(self):
        self.context_manager.stop()
        shutil.rmtree(self._temp_dir)

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
            inputs=[
                self._create_address(a)
                for a in ['llaa', 'yyyy', 'tttt', 'zzoo']
            ],
            outputs=[
                self._create_address(a)
                for a in ['llaa', 'yyyy', 'tttt', 'zzoo', 'aeio']
            ])
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
        iorw = [self._create_address(str(i)) for i in range(start, start + 10)]
        i_r_ = [
            self._create_address(str(i))
            for i in range(start + 10, start + 20)
        ]
        ior_ = [
            self._create_address(str(i))
            for i in range(start + 20, start + 30)
        ]
        io__ = [
            self._create_address(str(i))
            for i in range(start + 30, start + 40)
        ]
        io_w = [
            self._create_address(str(i))
            for i in range(start + 40, start + 50)
        ]
        _o_w = [
            self._create_address(str(i))
            for i in range(start + 50, start + 60)
        ]
        _o__ = [
            self._create_address(str(i))
            for i in range(start + 60, start + 70)
        ]
        i___ = [
            self._create_address(str(i))
            for i in range(start + 70, start + 80)
        ]
        addresses = TestAddresses(
            inputs=iorw + ior_ + io__ + io_w + i___,
            outputs=ior_ + io__ + io_w + _o__ + _o_w,
            reads=i_r_ + ior_,
            writes=io_w + _o_w)
        return addresses

    def test_execution_results(self):
        """Tests that get_execution_results returns the correct values."""
        addr1 = self._create_address()
        addr2 = self._create_address()
        context_id = self.context_manager.create_context(
            state_hash=self.context_manager.get_first_root(),
            base_contexts=[],
            inputs=[addr1, addr2],
            outputs=[addr1, addr2])

        sets = {addr1: b'1'}
        events = [
            Event(
                event_type=teststr,
                attributes=[Event.Attribute(key=teststr, value=teststr)],
                data=teststr.encode()) for teststr in ("test1", "test2")
        ]
        deletes = {addr2: None}
        data = [(teststr.encode()) for teststr in ("test1", "test2")]

        self.context_manager.set(context_id, [sets])
        for event in events:
            self.context_manager.add_execution_event(context_id, event)

        self.context_manager.delete(context_id, deletes)
        for datum in data:
            self.context_manager.add_execution_data(
                context_id, datum)

        results = self.context_manager.get_execution_results(context_id)
        self.assertEqual(sets, results[0])
        self.assertEqual(deletes, results[1])
        self.assertEqual(events, results[2])
        self.assertEqual(data, results[3])

    def test_address_enforcement(self):
        """Tests that the ContextManager enforces address characteristics.

        Notes:
            1. Call get and set on the ContextManager with an address that is
               under a namespace, but is an invalid address, and test that
               the methods raise an AuthorizationException.
        """

        # 1)
        invalid_address1 = 'a' * 69 + 'n'
        invalid_address2 = 'b' * 69 + 'y'

        context_id1 = self.context_manager.create_context(
            state_hash=self.context_manager.get_first_root(),
            base_contexts=[],
            inputs=['aaaaaaaa', 'bbbbbbbb'],
            outputs=['aaaaaaaa', 'bbbbbbbb'])
        with self.assertRaises(context_manager.AuthorizationException):
            self.context_manager.get(
                context_id=context_id1,
                address_list=[invalid_address1, invalid_address2])
        with self.assertRaises(context_manager.AuthorizationException):
            self.context_manager.set(
                context_id=context_id1,
                address_value_list=[{invalid_address1: b'1'},
                                    {invalid_address2: b'2'}])

    def test_get_set_wrong_namespace(self):
        """Tests that getting and setting from outside the namespace will
        raise a AuthorizationException.

        Notes:
            1. Assert that sets on a context with addresses that aren't
               under an output namespace raise an AuthorizationException.

            2. Assert that gets on a context with addresses that aren't under
               an input namespace raise an AuthorizationException.
        """

        wrong_namespace1 = self._create_address('a')[-10:]
        wrong_namespace2 = '00000000'

        ctx_1 = self.context_manager.create_context(
            state_hash=self.context_manager.get_first_root(),
            base_contexts=[],
            inputs=[wrong_namespace1, wrong_namespace2],
            outputs=[wrong_namespace1, wrong_namespace2])
        # 1
        with self.assertRaises(context_manager.AuthorizationException):
            self.context_manager.set(
                context_id=ctx_1,
                address_value_list=[{self._create_address('a'): b'1'}])

        with self.assertRaises(context_manager.AuthorizationException):
            self.context_manager.set(
                context_id=ctx_1,
                address_value_list=[{self._create_address('c'): b'5'}])
        # 2
        with self.assertRaises(context_manager.AuthorizationException):
            self.context_manager.get(
                context_id=ctx_1,
                address_list=[self._create_address('a')])

        with self.assertRaises(context_manager.AuthorizationException):
            self.context_manager.get(
                context_id=ctx_1,
                address_list=[self._create_address('c')])

    def test_exception_on_invalid_input(self):
        """Tests that invalid inputs raise an exception. Tested with invalid
        characters, odd number of characters, and too long namespace;

        Notes:
            1) Assert that inputs with a namespace with an odd number of
               characters raise a CreateContextException.
            2) Assert that inputs with a 71 character namespace raise a
               CreateContextException.
            3) Assert that inputs with a namespace with several invalid
               characters raise a CreateContextException.
        """

        invalid_input_output1 = '0db7e8zc'  # invalid character
        invalid_input_output2 = '7ef84ed' * 10 + '5'  # too long, 71 chars
        invalid_input_output3 = 'yy76ftoph7465873ddde389f'  # invalid chars

        valid_input_output1 = 'd8f533bbb74443222daad4'
        valid_input_output2 = '77465847465784757848ddddddf'

        state_hash = self.context_manager.get_first_root()

        # 1
        with self.assertRaises(context_manager.CreateContextException):
            self.context_manager.create_context(
                state_hash=state_hash,
                base_contexts=[],
                inputs=[invalid_input_output1, valid_input_output1],
                outputs=[valid_input_output2])
        # 2
        with self.assertRaises(context_manager.CreateContextException):
            self.context_manager.create_context(
                state_hash=state_hash,
                base_contexts=[],
                inputs=[valid_input_output1, invalid_input_output2],
                outputs=[valid_input_output2])
        # 3
        with self.assertRaises(context_manager.CreateContextException):
            self.context_manager.create_context(
                state_hash=state_hash,
                base_contexts=[],
                inputs=[invalid_input_output3, valid_input_output2],
                outputs=[valid_input_output2, valid_input_output1])

    def test_exception_on_invalid_output(self):
        """Tests that invalid outputs raise an exception. Tested with invalid
        characters, odd number of characters, and too long namespace;

        Notes:
            1) Assert that outputs with a namespace with an odd number of
               characters raise a CreateContextException.
            2) Assert that outputs with a 71 character namespace raise a
               CreateContextException.
            3) Assert that outputs with a namespace with several invalid
               characters raise a CreateContextException.
        """

        invalid_input_output1 = '0db7e87'  # Odd number of characters
        invalid_input_output2 = '7ef84ed' * 10 + '5'  # too long, 71 chars
        invalid_input_output3 = 'yy76ftoph7465873ddde389f'  # invalid chars

        valid_input_output1 = 'd8f533bbb74443222daad4'
        valid_input_output2 = '77465847465784757848ddddddff'

        state_hash = self.context_manager.get_first_root()

        # 1
        with self.assertRaises(context_manager.CreateContextException):
            self.context_manager.create_context(
                state_hash=state_hash,
                base_contexts=[],
                inputs=[valid_input_output2, valid_input_output1],
                outputs=[invalid_input_output1])
        # 2
        with self.assertRaises(context_manager.CreateContextException):
            self.context_manager.create_context(
                state_hash=state_hash,
                base_contexts=[],
                inputs=[valid_input_output1, valid_input_output2],
                outputs=[invalid_input_output2])
        # 3
        with self.assertRaises(context_manager.CreateContextException):
            self.context_manager.create_context(
                state_hash=state_hash,
                base_contexts=[],
                inputs=[valid_input_output1, valid_input_output2],
                outputs=[valid_input_output2, invalid_input_output3])

    def test_namespace_gets(self):
        """Tests that gets for an address under a namespace will return the
        correct value.

        Notes:
            1) Create ctx_1 and set 'b' to b'8'.
            2) squash the previous context creating state_hash_1.
            3) Create 2 contexts off of this state hash and assert
               that gets on these contexts retrieve the correct
               value for an address that is not fully specified in the inputs.
            4) Set values to addresses in these contexts.
            5) Create 1 context off of these prior 2 contexts and assert that
               gets from this context retrieve the correct values for
               addresses that are not fully specified in the inputs. 2 of the
               values are found in the chain of contexts, and 1 is not found
               and so must be retrieved from the merkle tree.
        """

        # 1
        ctx_1 = self.context_manager.create_context(
            state_hash=self.context_manager.get_first_root(),
            base_contexts=[],
            inputs=[self._create_address('a')],
            outputs=[self._create_address('b')])

        self.context_manager.set(
            context_id=ctx_1,
            address_value_list=[{self._create_address('b'): b'8'}])

        # 2
        squash = self.context_manager.get_squash_handler()
        state_hash_1 = squash(
            state_root=self.context_manager.get_first_root(),
            context_ids=[ctx_1],
            persist=True,
            clean_up=True)

        # 3
        ctx_1a = self.context_manager.create_context(
            state_hash=state_hash_1,
            base_contexts=[],
            inputs=[self._create_address('a')[:10]],
            outputs=[self._create_address('c')])
        self.assertEqual(
            self.context_manager.get(
                context_id=ctx_1a,
                address_list=[self._create_address('a')]),
            [(self._create_address('a'), None)])

        ctx_1b = self.context_manager.create_context(
            state_hash=state_hash_1,
            base_contexts=[],
            inputs=[self._create_address('b')[:6]],
            outputs=[self._create_address('z')])
        self.assertEqual(
            self.context_manager.get(
                context_id=ctx_1b,
                address_list=[self._create_address('b')]),
            [(self._create_address('b'), b'8')])

        # 4
        self.context_manager.set(
            context_id=ctx_1b,
            address_value_list=[{self._create_address('z'): b'2'}])

        self.context_manager.set(
            context_id=ctx_1a,
            address_value_list=[{self._create_address('c'): b'1'}]
        )

        ctx_2 = self.context_manager.create_context(
            state_hash=state_hash_1,
            base_contexts=[ctx_1a, ctx_1b],
            inputs=[
                self._create_address('z')[:10],
                self._create_address('c')[:10],
                self._create_address('b')[:10]
            ],
            outputs=[self._create_address('w')])

        self.assertEqual(
            self.context_manager.get(
                context_id=ctx_2,
                address_list=[self._create_address('z'),
                              self._create_address('c'),
                              self._create_address('b')]),
            [(self._create_address('z'), b'2'),
             (self._create_address('c'), b'1'),
             (self._create_address('b'), b'8')])

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
                                      persist=True, clean_up=True)

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

    def test_squash_no_updates(self):
        """Tests that squashing a context that has no state updates will return
           the starting state root hash.

        Notes:
            Set up the context

            Test:
                1) Squash the context.
                2) Assert that the state hash is the same as the starting
                hash.
        """
        context_id = self.context_manager.create_context(
            state_hash=self.first_state_hash,
            base_contexts=[],
            inputs=[],
            outputs=[])
        # 1)
        squash = self.context_manager.get_squash_handler()
        resulting_state_hash = squash(self.first_state_hash, [context_id],
                                      persist=True, clean_up=True)
        # 2
        self.assertIsNotNone(resulting_state_hash)
        self.assertEqual(resulting_state_hash, self.first_state_hash)

    def test_squash_deletes_no_update(self):
        """Tests that squashing a context that has no state updates,
        due to sets that were subsequently deleted, will return
        the starting state root hash.

        Notes:
            Set up the context

            Test:
                1) Send Updates that reverse each other.
                2) Squash the context.
                3) Assert that the state hash is the same as the starting
                hash.
        """
        context_id = self.context_manager.create_context(
            state_hash=self.first_state_hash,
            base_contexts=[],
            inputs=[],
            outputs=[self._create_address(a) for a in
                     ['yyyy', 'tttt']])

        # 1)
        self.context_manager.set(
            context_id,
            [{self._create_address(a): v} for a, v in
             [('yyyy', b'2'),
              ('tttt', b'4')]])
        self.context_manager.delete(
            context_id,
            [self._create_address(a) for a in
             ['yyyy', 'tttt']])

        # 2)
        squash = self.context_manager.get_squash_handler()
        resulting_state_hash = squash(self.first_state_hash, [context_id],
                                      persist=True, clean_up=True)
        # 3)
        self.assertIsNotNone(resulting_state_hash)
        self.assertEqual(resulting_state_hash, self.first_state_hash)

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
            persist=True,
            clean_up=True)

        # 2)
        context_a = self.context_manager.create_context(
            state_hash=sh1,
            inputs=test_addresses.writes,  # read from every address written to
            outputs=test_addresses.outputs,
            base_contexts=[]
        )

        address_values = self.context_manager.get(
            context_a,
            list(test_addresses.writes)
        )
        self.assertEqual(
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
            address_list=list(test_addresses.outputs)
        )
        self.assertEqual(
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
        self.assertEqual(
            self.context_manager.get(
                context_id_b,
                list(test_addresses2.writes + test_addresses.outputs)
            ),
            [(a, v) for a, v in zip(
                test_addresses2.writes + test_addresses.outputs,
                values3 + values2)]
        )

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
            persist=True,
            clean_up=True)

        # 2)
        context_1 = self.context_manager.create_context(
            state_hash=sh1,
            base_contexts=[],
            inputs=[self._create_address('abcd')],
            outputs=[self._create_address('aaaa')])
        context_2 = self.context_manager.create_context(
            state_hash=sh1,
            base_contexts=[],
            inputs=[self._create_address('bacd')],
            outputs=[self._create_address('bbbb')])
        context_3 = self.context_manager.create_context(
            state_hash=sh1,
            base_contexts=[],
            inputs=[self._create_address('abcd')],
            outputs=[
                self._create_address('cccc'),
                self._create_address('dddd')
            ])

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
            inputs=[
                self._create_address('bbbb'),
                self._create_address('aaaa')
            ],
            outputs=[
                self._create_address('cccc'),
                self._create_address('llll')
            ])

        # 5)
        self.context_manager.set(
            context_id=context_n,
            address_value_list=[{
                self._create_address('cccc'): b'4',
                self._create_address('llll'): b'8'
            }])

        # 6)
        cm_state_root = squash(
            state_root=sh1,
            context_ids=[context_n],
            persist=False,
            clean_up=True)

        tree = MerkleDatabase(self.database_results)
        calc_state_root = tree.update({
            self._create_address('aaaa'): b'1',
            self._create_address('bbbb'): b'2',
            self._create_address('cccc'): b'4',
            self._create_address('llll'): b'8'
        })
        self.assertEqual(calc_state_root, cm_state_root)

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
            persist=True,
            clean_up=True)

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
        inputs_3_2a_1 = [
            self._create_address('qq'),
            self._create_address('dd')
        ]
        outputs_3_2a_1 = [
            self._create_address('dd'),
            self._create_address('pp')
        ]
        context_3_2a_1 = self.context_manager.create_context(
            state_hash=sh1,
            base_contexts=[context_2a],
            inputs=inputs_3_2a_1,
            outputs=outputs_3_2a_1)
        inputs_3_2a_2 = [self._create_address('aa')]
        outputs_3_2a_2 = [
            self._create_address('aa'),
            self._create_address('ll')
        ]
        context_3_2a_2 = self.context_manager.create_context(
            state_hash=sh1,
            base_contexts=[context_2a],
            inputs=inputs_3_2a_2,
            outputs=outputs_3_2a_2)

        inputs_3_2b_1 = [
            self._create_address('nn'),
            self._create_address('ab')
        ]
        outputs_3_2b_1 = [
            self._create_address('mm'),
            self._create_address('ba')
        ]
        context_3_2b_1 = self.context_manager.create_context(
            state_hash=sh1,
            base_contexts=[context_2b],
            inputs=inputs_3_2b_1,
            outputs=outputs_3_2b_1)

        inputs_3_2b_2 = [
            self._create_address('nn'),
            self._create_address('oo')
        ]
        outputs_3_2b_2 = [
            self._create_address('ab'),
            self._create_address('oo')
        ]
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
            persist=False,
            clean_up=True)

        tree = MerkleDatabase(self.database_results)
        state_hash_from_1 = tree.update(
            set_items={a: v for a, v in zip(outputs_1,
                                            [bytes(i)
                                             for i in range(len(outputs_1))])},
            virtual=False)

        self.assertEqual(state_hash_from_1, sh1,
                         "The manually calculated state hash from the first "
                         "context and the one calculated by squashing that "
                         "state hash should be the same")
        tree.set_merkle_root(state_hash_from_1)

        test_sh2 = tree.update(
            set_items={
                self._create_address('aa'): bytes(0),
                self._create_address('ab'): bytes(0),
                self._create_address('ba'): bytes(1),
                self._create_address('dd'): bytes(0),
                self._create_address('ll'): bytes(1),
                self._create_address('mm'): bytes(0),
                self._create_address('oo'): bytes(1),
                self._create_address('pp'): bytes(1),
                self._create_address('nn'): bytes(0),
                self._create_address('cc'): bytes(0)})

        self.assertEqual(sh2, test_sh2, "Manually calculated and context "
                         "manager calculated merkle hashes "
                         "are the same")

    def test_wildcarded_inputs_outputs(self):
        """Tests the context manager with wildcarded inputs and outputs.

        Notes:
            1. Create a context with a wildcarded input and output and
               another non-wildcarded input and output.
            2. Get an address under the wildcard and set to both the
               non-wildcarded address and an address under the
               wildcard.
            3. Squash the context and compare to a manually generated
               state hash.
        """

        # 1
        namespaces = [
            self._create_address('a')[:8],
            self._create_address('b')
        ]

        ctx_1 = self.context_manager.create_context(
            inputs=namespaces,
            outputs=namespaces,
            base_contexts=[],
            state_hash=self.first_state_hash)

        # 2
        self.context_manager.get(
            context_id=ctx_1,
            address_list=[self._create_address('a')])

        self.context_manager.set(
            context_id=ctx_1,
            address_value_list=[{
                self._create_address('a'): b'1',
                self._create_address('b'): b'2'
            }])

        # 3
        squash = self.context_manager.get_squash_handler()

        tree = MerkleDatabase(self.database_results)
        tree.set_merkle_root(self.first_state_hash)

        calculated_state_root = tree.update(
            set_items={self._create_address('a'): b'1',
                       self._create_address('b'): b'2'})

        state_root = squash(
            state_root=self.first_state_hash,
            context_ids=[ctx_1],
            persist=True,
            clean_up=True)

        self.assertEqual(state_root, calculated_state_root)

    @unittest.skip("Necessary to catch scheduler bugs--Depth-first search")
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
            outputs=outputs_2)
        self.context_manager.set(
            context_id=ctx_2,
            address_value_list=[{
                self._create_address('b'): b'2'
            }])

        try:
            squash(
                state_root=sh0,
                context_ids=[ctx_1, ctx_2],
                persist=True,
                clean_up=True)
            self.fail("squash of two contexts with a duplicate address")
        except Exception:
            pass

    def test_simple_read_write_delete(self):
        """Tests that after sets and deletes, subsequent contexts have the
        correct value in the context for an address.

                       i:a
                       o:b
                   +-->ctx_2a+
                   |   s:b:2 |
                   |         |
              i:a  |         |    i:b        i:a,b,c
              o:a  |         |    o:b,c      o:c
        sh0+->ctx_1|         <--->ctx_3+---->ctx_4+------>sh1
              s:a:1|         |    d:b,c      s:c:4
                   |         |
                   |   i:a   |
                   |   o:c   |
                   +-->ctx_2b+
                       s:c:2

        Notes:
            1. From the diagram:
                - ctx_1, with input 'a' and output 'a' will have 'a' set to
                  b'1'.
                - ctx_2a will have 'b' set to b'2'
                - ctx_2b will have 'c' set to b'2'
                - ctx_3 will delete both 'b' and 'c'
                - ctx_4 will set 'c' to b'4'
                - ctx_4 will be squashed along with it's base contexts into
                  a new state hash.
            2. Assertions
                - Assert for every context that it has the correct state
                  before the set or delete.
        """

        sh0 = self.context_manager.get_first_root()

        ctx_1 = self.context_manager.create_context(
            state_hash=sh0,
            base_contexts=[],
            inputs=[self._create_address('a')],
            outputs=[self._create_address('a')])

        self.assertEqual(self.context_manager.get(
            ctx_1, [self._create_address('a')]),
            [(self._create_address('a'), None)],
            "ctx_1 has no value for 'a'")

        self.context_manager.set(ctx_1, [{self._create_address('a'): b'1'}])

        ctx_2a = self.context_manager.create_context(
            state_hash=sh0,
            base_contexts=[ctx_1],
            inputs=[self._create_address('a')],
            outputs=[self._create_address('b')])

        self.assertEqual(self.context_manager.get(
            ctx_2a, [self._create_address('a')]),
            [(self._create_address('a'), b'1')],
            "ctx_2a has the value b'1' for 'a'")

        self.context_manager.set(ctx_2a, [{self._create_address('b'): b'2'}])

        ctx_2b = self.context_manager.create_context(
            state_hash=sh0,
            base_contexts=[ctx_1],
            inputs=[self._create_address('a')],
            outputs=[self._create_address('c')])

        self.assertEqual(self.context_manager.get(
            ctx_2b, [self._create_address('a')]),
            [(self._create_address('a'), b'1')],
            "ctx_2b has the value b'1' for 'a'")

        self.context_manager.set(ctx_2b, [{self._create_address('c'): b'2'}])

        ctx_3 = self.context_manager.create_context(
            state_hash=sh0,
            base_contexts=[ctx_2b, ctx_2a],
            inputs=[self._create_address('b')],
            outputs=[self._create_address('b'), self._create_address('c')])

        self.assertEqual(self.context_manager.get(
            ctx_3, [self._create_address('b')]),
            [(self._create_address('b'), b'2')],
            "ctx_3 has the value b'2' for 'b'")

        self.context_manager.delete(ctx_3, [self._create_address('b'),
                                            self._create_address('c')])

        ctx_4 = self.context_manager.create_context(
            state_hash=sh0,
            base_contexts=[ctx_3],
            inputs=[
                self._create_address('a'),
                self._create_address('b'),
                self._create_address('c')
            ],
            outputs=[self._create_address('c')])

        self.assertEqual(self.context_manager.get(
            ctx_4, [self._create_address('a'),
                    self._create_address('b'),
                    self._create_address('c')]),
            [(self._create_address('a'), b'1'),
             (self._create_address('b'), None),
             (self._create_address('c'), None)],
            "ctx_4 has the correct values in state for 'a','b', 'c'")

        self.context_manager.set(ctx_4, [{self._create_address('c'): b'4'}])

        squash = self.context_manager.get_squash_handler()

        sh1 = squash(
            state_root=sh0,
            context_ids=[ctx_4],
            persist=True,
            clean_up=True)

        tree = MerkleDatabase(self.database_results)

        sh1_assertion = tree.update({
            self._create_address('a'): b'1',
            self._create_address('c'): b'4'
        })

        self.assertEqual(sh1, sh1_assertion,
                         "The context manager must "
                         "calculate the correct state hash")

    def test_complex_read_write_delete(self):
        """Tests complex reads, writes, and deletes from contexts.

                  i:a
                  o:b                           i:a
               +->ctx_1a+                       o:d
               |  s:b   |                    +->ctx_3a+
               |        |                    |  d:d   |
               |  i:a   |             i:a    |        |    i:""
               |  o:c   |             o:""   |        |    o:""
        sh0+----->ctx_1b<--->sh1+---->ctx_2+-+        <--->ctx_4+->sh2
               |  s:c   |             d:c    |  i:c   |
               |  i:a   |             s:e    |  o:b   |
               |  o:d   |                    +->ctx_3b+
               +->ctx_1c+                       d:b
                  s:d

        Notes:
            1. Aside from the initial state hash, there are two squashed
               state hashes. There are sets in ctx_1* and then after a squash,
               deletes of the same addresses.
            2. Assertions are made for ctx_3b that 'c' is not in state, for
               ctx_4 that 'b', 'c', and 'd' are not in state.
        """

        sh0 = self.first_state_hash
        squash = self.context_manager.get_squash_handler()

        ctx_1a = self.context_manager.create_context(
            state_hash=sh0,
            base_contexts=[],
            inputs=[self._create_address('a')],
            outputs=[self._create_address('b')])

        ctx_1b = self.context_manager.create_context(
            state_hash=sh0,
            base_contexts=[],
            inputs=[self._create_address('a')],
            outputs=[self._create_address('c')])

        ctx_1c = self.context_manager.create_context(
            state_hash=sh0,
            base_contexts=[],
            inputs=[self._create_address('a')],
            outputs=[self._create_address('d')])

        self.context_manager.set(ctx_1a, [{self._create_address('b'): b'1'}])

        self.context_manager.set(ctx_1b, [{self._create_address('c'): b'2'}])

        self.context_manager.set(ctx_1c, [{self._create_address('d'): b'3'}])

        sh1 = squash(
            state_root=sh0,
            context_ids=[ctx_1c, ctx_1b, ctx_1a],
            persist=True,
            clean_up=True)

        ctx_2 = self.context_manager.create_context(
            state_hash=sh1,
            base_contexts=[],
            inputs=[self._create_address('a')],
            outputs=[""])

        self.context_manager.delete(ctx_2, [self._create_address('c')])

        self.context_manager.set(ctx_2, [{self._create_address('e'): b'2'}])

        ctx_3a = self.context_manager.create_context(
            state_hash=sh1,
            base_contexts=[ctx_2],
            inputs=[self._create_address('a')],
            outputs=[self._create_address('d')])

        self.context_manager.delete(ctx_3a, [self._create_address('d')])

        ctx_3b = self.context_manager.create_context(
            state_hash=sh1,
            base_contexts=[ctx_2],
            inputs=[self._create_address('c')],
            outputs=[self._create_address('b')])

        self.assertEqual(
            self.context_manager.get(ctx_3b, [self._create_address('c')]),
            [(self._create_address('c'), None)],
            "Address 'c' has already been deleted from state.")

        self.context_manager.delete(ctx_3b, [self._create_address('b')])

        ctx_4 = self.context_manager.create_context(
            state_hash=sh1,
            base_contexts=[ctx_3b, ctx_3a],
            inputs=[""],
            outputs=[""])

        self.assertEqual(
            self.context_manager.get(ctx_4, [self._create_address('b'),
                                             self._create_address('c'),
                                             self._create_address('d')]),
            [(self._create_address('b'), None),
             (self._create_address('c'), None),
             (self._create_address('d'), None)],
            "Addresses 'b', 'c', and 'd' have been deleted from state.")

        sh2 = squash(
            state_root=sh1,
            context_ids=[ctx_4],
            persist=True,
            clean_up=True)

        tree = MerkleDatabase(self.database_results)

        sh1_assertion = tree.update(
            {
                self._create_address('b'): b'1',
                self._create_address('c'): b'2',
                self._create_address('d'): b'3'
            },
            virtual=False)

        self.assertEqual(sh1, sh1_assertion,
                         "The middle state hash must be correct.")

        tree.set_merkle_root(sh1)

        sh2_assertion = tree.update(
            {
                self._create_address('e'): b'2'
            },
            delete_items=[
                self._create_address('b'),
                self._create_address('c'),
                self._create_address('d')
            ],
            virtual=False)
        self.assertEqual(sh2, sh2_assertion,
                         "The final state hash must be correct")

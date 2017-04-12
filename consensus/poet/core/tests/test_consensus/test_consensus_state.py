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

from unittest import mock

import cbor

from sawtooth_poet.poet_consensus import consensus_state


class TestConsensusState(unittest.TestCase):
    def test_get_missing_validator_state(self):
        """Verify that retrieving missing validator state returns appropriate
        default values.
        """
        state = consensus_state.ConsensusState()

        # Try to get a non-existent validator ID and verify it returns default
        # value
        validator_state = \
            state.get_validator_state(validator_id='Bond, James Bond')
        self.assertIsNone(validator_state)

        validator_state = \
            state.get_validator_state(
                validator_id='Bond, James Bond',
                default=consensus_state.ValidatorState(
                    commit_block_number=0xdeadbeef,
                    key_block_claim_count=1,
                    poet_public_key='my key',
                    total_block_claim_count=2))
        self.assertEqual(validator_state.commit_block_number, 0xdeadbeef)
        self.assertEqual(validator_state.key_block_claim_count, 1)
        self.assertEqual(validator_state.poet_public_key, 'my key')
        self.assertEqual(validator_state.total_block_claim_count, 2)

    def test_set_validator_state(self):
        """Verify that trying to set validator state with invalid validator
        state values/types fail.  Verifying that doing a get after a
        successful set returns the expected data.
        """
        state = consensus_state.ConsensusState()

        # Test invalid commit block number in validator state
        for invalid_cbn in [None, (), [], {}, '1', 1.1, -1]:
            with self.assertRaises(ValueError):
                state.set_validator_state(
                    validator_id='Bond, James Bond',
                    validator_state=consensus_state.ValidatorState(
                        commit_block_number=invalid_cbn,
                        key_block_claim_count=0,
                        poet_public_key='my key',
                        total_block_claim_count=0))

        # Test invalid key block claim counts in validator state
        for invalid_kbcc in [None, (), [], {}, '1', 1.1, -1]:
            with self.assertRaises(ValueError):
                state.set_validator_state(
                    validator_id='Bond, James Bond',
                    validator_state=consensus_state.ValidatorState(
                        commit_block_number=0xdeadbeef,
                        key_block_claim_count=invalid_kbcc,
                        poet_public_key='my key',
                        total_block_claim_count=0))

        # Test invalid PoET public key in validator state
        for invalid_ppk in [None, (), [], {}, 1, 1.1, '']:
            with self.assertRaises(ValueError):
                state.set_validator_state(
                    validator_id='Bond, James Bond',
                    validator_state=consensus_state.ValidatorState(
                        commit_block_number=0xdeadbeef,
                        key_block_claim_count=0,
                        poet_public_key=invalid_ppk,
                        total_block_claim_count=0))

        # Test invalid total block claim count in validator state
        for invalid_tbcc in [None, (), [], {}, '1', 1.1, -1]:
            with self.assertRaises(ValueError):
                state.set_validator_state(
                    validator_id='Bond, James Bond',
                    validator_state=consensus_state.ValidatorState(
                        commit_block_number=0xdeadbeef,
                        key_block_claim_count=0,
                        poet_public_key='my key',
                        total_block_claim_count=invalid_tbcc))

        # Test with total block claim count < key block claim count
        with self.assertRaises(ValueError):
            state.set_validator_state(
                validator_id='Bond, James Bond',
                validator_state=consensus_state.ValidatorState(
                    commit_block_number=0xdeadbeef,
                    key_block_claim_count=2,
                    poet_public_key='my key',
                    total_block_claim_count=1))

        # Verify that can retrieve after set and validator state matches
        validator_state = \
            consensus_state.ValidatorState(
                commit_block_number=0xdeadbeef,
                key_block_claim_count=0,
                poet_public_key='my key',
                total_block_claim_count=0)
        state.set_validator_state(
            validator_id='Bond, James Bond',
            validator_state=validator_state)

        retrieved_validator_state = \
            state.get_validator_state(validator_id='Bond, James Bond')

        self.assertEqual(
            validator_state.commit_block_number,
            retrieved_validator_state.commit_block_number)
        self.assertEqual(
            validator_state.key_block_claim_count,
            retrieved_validator_state.key_block_claim_count)
        self.assertEqual(
            validator_state.poet_public_key,
            retrieved_validator_state.poet_public_key)
        self.assertEqual(
            validator_state.total_block_claim_count,
            retrieved_validator_state.total_block_claim_count)

        # Verify that updating an existing validator state matches on get
        validator_state = \
            consensus_state.ValidatorState(
                commit_block_number=0xfeedbeef,
                key_block_claim_count=1,
                poet_public_key='my new key',
                total_block_claim_count=2)
        state.set_validator_state(
            validator_id='Bond, James Bond',
            validator_state=validator_state)

        retrieved_validator_state = \
            state.get_validator_state(validator_id='Bond, James Bond')

        self.assertEqual(
            validator_state.commit_block_number,
            retrieved_validator_state.commit_block_number)
        self.assertEqual(
            validator_state.key_block_claim_count,
            retrieved_validator_state.key_block_claim_count)
        self.assertEqual(
            validator_state.poet_public_key,
            retrieved_validator_state.poet_public_key)
        self.assertEqual(
            validator_state.total_block_claim_count,
            retrieved_validator_state.total_block_claim_count)

    def test_serialize(self):
        """Verify that deserializing invalid data results in the appropriate
        error.  Verify that serializing state and then deserializing results
        in the same state values.
        """
        # Simple deserialization check of buffer
        for invalid_state in [None, '', 1, 1.1, (), [], {}]:
            state = consensus_state.ConsensusState()
            with self.assertRaises(ValueError):
                state.parse_from_bytes(cbor.dumps(invalid_state))

        # Invalid expected block claim count
        for invalid_ebcc in [None, 'not a float', (), [], {}, -1,
                             float('nan'), float('inf'), float('-inf')]:
            state = consensus_state.ConsensusState()
            state.expected_block_claim_count = invalid_ebcc
            with self.assertRaises(ValueError):
                state.parse_from_bytes(state.serialize_to_bytes())

        # Invalid total block claim count
        for invalid_tbcc in [None, 'not an int', (), [], {}, -1]:
            state = consensus_state.ConsensusState()
            state.total_block_claim_count = invalid_tbcc
            with self.assertRaises(ValueError):
                state.parse_from_bytes(state.serialize_to_bytes())

        # Invalid validators
        for invalid_validators in [None, '', 1, 1.1, (), []]:
            state = consensus_state.ConsensusState()
            # pylint: disable=protected-access
            state._validators = invalid_validators
            with self.assertRaises(ValueError):
                state.parse_from_bytes(state.serialize_to_bytes())

        state = consensus_state.ConsensusState()
        state.set_validator_state(
            validator_id='Bond, James Bond',
            validator_state=consensus_state.ValidatorState(
                commit_block_number=0xdeadbeef,
                key_block_claim_count=1,
                poet_public_key='key',
                total_block_claim_count=1))
        doppelganger_state = consensus_state.ConsensusState()

        # Truncate the serialized value on purpose
        with self.assertRaises(ValueError):
            doppelganger_state.parse_from_bytes(
                state.serialize_to_bytes()[:-1])
        with self.assertRaises(ValueError):
            doppelganger_state.parse_from_bytes(
                state.serialize_to_bytes()[1:])

        # Circumvent testing of validator state validity so that we can
        # serialize to invalid data to verify deserializing

        # Test invalid commit block number in validator state
        for invalid_cbn in [None, (), [], {}, '1', 1.1, -1]:
            state = consensus_state.ConsensusState()
            with mock.patch(
                    'sawtooth_poet.poet_consensus.consensus_state.'
                    'ConsensusState._check_validator_state'):
                state.set_validator_state(
                    validator_id='Bond, James Bond',
                    validator_state=consensus_state.ValidatorState(
                        commit_block_number=invalid_cbn,
                        key_block_claim_count=0,
                        poet_public_key='key 1',
                        total_block_claim_count=1))

            serialized = state.serialize_to_bytes()
            with self.assertRaises(ValueError):
                state.parse_from_bytes(serialized)

        # Test invalid key block claim counts in validator state
        for invalid_kbcc in [None, (), [], {}, '1', 1.1, -1]:
            state = consensus_state.ConsensusState()
            with mock.patch(
                    'sawtooth_poet.poet_consensus.consensus_state.'
                    'ConsensusState._check_validator_state'):
                state.set_validator_state(
                    validator_id='Bond, James Bond',
                    validator_state=consensus_state.ValidatorState(
                        commit_block_number=0xdeadbeef,
                        key_block_claim_count=invalid_kbcc,
                        poet_public_key='key 1',
                        total_block_claim_count=1))

            serialized = state.serialize_to_bytes()
            with self.assertRaises(ValueError):
                state.parse_from_bytes(serialized)

        # Test invalid PoET public key in validator state
        for invalid_ppk in [None, (), [], {}, 1, 1.1, '']:
            state = consensus_state.ConsensusState()
            with mock.patch(
                    'sawtooth_poet.poet_consensus.consensus_state.'
                    'ConsensusState._check_validator_state'):
                state.set_validator_state(
                    validator_id='Bond, James Bond',
                    validator_state=consensus_state.ValidatorState(
                        commit_block_number=0xdeadbeef,
                        key_block_claim_count=1,
                        poet_public_key=invalid_ppk,
                        total_block_claim_count=1))

            serialized = state.serialize_to_bytes()
            with self.assertRaises(ValueError):
                state.parse_from_bytes(serialized)

        # Test total block claim count in validator state
        for invalid_tbcc in [None, (), [], {}, '1', 1.1, -1]:
            state = consensus_state.ConsensusState()
            with mock.patch(
                    'sawtooth_poet.poet_consensus.consensus_state.'
                    'ConsensusState._check_validator_state'):
                state.set_validator_state(
                    validator_id='Bond, James Bond',
                    validator_state=consensus_state.ValidatorState(
                        commit_block_number=0xdeadbeef,
                        key_block_claim_count=1,
                        poet_public_key='key',
                        total_block_claim_count=invalid_tbcc))

            serialized = state.serialize_to_bytes()
            with self.assertRaises(ValueError):
                state.parse_from_bytes(serialized)

        # Test with total block claim count < key block claim count
        with mock.patch(
                'sawtooth_poet.poet_consensus.consensus_state.'
                'ConsensusState._check_validator_state'):
            state.set_validator_state(
                validator_id='Bond, James Bond',
                validator_state=consensus_state.ValidatorState(
                    commit_block_number=0xdeadbeef,
                    key_block_claim_count=2,
                    poet_public_key='key',
                    total_block_claim_count=1))

        state = consensus_state.ConsensusState()

        # Simple serialization of new consensus state and then deserialize
        # and compare

        doppelganger_state = consensus_state.ConsensusState()
        doppelganger_state.parse_from_bytes(state.serialize_to_bytes())

        self.assertEqual(
            state.expected_block_claim_count,
            doppelganger_state.expected_block_claim_count)
        self.assertEqual(
            state.total_block_claim_count,
            doppelganger_state.total_block_claim_count)

        # Now put a couple of validators in, serialize, deserialize, and
        # verify they are in deserialized
        validator_state_1 = \
            consensus_state.ValidatorState(
                commit_block_number=0xdeadbeef,
                key_block_claim_count=1,
                poet_public_key='key 1',
                total_block_claim_count=2)
        validator_state_2 = \
            consensus_state.ValidatorState(
                commit_block_number=0xfeedbeef,
                key_block_claim_count=3,
                poet_public_key='key 2',
                total_block_claim_count=4)

        state.set_validator_state(
            validator_id='Bond, James Bond',
            validator_state=validator_state_1)
        state.set_validator_state(
            validator_id='Smart, Maxwell Smart',
            validator_state=validator_state_2)

        doppelganger_state.parse_from_bytes(state.serialize_to_bytes())

        validator_state = \
            doppelganger_state.get_validator_state(
                validator_id='Bond, James Bond')

        self.assertEqual(
            validator_state.commit_block_number,
            validator_state_1.commit_block_number)
        self.assertEqual(
            validator_state.key_block_claim_count,
            validator_state_1.key_block_claim_count)
        self.assertEqual(
            validator_state.poet_public_key,
            validator_state_1.poet_public_key)
        self.assertEqual(
            validator_state.total_block_claim_count,
            validator_state_1.total_block_claim_count)

        validator_state = \
            doppelganger_state.get_validator_state(
                validator_id='Smart, Maxwell Smart')

        self.assertEqual(
            validator_state.commit_block_number,
            validator_state_2.commit_block_number)
        self.assertEqual(
            validator_state.key_block_claim_count,
            validator_state_2.key_block_claim_count)
        self.assertEqual(
            validator_state.poet_public_key,
            validator_state_2.poet_public_key)
        self.assertEqual(
            validator_state.total_block_claim_count,
            validator_state_2.total_block_claim_count)

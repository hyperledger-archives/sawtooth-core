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

from sawtooth_poet_common.protobuf.validator_registry_pb2 \
    import ValidatorInfo
from sawtooth_poet_common.protobuf.validator_registry_pb2 \
    import SignUpInfo


class TestConsensusState(unittest.TestCase):
    def test_get_missing_validator_state(self):
        """Verify that retrieving missing validator state returns appropriate
        default values.
        """
        state = consensus_state.ConsensusState()

        # Try to get a non-existent validator ID and verify it returns default
        # value
        validator_info = \
            ValidatorInfo(
                id='validator_001',
                signup_info=SignUpInfo(
                    poet_public_key='key_001'))
        validator_state = \
            state.get_validator_state(validator_info=validator_info)

        self.assertEqual(validator_state.key_block_claim_count, 0)
        self.assertEqual(validator_state.poet_public_key, 'key_001')
        self.assertEqual(validator_state.total_block_claim_count, 0)

    def test_validator_did_claim_block(self):
        """Verify that trying to update consensus and validator state with
        validators that previous don't and do exist appropriately update the
        consensus and validator statistics.
        """
        state = consensus_state.ConsensusState()

        wait_certificate = mock.Mock()
        wait_certificate.duration = 3.1415
        wait_certificate.local_mean = 5.0

        poet_config_view = mock.Mock()
        poet_config_view.population_estimate_sample_size = 50

        validator_info = \
            ValidatorInfo(
                id='validator_001',
                signup_info=SignUpInfo(
                    poet_public_key='key_001'))

        # Have a non-existent validator claim a block, which should cause the
        # consensus state to add and set statistics appropriately.
        state.validator_did_claim_block(
            validator_info=validator_info,
            wait_certificate=wait_certificate,
            poet_config_view=poet_config_view)

        self.assertEqual(
            state.aggregate_local_mean,
            wait_certificate.local_mean)
        self.assertEqual(state.total_block_claim_count, 1)

        validator_state = \
            state.get_validator_state(validator_info=validator_info)

        self.assertEqual(validator_state.key_block_claim_count, 1)
        self.assertEqual(validator_state.poet_public_key, 'key_001')
        self.assertEqual(validator_state.total_block_claim_count, 1)

        # Have the existing validator claim another block and verify that
        # the consensus and validator statistics are updated properly
        state.validator_did_claim_block(
            validator_info=validator_info,
            wait_certificate=wait_certificate,
            poet_config_view=poet_config_view)

        self.assertEqual(
            state.aggregate_local_mean,
            2 * wait_certificate.local_mean)
        self.assertEqual(state.total_block_claim_count, 2)

        validator_state = \
            state.get_validator_state(validator_info=validator_info)

        self.assertEqual(validator_state.key_block_claim_count, 2)
        self.assertEqual(validator_state.poet_public_key, 'key_001')
        self.assertEqual(validator_state.total_block_claim_count, 2)

        # Have the existing validator claim another block, but with a new key,
        # and verify that the consensus and validator statistics are updated
        # properly
        validator_info.signup_info.poet_public_key = 'key_002'

        state.validator_did_claim_block(
            validator_info=validator_info,
            wait_certificate=wait_certificate,
            poet_config_view=poet_config_view)

        self.assertEqual(
            state.aggregate_local_mean,
            3 * wait_certificate.local_mean)
        self.assertEqual(state.total_block_claim_count, 3)

        validator_state = \
            state.get_validator_state(validator_info=validator_info)

        self.assertEqual(validator_state.key_block_claim_count, 1)
        self.assertEqual(validator_state.poet_public_key, 'key_002')
        self.assertEqual(validator_state.total_block_claim_count, 3)

    def test_serialize(self):
        """Verify that deserializing invalid data results in the appropriate
        error.  Verify that serializing state and then deserializing results
        in the same state values.
        """
        poet_config_view = mock.Mock()
        poet_config_view.population_estimate_sample_size = 50

        # Simple deserialization check of buffer
        for invalid_state in [None, '', 1, 1.1, (), [], {}]:
            state = consensus_state.ConsensusState()
            with self.assertRaises(ValueError):
                state.parse_from_bytes(cbor.dumps(invalid_state))

        # Missing aggregate local mean
        with mock.patch(
                'sawtooth_poet.poet_consensus.consensus_state.cbor.loads') \
                as mock_loads:
            mock_loads.return_value = {
                '_population_samples': [(2.718, 3.1415), (1.618, 0.618)],
                '_total_block_claim_count': 0,
                '_validators': {}
            }
            with self.assertRaises(ValueError):
                state.parse_from_bytes(b'')

        # Invalid aggregate local mean
        for invalid_alm in [None, 'not a float', (), [], {}, -1,
                            float('nan'), float('inf'), float('-inf')]:
            state = consensus_state.ConsensusState()
            with mock.patch(
                    'sawtooth_poet.poet_consensus.consensus_state.cbor.'
                    'loads') \
                    as mock_loads:
                mock_loads.return_value = {
                    '_aggregate_local_mean': invalid_alm,
                    '_population_samples': [(2.718, 3.1415), (1.618, 0.618)],
                    '_total_block_claim_count': 0,
                    '_validators': {}
                }
                with self.assertRaises(ValueError):
                    state.parse_from_bytes(b'')

        # Missing population samples
        with mock.patch(
                'sawtooth_poet.poet_consensus.consensus_state.cbor.loads') \
                as mock_loads:
            mock_loads.return_value = {
                '_aggregate_local_mean': 0.0,
                '_total_block_claim_count': 0,
                '_validators': {}
            }
            with self.assertRaises(ValueError):
                state.parse_from_bytes(b'')

        # Invalid population samples
        for invalid_ps in [None, 1, 1.0, 'str', (1,), [1],
                           (1.0, None), (1.0, 'str'), (1.0, ()), (1.0, []),
                           (1.0, {}),
                           (1.0, float('nan')), (1.0, float('inf')),
                           (1.0, float('-inf')), (float('nan'), 1.0),
                           (float('inf'), 1.0), (float('-inf'), 1.0),
                           (None, 1.0), ('str', 1.0), ((), 1.0), ([], 1.0),
                           ({}, 1.0),
                           [1.0, None], [1.0, 'str'], [1.0, ()], [1.0, []],
                           [1.0, {}],
                           [1.0, float('nan')], [1.0, float('inf')],
                           [1.0, float('-inf')], [float('nan'), 1.0],
                           [float('inf'), 1.0], [float('-inf'), 1.0],
                           [None, 1.0], ['str', 1.0], [(), 1.0], [[], 1.0],
                           [{}, 1.0]]:
            state = consensus_state.ConsensusState()
            with mock.patch(
                    'sawtooth_poet.poet_consensus.consensus_state.cbor.'
                    'loads') \
                    as mock_loads:
                mock_loads.return_value = {
                    '_aggregate_local_mean': 0.0,
                    '_population_samples': invalid_ps,
                    '_total_block_claim_count': 0,
                    '_validators': {}
                }
                with self.assertRaises(ValueError):
                    state.parse_from_bytes(b'')

        # Missing total block claim count
        with mock.patch(
                'sawtooth_poet.poet_consensus.consensus_state.cbor.loads') \
                as mock_loads:
            mock_loads.return_value = {
                '_aggregate_local_mean': 0.0,
                '_population_samples': [(2.718, 3.1415), (1.618, 0.618)],
                '_validators': {}
            }
            with self.assertRaises(ValueError):
                state.parse_from_bytes(b'')

        # Invalid total block claim count
        for invalid_tbcc in [None, 'not an int', (), [], {}, -1]:
            state = consensus_state.ConsensusState()
            with mock.patch(
                    'sawtooth_poet.poet_consensus.consensus_state.cbor.'
                    'loads') \
                    as mock_loads:
                mock_loads.return_value = {
                    '_aggregate_local_mean': 0.0,
                    '_population_samples': [(2.718, 3.1415), (1.618, 0.618)],
                    '_total_block_claim_count': invalid_tbcc,
                    '_validators': {}
                }
                with self.assertRaises(ValueError):
                    state.parse_from_bytes(b'')

        # Invalid validators
        for invalid_validators in [None, '', 1, 1.1, (), []]:
            state = consensus_state.ConsensusState()
            with mock.patch(
                    'sawtooth_poet.poet_consensus.consensus_state.cbor.'
                    'loads') \
                    as mock_loads:
                mock_loads.return_value = {
                    '_aggregate_local_mean': 0.0,
                    '_population_samples': [(2.718, 3.1415), (1.618, 0.618)],
                    '_total_block_claim_count': 0,
                    '_validators': invalid_validators
                }
                with self.assertRaises(ValueError):
                    state.parse_from_bytes(b'')

        state = consensus_state.ConsensusState()
        wait_certificate = mock.Mock()
        wait_certificate.duration = 3.14
        wait_certificate.local_mean = 5.0

        validator_info = \
            ValidatorInfo(
                id='validator_001',
                signup_info=SignUpInfo(
                    poet_public_key='key_001'))

        state.validator_did_claim_block(
            validator_info=validator_info,
            wait_certificate=wait_certificate,
            poet_config_view=poet_config_view)
        doppelganger_state = consensus_state.ConsensusState()

        # Truncate the serialized value on purpose
        with self.assertRaises(ValueError):
            doppelganger_state.parse_from_bytes(
                state.serialize_to_bytes()[:-1])
        with self.assertRaises(ValueError):
            doppelganger_state.parse_from_bytes(
                state.serialize_to_bytes()[1:])

        # Test invalid key block claim counts in validator state
        for invalid_kbcc in [None, (), [], {}, '1', 1.1, -1]:
            state = consensus_state.ConsensusState()
            with mock.patch(
                    'sawtooth_poet.poet_consensus.consensus_state.cbor.'
                    'loads') as mock_loads:
                mock_loads.return_value = {
                    '_aggregate_local_mean': 0.0,
                    '_population_samples': [(2.718, 3.1415), (1.618, 0.618)],
                    '_total_block_claim_count': 0,
                    '_validators': {
                        'validator_001': [invalid_kbcc, 'ppk_001', 0]
                    }
                }
                with self.assertRaises(ValueError):
                    state.parse_from_bytes(b'')

        # Test invalid PoET public key in validator state
        for invalid_ppk in [None, (), [], {}, 1, 1.1, '']:
            state = consensus_state.ConsensusState()
            with mock.patch(
                    'sawtooth_poet.poet_consensus.consensus_state.cbor.'
                    'loads') as mock_loads:
                mock_loads.return_value = {
                    '_aggregate_local_mean': 0.0,
                    '_population_samples': [(2.718, 3.1415), (1.618, 0.618)],
                    '_total_block_claim_count': 0,
                    '_validators': {
                        'validator_001': [0, invalid_ppk, 0]
                    }
                }
                with self.assertRaises(ValueError):
                    state.parse_from_bytes(b'')

        # Test total block claim count in validator state
        for invalid_tbcc in [None, (), [], {}, '1', 1.1, -1]:
            state = consensus_state.ConsensusState()
            with mock.patch(
                    'sawtooth_poet.poet_consensus.consensus_state.cbor.'
                    'loads') as mock_loads:
                mock_loads.return_value = {
                    '_aggregate_local_mean': 0.0,
                    '_population_samples': [(2.718, 3.1415), (1.618, 0.618)],
                    '_total_block_claim_count': 0,
                    '_validators': {
                        'validator_001': [0, 'ppk_001', invalid_tbcc]
                    }
                }
                with self.assertRaises(ValueError):
                    state.parse_from_bytes(b'')

        # Test with total block claim count < key block claim count
        state = consensus_state.ConsensusState()
        with mock.patch(
                'sawtooth_poet.poet_consensus.consensus_state.cbor.'
                'loads') as mock_loads:
            mock_loads.return_value = {
                '_aggregate_local_mean': 0.0,
                '_population_samples': [(2.718, 3.1415), (1.618, 0.618)],
                '_total_block_claim_count': 0,
                '_validators': {
                    'validator_001': [2, 'ppk_001', 1]
                }
            }
            with self.assertRaises(ValueError):
                state.parse_from_bytes(b'')

        # Simple serialization of new consensus state and then deserialize
        # and compare
        state = consensus_state.ConsensusState()

        doppelganger_state = consensus_state.ConsensusState()
        doppelganger_state.parse_from_bytes(state.serialize_to_bytes())

        self.assertEqual(
            state.aggregate_local_mean,
            doppelganger_state.aggregate_local_mean)
        self.assertEqual(
            state.total_block_claim_count,
            doppelganger_state.total_block_claim_count)

        # Now put a couple of validators in, serialize, deserialize, and
        # verify they are in deserialized
        wait_certificate_1 = mock.Mock()
        wait_certificate_1.duration = 3.14
        wait_certificate_1.local_mean = 5.0
        wait_certificate_2 = mock.Mock()
        wait_certificate_2.duration = 1.618
        wait_certificate_2.local_mean = 2.718

        validator_info_1 = \
            ValidatorInfo(
                id='validator_001',
                signup_info=SignUpInfo(
                    poet_public_key='key_001'))
        validator_info_2 = \
            ValidatorInfo(
                id='validator_002',
                signup_info=SignUpInfo(
                    poet_public_key='key_002'))

        state.validator_did_claim_block(
            validator_info=validator_info_1,
            wait_certificate=wait_certificate_1,
            poet_config_view=poet_config_view)
        state.validator_did_claim_block(
            validator_info=validator_info_2,
            wait_certificate=wait_certificate_2,
            poet_config_view=poet_config_view)

        doppelganger_state.parse_from_bytes(state.serialize_to_bytes())

        self.assertEqual(
            state.aggregate_local_mean,
            doppelganger_state.aggregate_local_mean)
        self.assertEqual(
            state.total_block_claim_count,
            doppelganger_state.total_block_claim_count)

        validator_state = \
            state.get_validator_state(
                validator_info=validator_info_1)
        doppleganger_validator_state = \
            doppelganger_state.get_validator_state(
                validator_info=validator_info_1)

        self.assertEqual(
            validator_state.key_block_claim_count,
            doppleganger_validator_state.key_block_claim_count)
        self.assertEqual(
            validator_state.poet_public_key,
            doppleganger_validator_state.poet_public_key)
        self.assertEqual(
            validator_state.total_block_claim_count,
            doppleganger_validator_state.total_block_claim_count)

        validator_state = \
            state.get_validator_state(
                validator_info=validator_info_2)
        doppleganger_validator_state = \
            doppelganger_state.get_validator_state(
                validator_info=validator_info_2)

        self.assertEqual(
            validator_state.key_block_claim_count,
            doppleganger_validator_state.key_block_claim_count)
        self.assertEqual(
            validator_state.poet_public_key,
            doppleganger_validator_state.poet_public_key)
        self.assertEqual(
            validator_state.total_block_claim_count,
            doppleganger_validator_state.total_block_claim_count)

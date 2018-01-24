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

import math
import random
from unittest import TestCase
from unittest import mock

import cbor

from sawtooth_poet.poet_consensus import consensus_state

from sawtooth_poet_common.protobuf.validator_registry_pb2 \
    import ValidatorInfo

from sawtooth_poet_common.protobuf.validator_registry_pb2 \
    import SignUpInfo


class TestConsensusState(TestCase):
    MINIMUM_WAIT_TIME = 1.0

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

        poet_settings_view = mock.Mock()
        poet_settings_view.population_estimate_sample_size = 50

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
            poet_settings_view=poet_settings_view)

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
            poet_settings_view=poet_settings_view)

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
            poet_settings_view=poet_settings_view)

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
        poet_settings_view = mock.Mock()
        poet_settings_view.population_estimate_sample_size = 50

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
            poet_settings_view=poet_settings_view)
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

        mock_poet_settings_view = mock.Mock()
        mock_poet_settings_view.target_wait_time = 30.0
        mock_poet_settings_view.initial_wait_time = 3000.0
        mock_poet_settings_view.population_estimate_sample_size = 50

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
            poet_settings_view=poet_settings_view)
        state.validator_did_claim_block(
            validator_info=validator_info_2,
            wait_certificate=wait_certificate_2,
            poet_settings_view=poet_settings_view)

        doppelganger_state.parse_from_bytes(state.serialize_to_bytes())

        self.assertEqual(
            state.aggregate_local_mean,
            doppelganger_state.aggregate_local_mean)
        self.assertAlmostEqual(
            first=state.compute_local_mean(
                poet_settings_view=mock_poet_settings_view),
            second=doppelganger_state.compute_local_mean(
                poet_settings_view=mock_poet_settings_view),
            places=4)
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

    def test_local_mean(self):
        """Verify that the consensus state properly computes the local mean
        during both the bootstrapping phase (i.e., before there are enough
        blocks in the chain to satisfy the population estimate sample size)
        and once there are enough blocks in the chain.
        """

        mock_poet_settings_view = mock.Mock()
        mock_poet_settings_view.target_wait_time = 30.0
        mock_poet_settings_view.initial_wait_time = 3000.0
        mock_poet_settings_view.population_estimate_sample_size = 50

        # Test that during bootstrapping, the local means adhere to the
        # following:
        #
        # ratio = 1.0 * blockCount / sampleSize
        # localMean = targetWaitTime*(1-ratio**2) + initialWaitTime*ratio**2

        def _compute_fixed_local_mean(count):
            ratio = \
                1.0 * count / \
                mock_poet_settings_view.population_estimate_sample_size
            return \
                (mock_poet_settings_view.target_wait_time * (1 - ratio**2)) + \
                (mock_poet_settings_view.initial_wait_time * ratio**2)

        validator_info = \
            ValidatorInfo(
                id='validator_001',
                signup_info=SignUpInfo(
                    poet_public_key='key_001'))

        # We are first going to bootstrap the blockchain by claiming exactly
        # population estimate sample size blocks.  Each one should match the
        # corresponding expected fixed local mean.
        wait_certificates = []
        state = consensus_state.ConsensusState()
        sample_size = mock_poet_settings_view.population_estimate_sample_size
        for _ in range(sample_size):
            # Compute a wait certificate with a fixed local mean, add it to
            # our samples, verify that its local mean equals the one computed
            # by the consensus state, and then update the consensus state as if
            # the block with this wait certificate was claimed.
            mock_wait_certificate = mock.Mock()
            mock_wait_certificate.duration = \
                random.uniform(
                    TestConsensusState.MINIMUM_WAIT_TIME,
                    TestConsensusState.MINIMUM_WAIT_TIME + 10)
            mock_wait_certificate.local_mean = \
                _compute_fixed_local_mean(len(wait_certificates))
            wait_certificates.append(mock_wait_certificate)

            self.assertAlmostEqual(
                first=mock_wait_certificate.local_mean,
                second=state.compute_local_mean(mock_poet_settings_view),
                places=4)

            state.validator_did_claim_block(
                validator_info=validator_info,
                wait_certificate=mock_wait_certificate,
                poet_settings_view=mock_poet_settings_view)

        # Test that after bootstrapping, the local means adhere to the
        # following:
        #
        # sw, sm = 0.0
        # for most recent population estimate sample size blocks:
        #   sw += waitCertificate.duration - minimumWaitTime
        #   sm += waitCertificate.localMean
        # localMean = targetWaitTme * (sm / sw)

        def _compute_historical_local_mean(wcs):
            sw = 0.0
            sm = 0.0

            for wc in wcs:
                sw += wc.duration - TestConsensusState.MINIMUM_WAIT_TIME
                sm += wc.local_mean

            return mock_poet_settings_view.target_wait_time * (sm / sw)

        # Let's run through another population estimate sample size blocks
        # and verify that we get the local means expected
        sample_size = mock_poet_settings_view.population_estimate_sample_size
        for _ in range(sample_size):
            # Compute a wait certificate with a historical local mean, add it
            # to our samples, evict the oldest sample, verify that its local
            # mean equals the one computed by the consensus state, and then
            # update the consensus state as if the block with this wait
            # certificate was claimed.
            mock_wait_certificate = mock.Mock()
            mock_wait_certificate.duration = \
                random.uniform(
                    TestConsensusState.MINIMUM_WAIT_TIME,
                    TestConsensusState.MINIMUM_WAIT_TIME + 10)
            mock_wait_certificate.local_mean = \
                _compute_historical_local_mean(wait_certificates)
            wait_certificates.append(mock_wait_certificate)
            wait_certificates = wait_certificates[1:]

            self.assertAlmostEqual(
                first=mock_wait_certificate.local_mean,
                second=state.compute_local_mean(mock_poet_settings_view),
                places=4)

            state.validator_did_claim_block(
                validator_info=validator_info,
                wait_certificate=mock_wait_certificate,
                poet_settings_view=mock_poet_settings_view)

    def test_block_claim_limit(self):
        """Verify that consensus state properly indicates whether or not a
        validator has reached the block claim limit
        """
        mock_wait_certificate = mock.Mock()
        mock_wait_certificate.duration = 3.14
        mock_wait_certificate.local_mean = 5.0

        mock_poet_settings_view = mock.Mock()
        mock_poet_settings_view.key_block_claim_limit = 10
        mock_poet_settings_view.population_estimate_sample_size = 50

        validator_info = \
            ValidatorInfo(
                id='validator_001',
                signup_info=SignUpInfo(
                    poet_public_key='key_001'))
        state = consensus_state.ConsensusState()

        # Verify that validator does not trigger key block claim limit and also
        # "claim" blocks
        for _ in range(mock_poet_settings_view.key_block_claim_limit):
            self.assertFalse(
                state.validator_has_claimed_block_limit(
                    validator_info=validator_info,
                    poet_settings_view=mock_poet_settings_view))
            state.validator_did_claim_block(
                validator_info=validator_info,
                wait_certificate=mock_wait_certificate,
                poet_settings_view=mock_poet_settings_view)

        # Now that validator has claimed limit for key, verify that it triggers
        # the test
        self.assertTrue(
            state.validator_has_claimed_block_limit(
                validator_info=validator_info,
                poet_settings_view=mock_poet_settings_view))

        # Switch keys and verify that validator again doesn't trigger test
        validator_info = \
            ValidatorInfo(
                id='validator_001',
                signup_info=SignUpInfo(
                    poet_public_key='key_002'))
        self.assertFalse(
            state.validator_has_claimed_block_limit(
                validator_info=validator_info,
                poet_settings_view=mock_poet_settings_view))

    def test_block_claim_delay(self):
        """Verify that consensus state properly indicates whether or not a
        validator is trying to claim a block before the block claim delay
        """
        mock_validator_registry_view = mock.Mock()
        mock_validator_registry_view.get_validators.return_value = [
            'validator_001',
            'validator_002',
            'validator_003',
            'validator_004',
            'validator_005',
            'validator_006',
            'validator_008',
            'validator_009',
            'validator_010'
        ]

        mock_wait_certificate = mock.Mock()
        mock_wait_certificate.duration = 3.14
        mock_wait_certificate.local_mean = 5.0

        mock_poet_settings_view = mock.Mock()
        mock_poet_settings_view.key_block_claim_limit = 10000
        mock_poet_settings_view.block_claim_delay = 2
        mock_poet_settings_view.population_estimate_sample_size = 50

        mock_block = mock.Mock()
        mock_block.block_num = 100

        mock_block_store = mock.Mock()
        mock_block_store.get_block_by_transaction_id.return_value = mock_block

        validator_info = \
            ValidatorInfo(
                id='validator_001',
                signup_info=SignUpInfo(
                    poet_public_key='key_002'),
                transaction_id='transaction_001')

        # Claim a bunch of blocks to get past the bootstrapping necessary to
        # get to the point where we will actually test the block claim delay
        state = consensus_state.ConsensusState()
        for _ in range(100):
            state.validator_did_claim_block(
                validator_info=validator_info,
                wait_certificate=mock_wait_certificate,
                poet_settings_view=mock_poet_settings_view)

        # Test with blocks satisfying the claim delay
        for block_number in [103, 105, 110, 200, 1000]:
            self.assertFalse(
                state.validator_is_claiming_too_early(
                    validator_info=validator_info,
                    block_number=block_number,
                    validator_registry_view=mock_validator_registry_view,
                    poet_settings_view=mock_poet_settings_view,
                    block_store=mock_block_store))

        # Test with blocks not satisfying the claim delay
        for block_number in [100, 101, 102]:
            self.assertTrue(
                state.validator_is_claiming_too_early(
                    validator_info=validator_info,
                    block_number=block_number,
                    validator_registry_view=mock_validator_registry_view,
                    poet_settings_view=mock_poet_settings_view,
                    block_store=mock_block_store))

    @mock.patch('sawtooth_poet.poet_consensus.consensus_state.utils.'
                'deserialize_wait_certificate')
    def test_block_claim_frequency(self, mock_deserialize):
        """Verify that consensus state properly indicates whether or not a
        validator is trying to claim blocks too frequently
        """
        mock_poet_settings_view = mock.Mock()
        mock_poet_settings_view.target_wait_time = 5.0
        mock_poet_settings_view.key_block_claim_limit = 10
        mock_poet_settings_view.population_estimate_sample_size = 50
        mock_poet_settings_view.ztest_minimum_win_count = 3
        mock_poet_settings_view.ztest_maximum_win_deviation = 3.075

        mock_wait_certificate = mock.Mock()
        mock_wait_certificate.duration = 3.14
        mock_wait_certificate.local_mean = \
            mock_poet_settings_view.target_wait_time * 2
        mock_wait_certificate.population_estimate.return_value = 2

        mock_deserialize.return_value = mock_wait_certificate

        mock_block = mock.Mock()
        mock_block.previous_block_id = 'block_000'
        mock_block.header.signer_public_key = 'validator_001_key'

        mock_block_cache = mock.MagicMock()
        mock_block_cache.__getitem__.return_value = mock_block

        validator_info = \
            ValidatorInfo(
                id=mock_block.header.signer_public_key,
                signup_info=SignUpInfo(
                    poet_public_key='key_002'))

        # Verify that zTest does not apply while there are fewer than
        # population estimate sample size blocks committed
        state = consensus_state.ConsensusState()
        sample_size = mock_poet_settings_view.population_estimate_sample_size
        for _ in range(sample_size):
            self.assertFalse(state.validator_is_claiming_too_frequently(
                validator_info=validator_info,
                previous_block_id='previous_id',
                poet_settings_view=mock_poet_settings_view,
                population_estimate=2,
                block_cache=mock_block_cache,
                poet_enclave_module=None))
            state.validator_did_claim_block(
                validator_info=validator_info,
                wait_certificate=mock_wait_certificate,
                poet_settings_view=mock_poet_settings_view)

        # Per the spec, a z-score is calculated for each block, beyond the
        # minimum, that the validator has claimed.  The z-score is computed as:
        #
        # zScore = (observed - expected) / stddev
        #
        # Where:
        # observed = the number of blocks won by validator
        # expected = the number statistically expected to be won by validator,
        #     which in the case is 1/2 of the blocks (as population estimate is
        #     fixed at 2)
        # probability = expected / number blocks
        # stddev = square root(number blocks * probability * (1 - probability)

        # Compute how many more blocks beyond the minimum that the validator
        # can claim without triggering the frequency test
        observed = mock_poet_settings_view.ztest_minimum_win_count
        while True:
            expected = \
                float(observed) / \
                mock_wait_certificate.population_estimate.return_value
            probability = expected / observed
            stddev = math.sqrt(observed * probability * (1 - probability))
            z_score = (observed - expected) / stddev

            if z_score > mock_poet_settings_view.ztest_maximum_win_deviation:
                break

            observed += 1

        # Verify that the validator can claim up to just before the number of
        # blocks calculated above (this would be the blocks before the minimum
        # win count as well as up to just before it triggered the frequency
        # test).
        for _ in range(observed - 1):
            self.assertFalse(state.validator_is_claiming_too_frequently(
                validator_info=validator_info,
                previous_block_id='previous_id',
                poet_settings_view=mock_poet_settings_view,
                population_estimate=2,
                block_cache=mock_block_cache,
                poet_enclave_module=None))
            state.validator_did_claim_block(
                validator_info=validator_info,
                wait_certificate=mock_wait_certificate,
                poet_settings_view=mock_poet_settings_view)

        # Verify that now the validator triggers the frequency test
        self.assertTrue(state.validator_is_claiming_too_frequently(
            validator_info=validator_info,
            previous_block_id='previous_id',
            poet_settings_view=mock_poet_settings_view,
            population_estimate=2,
            block_cache=mock_block_cache,
            poet_enclave_module=None))

    def test_signup_commit_maximum_delay(self):
        """Verify that consensus state properly indicates whether or not a
        validator signup was committed before the maximum delay occurred
        """
        block_dictionary = {
            '001': mock.Mock(previous_block_id='000', identifier='001'),
            '002': mock.Mock(previous_block_id='001', identifier='002'),
            '003': mock.Mock(previous_block_id='002', identifier='003'),
            '004': mock.Mock(previous_block_id='003', identifier='004')
        }

        mock_block_cache = mock.MagicMock()
        mock_block_cache.__getitem__.side_effect = block_dictionary.__getitem__
        mock_block_cache.block_store.get_block_by_transaction_id.\
            return_value = block_dictionary['004']

        mock_poet_settings_view = mock.Mock()
        mock_poet_settings_view.signup_commit_maximum_delay = 1

        validator_info = \
            ValidatorInfo(
                id='validator_001',
                signup_info=SignUpInfo(
                    poet_public_key='key_002',
                    nonce='999'),
                transaction_id='transaction_001')

        # Simulate reaching beginning of chain before finding block ID
        with mock.patch('sawtooth_poet.poet_consensus.consensus_state.utils.'
                        'block_id_is_genesis') as mock_block_id_is_genesis:
            mock_block_id_is_genesis.return_value = True
            state = consensus_state.ConsensusState()
            self.assertTrue(
                state.validator_signup_was_committed_too_late(
                    validator_info=validator_info,
                    poet_settings_view=mock_poet_settings_view,
                    block_cache=mock_block_cache))

        # Simulate reaching the maximum commit delay before finding the block
        # we want with different delays
        validator_info = \
            ValidatorInfo(
                id='validator_001',
                signup_info=SignUpInfo(
                    poet_public_key='key_002',
                    nonce='999'),
                transaction_id='transaction_001')

        with mock.patch('sawtooth_poet.poet_consensus.consensus_state.utils.'
                        'block_id_is_genesis') as mock_block_id_is_genesis:
            mock_block_id_is_genesis.return_value = False
            state = consensus_state.ConsensusState()
            for delay in range(len(block_dictionary) - 1):
                mock_poet_settings_view.signup_commit_maximum_delay = delay
                self.assertTrue(
                    state.validator_signup_was_committed_too_late(
                        validator_info=validator_info,
                        poet_settings_view=mock_poet_settings_view,
                        block_cache=mock_block_cache))

        # Simulate finding block before maximum delay
        with mock.patch('sawtooth_poet.poet_consensus.consensus_state.utils.'
                        'block_id_is_genesis') as mock_block_id_is_genesis:
            mock_block_id_is_genesis.return_value = False
            state = consensus_state.ConsensusState()
            for (nonce, delay) in zip(['001', '002', '003'], [2, 1, 0]):
                mock_poet_settings_view.signup_commit_maximum_delay = delay
                validator_info = \
                    ValidatorInfo(
                        id='validator_001',
                        signup_info=SignUpInfo(
                            poet_public_key='key_002',
                            nonce=nonce),
                        transaction_id='transaction_001')
                self.assertFalse(
                    state.validator_signup_was_committed_too_late(
                        validator_info=validator_info,
                        poet_settings_view=mock_poet_settings_view,
                        block_cache=mock_block_cache))

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
import tempfile
import os
from importlib import reload

import cbor

from sawtooth_poet.poet_consensus import consensus_state
from sawtooth_poet.poet_consensus import consensus_state_store

from sawtooth_poet_common.protobuf.validator_registry_pb2 \
    import ValidatorInfo
from sawtooth_poet_common.protobuf.validator_registry_pb2 \
    import SignUpInfo


class TestConsensusStateStore(unittest.TestCase):
    def setUp(self):
        # pylint: disable=invalid-name,global-statement
        global consensus_state_store
        # Because ConsensusStateStore uses class variables to hold state
        # we need to reload the module after each test to clear state
        consensus_state_store = reload(consensus_state_store)

    @mock.patch('sawtooth_poet.poet_consensus.consensus_state_store.'
                'LMDBNoLockDatabase')
    def test_verify_db_creation(self, mock_lmdb):
        """Verify that the underlying consensus state store LMDB file is
        created underneath the provided data directory and with the correct
        file creation flag.
        """
        consensus_state_store.ConsensusStateStore(
            data_dir=tempfile.gettempdir(),
            validator_id='0123456789abcdef')

        # Verify that the database is created in the directory provided
        # and that it is created with the anydb flag for open if exists,
        # create if doesn't exist
        (filename, flag), _ = mock_lmdb.call_args

        self.assertTrue(filename.startswith(tempfile.gettempdir() + os.sep))
        self.assertEqual(flag, 'c')

    @mock.patch('sawtooth_poet.poet_consensus.consensus_state_store.'
                'LMDBNoLockDatabase')
    def test_nonexistent_key(self, mock_lmdb):
        """Verify that retrieval of a non-existent key raises the appropriate
        exception.
        """
        # Make LMDB return None for all keys
        mock_lmdb.return_value.__getitem__.return_value = None
        store = \
            consensus_state_store.ConsensusStateStore(
                data_dir=tempfile.gettempdir(),
                validator_id='0123456789abcdef')

        with self.assertRaises(KeyError):
            _ = store['bad key']

    @mock.patch('sawtooth_poet.poet_consensus.consensus_state_store.'
                'LMDBNoLockDatabase')
    def test_malformed_consensus_state(self, mock_lmdb):
        """Verify the a malformed consensus state that cannot be properly
        deserialized to a consensus state object raises the appropriate
        exception.
        """
        # Make LMDB return CBOR serialization of a non-dict
        mock_lmdb.return_value.__getitem__.return_value = cbor.dumps('bad')
        store = \
            consensus_state_store.ConsensusStateStore(
                data_dir=tempfile.gettempdir(),
                validator_id='0123456789abcdef')

        with self.assertRaises(KeyError):
            _ = store['bad key']

    @mock.patch('sawtooth_poet.poet_consensus.consensus_state_store.'
                'LMDBNoLockDatabase')
    def test_consensus_store_set_get(self, mock_lmdb):
        """Verify that externally visible state (len, etc.) of the consensus
        state store after set is expected.  Verify that retrieving a
        previously set consensus state object results in the same values
        set.
        """
        # Make LMDB return empty dict
        my_dict = {}
        mock_lmdb.return_value = my_dict

        mock_poet_config_view = mock.Mock()
        mock_poet_config_view.target_wait_time = 30.0
        mock_poet_config_view.initial_wait_time = 3000.0
        mock_poet_config_view.minimum_wait_time = 1.0
        mock_poet_config_view.population_estimate_sample_size = 50

        store = \
            consensus_state_store.ConsensusStateStore(
                data_dir=tempfile.gettempdir(),
                validator_id='0123456789abcdef')

        # Verify the length is zero and doesn't contain key
        self.assertEqual(len(store), 0)
        self.assertTrue('key' not in store)

        # Store consensus state
        state = consensus_state.ConsensusState()
        store['key'] = state

        # Verify the length and contains key
        self.assertEqual(len(store), 1)
        self.assertEqual(len(my_dict), 1)
        self.assertTrue('key' in store)
        self.assertTrue('key' in my_dict)

        # Retrieve the state and verify equality
        retrieved_state = store['key']

        self.assertEqual(
            state.aggregate_local_mean,
            retrieved_state.aggregate_local_mean)
        self.assertEqual(
            state.total_block_claim_count,
            retrieved_state.total_block_claim_count)

        # Have a validator claim a block and update the store
        wait_certificate = mock.Mock()
        wait_certificate.duration = 3.1415
        wait_certificate.local_mean = 5.0
        validator_info = \
            ValidatorInfo(
                id='validator_001',
                signup_info=SignUpInfo(
                    poet_public_key='key_001'))
        state.validator_did_claim_block(
            validator_info=validator_info,
            wait_certificate=wait_certificate,
            poet_config_view=mock_poet_config_view)
        store['key'] = state

        # Verify the length and contains key
        self.assertEqual(len(store), 1)
        self.assertEqual(len(my_dict), 1)
        self.assertTrue('key' in store)
        self.assertTrue('key' in my_dict)

        # Retrieve the state and verify equality
        retrieved_state = store['key']

        self.assertEqual(
            state.aggregate_local_mean,
            retrieved_state.aggregate_local_mean)
        self.assertEqual(
            state.total_block_claim_count,
            retrieved_state.total_block_claim_count)

        validator_state = \
            retrieved_state.get_validator_state(
                validator_info=validator_info)
        retrieved_validator_state = \
            retrieved_state.get_validator_state(
                validator_info=validator_info)

        self.assertEqual(
            validator_state.key_block_claim_count,
            retrieved_validator_state.key_block_claim_count)
        self.assertEqual(
            validator_state.poet_public_key,
            retrieved_validator_state.poet_public_key)
        self.assertEqual(
            validator_state.total_block_claim_count,
            retrieved_validator_state.total_block_claim_count)

        # Delete the key and then verify length and does not contain key
        del store['key']
        self.assertEqual(len(store), 0)
        self.assertEqual(len(my_dict), 0)
        self.assertTrue('key' not in store)
        self.assertTrue('key' not in my_dict)

        with self.assertRaises(KeyError):
            _ = store['key']

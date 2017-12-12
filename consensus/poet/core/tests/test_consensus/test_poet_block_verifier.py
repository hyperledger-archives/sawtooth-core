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

import shutil
import tempfile

from unittest import TestCase
from unittest import mock

from sawtooth_poet.poet_consensus.poet_block_verifier import PoetBlockVerifier
from sawtooth_poet.poet_consensus.mock_consensus_state import\
    MockConsensusState

from sawtooth_poet_common.protobuf.validator_registry_pb2 \
    import ValidatorInfo
from sawtooth_poet_common.protobuf.validator_registry_pb2 \
    import SignUpInfo


@mock.patch('sawtooth_poet.poet_consensus.poet_block_verifier.'
            'ConsensusStateStore')
@mock.patch('sawtooth_poet.poet_consensus.poet_block_verifier.BlockWrapper')
@mock.patch('sawtooth_poet.poet_consensus.poet_block_verifier.'
            'PoetSettingsView')
@mock.patch('sawtooth_poet.poet_consensus.poet_block_verifier.factory')
class TestPoetBlockVerifier(TestCase):

    def setUp(self):
        self._temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self._temp_dir)

    @mock.patch(
        'sawtooth_poet.poet_consensus.poet_block_verifier.ConsensusState')
    @mock.patch('sawtooth_poet.poet_consensus.poet_block_verifier.'
                'ValidatorRegistryView')
    @mock.patch('sawtooth_poet.poet_consensus.poet_block_verifier.utils')
    def test_non_poet_block(self,
                            mock_utils,
                            mock_validator_registry_view,
                            mock_consensus_state,
                            mock_poet_enclave_factory,
                            mock_poet_settings_view,
                            mock_block_wrapper,
                            mock_consensus_state_store):
        """Verify that the PoET block verifier indicates failure if the block
        is not a PoET block (i.e., the consensus field in the block header
        is not a serialized wait certificate).
        """

        # Ensure that the consensus state does not generate failures that would
        # allow this test to pass
        mock_state = MockConsensusState.create_mock_consensus_state()

        mock_consensus_state.consensus_state_for_block_id.return_value = \
            mock_state

        # Make utils pretend it cannot deserialize the wait certificate
        mock_utils.deserialize_wait_certificate.return_value = None

        mock_block_cache = mock.MagicMock()
        mock_state_view_factory = mock.Mock()
        mock_block = mock.Mock(identifier='0123456789abcdefedcba9876543210')

        mock_validator_registry_view.return_value.get_validator_info.\
            return_value = \
            ValidatorInfo(
                name='validator_001',
                id='validator_deadbeef',
                signup_info=SignUpInfo(
                    poet_public_key='00112233445566778899aabbccddeeff'))

        with mock.patch('sawtooth_poet.poet_consensus.poet_block_verifier.'
                        'LOGGER') as mock_logger:
            block_verifier = \
                PoetBlockVerifier(
                    block_cache=mock_block_cache,
                    state_view_factory=mock_state_view_factory,
                    data_dir=self._temp_dir,
                    config_dir=self._temp_dir,
                    validator_id='validator_deadbeef')
            self.assertFalse(
                block_verifier.verify_block(
                    block_wrapper=mock_block))

            # Could be a hack, but verify that the appropriate log message is
            # generated - so we at least have some faith that the failure was
            # because of what we are testing and not something else.  I know
            # that this is fragile if the log message is changed, so would
            # accept any suggestions on a better way to verify that the
            # function fails for the reason we expect.
            (message, *_), _ = mock_logger.error.call_args
            self.assertTrue(
                'was not created by PoET consensus module' in message)

    @mock.patch(
        'sawtooth_poet.poet_consensus.poet_block_verifier.ConsensusState')
    @mock.patch('sawtooth_poet.poet_consensus.poet_block_verifier.'
                'ValidatorRegistryView')
    @mock.patch('sawtooth_poet.poet_consensus.poet_block_verifier.utils')
    def test_invalid_wait_certificate(self,
                                      mock_utils,
                                      mock_validator_registry_view,
                                      mock_consensus_state,
                                      mock_poet_enclave_factory,
                                      mock_poet_settings_view,
                                      mock_block_wrapper,
                                      mock_consensus_state_store):

        # Ensure that the consensus state does not generate failures that would
        # allow this test to pass
        mock_state = MockConsensusState.create_mock_consensus_state()

        mock_consensus_state.consensus_state_for_block_id.return_value = \
            mock_state

        # Make the certificate's check_valid pretend it failed
        mock_wait_certificate = mock.Mock()
        mock_wait_certificate.check_valid.side_effect = \
            ValueError('Unit test fake failure')

        mock_utils.deserialize_wait_certificate.return_value = \
            mock_wait_certificate

        mock_block_cache = mock.MagicMock()
        mock_state_view_factory = mock.Mock()
        mock_block = mock.Mock(identifier='0123456789abcdefedcba9876543210')

        mock_validator_registry_view.return_value.get_validator_info.\
            return_value = \
            ValidatorInfo(
                name='validator_001',
                id='validator_deadbeef',
                signup_info=SignUpInfo(
                    poet_public_key='00112233445566778899aabbccddeeff'))

        with mock.patch('sawtooth_poet.poet_consensus.poet_block_verifier.'
                        'LOGGER') as mock_logger:
            block_verifier = \
                PoetBlockVerifier(
                    block_cache=mock_block_cache,
                    state_view_factory=mock_state_view_factory,
                    data_dir=self._temp_dir,
                    config_dir=self._temp_dir,
                    validator_id='validator_deadbeef')
            self.assertFalse(
                block_verifier.verify_block(
                    block_wrapper=mock_block))

            # Could be a hack, but verify that the appropriate log message is
            # generated - so we at least have some faith that the failure was
            # because of what we are testing and not something else.  I know
            # that this is fragile if the log message is changed, so would
            # accept any suggestions on a better way to verify that the
            # function fails for the reason we expect.
            (message, *_), _ = mock_logger.error.call_args
            self.assertTrue('Wait certificate check failed' in message)

    @mock.patch(
        'sawtooth_poet.poet_consensus.poet_block_verifier.ConsensusState')
    @mock.patch('sawtooth_poet.poet_consensus.poet_block_verifier.'
                'ValidatorRegistryView')
    @mock.patch('sawtooth_poet.poet_consensus.poet_block_verifier.utils')
    def test_block_claimed_by_unknown_validator(self,
                                                mock_utils,
                                                mock_validator_registry_view,
                                                mock_consensus_state,
                                                mock_poet_enclave_factory,
                                                mock_poet_settings_view,
                                                mock_block_wrapper,
                                                mock_consensus_state_store):
        """ Test verifies that PoET Block Verifier fails if a block is
        claimed by an unknown validator (the validator is not listed
        in the validator registry)
        """

        # create a mock_validator_registry_view that throws KeyError
        mock_validator_registry_view.return_value.get_validator_info.\
            side_effect = KeyError('Non-existent validator')

        # create a mock_wait_certificate that does nothing in check_valid
        mock_wait_certificate = mock.Mock()
        mock_wait_certificate.check_valid.return_value = None

        mock_utils.deserialize_wait_certificate.return_value = \
            mock_wait_certificate

        # create a mock_consensus_state that returns a mock with
        # the following settings:
        mock_state = MockConsensusState.create_mock_consensus_state()

        mock_consensus_state.consensus_state_for_block_id.return_value = \
            mock_state

        # check test
        mock_block_cache = mock.MagicMock()
        mock_state_view_factory = mock.Mock()
        mock_block = mock.Mock(identifier='0123456789abcdefedcba9876543210')
        mock_block.header.signer_public_key = \
            '90834587139405781349807435098745'

        with mock.patch('sawtooth_poet.poet_consensus.poet_block_verifier.'
                        'LOGGER') as mock_logger:

            block_verifier = \
                PoetBlockVerifier(
                    block_cache=mock_block_cache,
                    state_view_factory=mock_state_view_factory,
                    data_dir=self._temp_dir,
                    config_dir=self._temp_dir,
                    validator_id='validator_deadbeef')
            self.assertFalse(
                block_verifier.verify_block(
                    block_wrapper=mock_block))

            # Could be a hack, but verify that the appropriate log message is
            # generated - so we at least have some faith that the failure was
            # because of what we are testing and not something else.  I know
            # that this is fragile if the log message is changed, so would
            # accept any suggestions on a better way to verify that the
            # function fails for the reason we expect.
            (message, *_), _ = mock_logger.error.call_args
            self.assertTrue('Received block from an unregistered '
                            'validator' in message)

    @mock.patch(
        'sawtooth_poet.poet_consensus.poet_block_verifier.ConsensusState')
    @mock.patch('sawtooth_poet.poet_consensus.poet_block_verifier.'
                'ValidatorRegistryView')
    @mock.patch('sawtooth_poet.poet_consensus.poet_block_verifier.utils')
    def test_signup_info_not_committed_within_allowed_delay(
            self,
            mock_utils,
            mock_validator_registry_view,
            mock_consensus_state,
            mock_poet_enclave_factory,
            mock_poet_settings_view,
            mock_block_wrapper,
            mock_consensus_state_store):
        """ Test verifies that PoET Block Verifier fails if
        a validator's signup info was not committed to
        the block chain within the allowed configured delay
        """

        # create a mock_validator_registry_view with
        # get_validator_info that does nothing
        mock_validator_registry_view.return_value.get_validator_info. \
            return_value = \
            ValidatorInfo(
                name='validator_001',
                id='validator_deadbeef',
                signup_info=SignUpInfo(
                    poet_public_key='00112233445566778899aabbccddeeff'))

        # create a mock_wait_certificate that does nothing in check_valid
        mock_wait_certificate = mock.Mock()
        mock_wait_certificate.check_valid.return_value = None

        mock_utils.deserialize_wait_certificate.return_value = \
            mock_wait_certificate

        # create a mock_consensus_state that returns a mock with
        # the following settings:
        mock_state = MockConsensusState.create_mock_consensus_state(
            committed_too_late=True)

        mock_consensus_state.consensus_state_for_block_id.return_value = \
            mock_state

        # check test
        mock_block_cache = mock.MagicMock()
        mock_state_view_factory = mock.Mock()
        mock_block = mock.Mock(identifier='0123456789abcdefedcba9876543210')

        with mock.patch('sawtooth_poet.poet_consensus.poet_block_verifier.'
                        'LOGGER') as mock_logger:

            block_verifier = \
                PoetBlockVerifier(
                    block_cache=mock_block_cache,
                    state_view_factory=mock_state_view_factory,
                    data_dir=self._temp_dir,
                    config_dir=self._temp_dir,
                    validator_id='validator_deadbeef')
            self.assertFalse(
                block_verifier.verify_block(
                    block_wrapper=mock_block))

            # Could be a hack, but verify that the appropriate log message is
            # generated - so we at least have some faith that the failure was
            # because of what we are testing and not something else.  I know
            # that this is fragile if the log message is changed, so would
            # accept any suggestions on a better way to verify that the
            # function fails for the reason we expect.
            (message, *_), _ = mock_logger.error.call_args
            self.assertTrue('Validator signup information not '
                            'committed in a timely manner' in message)

    @mock.patch(
        'sawtooth_poet.poet_consensus.poet_block_verifier.ConsensusState')
    @mock.patch('sawtooth_poet.poet_consensus.poet_block_verifier.'
                'ValidatorRegistryView')
    @mock.patch('sawtooth_poet.poet_consensus.poet_block_verifier.utils')
    def test_k_policy(self,
                      mock_utils,
                      mock_validator_registry_view,
                      mock_consensus_state,
                      mock_poet_enclave_factory,
                      mock_poet_settings_view,
                      mock_block_wrapper,
                      mock_consensus_state_store):
        """ Test verifies the K Policy: that PoET Block Verifier fails
        if a validator attempts to claim more blocks than is allowed
        by the key block claim limit
        """

        # create a mock_validator_registry_view with get_validator_info
        # that does nothing
        mock_validator_registry_view.return_value.get_validator_info. \
            return_value = \
            ValidatorInfo(
                name='validator_001',
                id='validator_deadbeef',
                signup_info=SignUpInfo(
                    poet_public_key='00112233445566778899aabbccddeeff'))

        # create a mock_wait_certificate that does nothing in check_valid
        mock_wait_certificate = mock.Mock()
        mock_wait_certificate.check_valid.return_value = None

        mock_utils.deserialize_wait_certificate.return_value = \
            mock_wait_certificate

        # create a mock_consensus_state that returns a mock with
        # the following settings:
        mock_state = MockConsensusState.create_mock_consensus_state(
            claimed_block_limit=True)

        mock_consensus_state.consensus_state_for_block_id.return_value = \
            mock_state

        # check test
        mock_block_cache = mock.MagicMock()
        mock_state_view_factory = mock.Mock()
        mock_block = mock.Mock(identifier='0123456789abcdefedcba9876543210')

        with mock.patch('sawtooth_poet.poet_consensus.poet_block_verifier.'
                        'LOGGER') as mock_logger:

            block_verifier = \
                PoetBlockVerifier(
                    block_cache=mock_block_cache,
                    state_view_factory=mock_state_view_factory,
                    data_dir=self._temp_dir,
                    config_dir=self._temp_dir,
                    validator_id='validator_deadbeef')
            self.assertFalse(
                block_verifier.verify_block(
                    block_wrapper=mock_block))

            # Could be a hack, but verify that the appropriate log message is
            # generated - so we at least have some faith that the failure was
            # because of what we are testing and not something else.  I know
            # that this is fragile if the log message is changed, so would
            # accept any suggestions on a better way to verify that the
            # function fails for the reason we expect.
            (message, *_), _ = mock_logger.error.call_args
            self.assertTrue('Validator has reached maximum number of '
                            'blocks with key pair' in message)

    @mock.patch(
        'sawtooth_poet.poet_consensus.poet_block_verifier.ConsensusState')
    @mock.patch('sawtooth_poet.poet_consensus.poet_block_verifier.'
                'ValidatorRegistryView')
    @mock.patch('sawtooth_poet.poet_consensus.poet_block_verifier.utils')
    def test_c_policy(self,
                      mock_utils,
                      mock_validator_registry_view,
                      mock_consensus_state,
                      mock_poet_enclave_factory,
                      mock_poet_settings_view,
                      mock_block_wrapper,
                      mock_consensus_state_store):
        """ Test verifies the C Policy: that PoET Block Verifier fails
         if a validator attempts to claim a block before
         the block claim delay block has passed
        """

        # create a mock_validator_registry_view with get_validator_info
        # that does nothing
        mock_validator_registry_view.return_value.get_validator_info. \
            return_value = \
            ValidatorInfo(
                name='validator_001',
                id='validator_deadbeef',
                signup_info=SignUpInfo(
                    poet_public_key='00112233445566778899aabbccddeeff'))

        # create a mock_wait_certificate that does nothing in check_valid
        mock_wait_certificate = mock.Mock()
        mock_wait_certificate.check_valid.return_value = None

        mock_utils.deserialize_wait_certificate.return_value = \
            mock_wait_certificate

        # create a mock_consensus_state that returns a mock with
        # the following settings:
        mock_state = MockConsensusState.create_mock_consensus_state(
            claiming_too_early=True)

        mock_consensus_state.consensus_state_for_block_id.return_value = \
            mock_state

        # check test
        mock_block_cache = mock.MagicMock()
        mock_state_view_factory = mock.Mock()
        mock_block = mock.Mock(identifier='0123456789abcdefedcba9876543210')

        with mock.patch('sawtooth_poet.poet_consensus.poet_block_verifier.'
                        'LOGGER') as mock_logger:

            block_verifier = \
                PoetBlockVerifier(
                    block_cache=mock_block_cache,
                    state_view_factory=mock_state_view_factory,
                    data_dir=self._temp_dir,
                    config_dir=self._temp_dir,
                    validator_id='validator_deadbeef')
            self.assertFalse(
                block_verifier.verify_block(
                    block_wrapper=mock_block))

            # Could be a hack, but verify that the appropriate log message is
            # generated - so we at least have some faith that the failure was
            # because of what we are testing and not something else.  I know
            # that this is fragile if the log message is changed, so would
            # accept any suggestions on a better way to verify that the
            # function fails for the reason we expect.
            (message, *_), _ = mock_logger.error.call_args
            self.assertTrue('Validator has not waited long enough '
                            'since registering validator '
                            'information' in message)

    @mock.patch(
        'sawtooth_poet.poet_consensus.poet_block_verifier.ConsensusState')
    @mock.patch('sawtooth_poet.poet_consensus.poet_block_verifier.'
                'ValidatorRegistryView')
    @mock.patch('sawtooth_poet.poet_consensus.poet_block_verifier.utils')
    def test_z_policy(self,
                      mock_utils,
                      mock_validator_registry_view,
                      mock_consensus_state,
                      mock_poet_enclave_factory,
                      mock_poet_settings_view,
                      mock_block_wrapper,
                      mock_consensus_state_store):
        """ Test verifies the Z Policy: that PoET Block Verifier fails
        if a validator attempts to claim more blocks frequently than is allowed
        """

        # create a mock_validator_registry_view that does nothing
        # in get_validator_info
        mock_validator_registry_view.return_value.get_validator_info. \
            return_value = \
            ValidatorInfo(
                name='validator_001',
                id='validator_deadbeef',
                signup_info=SignUpInfo(
                    poet_public_key='00112233445566778899aabbccddeeff'))

        # create a mock_wait_certificate that does nothing in check_valid
        mock_wait_certificate = mock.Mock()
        mock_wait_certificate.check_valid.return_value = None

        mock_utils.deserialize_wait_certificate.return_value = \
            mock_wait_certificate

        # create a mock_consensus_state that returns a mock with
        # the following settings:
        mock_state = MockConsensusState.create_mock_consensus_state(
            claiming_too_frequently=True)

        mock_consensus_state.consensus_state_for_block_id.return_value = \
            mock_state

        # check test
        mock_block_cache = mock.MagicMock()
        mock_state_view_factory = mock.Mock()
        mock_block = mock.Mock(identifier='0123456789abcdefedcba9876543210')

        with mock.patch('sawtooth_poet.poet_consensus.poet_block_verifier.'
                        'LOGGER') as mock_logger:

            block_verifier = \
                PoetBlockVerifier(
                    block_cache=mock_block_cache,
                    state_view_factory=mock_state_view_factory,
                    data_dir=self._temp_dir,
                    config_dir=self._temp_dir,
                    validator_id='validator_deadbeef')
            self.assertFalse(
                block_verifier.verify_block(
                    block_wrapper=mock_block))

            # Could be a hack, but verify that the appropriate log message is
            # generated - so we at least have some faith that the failure was
            # because of what we are testing and not something else.  I know
            # that this is fragile if the log message is changed, so would
            # accept any suggestions on a better way to verify that the
            # function fails for the reason we expect.
            (message, *_), _ = mock_logger.error.call_args
            self.assertTrue('Validator is claiming blocks too '
                            'frequently' in message)

    @mock.patch(
        'sawtooth_poet.poet_consensus.poet_block_verifier.ConsensusState')
    @mock.patch('sawtooth_poet.poet_consensus.poet_block_verifier.'
                'ValidatorRegistryView')
    @mock.patch('sawtooth_poet.poet_consensus.poet_block_verifier.utils')
    def test_block_verifier_valid_block_claim(
            self,
            mock_utils,
            mock_validator_registry_view,
            mock_consensus_state,
            mock_poet_enclave_factory,
            mock_poet_settings_view,
            mock_block_wrapper,
            mock_consensus_state_store):
        """ Test verifies that PoET Block Verifier succeeds if
        a validator successfully passes all criteria necessary
        to claim a block
        """

        # create a mock_validator_registry_view with
        # get_validator_info that does nothing
        mock_validator_registry_view.return_value.get_validator_info. \
            return_value = \
            ValidatorInfo(
                name='validator_001',
                id='validator_deadbeef',
                signup_info=SignUpInfo(
                    poet_public_key='00112233445566778899aabbccddeeff'))

        # create a mock_wait_certificate that does nothing in check_valid
        mock_wait_certificate = mock.Mock()
        mock_wait_certificate.check_valid.return_value = None

        mock_utils.deserialize_wait_certificate.return_value = \
            mock_wait_certificate

        # create a mock_consensus_state that returns a mock with
        # the following settings:
        mock_state = MockConsensusState.create_mock_consensus_state()

        mock_consensus_state.consensus_state_for_block_id.return_value = \
            mock_state

        # check test
        mock_block_cache = mock.MagicMock()
        mock_state_view_factory = mock.Mock()
        mock_block = mock.Mock(identifier='0123456789abcdefedcba9876543210')

        block_verifier = \
            PoetBlockVerifier(
                block_cache=mock_block_cache,
                state_view_factory=mock_state_view_factory,
                data_dir=self._temp_dir,
                config_dir=self._temp_dir,
                validator_id='validator_deadbeef')
        self.assertTrue(
            block_verifier.verify_block(
                block_wrapper=mock_block))

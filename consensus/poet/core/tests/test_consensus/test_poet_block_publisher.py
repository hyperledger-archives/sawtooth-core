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
import shutil
import tempfile

from importlib import reload

from unittest import TestCase
from unittest import mock

import sawtooth_signing as signing

from sawtooth_poet.poet_consensus import poet_block_publisher

from sawtooth_poet_common.protobuf.validator_registry_pb2 \
    import ValidatorInfo
from sawtooth_poet_common.protobuf.validator_registry_pb2 \
    import SignUpInfo


@mock.patch('sawtooth_poet.poet_consensus.poet_block_publisher.BlockWrapper')
@mock.patch('sawtooth_poet.poet_consensus.poet_block_publisher.PoetConfigView')
class TestPoetBlockPublisher(TestCase):

    def setUp(self):
        # pylint: disable=invalid-name,global-statement
        global poet_block_publisher
        # PoetBLockPublisher uses class variables to hold state
        # so the module needs to be reloaded after each test to clear state
        poet_block_publisher = reload(poet_block_publisher)

        self._temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self._temp_dir)

    @mock.patch('sawtooth_poet.poet_consensus.poet_block_publisher.'
                'SignupInfo')
    @mock.patch('sawtooth_poet.poet_consensus.poet_block_publisher.'
                'PoetKeyStateStore')
    @mock.patch('sawtooth_poet.poet_consensus.poet_block_publisher.'
                'ConsensusStateStore')
    @mock.patch('sawtooth_poet.poet_consensus.poet_block_publisher.factory')
    @mock.patch('sawtooth_poet.poet_consensus.poet_block_publisher.'
                'ConsensusState')
    @mock.patch('sawtooth_poet.poet_consensus.poet_block_publisher.'
                'ValidatorRegistryView')
    @mock.patch('sawtooth_poet.poet_consensus.poet_block_publisher.utils')
    def test_no_validator_registry(
            self,
            mock_utils,
            mock_validator_registry_view,
            mock_consensus_state,
            mock_poet_enclave_factory,
            mock_consensus_state_store,
            mock_poet_key_state_store,
            mock_signup_info,
            mock_poet_config_view,
            mock_block_wrapper):

        """ Test verifies that PoET Block Publisher fails
        if a validator doesn't have any signup info
        in the validator registry (the validator is not listed
        in the validator registry)
        """

        # create a mock_validator_registry_view that throws KeyError
        mock_validator_registry_view.return_value.get_validator_info. \
            side_effect = KeyError('Non-existent validator')

        # create a mock_wait_certificate that does nothing in check_valid
        mock_wait_certificate = mock.Mock()
        mock_wait_certificate.check_valid.return_value = None

        mock_utils.deserialize_wait_certificate.return_value = \
            mock_wait_certificate

        # create a mock_consensus_state that returns a mock with
        # the following settings:
        mock_state = mock.Mock()
        mock_state.validator_signup_was_committed_too_late.return_value = False
        mock_state.validator_has_claimed_block_limit.return_value = False
        mock_state.validator_is_claiming_too_early.return_value = False
        mock_state.validator_is_claiming_too_frequently.return_value = False

        mock_consensus_state.consensus_state_for_block_id.return_value = \
            mock_state

        mock_consensus_state_store.return_value.__getitem__.return_value = \
            mock_consensus_state

        # create mock_signup_info
        mock_signup_info.create_signup_info.return_value = \
            mock.Mock(
                poet_public_key='poet public key',
                proof_data='proof data',
                anti_sybil_id='anti-sybil ID',
                sealed_signup_data='sealed signup data')

        # create mock_batch_publisher
        mock_batch_publisher = mock.Mock(
            identity_signing_key=signing.generate_privkey())

        mock_block_cache = mock.MagicMock()
        mock_state_view_factory = mock.Mock()

        # create mock_block_header with the following fields
        mock_block = mock.Mock(identifier='0123456789abcdefedcba9876543210')
        mock_block.header.signer_pubkey = '90834587139405781349807435098745'
        mock_block.header.previous_block_id = '2'
        mock_block.header.block_num = 1
        mock_block.header.state_root_hash = '6'
        mock_block.header.batch_ids = '4'

        # check test
        block_publisher = \
            poet_block_publisher.PoetBlockPublisher(
                block_cache=mock_block_cache,
                state_view_factory=mock_state_view_factory,
                batch_publisher=mock_batch_publisher,
                data_dir=self._temp_dir,
                config_dir=self._temp_dir,
                validator_id='validator_deadbeef')

        self.assertFalse(
            block_publisher.initialize_block(
                block_header=mock_block.header))

        # check that batch publisher was called to send out
        # the txn header and txn for the validator registry update
        self.assertTrue(mock_batch_publisher.send.called)

    @mock.patch('sawtooth_poet.poet_consensus.poet_block_publisher.'
                'SignupInfo')
    @mock.patch('sawtooth_poet.poet_consensus.poet_block_publisher.'
                'PoetKeyStateStore')
    @mock.patch('sawtooth_poet.poet_consensus.poet_block_publisher.'
                'ConsensusStateStore')
    @mock.patch('sawtooth_poet.poet_consensus.poet_block_publisher.factory')
    @mock.patch('sawtooth_poet.poet_consensus.poet_block_publisher.'
                'ConsensusState')
    @mock.patch('sawtooth_poet.poet_consensus.poet_block_publisher.'
                'ValidatorRegistryView')
    @mock.patch('sawtooth_poet.poet_consensus.poet_block_publisher.utils')
    def test_signup_info_not_committed_within_allowed_delay(
            self,
            mock_utils,
            mock_validator_registry_view,
            mock_consensus_state,
            mock_poet_enclave_factory,
            mock_consensus_state_store,
            mock_poet_key_state_store,
            mock_signup_info,
            mock_poet_config_view,
            mock_block_wrapper):

        """ Test verifies that PoET Block Publisher fails if
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
        mock_state = mock.Mock()
        mock_state.validator_signup_was_committed_too_late.return_value = \
            True
        mock_state.validator_has_claimed_block_limit.return_value = False
        mock_state.validator_is_claiming_too_early.return_value = False
        mock_state.validator_is_claiming_too_frequently.return_value = False

        mock_consensus_state.consensus_state_for_block_id.return_value = \
            mock_state

        mock_consensus_state_store.return_value.__getitem__.return_value = \
            mock_consensus_state

        # create mock_signup_info
        mock_signup_info.create_signup_info.return_value = \
            mock.Mock(
                poet_public_key='poet public key',
                proof_data='proof data',
                anti_sybil_id='anti-sybil ID',
                sealed_signup_data='sealed signup data')

        mock_signup_info.unseal_signup_data.return_value = \
            '00112233445566778899aabbccddeeff'

        # create mock_batch_publisher
        mock_batch_publisher = mock.Mock(
            identity_signing_key=signing.generate_privkey())

        mock_block_cache = mock.MagicMock()
        mock_state_view_factory = mock.Mock()

        # create mock_block_header with the following fields
        mock_block = mock.Mock(identifier='0123456789abcdefedcba9876543210')
        mock_block.header.signer_pubkey = '90834587139405781349807435098745'
        mock_block.header.previous_block_id = '2'
        mock_block.header.block_num = 1
        mock_block.header.state_root_hash = '6'
        mock_block.header.batch_ids = '4'

        # check test
        with mock.patch('sawtooth_poet.poet_consensus.poet_block_publisher.'
                        'LOGGER') as mock_logger:
            block_publisher = \
                poet_block_publisher.PoetBlockPublisher(
                    block_cache=mock_block_cache,
                    state_view_factory=mock_state_view_factory,
                    batch_publisher=mock_batch_publisher,
                    data_dir=self._temp_dir,
                    config_dir=self._temp_dir,
                    validator_id='validator_deadbeef')

            self.assertFalse(
                block_publisher.initialize_block(
                    block_header=mock_block.header))

            # Could be a hack, but verify that the appropriate log message is
            # generated - so we at least have some faith that the failure was
            # because of what we are testing and not something else.  I know
            # that this is fragile if the log message is changed, so would
            # accept any suggestions on a better way to verify that the
            # function fails for the reason we expect.

            (message, *_), _ = mock_logger.error.call_args
            self.assertTrue('Validator signup information '
                            'not committed in a timely manner.' in message)

            # check that create.signup_info() was called to create
            # the validator registry payload with new set of keys
            self.assertTrue(mock_signup_info.create_signup_info.called)

    @mock.patch('sawtooth_poet.poet_consensus.poet_block_publisher.'
                'SignupInfo')
    @mock.patch('sawtooth_poet.poet_consensus.poet_block_publisher.'
                'PoetKeyStateStore')
    @mock.patch('sawtooth_poet.poet_consensus.poet_block_publisher.'
                'ConsensusStateStore')
    @mock.patch('sawtooth_poet.poet_consensus.poet_block_publisher.factory')
    @mock.patch('sawtooth_poet.poet_consensus.poet_block_publisher.'
                'ConsensusState')
    @mock.patch('sawtooth_poet.poet_consensus.poet_block_publisher.'
                'ValidatorRegistryView')
    @mock.patch('sawtooth_poet.poet_consensus.poet_block_publisher.utils')
    def test_k_policy(
            self,
            mock_utils,
            mock_validator_registry_view,
            mock_consensus_state,
            mock_poet_enclave_factory,
            mock_consensus_state_store,
            mock_poet_key_state_store,
            mock_signup_info,
            mock_poet_config_view,
            mock_block_wrapper):

        """ K Policy: Test verifies that PoET Block Publisher fails if
        if a validator attempts to claim more blocks than is allowed
        by the key block claim limit
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
        mock_state = mock.Mock()
        mock_state.validator_signup_was_committed_too_late.return_value = False
        mock_state.validator_has_claimed_block_limit.return_value = True
        mock_state.validator_is_claiming_too_early.return_value = False
        mock_state.validator_is_claiming_too_frequently.return_value = False

        mock_consensus_state.consensus_state_for_block_id.return_value = \
            mock_state

        mock_consensus_state_store.return_value.__getitem__.return_value = \
            mock_consensus_state

        # create mock_signup_info
        mock_signup_info.unseal_signup_data.return_value = \
            '00112233445566778899aabbccddeeff'

        # create mock_batch_publisher
        mock_batch_publisher = mock.Mock(
            identity_signing_key=signing.generate_privkey())

        mock_block_cache = mock.MagicMock()
        mock_state_view_factory = mock.Mock()

        # create mock_block_header with the following fields
        mock_block = mock.Mock(identifier='0123456789abcdefedcba9876543210')
        mock_block.header.signer_pubkey = '90834587139405781349807435098745'
        mock_block.header.previous_block_id = '2'
        mock_block.header.block_num = 1
        mock_block.header.state_root_hash = '6'
        mock_block.header.batch_ids = '4'

        # check test
        with mock.patch('sawtooth_poet.poet_consensus.poet_block_publisher.'
                        'LOGGER') as mock_logger:
            block_publisher = \
                poet_block_publisher.PoetBlockPublisher(
                    block_cache=mock_block_cache,
                    state_view_factory=mock_state_view_factory,
                    batch_publisher=mock_batch_publisher,
                    data_dir=self._temp_dir,
                    config_dir=self._temp_dir,
                    validator_id='validator_deadbeef')

            self.assertFalse(
                block_publisher.initialize_block(
                    block_header=mock_block.header))

            # Could be a hack, but verify that the appropriate log message is
            # generated - so we at least have some faith that the failure was
            # because of what we are testing and not something else.  I know
            # that this is fragile if the log message is changed, so would
            # accept any suggestions on a better way to verify that the
            # function fails for the reason we expect.

            (message, *_), _ = mock_logger.error.call_args
            self.assertTrue('Validator has reached maximum number of '
                            'blocks with key pair' in message)

            # check that create.signup_info() wasn't called
            # to renew the set of keys
            self.assertFalse(mock_signup_info.create_signup_info.called)

    @mock.patch('sawtooth_poet.poet_consensus.poet_block_publisher.'
                'SignupInfo')
    @mock.patch('sawtooth_poet.poet_consensus.poet_block_publisher.'
                'PoetKeyStateStore')
    @mock.patch('sawtooth_poet.poet_consensus.poet_block_publisher.'
                'ConsensusStateStore')
    @mock.patch('sawtooth_poet.poet_consensus.poet_block_publisher.factory')
    @mock.patch('sawtooth_poet.poet_consensus.poet_block_publisher.'
                'ConsensusState')
    @mock.patch('sawtooth_poet.poet_consensus.poet_block_publisher.'
                'ValidatorRegistryView')
    @mock.patch('sawtooth_poet.poet_consensus.poet_block_publisher.utils')
    def test_c_policy(
            self,
            mock_utils,
            mock_validator_registry_view,
            mock_consensus_state,
            mock_poet_enclave_factory,
            mock_consensus_state_store,
            mock_poet_key_state_store,
            mock_signup_info,
            mock_poet_config_view,
            mock_block_wrapper):

        """ C Policy: Test verifies that PoET Block Publisher fails
        if a validator attempts to claim a block before
        the block claim delay block has passed
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
        mock_state = mock.Mock()
        mock_state.validator_signup_was_committed_too_late.return_value = False
        mock_state.validator_has_claimed_block_limit.return_value = False
        mock_state.validator_is_claiming_too_early.return_value = True
        mock_state.validator_is_claiming_too_frequently.return_value = False

        mock_consensus_state.consensus_state_for_block_id.return_value = \
            mock_state

        mock_consensus_state_store.return_value.__getitem__.return_value = \
            mock_consensus_state

        # create mock_signup_info
        mock_signup_info.unseal_signup_data.return_value = \
            '00112233445566778899aabbccddeeff'

        # create mock_batch_publisher
        mock_batch_publisher = mock.Mock(
            identity_signing_key=signing.generate_privkey())

        mock_block_cache = mock.MagicMock()
        mock_state_view_factory = mock.Mock()

        # create mock_block_header with the following fields
        mock_block = mock.Mock(identifier='0123456789abcdefedcba9876543210')
        mock_block.header.signer_pubkey = '90834587139405781349807435098745'
        mock_block.header.previous_block_id = '2'
        mock_block.header.block_num = 1
        mock_block.header.state_root_hash = '6'
        mock_block.header.batch_ids = '4'

        # check test
        with mock.patch('sawtooth_poet.poet_consensus.poet_block_publisher.'
                        'LOGGER') as mock_logger:
            block_publisher = \
                poet_block_publisher.PoetBlockPublisher(
                    block_cache=mock_block_cache,
                    state_view_factory=mock_state_view_factory,
                    batch_publisher=mock_batch_publisher,
                    data_dir=self._temp_dir,
                    config_dir=self._temp_dir,
                    validator_id='validator_deadbeef')

            self.assertFalse(
                block_publisher.initialize_block(
                    block_header=mock_block.header))

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

    @mock.patch('sawtooth_poet.poet_consensus.poet_block_publisher.'
                'SignupInfo')
    @mock.patch('sawtooth_poet.poet_consensus.poet_block_publisher.'
                'PoetKeyStateStore')
    @mock.patch('sawtooth_poet.poet_consensus.poet_block_publisher.'
                'ConsensusStateStore')
    @mock.patch('sawtooth_poet.poet_consensus.poet_block_publisher.factory')
    @mock.patch('sawtooth_poet.poet_consensus.poet_block_publisher.'
                'ConsensusState')
    @mock.patch('sawtooth_poet.poet_consensus.poet_block_publisher.'
                'ValidatorRegistryView')
    @mock.patch('sawtooth_poet.poet_consensus.poet_block_publisher.utils')
    def test_z_policy(
            self,
            mock_utils,
            mock_validator_registry_view,
            mock_consensus_state,
            mock_poet_enclave_factory,
            mock_consensus_state_store,
            mock_poet_key_state_store,
            mock_signup_info,
            mock_poet_config_view,
            mock_block_wrapper):

        """ Z Policy: Test verifies that PoET Block Publisher fails
        if a validator attempts to claim more blocks frequently than is allowed
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
        mock_state = mock.Mock()
        mock_state.validator_signup_was_committed_too_late.return_value = False
        mock_state.validator_has_claimed_block_limit.return_value = False
        mock_state.validator_is_claiming_too_early.return_value = False
        mock_state.validator_is_claiming_too_frequently.return_value = True

        mock_consensus_state.consensus_state_for_block_id.return_value = \
            mock_state

        mock_consensus_state_store.return_value.__getitem__.return_value = \
            mock_consensus_state

        # create mock_signup_info
        mock_signup_info.unseal_signup_data.return_value = \
            '00112233445566778899aabbccddeeff'

        # create mock_batch_publisher
        mock_batch_publisher = mock.Mock(
            identity_signing_key=signing.generate_privkey())

        mock_block_cache = mock.MagicMock()
        mock_state_view_factory = mock.Mock()

        # create mock_block_header with the following fields
        mock_block = mock.Mock(identifier='0123456789abcdefedcba9876543210')
        mock_block.header.signer_pubkey = '90834587139405781349807435098745'
        mock_block.header.previous_block_id = '2'
        mock_block.header.block_num = 1
        mock_block.header.state_root_hash = '6'
        mock_block.header.batch_ids = '4'

        # check test
        with mock.patch('sawtooth_poet.poet_consensus.poet_block_publisher.'
                        'LOGGER') as mock_logger:
            block_publisher = \
                poet_block_publisher.PoetBlockPublisher(
                    block_cache=mock_block_cache,
                    state_view_factory=mock_state_view_factory,
                    batch_publisher=mock_batch_publisher,
                    data_dir=self._temp_dir,
                    config_dir=self._temp_dir,
                    validator_id='validator_deadbeef')

            self.assertFalse(
                block_publisher.initialize_block(
                    block_header=mock_block.header))

            # Could be a hack, but verify that the appropriate log message is
            # generated - so we at least have some faith that the failure was
            # because of what we are testing and not something else.  I know
            # that this is fragile if the log message is changed, so would
            # accept any suggestions on a better way to verify that the
            # function fails for the reason we expect.

            (message, *_), _ = mock_logger.error.call_args
            self.assertTrue('Validator is claiming blocks too '
                            'frequently' in message)

    @mock.patch('sawtooth_poet.poet_consensus.poet_block_publisher.'
                'SignupInfo')
    @mock.patch('sawtooth_poet.poet_consensus.poet_block_publisher.'
                'PoetKeyStateStore')
    @mock.patch('sawtooth_poet.poet_consensus.poet_block_publisher.'
                'ConsensusStateStore')
    @mock.patch('sawtooth_poet.poet_consensus.poet_block_publisher.factory')
    @mock.patch('sawtooth_poet.poet_consensus.poet_block_publisher.'
                'ConsensusState')
    @mock.patch('sawtooth_poet.poet_consensus.poet_block_publisher.'
                'ValidatorRegistryView')
    @mock.patch('sawtooth_poet.poet_consensus.poet_block_publisher.utils')
    def test_block_publisher_success_case(
            self,
            mock_utils,
            mock_validator_registry_view,
            mock_consensus_state,
            mock_poet_enclave_factory,
            mock_consensus_state_store,
            mock_poet_key_state_store,
            mock_signup_info,
            mock_poet_config_view,
            mock_block_wrapper):

        """ Test verifies that PoET Block Publisher succeeds
        if a validator successfully passes all criteria necessary
        to publish a block
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
        mock_state = mock.Mock()
        mock_state.validator_signup_was_committed_too_late.return_value = False
        mock_state.validator_has_claimed_block_limit.return_value = False
        mock_state.validator_is_claiming_too_early.return_value = False
        mock_state.validator_is_claiming_too_frequently.return_value = False

        mock_consensus_state.consensus_state_for_block_id.return_value = \
            mock_state

        mock_consensus_state_store.return_value.__getitem__.return_value = \
            mock_consensus_state

        # create mock_signup_info
        mock_signup_info.unseal_signup_data.return_value = \
            '00112233445566778899aabbccddeeff'

        # create mock_batch_publisher
        mock_batch_publisher = mock.Mock(
            identity_signing_key=signing.generate_privkey())

        mock_block_cache = mock.MagicMock()
        mock_state_view_factory = mock.Mock()

        # create mock_block_header with the following fields
        mock_block = mock.Mock(identifier='0123456789abcdefedcba9876543210')
        mock_block.header.signer_pubkey = '90834587139405781349807435098745'
        mock_block.header.previous_block_id = '2'
        mock_block.header.block_num = 1
        mock_block.header.state_root_hash = '6'
        mock_block.header.batch_ids = '4'

        # check test
        block_publisher = \
            poet_block_publisher.PoetBlockPublisher(
                block_cache=mock_block_cache,
                state_view_factory=mock_state_view_factory,
                batch_publisher=mock_batch_publisher,
                data_dir=self._temp_dir,
                config_dir=self._temp_dir,
                validator_id='validator_deadbeef')

        self.assertTrue(
            block_publisher.initialize_block(
                block_header=mock_block.header))

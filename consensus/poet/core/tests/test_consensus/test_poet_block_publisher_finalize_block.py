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
                'WaitCertificate')
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
    def test_block_publisher_doesnt_finalize_block(
            self,
            mock_utils,
            mock_validator_registry_view,
            mock_consensus_state,
            mock_poet_enclave_factory,
            mock_consensus_state_store,
            mock_poet_key_state_store,
            mock_signup_info,
            mock_wait_certificate,
            mock_poet_config_view,
            mock_block_wrapper):

        """ Test verifies that PoET Block Publisher doesn't finalize
            a candidate block that doesn't have a valid wait certificate.
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

        # create a mock_wait_certificate that pretends to fail
        mock_wait_certificate.create_wait_certificate.side_effect = \
            ValueError('Unit test fake failure')

        # create a mock_consensus_state that returns a mock with
        # the following settings:
        mock_state = mock.Mock()
        mock_state.validator_signup_was_committed_too_late.return_value = False
        mock_state.validator_has_claimed_block_limit.return_value = False
        mock_state.validator_is_claiming_too_early.return_value = False
        mock_state.validator_is_claiming_too_frequently.return_value = False

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

            with mock.patch('sawtooth_poet.poet_consensus.'
                            'poet_block_publisher.json') as _:
                self.assertFalse(
                    block_publisher.finalize_block(
                        block_header=mock_block.header))

            # Could be a hack, but verify that the appropriate log message is
            # generated - so we at least have some faith that the failure was
            # because of what we are testing and not something else.  I know
            # that this is fragile if the log message is changed, so would
            # accept any suggestions on a better way to verify that the
            # function fails for the reason we expect.

            (message, *_), _ = mock_logger.error.call_args
            self.assertTrue('Failed to create wait certificate: '
                            in message)

    @mock.patch('sawtooth_poet.poet_consensus.poet_block_publisher'
                '.WaitCertificate')
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
    def test_block_publisher_finalize_block(
            self,
            mock_utils,
            mock_validator_registry_view,
            mock_consensus_state,
            mock_poet_enclave_factory,
            mock_consensus_state_store,
            mock_poet_key_state_store,
            mock_signup_info,
            mock_wait_certificate,
            mock_poet_config_view,
            mock_block_wrapper):

        """ Test verifies that PoET Block Publisher finalizes the block,
            meaning that the candidate block is good and should be generated.
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
        my_wait_certificate = mock.Mock()
        my_wait_certificate.check_valid.return_value = None
        mock_wait_certificate.create_wait_certificate.return_value = \
            my_wait_certificate

        # create a mock_consensus_state that returns a mock with
        # the following settings:
        mock_state = mock.Mock()
        mock_state.validator_signup_was_committed_too_late.return_value = False
        mock_state.validator_has_claimed_block_limit.return_value = False
        mock_state.validator_is_claiming_too_early.return_value = False
        mock_state.validator_is_claiming_too_frequently.return_value = False

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

        with mock.patch('sawtooth_poet.poet_consensus.'
                        'poet_block_publisher.json') as _:
            self.assertTrue(block_publisher.finalize_block(
                block_header=mock_block.header))

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

from sawtooth_poet.poet_consensus import poet_fork_resolver

from sawtooth_poet_common.protobuf.validator_registry_pb2 \
    import ValidatorInfo
from sawtooth_poet_common.protobuf.validator_registry_pb2 \
    import SignUpInfo


# @mock.patch('sawtooth_poet.poet_consensus.poet_fork_resolver.BlockWrapper')
# @mock.patch('sawtooth_poet.poet_consensus.poet_fork_resolver.'
#             'PoetSettingsView')
class TestPoetForkResolver(TestCase):

    def setUp(self):
        # pylint: disable=invalid-name,global-statement
        global poet_fork_resolver
        # PoetBLockResolver uses class variables to hold state
        # so the module needs to be reloaded after each test to clear state
        poet_fork_resolver = reload(poet_fork_resolver)

        self._temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self._temp_dir)

    @mock.patch('sawtooth_poet.poet_consensus.poet_fork_resolver.'
                'ConsensusStateStore')
    @mock.patch('sawtooth_poet.poet_consensus.poet_fork_resolver.factory')
    @mock.patch('sawtooth_poet.poet_consensus.poet_fork_resolver.'
                'ConsensusState')
    @mock.patch('sawtooth_poet.poet_consensus.poet_fork_resolver.'
                'ValidatorRegistryView')
    @mock.patch('sawtooth_poet.poet_consensus.poet_fork_resolver.utils')
    def test_new_fork_head_not_poet_block(
            self,
            mock_utils,
            mock_validator_registry_view,
            mock_consensus_state,
            mock_poet_enclave_factory,
            mock_consensus_state_store):
        """ Test verifies that if the new fork head is not a valid block,
            raises appropriate exception
        """

        # create a mock_validator_registry_view
        mock_validator_registry_view.return_value.get_validator_info. \
            return_value = \
            ValidatorInfo(
                name='validator_001',
                id='validator_deadbeef',
                signup_info=SignUpInfo(
                    poet_public_key='00112233445566778899aabbccddeeff'))

        # Make utils pretend it cannot deserialize the wait certificate
        # of the new fork head
        mock_utils.deserialize_wait_certificate.return_value = None

        mock_block_cache = mock.MagicMock()
        mock_state_view_factory = mock.Mock()

        # create mock_cur_fork_head
        mock_cur_fork_header = \
            mock.Mock(
                identifier='0123456789abcdefedcba9876543210',
                signer_public_key='90834587139405781349807435098745',
                previous_block_id='2',
                header_signature='00112233445566778899aabbccddeeff')

        # create mock_new_fork_head
        mock_new_fork_header = \
            mock.Mock(
                identifier='0123456789abcdefedcba9876543211',
                signer_public_key='90834587139405781349807435098745',
                previous_block_id='2',
                header_signature='00112233445566778899aabbccddeeff')

        # check test
        fork_resolver = \
            poet_fork_resolver.PoetForkResolver(
                block_cache=mock_block_cache,
                state_view_factory=mock_state_view_factory,
                data_dir=self._temp_dir,
                config_dir=self._temp_dir,
                validator_id='validator_deadbeef')

        with self.assertRaises(TypeError) as cm:
            fork_resolver.compare_forks(
                cur_fork_head=mock_cur_fork_header,
                new_fork_head=mock_new_fork_header)
            self.assertEqual(
                'New fork head {} is not a PoET block',
                str(cm.exception))

    @mock.patch('sawtooth_poet.poet_consensus.poet_fork_resolver.'
                'ConsensusStateStore')
    @mock.patch('sawtooth_poet.poet_consensus.poet_fork_resolver.factory')
    @mock.patch('sawtooth_poet.poet_consensus.poet_fork_resolver.'
                'ConsensusState')
    @mock.patch('sawtooth_poet.poet_consensus.poet_fork_resolver.'
                'ValidatorRegistryView')
    @mock.patch('sawtooth_poet.poet_consensus.poet_fork_resolver.utils')
    def test_cur_fork_head_not_poet_block(
            self,
            mock_utils,
            mock_validator_registry_view,
            mock_consensus_state,
            mock_poet_enclave_factory,
            mock_consensus_state_store):
        """ Test verifies that if the current fork head is not a valid block,
            and if new_fork_head.previous_block_id == cur_fork_head.identifier
            then the new fork head switches consensus. Otherwise, raises the
            appropriate exception - trying to compare a PoET block to a
            non-PoET block that is not the direct predecessor
        """

        # create a mock_validator_registry_view
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

        # set mock_utils.deserialize_wait_certificate
        # to return a specific value for each fork_head that is used in
        # poet_fork_resolver.compare()
        # with cur_fork_head being deserialized first
        mock_utils.deserialize_wait_certificate.side_effect = \
            [None,
             mock_wait_certificate,
             None,
             mock_wait_certificate]

        mock_block_cache = mock.MagicMock()
        mock_state_view_factory = mock.Mock()

        # create mock_cur_fork_head
        mock_cur_fork_header = \
            mock.Mock(
                identifier='0123456789abcdefedcba9876543210',
                signer_public_key='90834587139405781349807435098745',
                previous_block_id='2',
                header_signature='00112233445566778899aabbccddeeff')

        # create mock_new_fork_head
        mock_new_fork_header = \
            mock.Mock(
                identifier='0123456789abcdefedcba9876543211',
                signer_public_key='90834587139405781349807435098745',
                previous_block_id='2',
                header_signature='00112233445566778899aabbccddeeff')

        fork_resolver = \
            poet_fork_resolver.PoetForkResolver(
                block_cache=mock_block_cache,
                state_view_factory=mock_state_view_factory,
                data_dir=self._temp_dir,
                config_dir=self._temp_dir,
                validator_id='validator_deadbeef')

        # Subtest 1: check that the test fails when the current
        # fork head is not a valid PoET block
        with self.assertRaises(TypeError) as cm:
            fork_resolver.compare_forks(
                cur_fork_head=mock_cur_fork_header,
                new_fork_head=mock_new_fork_header)
            self.assertEqual(
                'Trying to compare a PoET block to a non-PoET '
                'block that is not the direct predecessor',
                str(cm.exception))

        # Subtest 2: check that if new_fork_head.previous_block_id
        # == cur_fork_head.identifier
        # then the new fork head switches consensus

        # modify mock_cur_fork_header.identifier
        mock_cur_fork_header.identifier = \
            mock_new_fork_header.previous_block_id

        # check test
        with mock.patch('sawtooth_poet.poet_consensus.poet_fork_resolver.'
                        'LOGGER') as mock_logger:
            self.assertTrue(fork_resolver.compare_forks(
                cur_fork_head=mock_cur_fork_header,
                new_fork_head=mock_new_fork_header))

            # Could be a hack, but verify that the appropriate log message is
            # generated - so we at least have some faith that the failure was
            # because of what we are testing and not something else.  I know
            # that this is fragile if the log message is changed, so would
            # accept any suggestions on a better way to verify that the
            # function fails for the reason we expect.

            (message, *_), _ = mock_logger.info.call_args
            self.assertTrue('New fork head switches consensus to PoET'
                            in message)

    @mock.patch('sawtooth_poet.poet_consensus.poet_fork_resolver.'
                'ConsensusStateStore')
    @mock.patch('sawtooth_poet.poet_consensus.poet_fork_resolver.factory')
    @mock.patch('sawtooth_poet.poet_consensus.poet_fork_resolver.'
                'ConsensusState')
    @mock.patch('sawtooth_poet.poet_consensus.poet_fork_resolver.'
                'ValidatorRegistryView')
    @mock.patch('sawtooth_poet.poet_consensus.poet_fork_resolver.utils')
    def test_both_valid_poet_blocks(
            self,
            mock_utils,
            mock_validator_registry_view,
            mock_consensus_state,
            mock_poet_enclave_factory,
            mock_consensus_state_store):
        """ If both current and new fork heads are valid PoET blocks,
            the test checks if they share the same immediate previous block,
            then the one with the smaller wait duration is chosen
        """

        # create a mock_validator_registry_view
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

        # set new_mock_wait_certificate local_mean and duration
        mock_wait_certificate.local_mean = 0.0
        mock_wait_certificate.duration = 1.0

        # create a new_fork_mock_wait_certificate with a higher duration time
        new_fork_mock_wait_certificate = mock.Mock()
        new_fork_mock_wait_certificate.check_valid.return_value = None
        new_fork_mock_wait_certificate.local_mean = 0.0
        new_fork_mock_wait_certificate.duration = 2.0

        # set mock_utils.deserialize_wait_certificate
        # to return a specific value for each fork_head that is used in
        # poet_fork_resolver.compare()
        # with cur_fork_head being deserialized first
        mock_utils.deserialize_wait_certificate.side_effect = \
            [mock_wait_certificate,
             new_fork_mock_wait_certificate
             ]

        mock_block_cache = mock.MagicMock()
        mock_state_view_factory = mock.Mock()

        # create mock_cur_fork_head
        mock_cur_fork_header = \
            mock.Mock(
                identifier='0123456789abcdefedcba9876543210',
                signer_public_key='90834587139405781349807435098745',
                previous_block_id='2',
                header_signature='00112233445566778899aabbccddeeff')

        # create mock_new_fork_head with same previous block id
        mock_new_fork_header = \
            mock.Mock(
                identifier='0123456789abcdefedcba9876543211',
                signer_public_key='90834587139405781349807435098745',
                previous_block_id='2',
                header_signature='00112233445566778899aabbccddeeff')

        fork_resolver = \
            poet_fork_resolver.PoetForkResolver(
                block_cache=mock_block_cache,
                state_view_factory=mock_state_view_factory,
                data_dir=self._temp_dir,
                config_dir=self._temp_dir,
                validator_id='validator_deadbeef')

        # Subtest 1: when current fork head has the smaller wait duration
        with mock.patch('sawtooth_poet.poet_consensus.poet_fork_resolver.'
                        'LOGGER') as mock_logger:
            self.assertFalse(fork_resolver.compare_forks(
                cur_fork_head=mock_cur_fork_header,
                new_fork_head=mock_new_fork_header))

            # Could be a hack, but verify that the appropriate log message is
            # generated - so we at least have some faith that the failure was
            # because of what we are testing and not something else.  I know
            # that this is fragile if the log message is changed, so would
            # accept any suggestions on a better way to verify that the
            # function fails for the reason we expect.

            (message, *_), _ = mock_logger.info.call_args
            self.assertTrue('Current fork wait duration (%f) '
                            'less than new fork wait duration (%f)' in message)

        # Subtest 2: when new fork head has the smaller wait duration

        # change new_fork_mock_wait_certificate duration to a smaller value
        new_fork_mock_wait_certificate.duration = 0.0

        # set mock_utils.deserialize_wait_certificate
        # to return a specific value for each fork_head
        # with cur_fork_head being deserialized first
        mock_utils.deserialize_wait_certificate.side_effect = \
            [mock_wait_certificate,
             new_fork_mock_wait_certificate]

        # check test
        with mock.patch('sawtooth_poet.poet_consensus.poet_fork_resolver.'
                        'LOGGER') as mock_logger:
            self.assertTrue(fork_resolver.compare_forks(
                cur_fork_head=mock_cur_fork_header,
                new_fork_head=mock_new_fork_header))

            # Could be a hack, but verify that the appropriate log message is
            # generated - so we at least have some faith that the failure was
            # because of what we are testing and not something else.  I know
            # that this is fragile if the log message is changed, so would
            # accept any suggestions on a better way to verify that the
            # function fails for the reason we expect.

            (message, *_), _ = mock_logger.info.call_args
            self.assertTrue('New fork wait duration (%f) '
                            'less than current fork wait duration '
                            in message)

        # Subtest 3: when new & current fork heads have
        # the same wait duration

        # change new_fork_mock_wait_certificate duration to a smaller value
        new_fork_mock_wait_certificate.duration = 1.0

        # set mock_utils.deserialize_wait_certificate
        # to return a specific value for each fork_head
        # with cur_fork_head being deserialized first
        mock_utils.deserialize_wait_certificate.side_effect = \
            [mock_wait_certificate,
             new_fork_mock_wait_certificate]

        # check test
        with mock.patch('sawtooth_poet.poet_consensus.poet_fork_resolver.'
                        'LOGGER') as mock_logger:
            self.assertTrue(fork_resolver.compare_forks(
                cur_fork_head=mock_cur_fork_header,
                new_fork_head=mock_new_fork_header))

            # Could be a hack, but verify that the appropriate log message is
            # generated - so we at least have some faith that the failure was
            # because of what we are testing and not something else.  I know
            # that this is fragile if the log message is changed, so would
            # accept any suggestions on a better way to verify that the
            # function fails for the reason we expect.

            (message, *_), _ = mock_logger.info.call_args
            self.assertTrue('New fork header signature (%s) '
                            'greater than current fork header signature (%s)'
                            in message)

    @mock.patch('sawtooth_poet.poet_consensus.poet_fork_resolver.'
                'ConsensusStateStore')
    @mock.patch('sawtooth_poet.poet_consensus.poet_fork_resolver.factory')
    @mock.patch('sawtooth_poet.poet_consensus.poet_fork_resolver.'
                'ConsensusState')
    @mock.patch('sawtooth_poet.poet_consensus.poet_fork_resolver.'
                'ValidatorRegistryView')
    @mock.patch('sawtooth_poet.poet_consensus.poet_fork_resolver.utils')
    def test_different_previous_block_id(
            self,
            mock_utils,
            mock_validator_registry_view,
            mock_consensus_state,
            mock_poet_enclave_factory,
            mock_consensus_state_store):
        """ When both current and new fork heads are valid
            PoET blocks with different previous block ids,
            the test verifies that the one with
            the higher aggregate local mean wins
        """

        # create a mock_validator_registry_view
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
        # set new_mock_wait_certificate local_mean and duration
        mock_wait_certificate.local_mean = 0.0

        # set mock_utils.deserialize_wait_certificate
        # to return a specific value for each fork_head
        # with cur_fork_head being deserialized first
        mock_utils.deserialize_wait_certificate.side_effect = \
            [mock_wait_certificate,
             mock_wait_certificate,
             mock_wait_certificate,
             mock_wait_certificate,
             mock_wait_certificate,
             mock_wait_certificate,
             mock_wait_certificate,
             mock_wait_certificate,
             mock_wait_certificate,
             mock_wait_certificate
             ]

        mock_block_cache = mock.MagicMock()
        mock_state_view_factory = mock.Mock()

        # create mock_cur_fork_head
        mock_cur_fork_header = \
            mock.Mock(
                identifier='0123456789abcdefedcba9876543210',
                signer_public_key='90834587139405781349807435098745',
                previous_block_id='2',
                header_signature='00112233445566778899aabbccddeeff')

        # create mock_new_fork_head
        mock_new_fork_header = \
            mock.Mock(
                identifier='0123456789abcdefedcba9876543211',
                signer_public_key='90834587139405781349807435098745',
                previous_block_id='3',
                header_signature='00112233445566778899aabbccddeeff')

        fork_resolver = \
            poet_fork_resolver.PoetForkResolver(
                block_cache=mock_block_cache,
                state_view_factory=mock_state_view_factory,
                data_dir=self._temp_dir,
                config_dir=self._temp_dir,
                validator_id='validator_deadbeef')

        # Subtest 1: when the current fork head has
        # the higher aggregate local mean
        # create a mock_cur_fork_consensus_state
        mock_cur_fork_consensus_state = mock.Mock()
        mock_cur_fork_consensus_state.aggregate_local_mean = 1.0

        # create a mock_new_fork_consensus_state
        mock_new_fork_consensus_state = mock.Mock()
        mock_new_fork_consensus_state.aggregate_local_mean = 0.0

        # set mock_consensus_state.consensus_state_for_block_id return
        # the current & new fork consensus states
        mock_consensus_state.consensus_state_for_block_id.side_effect = \
            [mock_cur_fork_consensus_state,
             mock_new_fork_consensus_state]

        # check test
        self.assertFalse(fork_resolver.compare_forks(
            cur_fork_head=mock_cur_fork_header,
            new_fork_head=mock_new_fork_header))

        # Subtest 2: when the new fork head has
        # the higher aggregate local mean

        # set mock_consensus_state.consensus_state_for_block_id return
        # the current & new fork consensus states
        mock_consensus_state.consensus_state_for_block_id.side_effect = \
            [mock_cur_fork_consensus_state,
             mock_new_fork_consensus_state,
             mock_new_fork_consensus_state]

        # change the aggregate_local_mean values
        mock_cur_fork_consensus_state.aggregate_local_mean = 0.0
        mock_new_fork_consensus_state.aggregate_local_mean = 1.0

        # check test
        self.assertTrue(fork_resolver.compare_forks(
            cur_fork_head=mock_cur_fork_header,
            new_fork_head=mock_new_fork_header))

        # Subtest 3: when both the new & current fork heads have
        # the same aggregate local mean

        # set mock_consensus_state.consensus_state_for_block_id return
        # the current & new fork consensus states
        mock_consensus_state.consensus_state_for_block_id.side_effect = \
            [mock_cur_fork_consensus_state,
             mock_new_fork_consensus_state,
             mock_new_fork_consensus_state]

        # set the aggregate_local_mean values equal
        mock_cur_fork_consensus_state.aggregate_local_mean = 1.0
        mock_new_fork_consensus_state.aggregate_local_mean = 1.0

        # check test
        self.assertTrue(fork_resolver.compare_forks(
            cur_fork_head=mock_cur_fork_header,
            new_fork_head=mock_new_fork_header))

        # Subset 4: If we have gotten to this point and we have not chosen
        # a fork head yet, we are going to fall back
        # on using the block identifiers (header signatures).
        # The lexicographically larger one will be the chosen one.

        # create mock_new_fork_head with a smaller header_signature
        mock_smaller_header_signature = \
            mock.Mock(
                identifier='0123456789abcdefedcba9876543211',
                signer_public_key='90834587139405781349807435098745',
                previous_block_id='4',
                header_signature='00112233445566778899aabbccddee')

        # create a mock_smaller_header_signature_consensus_state
        mock_smaller_header_signature_consensus_state = mock.Mock()
        mock_smaller_header_signature_consensus_state.\
            aggregate_local_mean = 0.0

        mock_cur_fork_consensus_state.aggregate_local_mean = 0.0

        mock_consensus_state.consensus_state_for_block_id.side_effect = \
            [mock_cur_fork_consensus_state,
             mock_smaller_header_signature_consensus_state]

        # check test when Current fork header signature is greater than
        # the new fork header signature
        self.assertFalse(fork_resolver.compare_forks(
            cur_fork_head=mock_cur_fork_header,
            new_fork_head=mock_smaller_header_signature))

        # Subtest 5: Check when new header signature is greater than
        # the current fork header signature

        mock_consensus_state.consensus_state_for_block_id.side_effect = \
            [mock_smaller_header_signature_consensus_state,
             mock_new_fork_consensus_state,
             mock_new_fork_consensus_state]

        mock_smaller_header_signature_consensus_state.\
            aggregate_local_mean = 0.0
        mock_new_fork_consensus_state.aggregate_local_mean = 0.0

        # check test
        self.assertTrue(fork_resolver.compare_forks(
            cur_fork_head=mock_smaller_header_signature,
            new_fork_head=mock_new_fork_header))

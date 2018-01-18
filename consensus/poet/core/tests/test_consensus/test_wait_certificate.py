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

from importlib import reload
import time
import tempfile
import shutil
from unittest import TestCase
from unittest import mock
from unittest import skip

import sawtooth_poet_simulator.poet_enclave_simulator.poet_enclave_simulator \
    as poet_enclave

from sawtooth_poet.poet_consensus.signup_info import SignupInfo
from sawtooth_poet.poet_consensus.wait_timer import WaitTimer
from sawtooth_poet.poet_consensus.wait_certificate import WaitCertificate

from sawtooth_poet_common.protobuf.validator_registry_pb2 \
    import ValidatorInfo
from sawtooth_poet_common.protobuf.validator_registry_pb2 \
    import SignUpInfo

from sawtooth_validator.journal.block_wrapper import NULL_BLOCK_IDENTIFIER

from test_consensus.utils import create_random_public_key_hash


class TestWaitCertificate(TestCase):
    @classmethod
    def setUpClass(cls):
        cls._originator_public_key_hash = create_random_public_key_hash()
        cls._temp_dir = tempfile.mkdtemp()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls._temp_dir)

    def setUp(self):
        # This is a little ham-handed, but we need to ensure that the
        # PoET enclave is set back to initial state at the start of every
        # test.
        self.poet_enclave_module = reload(poet_enclave)
        self.poet_enclave_module.initialize(self._temp_dir, self._temp_dir)

        self.mock_poet_settings_view = mock.Mock()
        self.mock_poet_settings_view.target_wait_time = 5.0
        self.mock_poet_settings_view.initial_wait_time = 0.0
        self.mock_poet_settings_view.population_estimate_sample_size = 50

        self.mock_consensus_state = mock.Mock()
        self.mock_consensus_state.compute_local_mean.return_value = 5.0

        self.mock_prev_certificate_id = NULL_BLOCK_IDENTIFIER

    def test_create_before_create_signup_info(self):
        # Make sure that trying to create a wait certificate before signup
        # information is provided causes an error
        with self.assertRaises(ValueError):
            WaitCertificate.create_wait_certificate(
                poet_enclave_module=self.poet_enclave_module,
                sealed_signup_data='',
                wait_timer=None,
                block_hash="Reader's Digest")

    def test_create_before_create_wait_timer(self):
        # Need to create signup information
        signup_info = SignupInfo.create_signup_info(
            poet_enclave_module=self.poet_enclave_module,
            originator_public_key_hash=self._originator_public_key_hash,
            nonce=NULL_BLOCK_IDENTIFIER)

        # Make sure that trying to create a wait certificate before creating
        # a wait timer causes an error
        with self.assertRaises(ValueError):
            WaitCertificate.create_wait_certificate(
                poet_enclave_module=self.poet_enclave_module,
                sealed_signup_data=signup_info.sealed_signup_data,
                wait_timer=None,
                block_hash="Reader's Digest")

    def test_create_before_wait_timer_expires(self):
        # Need to create signup information
        signup_info = SignupInfo.create_signup_info(
            poet_enclave_module=self.poet_enclave_module,
            originator_public_key_hash=self._originator_public_key_hash,
            nonce=NULL_BLOCK_IDENTIFIER)

        # Create a wait certificate for the genesis block so that we can
        # create another wait certificate that has to play by the rules.
        wt = \
            WaitTimer.create_wait_timer(
                poet_enclave_module=self.poet_enclave_module,
                sealed_signup_data=signup_info.sealed_signup_data,
                validator_address='1660 Pennsylvania Avenue NW',
                previous_certificate_id=NULL_BLOCK_IDENTIFIER,
                consensus_state=self.mock_consensus_state,
                poet_settings_view=self.mock_poet_settings_view)
        wc = \
            WaitCertificate.create_wait_certificate(
                poet_enclave_module=self.poet_enclave_module,
                sealed_signup_data=signup_info.sealed_signup_data,
                wait_timer=wt,
                block_hash="Reader's Digest")

        wt = \
            WaitTimer.create_wait_timer(
                poet_enclave_module=self.poet_enclave_module,
                sealed_signup_data=signup_info.sealed_signup_data,
                validator_address='1660 Pennsylvania Avenue NW',
                previous_certificate_id=wc.identifier,
                consensus_state=self.mock_consensus_state,
                poet_settings_view=self.mock_poet_settings_view)

        with self.assertRaises(ValueError):
            WaitCertificate.create_wait_certificate(
                poet_enclave_module=self.poet_enclave_module,
                sealed_signup_data=signup_info.sealed_signup_data,
                wait_timer=wt,
                block_hash="Reader's Digest")

    @skip("Disabled until poet integration -- too slow!!!!!")
    def test_create_after_wait_timer_timed_out(self):
        # Need to create signup information
        signup_info = SignupInfo.create_signup_info(
            poet_enclave_module=self.poet_enclave_module,
            originator_public_key_hash=self._originator_public_key_hash,
            nonce=NULL_BLOCK_IDENTIFIER)

        # Create a wait certificate for the genesis block so that we can
        # create another wait certificate that has to play by the rules.
        wt = \
            WaitTimer.create_wait_timer(
                poet_enclave_module=self.poet_enclave_module,
                sealed_signup_data=signup_info.sealed_signup_data,
                validator_address='1660 Pennsylvania Avenue NW',
                previous_certificate_id=NULL_BLOCK_IDENTIFIER,
                consensus_state=self.mock_consensus_state,
                poet_settings_view=self.mock_poet_settings_view)
        wc = \
            WaitCertificate.create_wait_certificate(
                poet_enclave_module=self.poet_enclave_module,
                sealed_signup_data=signup_info.sealed_signup_data,
                wait_timer=wt,
                block_hash="Reader's Digest")

        wt = \
            WaitTimer.create_wait_timer(
                poet_enclave_module=self.poet_enclave_module,
                sealed_signup_data=signup_info.sealed_signup_data,
                validator_address='1660 Pennsylvania Avenue NW',
                previous_certificate_id=wc.identifier,
                consensus_state=self.mock_consensus_state,
                poet_settings_view=self.mock_poet_settings_view)

        while not wt.has_expired(time.time()):
            time.sleep(1)
        time.sleep(self.poet_enclave_module.TIMER_TIMEOUT_PERIOD + 1)

        with self.assertRaises(ValueError):
            WaitCertificate.create_wait_certificate(
                poet_enclave_module=self.poet_enclave_module,
                sealed_signup_data=signup_info.sealed_signup_data,
                wait_timer=wt,
                block_hash="Reader's Digest")

    def test_create_with_wrong_signup_data(self):
        # Need to create signup information
        signup_info = SignupInfo.create_signup_info(
            poet_enclave_module=self.poet_enclave_module,
            originator_public_key_hash=self._originator_public_key_hash,
            nonce=NULL_BLOCK_IDENTIFIER)

        signup_info2 = SignupInfo.create_signup_info(
            poet_enclave_module=self.poet_enclave_module,
            originator_public_key_hash=self._originator_public_key_hash,
            nonce=NULL_BLOCK_IDENTIFIER)

        # Create two timers and try to create the wait certificate with the
        # first one, which should fail as it is not the current wait timer
        wt1 = \
            WaitTimer.create_wait_timer(
                poet_enclave_module=self.poet_enclave_module,
                sealed_signup_data=signup_info.sealed_signup_data,
                validator_address='1660 Pennsylvania Avenue NW',
                previous_certificate_id=NULL_BLOCK_IDENTIFIER,
                consensus_state=self.mock_consensus_state,
                poet_settings_view=self.mock_poet_settings_view)
        wt2 = \
            WaitTimer.create_wait_timer(
                poet_enclave_module=self.poet_enclave_module,
                sealed_signup_data=signup_info2.sealed_signup_data,
                validator_address='1660 Pennsylvania Avenue NW',
                previous_certificate_id=NULL_BLOCK_IDENTIFIER,
                consensus_state=self.mock_consensus_state,
                poet_settings_view=self.mock_poet_settings_view)

        # Verify that we cannot create a wait certificate using the first
        # wait timer with the second signup data
        with self.assertRaises(ValueError):
            WaitCertificate.create_wait_certificate(
                poet_enclave_module=self.poet_enclave_module,
                sealed_signup_data=signup_info2.sealed_signup_data,
                wait_timer=wt1,
                block_hash="Reader's Digest")

        WaitCertificate.create_wait_certificate(
            poet_enclave_module=self.poet_enclave_module,
            sealed_signup_data=signup_info2.sealed_signup_data,
            wait_timer=wt2,
            block_hash="Reader's Digest")

    @skip("Simulator doesn't provide replay protection")
    def test_create_with_reused_wait_timer(self):
        # Need to create signup information
        signup_info = SignupInfo.create_signup_info(
            poet_enclave_module=self.poet_enclave_module,
            originator_public_key_hash=self._originator_public_key_hash,
            nonce=NULL_BLOCK_IDENTIFIER)

        # Create a wait certificate for the genesis block so that we can
        # create another wait certificate that has to play by the rules.
        wt = \
            WaitTimer.create_wait_timer(
                poet_enclave_module=self.poet_enclave_module,
                sealed_signup_data=signup_info.sealed_signup_data,
                validator_address='1660 Pennsylvania Avenue NW',
                previous_certificate_id=NULL_BLOCK_IDENTIFIER,
                consensus_state=self.mock_consensus_state,
                poet_settings_view=self.mock_poet_settings_view)
        wc = \
            WaitCertificate.create_wait_certificate(
                poet_enclave_module=self.poet_enclave_module,
                sealed_signup_data=signup_info.sealed_signup_data,
                wait_timer=wt,
                block_hash="Reader's Digest")

        consumed_wt = wt

        # Verify that we cannot use the consumed wait timer to create a wait
        # certificate either before or after creating a new wait timer
        with self.assertRaises(ValueError):
            WaitCertificate.create_wait_certificate(
                poet_enclave_module=self.poet_enclave_module,
                sealed_signup_data=signup_info.sealed_signup_data,
                wait_timer=consumed_wt,
                block_hash="Reader's Digest")
        wt = \
            WaitTimer.create_wait_timer(
                poet_enclave_module=self.poet_enclave_module,
                sealed_signup_data=signup_info.sealed_signup_data,
                validator_address='1660 Pennsylvania Avenue NW',
                previous_certificate_id=wc.identifier,
                consensus_state=self.mock_consensus_state,
                poet_settings_view=self.mock_poet_settings_view)
        with self.assertRaises(ValueError):
            WaitCertificate.create_wait_certificate(
                poet_enclave_module=self.poet_enclave_module,
                sealed_signup_data=signup_info.sealed_signup_data,
                wait_timer=consumed_wt,
                block_hash="Reader's Digest")

        # Verify that once the new timer expires, we can create a wait
        # certificate with it
        while not wt.has_expired(time.time()):
            time.sleep(1)

        WaitCertificate.create_wait_certificate(
            poet_enclave_module=self.poet_enclave_module,
            sealed_signup_data=signup_info.sealed_signup_data,
            wait_timer=wt,
            block_hash="Reader's Digest")

    def test_create(self):
        # Need to create signup information and wait timer first
        signup_info = \
            SignupInfo.create_signup_info(
                poet_enclave_module=self.poet_enclave_module,
                originator_public_key_hash=self._originator_public_key_hash,
                nonce=NULL_BLOCK_IDENTIFIER)

        # create mock_poet_enclave_wait_timer
        mock_poet_enclave_wait_timer = \
            mock.Mock(sealed_signup_data=signup_info.sealed_signup_data,
                      validator_address='1060 W Addison Street',
                      duration=1.0,
                      previous_certificate_id=NULL_BLOCK_IDENTIFIER,
                      local_mean=5.0,
                      signature='00112233445566778899aabbccddeeff',
                      serialized_timer=None,
                      request_time=time.time())

        # create mock_poet_enclave_wait_certificate
        mock_poet_enclave_wait_certificate = \
            mock.Mock(sealed_signup_data=signup_info.sealed_signup_data,
                      duration=1.0,
                      previous_certificate_id=NULL_BLOCK_IDENTIFIER,
                      local_mean=5.0,
                      request_time=time.time(),
                      validator_address='1060 W Addison Street',
                      nonce=NULL_BLOCK_IDENTIFIER,
                      block_hash="Reader's Digest",
                      signature='00112233445566778899aabbccddeeff',
                      serialized_certificate='001122334455667'
                                             '78899aabbccddeeff')

        # create mock_poet_enclave_module
        mock_poet_enclave_module = mock.Mock()
        mock_poet_enclave_module.create_wait_timer.return_value = \
            mock_poet_enclave_wait_timer

        # set the mock enclave wait certificate and wait timer to
        # have the same request_time
        mock_poet_enclave_wait_certificate.request_time = \
            mock_poet_enclave_wait_timer.request_time

        # set the mock enclave wait certificate and wait timer to
        # have the same previous_certificate_id
        mock_poet_enclave_wait_certificate.previous_certificate_id = \
            mock_poet_enclave_wait_timer.previous_certificate_id

        # set the identifier for mock_poet_enclave_wait_certificate
        mock_poet_enclave_wait_certificate.identifier.return_value = \
            mock_poet_enclave_wait_certificate.previous_certificate_id[:16]

        mock_poet_enclave_module.create_wait_certificate.return_value = \
            mock_poet_enclave_wait_certificate

        mock_poet_enclave_module.deserialize_wait_certificate.return_value = \
            mock_poet_enclave_wait_certificate

        # create wait timer
        wt = \
            WaitTimer.create_wait_timer(
                poet_enclave_module=mock_poet_enclave_module,
                sealed_signup_data=signup_info.sealed_signup_data,
                validator_address='1660 Pennsylvania Avenue NW',
                previous_certificate_id=NULL_BLOCK_IDENTIFIER,
                consensus_state=self.mock_consensus_state,
                poet_settings_view=self.mock_poet_settings_view)

        # Now we can create a wait certificate and verify that it correlates
        # to the wait timer we just created
        wc = \
            WaitCertificate.create_wait_certificate(
                poet_enclave_module=mock_poet_enclave_module,
                sealed_signup_data=signup_info.sealed_signup_data,
                wait_timer=wt,
                block_hash="Reader's Digest")

        self.assertIsNotNone(wc)
        self.assertEqual(
            wc.previous_certificate_id,
            wt.previous_certificate_id)
        self.assertAlmostEqual(wc.local_mean, wt.local_mean)
        self.assertAlmostEqual(wc.request_time, wt.request_time)
        self.assertAlmostEqual(wc.duration, wt.duration)
        self.assertEqual(wc.validator_address, wt.validator_address)
        self.assertEqual(wc.block_hash, "Reader's Digest")
        self.assertIsNotNone(wc.signature)
        self.assertIsNotNone(wc.identifier)

        # A newly-created wait certificate should be valid
        wc.check_valid(
            poet_enclave_module=mock_poet_enclave_module,
            previous_certificate_id=NULL_BLOCK_IDENTIFIER,
            poet_public_key=signup_info.poet_public_key,
            consensus_state=self.mock_consensus_state,
            poet_settings_view=self.mock_poet_settings_view)

        validator_info = \
            ValidatorInfo(
                id='validator_001',
                signup_info=SignUpInfo(
                    poet_public_key='key_001'))
        self.mock_consensus_state.validator_did_claim_block(
            validator_info=validator_info,
            wait_certificate=wc,
            poet_settings_view=self.mock_poet_settings_view)

        # Create another wait certificate and verify it is valid also
        wt = \
            WaitTimer.create_wait_timer(
                poet_enclave_module=mock_poet_enclave_module,
                sealed_signup_data=signup_info.sealed_signup_data,
                validator_address='1660 Pennsylvania Avenue NW',
                previous_certificate_id=wc.identifier,
                consensus_state=self.mock_consensus_state,
                poet_settings_view=self.mock_poet_settings_view)

        # Now we can create a wait certificate and verify that it correlates
        # to the wait timer we just created
        another_wc = \
            WaitCertificate.create_wait_certificate(
                poet_enclave_module=mock_poet_enclave_module,
                sealed_signup_data=signup_info.sealed_signup_data,
                wait_timer=wt,
                block_hash="Pepto Bismol")

        another_wc.check_valid(
            poet_enclave_module=mock_poet_enclave_module,
            previous_certificate_id=wc.identifier,
            poet_public_key=signup_info.poet_public_key,
            consensus_state=self.mock_consensus_state,
            poet_settings_view=self.mock_poet_settings_view)

    def test_serialization(self):
        # Need to create signup information and wait timer first
        signup_info = \
            SignupInfo.create_signup_info(
                poet_enclave_module=self.poet_enclave_module,
                originator_public_key_hash=self._originator_public_key_hash,
                nonce=NULL_BLOCK_IDENTIFIER)

        # create mock_poet_enclave_wait_timer
        mock_poet_enclave_wait_timer = \
            mock.Mock(validator_address='1060 W Addison Street',
                      duration=1.0,
                      previous_certificate_id=NULL_BLOCK_IDENTIFIER,
                      local_mean=5.0,
                      signature='00112233445566778899aabbccddeeff',
                      serialized_timer=None,
                      request_time=time.time())

        # create mock_poet_enclave_wait_certificate
        mock_poet_enclave_wait_certificate = \
            mock.Mock(duration=1.0,
                      previous_certificate_id=NULL_BLOCK_IDENTIFIER,
                      local_mean=5.0,
                      request_time=time.time(),
                      validator_address='1060 W Addison Street',
                      nonce=NULL_BLOCK_IDENTIFIER,
                      block_hash="Reader's Digest",
                      signature='00112233445566778899aabbccddeeff',
                      serialized_certificate=None)

        # create mock_poet_enclave_module
        mock_poet_enclave_module = mock.Mock()
        mock_poet_enclave_module.create_wait_timer.return_value = \
            mock_poet_enclave_wait_timer

        # set the mock enclave wait certificate and wait timer to
        # have the same previous_certificate_id
        mock_poet_enclave_wait_certificate.previous_certificate_id = \
            mock_poet_enclave_wait_timer.previous_certificate_id

        mock_poet_enclave_module.create_wait_certificate.return_value = \
            mock_poet_enclave_wait_certificate

        mock_poet_enclave_module.deserialize_wait_certificate.return_value = \
            mock_poet_enclave_wait_certificate

        wt = \
            WaitTimer.create_wait_timer(
                poet_enclave_module=mock_poet_enclave_module,
                sealed_signup_data=signup_info.sealed_signup_data,
                validator_address='1660 Pennsylvania Avenue NW',
                previous_certificate_id=NULL_BLOCK_IDENTIFIER,
                consensus_state=self.mock_consensus_state,
                poet_settings_view=self.mock_poet_settings_view)

        # Now we can create a wait certificate and serialize
        wc = \
            WaitCertificate.create_wait_certificate(
                poet_enclave_module=mock_poet_enclave_module,
                sealed_signup_data=signup_info.sealed_signup_data,
                wait_timer=wt,
                block_hash="Reader's Digest")

        dumped = wc.dump()

        self.assertIsNotNone(dumped.get('SerializedCertificate'))
        self.assertIsNotNone(dumped.get('Signature'))

        # Deserialize and verify that wait certificates are the same
        # and that deserialized one is valid
        wc_copy = \
            WaitCertificate.wait_certificate_from_serialized(
                poet_enclave_module=mock_poet_enclave_module,
                serialized=dumped.get('SerializedCertificate'),
                signature=dumped.get('Signature'))

        self.assertEqual(
            wc.previous_certificate_id,
            wc_copy.previous_certificate_id)
        self.assertEqual(wc.local_mean, wc_copy.local_mean)
        self.assertAlmostEqual(wc.request_time, wc_copy.request_time)
        self.assertAlmostEqual(wc.duration, wc_copy.duration)
        self.assertEqual(wc.validator_address, wc_copy.validator_address)
        self.assertEqual(wc.block_hash, wc_copy.block_hash)
        self.assertEqual(wc.signature, wc_copy.signature)
        self.assertEqual(wc.identifier, wc_copy.identifier)

        # Serialize the copy and verify that its serialization and
        # signature are the same
        dumped_copy = wc_copy.dump()

        self.assertTrue(
            dumped.get('SerializedCertificate'),
            dumped_copy.get('SerializedCertificate'))
        self.assertTrue(
            dumped.get('Signature'),
            dumped_copy.get('Signature'))

        wc_copy.check_valid(
            poet_enclave_module=mock_poet_enclave_module,
            previous_certificate_id=NULL_BLOCK_IDENTIFIER,
            poet_public_key=signup_info.poet_public_key,
            consensus_state=self.mock_consensus_state,
            poet_settings_view=self.mock_poet_settings_view)

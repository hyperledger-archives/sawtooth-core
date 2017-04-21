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
from unittest import TestCase
from unittest import mock
from unittest import skip

import sawtooth_poet_simulator.poet_enclave_simulator.poet_enclave_simulator \
    as poet_enclave

from sawtooth_poet.poet_consensus.consensus_state import ConsensusState
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

    def setUp(self):
        # This is a little ham-handed, but we need to ensure that the
        # PoET enclave is set back to initial state at the start of every
        # test.
        self.poet_enclave_module = reload(poet_enclave)

        args = {"NodeName": "DasValidator"}
        self.poet_enclave_module.initialize(**args)

        self.mock_poet_config_view = mock.Mock()
        self.mock_poet_config_view.target_wait_time = 5.0
        self.mock_poet_config_view.initial_wait_time = 0.0
        self.mock_poet_config_view.minimum_wait_time = 1.0
        self.mock_poet_config_view.population_estimate_sample_size = 50

        self.consensus_state = ConsensusState()

    def test_create_before_create_signup_info(self):
        # Make sure that trying to create a wait certificate before signup
        # information is provided causes an error
        with self.assertRaises(ValueError):
            WaitCertificate.create_wait_certificate(
                poet_enclave_module=self.poet_enclave_module,
                wait_timer=None,
                block_hash="Reader's Digest")

    def test_create_before_create_wait_timer(self):
        # Need to create signup information
        SignupInfo.create_signup_info(
            poet_enclave_module=self.poet_enclave_module,
            validator_address='1660 Pennsylvania Avenue NW',
            originator_public_key_hash=self._originator_public_key_hash,
            most_recent_wait_certificate_id=NULL_BLOCK_IDENTIFIER)

        # Make sure that trying to create a wait certificate before creating
        # a wait timer causes an error
        with self.assertRaises(ValueError):
            WaitCertificate.create_wait_certificate(
                poet_enclave_module=self.poet_enclave_module,
                wait_timer=None,
                block_hash="Reader's Digest")

    def test_create_before_wait_timer_expires(self):
        # Need to create signup information
        SignupInfo.create_signup_info(
            poet_enclave_module=self.poet_enclave_module,
            validator_address='1660 Pennsylvania Avenue NW',
            originator_public_key_hash=self._originator_public_key_hash,
            most_recent_wait_certificate_id=NULL_BLOCK_IDENTIFIER)

        # Create a wait certificate for the genesis block so that we can
        # create another wait certificate that has to play by the rules.
        wt = \
            WaitTimer.create_wait_timer(
                poet_enclave_module=self.poet_enclave_module,
                validator_address='1660 Pennsylvania Avenue NW',
                previous_certificate_id=NULL_BLOCK_IDENTIFIER,
                consensus_state=self.consensus_state,
                poet_config_view=self.mock_poet_config_view)
        wc = \
            WaitCertificate.create_wait_certificate(
                poet_enclave_module=self.poet_enclave_module,
                wait_timer=wt,
                block_hash="Reader's Digest")

        wt = \
            WaitTimer.create_wait_timer(
                poet_enclave_module=self.poet_enclave_module,
                validator_address='1660 Pennsylvania Avenue NW',
                previous_certificate_id=wc.identifier,
                consensus_state=self.consensus_state,
                poet_config_view=self.mock_poet_config_view)

        with self.assertRaises(ValueError):
            WaitCertificate.create_wait_certificate(
                poet_enclave_module=self.poet_enclave_module,
                wait_timer=wt,
                block_hash="Reader's Digest")

    @skip("Disabled until poet integration -- too slow!!!!!")
    def test_create_after_wait_timer_timed_out(self):
        # Need to create signup information
        SignupInfo.create_signup_info(
            poet_enclave_module=self.poet_enclave_module,
            validator_address='1660 Pennsylvania Avenue NW',
            originator_public_key_hash=self._originator_public_key_hash,
            most_recent_wait_certificate_id=NULL_BLOCK_IDENTIFIER)

        # Create a wait certificate for the genesis block so that we can
        # create another wait certificate that has to play by the rules.
        wt = \
            WaitTimer.create_wait_timer(
                poet_enclave_module=self.poet_enclave_module,
                validator_address='1660 Pennsylvania Avenue NW',
                previous_certificate_id=NULL_BLOCK_IDENTIFIER,
                consensus_state=self.consensus_state,
                poet_config_view=self.mock_poet_config_view)
        wc = \
            WaitCertificate.create_wait_certificate(
                poet_enclave_module=self.poet_enclave_module,
                wait_timer=wt,
                block_hash="Reader's Digest")

        wt = \
            WaitTimer.create_wait_timer(
                poet_enclave_module=self.poet_enclave_module,
                validator_address='1660 Pennsylvania Avenue NW',
                previous_certificate_id=wc.identifier,
                consensus_state=self.consensus_state,
                poet_config_view=self.mock_poet_config_view)
        while not wt.has_expired(time.time()):
            time.sleep(1)
        time.sleep(self.poet_enclave_module.TIMER_TIMEOUT_PERIOD + 1)

        with self.assertRaises(ValueError):
            WaitCertificate.create_wait_certificate(
                poet_enclave_module=self.poet_enclave_module,
                wait_timer=wt,
                block_hash="Reader's Digest")

    def test_create_with_wrong_wait_timer(self):
        # Need to create signup information
        SignupInfo.create_signup_info(
            poet_enclave_module=self.poet_enclave_module,
            validator_address='1660 Pennsylvania Avenue NW',
            originator_public_key_hash=self._originator_public_key_hash,
            most_recent_wait_certificate_id=NULL_BLOCK_IDENTIFIER)

        # Create two timers and try to create the wait certificate with the
        # first one, which should fail as it is not the current wait timer
        invalid_wt = \
            WaitTimer.create_wait_timer(
                poet_enclave_module=self.poet_enclave_module,
                validator_address='1660 Pennsylvania Avenue NW',
                previous_certificate_id=NULL_BLOCK_IDENTIFIER,
                consensus_state=self.consensus_state,
                poet_config_view=self.mock_poet_config_view)
        valid_wt = \
            WaitTimer.create_wait_timer(
                poet_enclave_module=self.poet_enclave_module,
                validator_address='1660 Pennsylvania Avenue NW',
                previous_certificate_id=NULL_BLOCK_IDENTIFIER,
                consensus_state=self.consensus_state,
                poet_config_view=self.mock_poet_config_view)

        # Verify that we cannot create a wait certificate with the old wait
        # timer, but we can with the new one
        with self.assertRaises(ValueError):
            WaitCertificate.create_wait_certificate(
                poet_enclave_module=self.poet_enclave_module,
                wait_timer=invalid_wt,
                block_hash="Reader's Digest")

        WaitCertificate.create_wait_certificate(
            poet_enclave_module=self.poet_enclave_module,
            wait_timer=valid_wt,
            block_hash="Reader's Digest")

    def test_create_with_reused_wait_timer(self):
        # Need to create signup information
        SignupInfo.create_signup_info(
            poet_enclave_module=self.poet_enclave_module,
            validator_address='1660 Pennsylvania Avenue NW',
            originator_public_key_hash=self._originator_public_key_hash,
            most_recent_wait_certificate_id=NULL_BLOCK_IDENTIFIER)

        # Create a wait certificate for the genesis block so that we can
        # create another wait certificate that has to play by the rules.
        wt = \
            WaitTimer.create_wait_timer(
                poet_enclave_module=self.poet_enclave_module,
                validator_address='1660 Pennsylvania Avenue NW',
                previous_certificate_id=NULL_BLOCK_IDENTIFIER,
                consensus_state=self.consensus_state,
                poet_config_view=self.mock_poet_config_view)
        wc = \
            WaitCertificate.create_wait_certificate(
                poet_enclave_module=self.poet_enclave_module,
                wait_timer=wt,
                block_hash="Reader's Digest")

        consumed_wt = wt

        # Verify that we cannot use the consumed wait timer to create a wait
        # certificate either before or after creating a new wait timer
        with self.assertRaises(ValueError):
            WaitCertificate.create_wait_certificate(
                poet_enclave_module=self.poet_enclave_module,
                wait_timer=consumed_wt,
                block_hash="Reader's Digest")
        wt = \
            WaitTimer.create_wait_timer(
                poet_enclave_module=self.poet_enclave_module,
                validator_address='1660 Pennsylvania Avenue NW',
                previous_certificate_id=wc.identifier,
                consensus_state=self.consensus_state,
                poet_config_view=self.mock_poet_config_view)
        with self.assertRaises(ValueError):
            WaitCertificate.create_wait_certificate(
                poet_enclave_module=self.poet_enclave_module,
                wait_timer=consumed_wt,
                block_hash="Reader's Digest")

        # Verify that once the new timer expires, we can create a wait
        # certificate with it
        while not wt.has_expired(time.time()):
            time.sleep(1)

        WaitCertificate.create_wait_certificate(
            poet_enclave_module=self.poet_enclave_module,
            wait_timer=wt,
            block_hash="Reader's Digest")

    @skip("Disabled until poet integration -- too slow!!!!!")
    def test_create(self):
        # Need to create signup information and wait timer first
        signup_info = \
            SignupInfo.create_signup_info(
                poet_enclave_module=self.poet_enclave_module,
                validator_address='1660 Pennsylvania Avenue NW',
                originator_public_key_hash=self._originator_public_key_hash,
                most_recent_wait_certificate_id=NULL_BLOCK_IDENTIFIER)

        wt = \
            WaitTimer.create_wait_timer(
                poet_enclave_module=self.poet_enclave_module,
                validator_address='1660 Pennsylvania Avenue NW',
                previous_certificate_id=NULL_BLOCK_IDENTIFIER,
                consensus_state=self.consensus_state,
                poet_config_view=self.mock_poet_config_view)
        while not wt.has_expired(time.time()):
            time.sleep(1)

        # Now we can create a wait certificate and verify that it correlates
        # to the wait timer we just created
        wc = \
            WaitCertificate.create_wait_certificate(
                poet_enclave_module=self.poet_enclave_module,
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
            poet_enclave_module=self.poet_enclave_module,
            previous_certificate_id=NULL_BLOCK_IDENTIFIER,
            poet_public_key=signup_info.poet_public_key,
            consensus_state=self.consensus_state,
            poet_config_view=self.mock_poet_config_view)

        validator_info = \
            ValidatorInfo(
                id='validator_001',
                signup_info=SignUpInfo(
                    poet_public_key='key_001'))
        self.consensus_state.validator_did_claim_block(
            validator_info=validator_info,
            wait_certificate=wc,
            poet_config_view=self.mock_poet_config_view)

        # Create another wait certificate and verify it is valid also
        wt = \
            WaitTimer.create_wait_timer(
                poet_enclave_module=self.poet_enclave_module,
                validator_address='1660 Pennsylvania Avenue NW',
                previous_certificate_id=wc.identifier,
                consensus_state=self.consensus_state,
                poet_config_view=self.mock_poet_config_view)
        while not wt.has_expired(time.time()):
            time.sleep(1)

        # Now we can create a wait certificate and verify that it correlates
        # to the wait timer we just created
        another_wc = \
            WaitCertificate.create_wait_certificate(
                poet_enclave_module=self.poet_enclave_module,
                wait_timer=wt,
                block_hash="Pepto Bismol")

        another_wc.check_valid(
            poet_enclave_module=self.poet_enclave_module,
            previous_certificate_id=wc.identifier,
            poet_public_key=signup_info.poet_public_key,
            consensus_state=self.consensus_state,
            poet_config_view=self.mock_poet_config_view)

    @skip("Disabled until poet integration -- too slow!!!!!")
    def test_serialization(self):
        # Need to create signup information and wait timer first
        signup_info = \
            SignupInfo.create_signup_info(
                poet_enclave_module=self.poet_enclave_module,
                validator_address='1660 Pennsylvania Avenue NW',
                originator_public_key_hash=self._originator_public_key_hash,
                most_recent_wait_certificate_id=NULL_BLOCK_IDENTIFIER)

        wt = \
            WaitTimer.create_wait_timer(
                poet_enclave_module=self.poet_enclave_module,
                validator_address='1660 Pennsylvania Avenue NW',
                previous_certificate_id=NULL_BLOCK_IDENTIFIER,
                consensus_state=self.consensus_state,
                poet_config_view=self.mock_poet_config_view)
        while not wt.has_expired(time.time()):
            time.sleep(1)

        # Now we can create a wait certificate and serialize
        wc = \
            WaitCertificate.create_wait_certificate(
                poet_enclave_module=self.poet_enclave_module,
                wait_timer=wt,
                block_hash="Reader's Digest")

        dumped = wc.dump()

        self.assertIsNotNone(dumped.get('SerializedCertificate'))
        self.assertIsNotNone(dumped.get('Signature'))

        # Deserialize and verify that wait certificates are the same
        # and that deserialized one is valid
        wc_copy = \
            WaitCertificate.wait_certificate_from_serialized(
                poet_enclave_module=self.poet_enclave_module,
                serialized=dumped.get('SerializedCertificate'),
                signature=dumped.get('Signature'))

        self.assertEqual(
            wc.previous_certificate_id,
            wc_copy.previous_certificate_id)
        self.assertAlmostEqual(wc.local_mean, wc_copy.local_mean)
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
            poet_enclave_module=self.poet_enclave_module,
            previous_certificate_id=NULL_BLOCK_IDENTIFIER,
            poet_public_key=signup_info.poet_public_key,
            consensus_state=self.consensus_state,
            poet_config_view=self.mock_poet_config_view)

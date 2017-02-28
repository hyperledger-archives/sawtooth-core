# Copyright 2016 Intel Corporation
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
import time

import sawtooth_validator.consensus.poet1.poet_enclave_simulator.\
    poet_enclave_simulator as poet_enclave

from sawtooth_validator.consensus.poet1.signup_info import SignupInfo
from sawtooth_validator.consensus.poet1.wait_timer import WaitTimer
from sawtooth_validator.consensus.poet1.wait_certificate \
    import WaitCertificate
from gossip.common import NullIdentifier
from utils import create_random_public_key_hash


class TestWaitCertificate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._originator_public_key_hash = create_random_public_key_hash()

    def setUp(self):
        # This is a little ham-handed, but we need to ensure that the
        # PoET enclave is set back to initial state at the start of every
        # test.
        SignupInfo.poet_enclave = reload(poet_enclave)
        WaitTimer.poet_enclave = poet_enclave
        WaitCertificate.poet_enclave = poet_enclave

        args = {"NodeName": "DasValidator"}
        SignupInfo.poet_enclave.initialize(**args)

    def test_create_wait_certificate_before_create_signup_info(self):
        # Make sure that trying to create a wait certificate before signup
        # information is provided causes an error
        with self.assertRaises(ValueError):
            WaitCertificate.create_wait_certificate(
                wait_timer=None,
                block_hash="Reader's Digest")

    def test_create_wait_certificate_before_create_wait_timer(self):
        # Need to create signup information
        SignupInfo.create_signup_info(
            validator_address='1660 Pennsylvania Avenue NW',
            originator_public_key_hash=self._originator_public_key_hash,
            most_recent_wait_certificate_id=NullIdentifier)

        with self.assertRaises(ValueError):
            WaitCertificate.create_wait_certificate(
                wait_timer=None,
                block_hash="Reader's Digest")

    def test_create_wait_certificate_before_wait_timer_expires(self):
        # Need to create signup information
        SignupInfo.create_signup_info(
            validator_address='1660 Pennsylvania Avenue NW',
            originator_public_key_hash=self._originator_public_key_hash,
            most_recent_wait_certificate_id=NullIdentifier)

        # Create a wait certificate for the genesis block so that we can
        # create another wait certificate that has to play by the rules.
        wt = \
            WaitTimer.create_wait_timer(
                validator_address='1660 Pennsylvania Avenue NW',
                certificates=[])
        wc = \
            WaitCertificate.create_wait_certificate(
                wait_timer=wt,
                block_hash="Reader's Digest")

        wt = \
            WaitTimer.create_wait_timer(
                validator_address='1660 Pennsylvania Avenue NW',
                certificates=[wc])
        with self.assertRaises(ValueError):
            wc = \
                WaitCertificate.create_wait_certificate(
                    wait_timer=wt,
                    block_hash="Reader's Digest")

    def test_create_wait_certificate_after_wait_timer_timed_out(self):
        # Need to create signup information
        SignupInfo.create_signup_info(
            validator_address='1660 Pennsylvania Avenue NW',
            originator_public_key_hash=self._originator_public_key_hash,
            most_recent_wait_certificate_id=NullIdentifier)

        # Create a wait certificate for the genesis block so that we can
        # create another wait certificate that has to play by the rules.
        wt = \
            WaitTimer.create_wait_timer(
                validator_address='1660 Pennsylvania Avenue NW',
                certificates=[])
        wc = \
            WaitCertificate.create_wait_certificate(
                wait_timer=wt,
                block_hash="Reader's Digest")

        wt = \
            WaitTimer.create_wait_timer(
                validator_address='1660 Pennsylvania Avenue NW',
                certificates=[wc])
        while not wt.has_expired(time.time()):
            time.sleep(1)
        time.sleep(10)

        with self.assertRaises(ValueError):
            wc = \
                WaitCertificate.create_wait_certificate(
                    wait_timer=wt,
                    block_hash="Reader's Digest")

    def test_create_wait_certificate(self):
        # Need to create signup information and wait timer first
        signup_info = \
            SignupInfo.create_signup_info(
                validator_address='1660 Pennsylvania Avenue NW',
                originator_public_key_hash=self._originator_public_key_hash,
                most_recent_wait_certificate_id=NullIdentifier)

        wt = \
            WaitTimer.create_wait_timer(
                validator_address='1660 Pennsylvania Avenue NW',
                certificates=[])
        while not wt.has_expired(time.time()):
            time.sleep(1)

        # Now we can create a wait certificate and verify that it correlates
        # to the wait timer we just created
        wc = \
            WaitCertificate.create_wait_certificate(
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
        self.assertTrue(wc.is_valid([], signup_info.poet_public_key))

        # Create another wait certificate and verify it is valid also
        wt = \
            WaitTimer.create_wait_timer(
                validator_address='1660 Pennsylvania Avenue NW',
                certificates=[wc])
        while not wt.has_expired(time.time()):
            time.sleep(1)

        # Now we can create a wait certificate and verify that it correlates
        # to the wait timer we just created
        another_wc = \
            WaitCertificate.create_wait_certificate(
                wait_timer=wt,
                block_hash="Pepto Bismol")

        self.assertTrue(
            another_wc.is_valid([wc], signup_info.poet_public_key))

    def test_wait_certificate_serialization(self):
        # Need to create signup information and wait timer first
        signup_info = \
            SignupInfo.create_signup_info(
                validator_address='1660 Pennsylvania Avenue NW',
                originator_public_key_hash=self._originator_public_key_hash,
                most_recent_wait_certificate_id=NullIdentifier)

        wt = \
            WaitTimer.create_wait_timer(
                validator_address='1660 Pennsylvania Avenue NW',
                certificates=[])
        while not wt.has_expired(time.time()):
            time.sleep(1)

        # Now we can create a wait certificate and serialize
        wc = \
            WaitCertificate.create_wait_certificate(
                wait_timer=wt,
                block_hash="Reader's Digest")

        dumped = wc.dump()

        self.assertIsNotNone(dumped.get('SerializedCertificate'))
        self.assertIsNotNone(dumped.get('Signature'))

        # Deserialize and verify that wait certificates are the same
        # and that deserialized one is valid
        wc_copy = \
            WaitCertificate.wait_certificate_from_serialized(
                dumped.get('SerializedCertificate'),
                dumped.get('Signature'))

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

        self.assertTrue(wc_copy.is_valid([], signup_info.poet_public_key))

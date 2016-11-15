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
import hashlib

from sawtooth_signing import pbct_nativerecover as signing
import sawtooth_validator.consensus.poet1.poet_enclave_simulator.\
    poet_enclave_simulator as poet_enclave

from sawtooth_validator.consensus.poet1.signup_info import SignupInfo
from sawtooth_validator.consensus.poet1.wait_timer import WaitTimer
from sawtooth_validator.consensus.poet1.wait_certificate \
    import WaitCertificate
from sawtooth_validator.consensus.poet1.wait_certificate \
    import WaitCertificateError

from gossip.common import NullIdentifier


class TestWaitCertificate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._originator_public_key = cls._create_random_public_key()
        cls._originator_public_key_hash = \
            hashlib.sha256(
                signing.encode_pubkey(
                    cls._originator_public_key,
                    'hex')).hexdigest()

    @classmethod
    def _create_random_private_key(cls):
        return signing.generate_privkey()

    @classmethod
    def _create_random_public_key(cls):
        return signing.generate_pubkey(cls._create_random_private_key())

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
        with self.assertRaises(WaitCertificateError):
            WaitCertificate.create_wait_certificate("Reader's Digest")

    def test_create_wait_certificate_before_create_wait_timer(self):
        # Need to create signup information
        SignupInfo.create_signup_info(
            originator_public_key_hash=self._originator_public_key_hash,
            most_recent_wait_certificate_id=NullIdentifier)

        with self.assertRaises(WaitCertificateError):
            WaitCertificate.create_wait_certificate("Reader's Digest")

    def test_create_wait_certificate(self):
        # Need to create signup information and wait timer first
        signup_info = \
            SignupInfo.create_signup_info(
                originator_public_key_hash=self._originator_public_key_hash,
                most_recent_wait_certificate_id=NullIdentifier)

        wt = WaitTimer.create_wait_timer([])

        # Now we can create a wait certificate and verify that it correlates
        # to the wait timer we just created
        wc = WaitCertificate.create_wait_certificate("Reader's Digest")

        self.assertIsNotNone(wc)

        self.assertEquals(
            wc.previous_certificate_id,
            wt.previous_certificate_id)
        self.assertEqual(wc.local_mean, wt.local_mean)
        self.assertEqual(wc.request_time, wt.request_time)
        self.assertEqual(wc.duration, wt.duration)
        self.assertEqual(wc.block_digest, "Reader's Digest")
        self.assertIsNotNone(wc.signature)
        self.assertIsNotNone(wc.identifier)

        # A newly-created wait certificate should be valid
        self.assertTrue(wc.is_valid([], signup_info.poet_public_key))

    def test_wait_certificate_serialization(self):
        # Need to create signup information and wait timer first
        signup_info = \
            SignupInfo.create_signup_info(
                originator_public_key_hash=self._originator_public_key_hash,
                most_recent_wait_certificate_id=NullIdentifier)

        wt = WaitTimer.create_wait_timer([])

        # Now we can create a wait certificate and serialize
        wc = WaitCertificate.create_wait_certificate("Reader's Digest")

        dumped = wc.dump()

        self.assertIsNotNone(dumped.get('SerializedCertificate'))
        self.assertIsNotNone(dumped.get('Signature'))

        # Deserialize and verify that wait certificates are the same
        # and that deserialized one is valid
        wc_copy = \
            WaitCertificate.wait_certificate_from_serialized(
                dumped.get('SerializedCertificate'),
                dumped.get('Signature'),
                signup_info.poet_public_key)

        self.assertEquals(
            wc.previous_certificate_id,
            wc_copy.previous_certificate_id)
        self.assertEqual(wc.local_mean, wc_copy.local_mean)
        self.assertEqual(wc.request_time, wc_copy.request_time)
        self.assertEqual(wc.duration, wc_copy.duration)
        self.assertEqual(wc.block_digest, wc_copy.block_digest)
        self.assertEqual(wc.signature, wc_copy.signature)
        self.assertEqual(wc.identifier, wc_copy.identifier)

        self.assertTrue(wc_copy.is_valid([], signup_info.poet_public_key))

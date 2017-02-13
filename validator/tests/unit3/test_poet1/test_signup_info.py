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

from sawtooth_validator.journal.consensus.poet1.signup_info import SignupInfo
from sawtooth_validator.journal.consensus.poet1.poet_enclave_simulator \
    import poet_enclave_simulator as poet_enclave
from sawtooth_validator.journal.block_wrapper import NULL_BLOCK_IDENTIFIER

from test_poet1.utils import create_random_public_key_hash


class TestSignupInfo(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        args = {"NodeName": "DasValidator"}
        poet_enclave.initialize(**args)
        SignupInfo.poet_enclave = poet_enclave

        cls._originator_public_key_hash = create_random_public_key_hash()
        cls._another_public_key_hash = create_random_public_key_hash()

    @classmethod
    def _create_random_private_key(cls):
        return signing.generate_privkey()

    @classmethod
    def _create_random_public_key(cls):
        return signing.generate_pubkey(cls._create_random_private_key())

    def test_basic_create_signup_info(self):
        signup_info = \
            SignupInfo.create_signup_info(
                validator_address='1660 Pennsylvania Avenue NW',
                originator_public_key_hash=self._originator_public_key_hash,
                most_recent_wait_certificate_id=NULL_BLOCK_IDENTIFIER)

        self.assertIsNotNone(signup_info.poet_public_key)
        self.assertIsNotNone(signup_info.proof_data)
        self.assertIsNotNone(signup_info.anti_sybil_id)
        self.assertIsNotNone(signup_info.sealed_signup_data)

    def test_verify_serialized_signup_info(self):
        signup_info = \
            SignupInfo.create_signup_info(
                validator_address='1660 Pennsylvania Avenue NW',
                originator_public_key_hash=self._originator_public_key_hash,
                most_recent_wait_certificate_id=NULL_BLOCK_IDENTIFIER)
        serialized = signup_info.serialize()
        copy_signup_info = SignupInfo.signup_info_from_serialized(serialized)

        self.assertEqual(
            signup_info.poet_public_key,
            copy_signup_info.poet_public_key)
        self.assertEqual(signup_info.proof_data, copy_signup_info.proof_data)
        self.assertEqual(
            signup_info.anti_sybil_id,
            copy_signup_info.anti_sybil_id)
        self.assertIsNone(copy_signup_info.sealed_signup_data)

    def test_verify_unsealing_data(self):
        signup_info = \
            SignupInfo.create_signup_info(
                validator_address='1660 Pennsylvania Avenue NW',
                originator_public_key_hash=self._originator_public_key_hash,
                most_recent_wait_certificate_id=NULL_BLOCK_IDENTIFIER)
        poet_public_key = \
            SignupInfo.unseal_signup_data(
                validator_address='1660 Pennsylvania Avenue NW',
                sealed_signup_data=signup_info.sealed_signup_data)

        self.assertEqual(
            signup_info.poet_public_key,
            poet_public_key,
            msg="PoET public key in signup info and sealed data don't match")

    def test_verify_signup_info(self):
        signup_info = \
            SignupInfo.create_signup_info(
                validator_address='1660 Pennsylvania Avenue NW',
                originator_public_key_hash=self._originator_public_key_hash,
                most_recent_wait_certificate_id=NULL_BLOCK_IDENTIFIER)

        try:
            signup_info.check_valid(
                originator_public_key_hash=self._originator_public_key_hash,
                most_recent_wait_certificate_id=NULL_BLOCK_IDENTIFIER)
        except ValueError as e:
            self.fail('Error with SignupInfo: {}'.format(e))

    def test_non_matching_originator_public_key(self):
        signup_info = \
            SignupInfo.create_signup_info(
                validator_address='1660 Pennsylvania Avenue NW',
                originator_public_key_hash=self._originator_public_key_hash,
                most_recent_wait_certificate_id=NULL_BLOCK_IDENTIFIER)

        with self.assertRaises(ValueError):
            signup_info.check_valid(
                originator_public_key_hash=self._another_public_key_hash,
                most_recent_wait_certificate_id=NULL_BLOCK_IDENTIFIER)

    def test_non_matching_most_recent_wait_certificate_id(self):
        signup_info = \
            SignupInfo.create_signup_info(
                validator_address='1660 Pennsylvania Avenue NW',
                originator_public_key_hash=self._originator_public_key_hash,
                most_recent_wait_certificate_id=NULL_BLOCK_IDENTIFIER)

        # NOTE - this requires that the signup information check for validity
        #        actually make this check.  Currently the check is not done.
        #        Once the check is added back, it should raise a
        #        ValueError exception and this test will fail, alerting
        #        you that you need to wrap the call in self.assertRaises
        #
        # with self.assertRaises(ValueError):
        signup_info.check_valid(
            originator_public_key_hash=self._originator_public_key_hash,
            most_recent_wait_certificate_id='SomeFunkyCertificateID')

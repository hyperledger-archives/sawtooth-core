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

import pybitcointools
from gossip.common import NullIdentifier
from journal.consensus.poet1.signup_info import SignupInfo
from journal.consensus.poet1.signup_info import SignupInfoError
from journal.consensus.poet1.poet_enclave_simulator \
    import poet_enclave_simulator as poet_enclave


class TestSignupInfo(unittest.TestCase):

    _originator_public_key = None
    _another_originator_public_key = None

    @classmethod
    def setUpClass(cls):
        args = {"NodeName": "DasValidator"}
        poet_enclave.initialize(**args)
        SignupInfo.poet_enclave = poet_enclave

        cls._originator_public_key = cls._create_random_public_key()
        cls._another_originator_public_key = cls._create_random_public_key()

    @classmethod
    def _create_random_private_key(cls):
        return pybitcointools.random_key()

    @classmethod
    def _create_random_public_key(cls):
        return pybitcointools.privtopub(cls._create_random_private_key())

    def test_basic_create_signup_info(self):
        signup_info = \
            SignupInfo.create_signup_info(
                originator_public_key=self._originator_public_key,
                validator_network_basename='This is CNN.',
                most_recent_wait_certificate_id=NullIdentifier)

        self.assertIsNotNone(signup_info.poet_public_key)
        self.assertIsNotNone(signup_info.proof_data)
        self.assertIsNotNone(signup_info.sealed_signup_data)

    def test_verify_serialized_signup_info(self):
        signup_info = \
            SignupInfo.create_signup_info(
                originator_public_key=self._originator_public_key,
                validator_network_basename='This is CNN.',
                most_recent_wait_certificate_id=NullIdentifier)
        serialized = signup_info.serialize()
        copy_signup_info = SignupInfo.signup_info_from_serialized(serialized)

        self.assertEqual(
            signup_info.poet_public_key,
            copy_signup_info.poet_public_key)
        self.assertEqual(signup_info.proof_data, copy_signup_info.proof_data)
        self.assertIsNone(copy_signup_info.sealed_signup_data)

    def test_verify_unsealing_data(self):
        signup_info = \
            SignupInfo.create_signup_info(
                originator_public_key=self._originator_public_key,
                validator_network_basename='This is CNN.',
                most_recent_wait_certificate_id=NullIdentifier)
        encoded_poet_public_key = \
            SignupInfo.unseal_signup_data(signup_info.sealed_signup_data)

        self.assertEqual(
            signup_info.poet_public_key,
            encoded_poet_public_key,
            msg="PoET public key in signup info and sealed data don't match")

    def test_verify_signup_info(self):
        signup_info = \
            SignupInfo.create_signup_info(
                originator_public_key=self._originator_public_key,
                validator_network_basename='This is CNN.',
                most_recent_wait_certificate_id=NullIdentifier)

        try:
            signup_info.check_valid(
                originator_public_key=self._originator_public_key,
                validator_network_basename="This is CNN.",
                most_recent_wait_certificate_id=NullIdentifier)
        except SignupInfoError as e:
            self.fail('Error with SignupInfo: {}'.format(e))

    def test_non_matching_originator_public_key(self):
        signup_info = \
            SignupInfo.create_signup_info(
                originator_public_key=self._originator_public_key,
                validator_network_basename='This is CNN.',
                most_recent_wait_certificate_id=NullIdentifier)

        with self.assertRaises(SignupInfoError):
            signup_info.check_valid(
                originator_public_key=self._another_originator_public_key,
                validator_network_basename="This is CNN.",
                most_recent_wait_certificate_id=NullIdentifier)

    def test_non_matching_validator_network_basename(self):
        signup_info = \
            SignupInfo.create_signup_info(
                originator_public_key=self._originator_public_key,
                validator_network_basename='This is CNN.',
                most_recent_wait_certificate_id=NullIdentifier)

        with self.assertRaises(SignupInfoError):
            signup_info.check_valid(
                originator_public_key=self._originator_public_key,
                validator_network_basename="This is Fox News.",
                most_recent_wait_certificate_id=NullIdentifier)

    def test_non_matching_most_recent_wait_certificate_id(self):
        signup_info = \
            SignupInfo.create_signup_info(
                originator_public_key=self._originator_public_key,
                validator_network_basename='This is CNN.',
                most_recent_wait_certificate_id=NullIdentifier)

        # NOTE - this requires that the signup information check for validity
        #        actually make this check.  Currently the check is not done.
        #        Once the check is added back, it should raise a
        #        SignupInfoError exception and this test will fail, alerting
        #        you that you need to wrap the call in self.assertRaises
        #
        # with self.assertRaises(SignupInfoError):
        signup_info.check_valid(
            originator_public_key=self._originator_public_key,
            validator_network_basename="This is CNN.",
            most_recent_wait_certificate_id='SomeFunkyCertificateID')

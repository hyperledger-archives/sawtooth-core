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
from journal.consensus.poet1.signup_info import SignupInfo
from journal.consensus.poet1.poet_enclave_simulator \
    import poet_enclave_simulator as poet_enclave


class TestPoet1SignupInfo(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        args = {}
        poet_enclave.initialize(**args)
        SignupInfo.poet_enclave = poet_enclave

    @classmethod
    def _create_random_private_key(cls):
        return pybitcointools.random_key()

    @classmethod
    def _create_random_public_key(cls):
        return pybitcointools.privtopub(cls._create_random_private_key())

    def test_basic_create_signup_info(self):
        signup_info = \
            SignupInfo.create_signup_info(
                self._create_random_public_key())

        self.assertIsNotNone(signup_info.poet_public_key)
        self.assertIsNotNone(signup_info.anti_sybil_id)
        self.assertIsNotNone(signup_info.proof_data)
        self.assertIsNotNone(signup_info.sealed_signup_data)

    def test_verify_serialized_signup_info(self):
        signup_info = \
            SignupInfo.create_signup_info(
                self._create_random_public_key())
        serialized = signup_info.serialize()
        copy_signup_info = SignupInfo.signup_info_from_serialized(serialized)

        self.assertEqual(
            signup_info.poet_public_key,
            copy_signup_info.poet_public_key)
        self.assertEqual(
            signup_info.anti_sybil_id,
            copy_signup_info.anti_sybil_id)
        self.assertEqual(signup_info.proof_data, copy_signup_info.proof_data)
        self.assertIsNone(copy_signup_info.sealed_signup_data)

    def test_verify_unsealing_data(self):
        signup_info = \
            SignupInfo.create_signup_info(
                self._create_random_public_key())
        encoded_poet_public_key = \
            SignupInfo.unseal_signup_data(signup_info.sealed_signup_data)

        self.assertEqual(
            signup_info.poet_public_key,
            encoded_poet_public_key,
            msg="PoET public key in signup info and sealed data don't match")

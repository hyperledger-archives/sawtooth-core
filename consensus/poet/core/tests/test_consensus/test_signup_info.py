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

import unittest
import tempfile
import shutil

from sawtooth_poet_simulator.poet_enclave_simulator \
    import poet_enclave_simulator as poet_enclave

from sawtooth_poet.poet_consensus.signup_info import SignupInfo

from sawtooth_validator.journal.block_wrapper import NULL_BLOCK_IDENTIFIER

from test_consensus.utils import create_random_public_key_hash


class TestSignupInfo(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._temp_dir = tempfile.mkdtemp()
        cls._originator_public_key_hash = create_random_public_key_hash()
        cls._another_public_key_hash = create_random_public_key_hash()
        poet_enclave.initialize(cls._temp_dir, cls._temp_dir)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls._temp_dir)

    def test_create(self):
        signup_info = \
            SignupInfo.create_signup_info(
                poet_enclave_module=poet_enclave,
                originator_public_key_hash=self._originator_public_key_hash,
                nonce=NULL_BLOCK_IDENTIFIER)

        self.assertIsNotNone(signup_info.poet_public_key)
        self.assertIsNotNone(signup_info.proof_data)
        self.assertIsNotNone(signup_info.anti_sybil_id)
        self.assertIsNotNone(signup_info.sealed_signup_data)

    def test_serialization(self):
        signup_info = \
            SignupInfo.create_signup_info(
                poet_enclave_module=poet_enclave,
                originator_public_key_hash=self._originator_public_key_hash,
                nonce=NULL_BLOCK_IDENTIFIER)
        serialized = signup_info.serialize()
        copy_signup_info = \
            SignupInfo.signup_info_from_serialized(
                poet_enclave_module=poet_enclave,
                serialized=serialized)

        self.assertEqual(
            signup_info.poet_public_key,
            copy_signup_info.poet_public_key)
        self.assertEqual(signup_info.proof_data, copy_signup_info.proof_data)
        self.assertEqual(
            signup_info.anti_sybil_id,
            copy_signup_info.anti_sybil_id)
        self.assertIsNone(copy_signup_info.sealed_signup_data)

    def test_unsealing_data(self):
        signup_info = \
            SignupInfo.create_signup_info(
                poet_enclave_module=poet_enclave,
                originator_public_key_hash=self._originator_public_key_hash,
                nonce=NULL_BLOCK_IDENTIFIER)
        poet_public_key = \
            SignupInfo.unseal_signup_data(
                poet_enclave_module=poet_enclave,
                sealed_signup_data=signup_info.sealed_signup_data)

        self.assertEqual(
            signup_info.poet_public_key,
            poet_public_key,
            msg="PoET public key in signup info and sealed data don't match")

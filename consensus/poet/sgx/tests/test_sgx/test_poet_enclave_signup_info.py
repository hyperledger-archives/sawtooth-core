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

import os
import tempfile
import shutil

from unittest import TestCase
from unittest import mock

from test_sgx.utils import create_random_public_key_hash
# pylint: disable=no-name-in-module
from sawtooth_poet_sgx.poet_enclave_sgx import poet_enclave as poet

from sawtooth_validator.config.path import get_default_path_config


class TestPoetEnclaveSignupInfo(TestCase):
    @classmethod
    def setUpClass(cls):
        cls._mock_toml_config = {
            'spid': os.environ['POET_ENCLAVE_SPID'],
            'ias_url': 'https://test-as.sgx.trustedservices.intel.com:443',
            'spid_cert_file': os.path.join(
                get_default_path_config().config_dir,
                'maiden-lane-poet-linkable-quotes.pem')
        }

        cls._temp_dir = tempfile.mkdtemp()

        with mock.patch(
                'sawtooth_poet_sgx.poet_enclave_sgx.poet_enclave.open') as _:
            with mock.patch(
                    'sawtooth_poet_sgx.poet_enclave_sgx.poet_enclave.toml') \
                    as mock_toml:
                mock_toml.loads.return_value = cls._mock_toml_config
                poet.initialize(config_dir='', data_dir=cls._temp_dir)

        cls._originator_public_key_hash = create_random_public_key_hash()

    @classmethod
    def tearDownClass(cls):
        poet.shutdown()
        shutil.rmtree(cls._temp_dir)

    @classmethod
    def _create_signup_info(cls):
        return \
            poet.create_signup_info(
                originator_public_key_hash=cls._originator_public_key_hash,
                nonce=poet.NULL_IDENTIFIER)

    def test_basic_create_signup_info(self):
        signup_info = self._create_signup_info()

        self.assertIsNotNone(signup_info)
        self.assertIsNotNone(signup_info.poet_public_key)
        self.assertIsNotNone(signup_info.sealed_signup_data)
        self.assertIsNotNone(signup_info.proof_data)
        self.assertIsNotNone(signup_info.anti_sybil_id)

    def test_verify_serialized_signup_info(self):
        signup_info = self._create_signup_info()

        serialized_signup_info = signup_info.serialize()

        signup_info_doppleganger = \
            poet.deserialize_signup_info(serialized_signup_info)

        self.assertIsNotNone(signup_info_doppleganger)
        self.assertEqual(
            signup_info.poet_public_key,
            signup_info_doppleganger.poet_public_key)
        self.assertNotEqual(
            signup_info.sealed_signup_data,
            signup_info_doppleganger.sealed_signup_data)
        self.assertEqual(
            signup_info.proof_data,
            signup_info_doppleganger.proof_data)
        self.assertEqual(
            signup_info.anti_sybil_id,
            signup_info_doppleganger.anti_sybil_id)

    def test_verify_unsealing_data(self):
        signup_info = self._create_signup_info()

        self.assertEqual(
            signup_info.poet_public_key,
            poet.unseal_signup_data(signup_info.sealed_signup_data))

    def test_release_signup_data(self):
        signup_info = self._create_signup_info()

        poet.release_signup_data(signup_info.sealed_signup_data)

        with self.assertRaises(SystemError):
            poet.unseal_signup_data(signup_info.sealed_signup_data)

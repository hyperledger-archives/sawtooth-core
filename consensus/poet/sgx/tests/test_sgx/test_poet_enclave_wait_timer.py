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

import time
import os
import tempfile
import shutil

from unittest import TestCase
from unittest import mock

from test_sgx.utils import random_name
from test_sgx.utils import create_random_public_key_hash
# pylint: disable=no-name-in-module
from sawtooth_poet_sgx.poet_enclave_sgx import poet_enclave as poet

from sawtooth_validator.config.path import get_default_path_config


class TestPoetEnclaveWaitTimer(TestCase):
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

    def test_before_creating_signup_info(self):
        # If we have not created signup information, an exception should be
        # thrown if we try to create a wait timer.
        with self.assertRaises(ValueError):
            addr = random_name(34)
            previous_cert_id = poet.NULL_IDENTIFIER
            poet.create_wait_timer(None, addr, previous_cert_id, 100)

    def test_create(self):
        addr = random_name(34)

        signup_info = poet.create_signup_info(
            originator_public_key_hash=self._originator_public_key_hash,
            nonce=poet.NULL_IDENTIFIER)
        sealed_data = signup_info.sealed_signup_data

        previous_cert_id = poet.NULL_IDENTIFIER
        wait_timer = poet.create_wait_timer(
            sealed_data, addr, previous_cert_id, 100)
        self.assertEqual(wait_timer.previous_certificate_id, previous_cert_id)
        self.assertEqual(wait_timer.local_mean, 100)

        # Random previous cert id
        previous_cert_id = random_name(poet.IDENTIFIER_LENGTH)

        # Invalid types for validator address
        with self.assertRaises(TypeError):
            poet.create_wait_timer(sealed_data, [], previous_cert_id, 100)
        with self.assertRaises(TypeError):
            poet.create_wait_timer(sealed_data, {}, previous_cert_id, 100)
        with self.assertRaises(ValueError):
            poet.create_wait_timer(sealed_data, None, previous_cert_id, 100)
        with self.assertRaises(TypeError):
            poet.create_wait_timer(sealed_data, 8888, previous_cert_id, 100)

        # Bad local means
        with self.assertRaises(ValueError):
            poet.create_wait_timer(sealed_data, addr, previous_cert_id, -1)
        with self.assertRaises(ValueError):
            poet.create_wait_timer(sealed_data, addr, previous_cert_id, 0)
        with self.assertRaises(TypeError):
            poet.create_wait_timer(sealed_data, addr, previous_cert_id, [])
        with self.assertRaises(TypeError):
            poet.create_wait_timer(sealed_data, addr, previous_cert_id, None)
        with self.assertRaises(TypeError):
            poet.create_wait_timer(sealed_data, addr, previous_cert_id, "3")

        # Invalid types for previous certificate
        with self.assertRaises(TypeError):
            poet.create_wait_timer(sealed_data, addr, [], 0)
        with self.assertRaises(TypeError):
            poet.create_wait_timer(sealed_data, addr, {}, 0)
        with self.assertRaises(ValueError):
            poet.create_wait_timer(sealed_data, addr, None, 0)
        with self.assertRaises(TypeError):
            poet.create_wait_timer(sealed_data, addr, 8888, 0)

        previous_cert_id = ""  # to short
        with self.assertRaises(ValueError):
            poet.create_wait_timer(sealed_data, addr, previous_cert_id, 100)

        previous_cert_id = random_name(8)  # to short
        with self.assertRaises(ValueError):
            poet.create_wait_timer(sealed_data, addr, previous_cert_id, 100)

        previous_cert_id = random_name(17)  # to long
        with self.assertRaises(ValueError):
            poet.create_wait_timer(sealed_data, addr, previous_cert_id, 100)

    def test_is_expired(self):
        addr = random_name(34)
        signup_info = poet.create_signup_info(
            originator_public_key_hash=self._originator_public_key_hash,
            nonce=poet.NULL_IDENTIFIER)
        sealed_data = signup_info.sealed_signup_data

        previous_cert_id = poet.NULL_IDENTIFIER
        start = time.time()
        wait_timer = poet.create_wait_timer(
            sealed_data, addr, previous_cert_id, 5)
        while not wait_timer.has_expired():
            time.sleep(1)
        end = time.time()
        self.assertLessEqual(wait_timer.duration, end - start)

        # we could tamper with the data to get it to register
        # is_expired sooner, but that will cause the validation to fail
        # as showing in the test_serialize tampered data tests below.

    def test_serialize(self):
        addr = random_name(34)
        signup_info = poet.create_signup_info(
            originator_public_key_hash=self._originator_public_key_hash,
            nonce=poet.NULL_IDENTIFIER)
        sealed_data = signup_info.sealed_signup_data

        previous_cert_id = poet.NULL_IDENTIFIER
        wait_timer = poet.create_wait_timer(
            sealed_data, addr, previous_cert_id, 5)
        serialized_wait_timer = wait_timer.serialize()

        wait_timer2 = poet.deserialize_wait_timer(
            serialized_wait_timer,
            wait_timer.signature)

        self.assertAlmostEqual(wait_timer.duration, wait_timer2.duration)
        self.assertEqual(wait_timer.request_time, wait_timer2.request_time)
        self.assertEqual(wait_timer.previous_certificate_id,
                         wait_timer2.previous_certificate_id)
        self.assertEqual(wait_timer.signature, wait_timer2.signature)

        # Bad serialized strings
        with self.assertRaises(TypeError):
            poet.deserialize_wait_timer([], wait_timer.signature)
        with self.assertRaises(TypeError):
            poet.deserialize_wait_timer({}, wait_timer.signature)
        with self.assertRaises(ValueError):
            poet.deserialize_wait_timer(None, wait_timer.signature)
        with self.assertRaises(TypeError):
            poet.deserialize_wait_timer(8, wait_timer.signature)
        with self.assertRaises(ValueError):
            poet.deserialize_wait_timer(
                random_name(len(serialized_wait_timer)),
                wait_timer.signature)
        with self.assertRaises(ValueError):
            poet.deserialize_wait_timer(
                serialized_wait_timer[:int(len(serialized_wait_timer) / 2)],
                wait_timer.signature)

        # Bad signatures
        with self.assertRaises(TypeError):
            poet.deserialize_wait_timer(serialized_wait_timer, [])
        with self.assertRaises(TypeError):
            poet.deserialize_wait_timer(serialized_wait_timer, {})
        with self.assertRaises(ValueError):
            poet.deserialize_wait_timer(serialized_wait_timer, None)
        with self.assertRaises(TypeError):
            poet.deserialize_wait_timer(serialized_wait_timer, 7)

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
from unittest import skip

from test_sgx.utils import random_name
from test_sgx.utils import create_random_public_key_hash
# pylint: disable=no-name-in-module
from sawtooth_poet_sgx.poet_enclave_sgx import poet_enclave as poet

from sawtooth_validator.config.path import get_default_path_config


class TestPoetEnclaveWaitCertificate(TestCase):
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

    def get_wait_timer(self, sealed_data, addr=None):
        pid = random_name(poet.IDENTIFIER_LENGTH)

        if addr is None:
            addr = random_name(34)

        # super short local mean to get small duration..
        wait_timer = poet.create_wait_timer(sealed_data, addr, pid, 1)

        while not wait_timer.has_expired():
            time.sleep(1)

        return wait_timer

    def get_wait_cert(self, sealed_data, addr=None):
        block_hash = random_name(32)
        wait_timer = self.get_wait_timer(sealed_data, addr)
        return poet.create_wait_certificate(
            sealed_data, wait_timer, block_hash)

    @skip("Disabled. Out of sync with simulator and Timeout fails to fail.")
    def test_create(self):
        addr = random_name(34)
        signup_info = poet.create_signup_info(
            originator_public_key_hash=self._originator_public_key_hash,
            nonce=poet.NULL_IDENTIFIER)
        sealed_data = signup_info.sealed_signup_data
        block_hash = random_name(32)

        # with expired timer -- positive case
        wait_timer = self.get_wait_timer(sealed_data, addr=addr)
        wait_cert = poet.create_wait_certificate(
            sealed_data, wait_timer, block_hash)
        self.assertEqual(wait_timer.duration, wait_cert.duration)
        self.assertEqual(wait_timer.local_mean, wait_cert.local_mean)
        self.assertNotEqual(wait_cert.nonce, '')
        self.assertEqual(wait_timer.previous_certificate_id,
                         wait_cert.previous_certificate_id)
        self.assertEqual(len(wait_cert.identifier()),
                         poet.IDENTIFIER_LENGTH)

        # We should not be able to create another wait certificate with the
        # same wait timer.
        with self.assertRaises(ValueError):
            poet.create_wait_certificate(sealed_data, wait_timer, block_hash)

        # When we create a new wait timer, it should not be possible to use
        # another, otherwise valid, wait timer to create a wait certificate.
        wait_timer = self.get_wait_timer(sealed_data, addr=addr)
        poet.create_wait_timer(sealed_data, addr, poet.NULL_IDENTIFIER, 1)

        with self.assertRaises(ValueError):
            poet.create_wait_certificate(sealed_data, wait_timer, block_hash)

        # the initial block does not need to wait, to accelerate
        # validator launch
        wait_timer = poet.create_wait_timer(
            sealed_data, addr, poet.NULL_IDENTIFIER, 1)
        wait_cert = poet.create_wait_certificate(
            sealed_data, wait_timer, block_hash)
        self.assertEqual(wait_timer.duration, wait_cert.duration)
        self.assertEqual(wait_timer.local_mean, wait_cert.local_mean)
        self.assertEqual(wait_timer.previous_certificate_id,
                         wait_cert.previous_certificate_id)

        # with unexpired timer
        wait_timer = \
            poet.create_wait_timer(
                sealed_data, addr, random_name(poet.IDENTIFIER_LENGTH), 10)
        with self.assertRaises(ValueError):
            poet.create_wait_certificate(sealed_data, wait_timer, block_hash)

        # With timed out timer
        wait_timer = self.get_wait_timer(sealed_data, addr=addr)
        time.sleep(10)
        with self.assertRaises(ValueError):
            wait_cert = poet.create_wait_certificate(
                sealed_data, wait_timer, block_hash)

        # verify that new wait certificate gets a different nonce.  In reality
        # we should test a statistically significant number of wait
        # certificates to verify that each gets a unique nonce, but we have to
        # wait for wait timers to expire and we want the test to finish
        # sometime this century.
        wait_timer = self.get_wait_timer(sealed_data, addr=addr)
        wait_cert2 = poet.create_wait_certificate(
            sealed_data, wait_timer, block_hash)
        self.assertNotEqual(wait_cert.nonce, wait_cert2.nonce)

    def test_create_out_of_seq(self):
        addr = random_name(34)
        signup_info_obj = poet.create_signup_info(
            originator_public_key_hash=self._originator_public_key_hash,
            nonce=poet.NULL_IDENTIFIER)
        sealed_data = signup_info_obj.sealed_signup_data
        block_hash = random_name(32)

        # use expired wait timers out of order
        wait_timer = self.get_wait_timer(sealed_data, addr)
        _ = self.get_wait_timer(sealed_data, addr)
        with self.assertRaises(ValueError):
            _ = poet.create_wait_certificate(
                sealed_data, wait_timer, block_hash)

    def test_serialize(self):
        addr = random_name(34)
        signup_info = poet.create_signup_info(
            originator_public_key_hash=self._originator_public_key_hash,
            nonce=poet.NULL_IDENTIFIER)
        sealed_data = signup_info.sealed_signup_data

        wait_cert = self.get_wait_cert(sealed_data, addr=addr)
        serialized_wait_cert = wait_cert.serialize()

        wait_cert2 = poet.deserialize_wait_certificate(
            serialized_wait_cert,
            wait_cert.signature)

        self.assertAlmostEqual(wait_cert.duration, wait_cert2.duration)
        self.assertEqual(wait_cert.local_mean, wait_cert2.local_mean)
        self.assertEqual(wait_cert.request_time, wait_cert2.request_time)
        self.assertEqual(wait_cert.nonce, wait_cert2.nonce)
        self.assertEqual(wait_cert.previous_certificate_id,
                         wait_cert2.previous_certificate_id)
        self.assertEqual(wait_cert.signature, wait_cert2.signature)
        self.assertEqual(wait_cert.identifier(), wait_cert2.identifier())

        # Bad Serial strings
        with self.assertRaises(ValueError):
            poet.deserialize_wait_certificate(None, wait_cert.signature)
        with self.assertRaises(TypeError):
            poet.deserialize_wait_certificate([], wait_cert.signature)
        with self.assertRaises(TypeError):
            poet.deserialize_wait_certificate(8, wait_cert.signature)
        with self.assertRaises(ValueError):
            poet.deserialize_wait_certificate(
                random_name(len(serialized_wait_cert)),
                wait_cert.signature)
        with self.assertRaises(ValueError):
            poet.deserialize_wait_certificate("{}", wait_cert.signature)

        with self.assertRaises(ValueError):
            poet.deserialize_wait_certificate(
                serialized_wait_cert[:int(len(serialized_wait_cert) / 2)],
                wait_cert.signature)

        # Bad signature strings
        with self.assertRaises(ValueError):
            poet.deserialize_wait_certificate(serialized_wait_cert, None)
        with self.assertRaises(TypeError):
            poet.deserialize_wait_certificate(serialized_wait_cert, [])
        with self.assertRaises(TypeError):
            poet.deserialize_wait_certificate(serialized_wait_cert, 7)
        with self.assertRaises(TypeError):
            poet.deserialize_wait_certificate(8, wait_cert.signature)

    def test_verify(self):
        addr = random_name(34)
        signup_info = \
            poet.create_signup_info(
                originator_public_key_hash=self._originator_public_key_hash,
                nonce=poet.NULL_IDENTIFIER)
        sealed_data = signup_info.sealed_signup_data

        wait_cert = self.get_wait_cert(sealed_data, addr=addr)
        poet.verify_wait_certificate(
            wait_cert,
            signup_info.poet_public_key)

        # Bad wait certificate types
        with self.assertRaises(TypeError):
            poet.verify_wait_certificate([], signup_info.poet_public_key)

        with self.assertRaises(TypeError):
            poet.verify_wait_certificate({}, signup_info.poet_public_key)

        with self.assertRaises(ValueError):
            poet.verify_wait_certificate(None, signup_info.poet_public_key)

        with self.assertRaises(TypeError):
            poet.verify_wait_certificate("3", signup_info.poet_public_key)

        with self.assertRaises(TypeError):
            poet.verify_wait_certificate(3, signup_info.poet_public_key)

        # Bad public key types
        with self.assertRaises(TypeError):
            poet.verify_wait_certificate(wait_cert, [])

        with self.assertRaises(TypeError):
            poet.verify_wait_certificate(wait_cert, {})

        with self.assertRaises(ValueError):
            poet.verify_wait_certificate(wait_cert, None)

        with self.assertRaises(TypeError):
            poet.verify_wait_certificate(wait_cert, 3)

        # A different public key
        other_signup_info = \
            poet.create_signup_info(
                originator_public_key_hash=create_random_public_key_hash(),
                nonce=poet.NULL_IDENTIFIER)

        with self.assertRaises(ValueError):
            poet.verify_wait_certificate(
                wait_cert,
                other_signup_info.poet_public_key)

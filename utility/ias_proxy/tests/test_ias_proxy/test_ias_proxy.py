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
import subprocess
import signal
import os
import socket
import tempfile
import shutil

from unittest import TestCase
from unittest import mock

from test_ias_proxy.utils import random_name
from test_ias_proxy.utils import create_random_public_key_hash

# pylint: disable=no-name-in-module
from sawtooth_poet_sgx.poet_enclave_sgx import poet_enclave as poet


class TestIasProxyClient(TestCase):
    @classmethod
    def setUpClass(cls):

        enclave_path = \
            os.path.join(
                os.path.abspath(
                    os.path.dirname(
                        os.path.relpath(__file__))),
                '..',
                '..',
                'sawtooth_ias_proxy')
        cls.proxy_proc = \
            subprocess.Popen(
                args=['python3', 'ias_proxy.py'],
                cwd=enclave_path)
        print('Launched proxy server on pid: ' + str(cls.proxy_proc.pid))

        # Depending upon timing, the test can try to contact the proxy before
        # it is ready to accept connections.  So, until the proxy is ready
        # block the tests from progressing.
        # Note - if IAS proxy port changes, change this also
        while True:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            if sock.connect_ex(('localhost', 8899)) == 0:
                sock.close()
                break
            sock.close()
            print('IAS proxy not ready to accept connections')
            time.sleep(1)

        cls._mock_toml_config = {
            'spid': os.environ['POET_ENCLAVE_SPID'],
            'ias_url': 'http://localhost:8899',
            'spid_cert_file': 'dummy_cert.pem'
        }

        cls._temp_dir = tempfile.mkdtemp()

        with mock.patch(
                'sawtooth_poet_sgx.poet_enclave_sgx.poet_enclave.open'):
            with mock.patch(
                    'sawtooth_poet_sgx.poet_enclave_sgx.poet_enclave.toml') \
                    as mock_toml:
                mock_toml.loads.return_value = cls._mock_toml_config
                poet.initialize(config_dir='', data_dir=cls._temp_dir)

        cls._originator_public_key_hash = create_random_public_key_hash()

    @classmethod
    def tearDownClass(cls):
        cls.proxy_proc.send_signal(signal.SIGTERM)
        poet.shutdown()
        shutil.rmtree(cls._temp_dir)

    def get_wait_timer(self, signup_info=None, addr=None):
        pid = random_name(poet.IDENTIFIER_LENGTH)

        if addr is None:
            addr = random_name(34)

        if signup_info is None:
            signup_info = poet.create_signup_info(
                originator_public_key_hash=self._originator_public_key_hash,
                nonce=poet.NULL_IDENTIFIER)

        sealed_data = signup_info.sealed_signup_data

        # super short local mean to get small duration..
        wait_timer = poet.create_wait_timer(sealed_data, addr, pid, 1)

        while not wait_timer.has_expired():
            time.sleep(1)

        return wait_timer

    def get_wait_cert(self, signup_info=None, addr=None):
        block_hash = random_name(32)
        if signup_info is None:
            signup_info = poet.create_signup_info(
                originator_public_key_hash=self._originator_public_key_hash,
                nonce=poet.NULL_IDENTIFIER)

        sealed_data = signup_info.sealed_signup_data

        wait_timer = self.get_wait_timer(signup_info=signup_info, addr=addr)
        return \
            poet.create_wait_certificate(
                sealed_data,
                wait_timer,
                block_hash)

    def test_create(self):
        addr = random_name(34)
        signup_info = poet.create_signup_info(
            originator_public_key_hash=self._originator_public_key_hash,
            nonce=poet.NULL_IDENTIFIER)
        sealed_data = signup_info.sealed_signup_data
        block_hash = random_name(32)

        # the initial block does not need to wait, to accelerate
        # validator launch
        wait_timer = poet.create_wait_timer(
            sealed_data, addr, poet.NULL_IDENTIFIER, 1)
        wait_cert = \
            poet.create_wait_certificate(
                sealed_data,
                wait_timer,
                block_hash)
        self.assertEqual(wait_timer.duration, wait_cert.duration)
        self.assertEqual(wait_timer.local_mean, wait_cert.local_mean)
        self.assertEqual(wait_timer.previous_certificate_id,
                         wait_cert.previous_certificate_id)
        self.assertEqual(len(wait_cert.identifier()),
                         poet.IDENTIFIER_LENGTH)

    def test_verify(self):
        addr = random_name(34)
        signup_info = poet.create_signup_info(
            originator_public_key_hash=self._originator_public_key_hash,
            nonce=poet.NULL_IDENTIFIER)

        wait_cert = self.get_wait_cert(signup_info=signup_info, addr=addr)
        poet.verify_wait_certificate(
            wait_cert,
            signup_info.poet_public_key)

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
        other_signup_info = poet.create_signup_info(
            originator_public_key_hash=create_random_public_key_hash(),
            nonce=poet.NULL_IDENTIFIER)

        with self.assertRaises(ValueError):
            poet.verify_wait_certificate(
                wait_cert,
                other_signup_info.poet_public_key)

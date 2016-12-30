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

from utils import random_name


from sawtooth_validator.consensus.poet0.wait_certificate import is_close
from sawtooth_validator.consensus.poet0.poet_enclave_simulator \
    import poet0_enclave_simulator as pe_sim


class TestPoetEnclaveWaitCertificate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        args = {}
        pe_sim.initialize(**args)

    def get_wait_timer(self):
        pid = random_name(pe_sim.IDENTIFIER_LENGTH)

        addr = random_name(20)
        # super short local mean to get small duration..
        wait_timer = pe_sim.create_wait_timer(addr, pid, 1)

        while not wait_timer.is_expired():
            time.sleep(1)

        return wait_timer

    def get_wait_cert(self):
        block_hash = random_name(32)
        wait_timer = self.get_wait_timer()
        return pe_sim.create_wait_certificate(wait_timer, block_hash)

    def test_create(self):
        block_hash = random_name(32)
        addr = random_name(32)

        # with expired timer -- positive case
        wait_timer = self.get_wait_timer()
        wait_cert = pe_sim.create_wait_certificate(wait_timer, block_hash)
        self.assertEqual(wait_timer.duration, wait_cert.duration)
        self.assertEqual(wait_timer.local_mean, wait_cert.local_mean)
        self.assertEqual(wait_timer.previous_certificate_id,
                         wait_cert.previous_certificate_id)
        self.assertEqual(len(wait_cert.identifier()),
                         pe_sim.IDENTIFIER_LENGTH)

        # the initial block does not need to wait, to accelerate
        # validator launch
        wait_timer = pe_sim.create_wait_timer(addr, pe_sim.NULL_IDENTIFIER, 1)
        wait_cert = pe_sim.create_wait_certificate(wait_timer, block_hash)
        self.assertEqual(wait_timer.duration, wait_cert.duration)
        self.assertEqual(wait_timer.local_mean, wait_cert.local_mean)
        self.assertEqual(wait_timer.previous_certificate_id,
                         wait_cert.previous_certificate_id)

        # with unexpired timer
        wait_timer = pe_sim.create_wait_timer(
            addr,
            random_name(pe_sim.IDENTIFIER_LENGTH), 1)
        wait_cert = pe_sim.create_wait_certificate(wait_timer, block_hash)

        # with tampered timer
        wait_timer = pe_sim.create_wait_timer(
            addr,
            random_name(pe_sim.IDENTIFIER_LENGTH), 1)
        wait_timer.duration = 1
        wait_cert = pe_sim.create_wait_certificate(wait_timer, block_hash)
        self.assertIsNone(wait_cert)

        wait_timer = pe_sim.create_wait_timer(
            addr,
            random_name(pe_sim.IDENTIFIER_LENGTH), 1)
        wait_timer.local_mean = 1
        wait_cert = pe_sim.create_wait_certificate(wait_timer, block_hash)
        self.assertIsNone(wait_cert)

        wait_timer = pe_sim.create_wait_timer(
            addr,
            random_name(pe_sim.IDENTIFIER_LENGTH), 1)
        wait_timer.previous_certificate_id = \
            random_name(pe_sim.IDENTIFIER_LENGTH)
        wait_cert = pe_sim.create_wait_certificate(wait_timer, block_hash)
        self.assertIsNone(wait_cert)

    def test_serialize(self):
        wait_cert = self.get_wait_cert()
        serialized_wait_cert = wait_cert.serialize()

        wait_cert2 = pe_sim.deserialize_wait_certificate(
            serialized_wait_cert,
            wait_cert.signature)

        self.assertTrue(is_close(
            wait_cert.duration,
            wait_cert2.duration,
            rel_tol=0.001))
        self.assertEqual(wait_cert.local_mean, wait_cert2.local_mean)
        self.assertEqual(wait_cert.request_time, wait_cert2.request_time)
        self.assertEqual(wait_cert.previous_certificate_id,
                         wait_cert.previous_certificate_id)
        self.assertEqual(wait_cert.signature, wait_cert2.signature)
        self.assertEqual(wait_cert.identifier(), wait_cert2.identifier())

        # Bad Serial strings
        with self.assertRaises(TypeError) as context:
            wait_cert2 = pe_sim.deserialize_wait_certificate(
                None,
                wait_cert.signature)
        with self.assertRaises(TypeError) as context:
            wait_cert2 = pe_sim.deserialize_wait_certificate(
                [],
                wait_cert.signature)
        with self.assertRaises(TypeError) as context:
            wait_cert2 = pe_sim.deserialize_wait_certificate(
                8,
                wait_cert.signature)
        with self.assertRaises(ValueError) as context:
            wait_cert2 = pe_sim.deserialize_wait_certificate(
                random_name(len(serialized_wait_cert)),
                wait_cert.signature)
        with self.assertRaises(ValueError) as context:
            wait_cert2 = pe_sim.deserialize_wait_certificate(
                serialized_wait_cert[:len(serialized_wait_cert) / 2],
                wait_cert.signature)

        # Bad Types
        with self.assertRaises(TypeError) as context:
            wait_cert2 = pe_sim.deserialize_wait_certificate(
                serialized_wait_cert,
                None)
        with self.assertRaises(TypeError) as context:
            wait_cert2 = pe_sim.deserialize_wait_certificate(
                serialized_wait_cert,
                [])
        with self.assertRaises(ValueError) as context:
            wait_cert2 = pe_sim.deserialize_wait_certificate(
                serialized_wait_cert,
                "")
        with self.assertRaises(TypeError) as context:
            wait_cert2 = pe_sim.deserialize_wait_certificate(
                serialized_wait_cert,
                7)
        with self.assertRaises(ValueError) as context:
            wait_cert2 = pe_sim.deserialize_wait_certificate(
                serialized_wait_cert,
                random_name(len(wait_cert.signature)))

        with self.assertRaises(TypeError) as context:
            wait_cert2 = pe_sim.deserialize_wait_certificate(
                8,
                wait_cert.signature)

        # tampered data
        wait_cert = self.get_wait_cert()
        wait_cert.duration = 2
        serialized_wait_cert = wait_cert.serialize()
        with self.assertRaises(ValueError) as context:
            wait_cert2 = pe_sim.deserialize_wait_certificate(
                serialized_wait_cert,
                wait_cert.signature)

        wait_cert = self.get_wait_cert()
        wait_cert.request_time = 2
        serialized_wait_cert = wait_cert.serialize()
        with self.assertRaises(ValueError) as context:
            wait_cert2 = pe_sim.deserialize_wait_certificate(
                serialized_wait_cert,
                wait_cert.signature)

        wait_cert = self.get_wait_cert()
        wait_cert.previous_certificate_id = random_name(
            len(pe_sim.NULL_IDENTIFIER))
        serialized_wait_cert = wait_cert.serialize()
        with self.assertRaises(ValueError) as context:
            wait_cert2 = pe_sim.deserialize_wait_certificate(
                serialized_wait_cert,
                wait_cert.signature)

    def test_verify(self):
        wait_cert = self.get_wait_cert()
        pe_sim.verify_wait_certificate(wait_cert)

        with self.assertRaises(TypeError) as context:
            r = pe_sim.verify_wait_certificate([])
            self.assertFalse(r)
        with self.assertRaises(ValueError) as context:
            pe_sim.verify_wait_certificate(None)
        with self.assertRaises(TypeError) as context:
            pe_sim.verify_wait_certificate("3")

        # tamper with the data
        d = wait_cert.duration
        lm = wait_cert.local_mean
        pc = wait_cert.previous_certificate_id
        s = wait_cert.signature

        wait_cert.duration = 1
        r = pe_sim.verify_wait_certificate(wait_cert)
        self.assertFalse(r)

        # Make sure we restored the data correctly
        wait_cert.duration = d
        r = pe_sim.verify_wait_certificate(wait_cert)
        self.assertTrue(r)

        wait_cert.local_mean = 1001
        r = pe_sim.verify_wait_certificate(wait_cert)
        self.assertFalse(r)

        # Make sure we restored the data correctly
        wait_cert.local_mean = lm
        r = pe_sim.verify_wait_certificate(wait_cert)
        self.assertTrue(r)

        wait_cert.previous_certificate_id = \
            random_name(pe_sim.IDENTIFIER_LENGTH)
        r = pe_sim.verify_wait_certificate(wait_cert)
        self.assertFalse(r)

        # Make sure we restored the data correctly
        wait_cert.previous_certificate_id = pc
        r = pe_sim.verify_wait_certificate(wait_cert)
        self.assertTrue(r)

        wait_cert.signature = random_name(len(wait_cert.signature))
        r = pe_sim.verify_wait_certificate(wait_cert)
        self.assertFalse(r)

        # Make sure we restored the data correctly
        wait_cert.signature = s
        r = pe_sim.verify_wait_certificate(wait_cert)
        self.assertTrue(r)


if __name__ == '__main__':
    unittest.main()

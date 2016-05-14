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


from journal.consensus.poet.wait_certificate import is_close
from journal.consensus.poet.poet_enclave_simulator \
    import poet_enclave_simulator as poet


class TestPoetEnclaveWaitCertificate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        args = {}
        poet.initialize(**args)

    def get_wait_timer(self):
        pid = random_name(poet.IDENTIFIER_LENGTH)

        # super short local mean to get small duration..
        wait_timer = poet.create_wait_timer(pid, 1)

        while not wait_timer.is_expired():
            time.sleep(1)

        return wait_timer

    def get_wait_cert(self):
        wait_timer = self.get_wait_timer()
        return poet.create_wait_certificate(wait_timer)

    def test_create(self):
        # with expired timer -- positive case
        wait_timer = self.get_wait_timer()
        wait_cert = poet.create_wait_certificate(wait_timer)
        self.assertEqual(wait_timer.duration, wait_cert.duration)
        self.assertEqual(wait_timer.local_mean, wait_cert.local_mean)
        self.assertEqual(wait_timer.previous_certificate_id,
                         wait_cert.previous_certificate_id)
        self.assertEquals(len(wait_cert.identifier()),
                          poet.IDENTIFIER_LENGTH)

        # the initial block does not need to wait, to accelerate
        # validator launch
        wait_timer = poet.create_wait_timer(poet.NULL_IDENTIFIER, 1)
        wait_cert = poet.create_wait_certificate(wait_timer)
        self.assertEqual(wait_timer.duration, wait_cert.duration)
        self.assertEqual(wait_timer.local_mean, wait_cert.local_mean)
        self.assertEqual(wait_timer.previous_certificate_id,
                         wait_cert.previous_certificate_id)

        # with unexpired timer
        wait_timer = poet.create_wait_timer(
            random_name(poet.IDENTIFIER_LENGTH), 1)
        wait_cert = poet.create_wait_certificate(wait_timer)

        # with tampered timer
        wait_timer = poet.create_wait_timer(
            random_name(poet.IDENTIFIER_LENGTH), 1)
        wait_timer.duration = 1
        wait_cert = poet.create_wait_certificate(wait_timer)
        self.assertIsNone(wait_cert)

        wait_timer = poet.create_wait_timer(
            random_name(poet.IDENTIFIER_LENGTH), 1)
        wait_timer.local_mean = 1
        wait_cert = poet.create_wait_certificate(wait_timer)
        self.assertIsNone(wait_cert)

        wait_timer = poet.create_wait_timer(
            random_name(poet.IDENTIFIER_LENGTH), 1)
        wait_timer.previous_certificate_id = \
            random_name(poet.IDENTIFIER_LENGTH)
        wait_cert = poet.create_wait_certificate(wait_timer)
        self.assertIsNone(wait_cert)

    def test_serialize(self):
        wait_cert = self.get_wait_cert()
        serialized_wait_cert = wait_cert.serialize()

        wait_cert2 = poet.deserialize_wait_certificate(
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
            wait_cert2 = poet.deserialize_wait_certificate(
                None,
                wait_cert.signature)
        with self.assertRaises(TypeError) as context:
            wait_cert2 = poet.deserialize_wait_certificate(
                [],
                wait_cert.signature)
        with self.assertRaises(TypeError) as context:
            wait_cert2 = poet.deserialize_wait_certificate(
                8,
                wait_cert.signature)
        with self.assertRaises(ValueError) as context:
            wait_cert2 = poet.deserialize_wait_certificate(
                random_name(len(serialized_wait_cert)),
                wait_cert.signature)
        with self.assertRaises(ValueError) as context:
            wait_cert2 = poet.deserialize_wait_certificate(
                serialized_wait_cert[:len(serialized_wait_cert) / 2],
                wait_cert.signature)

        # Bad Types
        with self.assertRaises(TypeError) as context:
            wait_cert2 = poet.deserialize_wait_certificate(
                serialized_wait_cert,
                None)
        with self.assertRaises(TypeError) as context:
            wait_cert2 = poet.deserialize_wait_certificate(
                serialized_wait_cert,
                [])
        with self.assertRaises(ValueError) as context:
            wait_cert2 = poet.deserialize_wait_certificate(
                serialized_wait_cert,
                "")
        with self.assertRaises(TypeError) as context:
            wait_cert2 = poet.deserialize_wait_certificate(
                serialized_wait_cert,
                7)
        with self.assertRaises(ValueError) as context:
            wait_cert2 = poet.deserialize_wait_certificate(
                serialized_wait_cert,
                random_name(len(wait_cert.signature)))

        with self.assertRaises(TypeError) as context:
            wait_cert2 = poet.deserialize_wait_certificate(
                8,
                wait_cert.signature)

        # tampered data
        wait_cert = self.get_wait_cert()
        wait_cert.duration = 2
        serialized_wait_cert = wait_cert.serialize()
        with self.assertRaises(ValueError) as context:
            wait_cert2 = poet.deserialize_wait_certificate(
                serialized_wait_cert,
                wait_cert.signature)

        wait_cert = self.get_wait_cert()
        wait_cert.request_time = 2
        serialized_wait_cert = wait_cert.serialize()
        with self.assertRaises(ValueError) as context:
            wait_cert2 = poet.deserialize_wait_certificate(
                serialized_wait_cert,
                wait_cert.signature)

        wait_cert = self.get_wait_cert()
        wait_cert.previous_certificate_id = random_name(
            len(poet.NULL_IDENTIFIER))
        serialized_wait_cert = wait_cert.serialize()
        with self.assertRaises(ValueError) as context:
            wait_cert2 = poet.deserialize_wait_certificate(
                serialized_wait_cert,
                wait_cert.signature)

    def test_verify(self):
        wait_cert = self.get_wait_cert()
        poet.verify_wait_certificate(wait_cert)

        with self.assertRaises(TypeError) as context:
            r = poet.verify_wait_certificate([])
            self.assertFalse(r)
        with self.assertRaises(ValueError) as context:
            poet.verify_wait_certificate(None)
        with self.assertRaises(TypeError) as context:
            poet.verify_wait_certificate("3")

        # tamper with the data
        d = wait_cert.duration
        lm = wait_cert.local_mean
        pc = wait_cert.previous_certificate_id
        s = wait_cert.signature

        wait_cert.duration = 1
        r = poet.verify_wait_certificate(wait_cert)
        self.assertFalse(r)

        # Make sure we restored the data correctly
        wait_cert.duration = d
        r = poet.verify_wait_certificate(wait_cert)
        self.assertTrue(r)

        wait_cert.local_mean = 1001
        r = poet.verify_wait_certificate(wait_cert)
        self.assertFalse(r)

        # Make sure we restored the data correctly
        wait_cert.local_mean = lm
        r = poet.verify_wait_certificate(wait_cert)
        self.assertTrue(r)

        wait_cert.previous_certificate_id = \
            random_name(poet.IDENTIFIER_LENGTH)
        r = poet.verify_wait_certificate(wait_cert)
        self.assertFalse(r)

        # Make sure we restored the data correctly
        wait_cert.previous_certificate_id = pc
        r = poet.verify_wait_certificate(wait_cert)
        self.assertTrue(r)

        wait_cert.signature = random_name(len(wait_cert.signature))
        r = poet.verify_wait_certificate(wait_cert)
        self.assertFalse(r)

        # Make sure we restored the data correctly
        wait_cert.signature = s
        r = poet.verify_wait_certificate(wait_cert)
        self.assertTrue(r)


if __name__ == '__main__':
    unittest.main()

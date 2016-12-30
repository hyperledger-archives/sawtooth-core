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


class TestPoetEnclaveWaitTimer(unittest.TestCase):
    def test_create(self):
        addr = random_name(20)
        previous_cert_id = pe_sim.NULL_IDENTIFIER
        wait_timer = pe_sim.create_wait_timer(addr, previous_cert_id, 100)
        self.assertEqual(wait_timer.previous_certificate_id, previous_cert_id)
        self.assertEqual(wait_timer.local_mean, 100)

        # Random previous cert id
        previous_cert_id = random_name(pe_sim.IDENTIFIER_LENGTH)

        # Bad local means
        with self.assertRaises(TypeError) as context:
            wait_timer = pe_sim.create_wait_timer([], previous_cert_id, 100)
        with self.assertRaises(TypeError) as context:
            wait_timer = pe_sim.create_wait_timer({}, previous_cert_id, 100)
        with self.assertRaises(TypeError) as context:
            wait_timer = pe_sim.create_wait_timer(None, previous_cert_id, 100)
        with self.assertRaises(TypeError) as context:
            wait_timer = pe_sim.create_wait_timer(8888, previous_cert_id, 100)

        # Bad local means
        with self.assertRaises(ValueError) as context:
            wait_timer = pe_sim.create_wait_timer(addr, previous_cert_id, -1)
        with self.assertRaises(ValueError) as context:
            wait_timer = pe_sim.create_wait_timer(addr, previous_cert_id, 0)
        with self.assertRaises(TypeError) as context:
            wait_timer = pe_sim.create_wait_timer(addr, previous_cert_id, [])
        with self.assertRaises(TypeError) as context:
            wait_timer = pe_sim.create_wait_timer(addr, previous_cert_id, None)
        with self.assertRaises(TypeError) as context:
            wait_timer = pe_sim.create_wait_timer(addr, previous_cert_id, "3")

        # Bad previous cert len
        with self.assertRaises(TypeError) as context:
            wait_timer = pe_sim.create_wait_timer(addr, None, 0)

        previous_cert_id = ""  # to short
        with self.assertRaises(ValueError) as context:
            wait_timer = pe_sim.create_wait_timer(addr, previous_cert_id, 100)

        previous_cert_id = random_name(8)  # to short
        with self.assertRaises(ValueError) as context:
            wait_timer = pe_sim.create_wait_timer(addr, previous_cert_id, 100)

        previous_cert_id = random_name(17)  # to long
        with self.assertRaises(ValueError) as context:
            wait_timer = pe_sim.create_wait_timer(addr, previous_cert_id, 100)

    def test_is_expired(self):
        addr = random_name(20)
        previous_cert_id = pe_sim.NULL_IDENTIFIER
        wait_timer = pe_sim.create_wait_timer(addr, previous_cert_id, 5)
        start = time.time()
        while not wait_timer.is_expired():
            time.sleep(1)
        end = time.time()
        self.assertLessEqual(wait_timer.duration, end - start)

        # we could tamper with the data to get it to register
        # is_expired sooner, but that will cause the validation to fail
        # as showing in the test_serialize tampered data tests below.

    def test_serialize(self):
        addr = random_name(20)
        previous_cert_id = pe_sim.NULL_IDENTIFIER
        wait_timer = pe_sim.create_wait_timer(addr, previous_cert_id, 5)
        serialized_wait_timer = wait_timer.serialize()

        wait_timer2 = pe_sim.deserialize_wait_timer(
            serialized_wait_timer,
            wait_timer.signature)

        self.assertTrue(is_close(
            wait_timer.duration,
            wait_timer2.duration,
            rel_tol=0.0001))
        self.assertEqual(wait_timer.request_time, wait_timer2.request_time)
        self.assertEqual(wait_timer.previous_certificate_id,
                         wait_timer2.previous_certificate_id)
        self.assertEqual(wait_timer.signature, wait_timer2.signature)

        # Bad Serial strings
        with self.assertRaises(TypeError) as context:
            wait_timer2 = pe_sim.deserialize_wait_timer(
                None,
                wait_timer.signature)
        with self.assertRaises(TypeError) as context:
            wait_timer2 = pe_sim.deserialize_wait_timer([],
                                                        wait_timer.signature)
        with self.assertRaises(TypeError) as context:
            wait_timer2 = pe_sim.deserialize_wait_timer(8,
                                                        wait_timer.signature)
        with self.assertRaises(ValueError) as context:
            wait_timer2 = pe_sim.deserialize_wait_timer(
                random_name(len(serialized_wait_timer)),
                wait_timer.signature)
        with self.assertRaises(ValueError) as context:
            wait_timer2 = pe_sim.deserialize_wait_timer(
                serialized_wait_timer[:len(serialized_wait_timer) / 2],
                wait_timer.signature)

        # Bad Types
        with self.assertRaises(TypeError) as context:
            wait_timer2 = pe_sim.deserialize_wait_timer(serialized_wait_timer,
                                                        None)
        with self.assertRaises(TypeError) as context:
            wait_timer2 = pe_sim.deserialize_wait_timer(serialized_wait_timer,
                                                        [])
        with self.assertRaises(ValueError) as context:
            wait_timer2 = pe_sim.deserialize_wait_timer(
                serialized_wait_timer, "")
        with self.assertRaises(TypeError) as context:
            wait_timer2 = pe_sim.deserialize_wait_timer(
                serialized_wait_timer, 7)
        with self.assertRaises(ValueError) as context:
            wait_timer2 = pe_sim.deserialize_wait_timer(
                serialized_wait_timer,
                random_name(len(wait_timer.signature)))

        with self.assertRaises(TypeError) as context:
            wait_timer2 = pe_sim.deserialize_wait_timer(8,
                                                        wait_timer.signature)

    def test_serialize_2(self):

        addr = random_name(20)
        previous_cert_id = pe_sim.NULL_IDENTIFIER
        wait_timer = pe_sim.create_wait_timer(addr, previous_cert_id, 5)
        serialized_wait_timer = wait_timer.serialize()
        wait_timer2 = pe_sim.deserialize_wait_timer(
            serialized_wait_timer,
            wait_timer.signature)

        # tampered data
        wait_timer = pe_sim.create_wait_timer(addr, previous_cert_id, 5)
        wait_timer.duration = 2
        serialized_wait_timer = wait_timer.serialize()
        with self.assertRaises(ValueError) as context:
            wait_timer2 = pe_sim.deserialize_wait_timer(serialized_wait_timer,
                                                        wait_timer.signature)

        wait_timer = pe_sim.create_wait_timer(addr, previous_cert_id, 5)
        wait_timer.request_time = 2
        serialized_wait_timer = wait_timer.serialize()
        with self.assertRaises(ValueError) as context:
            wait_timer2 = pe_sim.deserialize_wait_timer(serialized_wait_timer,
                                                        wait_timer.signature)

        wait_timer = pe_sim.create_wait_timer(addr, previous_cert_id, 5)
        wait_timer.previous_certificate_id = random_name(
            len(pe_sim.NULL_IDENTIFIER))
        serialized_wait_timer = wait_timer.serialize()
        with self.assertRaises(ValueError) as context:
            wait_timer2 = pe_sim.deserialize_wait_timer(serialized_wait_timer,
                                                        wait_timer.signature)

        wait_timer = pe_sim.create_wait_timer(addr, previous_cert_id, 5)
        wait_timer.validator_address = random_name(20)
        serialized_wait_timer = wait_timer.serialize()
        with self.assertRaises(ValueError) as context:
            wait_timer2 = pe_sim.deserialize_wait_timer(serialized_wait_timer,
                                                        wait_timer.signature)

if __name__ == '__main__':
    unittest.main()

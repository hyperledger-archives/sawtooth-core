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


from utils import generate_certs, random_name

from journal.consensus.poet.wait_timer import WaitTimer
from journal.consensus.poet.poet_enclave_simulator \
    import poet_enclave_simulator as poet


class TestPoetWaitTimer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        args = {}
        poet.initialize(**args)
        WaitTimer.poet_enclave = poet

    def test_create_wait_timer(self):
        certs = []
        # invalid list
        with self.assertRaises(TypeError) as context:
            WaitTimer.create_wait_timer(None, certs)
        with self.assertRaises(TypeError) as context:
            WaitTimer.create_wait_timer([], certs)
        with self.assertRaises(TypeError) as context:
            WaitTimer.create_wait_timer({}, certs)
        with self.assertRaises(TypeError) as context:
            WaitTimer.create_wait_timer(555, certs)

        addr = random_name(20)
        # invalid list
        with self.assertRaises(TypeError) as context:
            WaitTimer.create_wait_timer(addr, None)
        with self.assertRaises(TypeError) as context:
            WaitTimer.create_wait_timer(addr, "")
        with self.assertRaises(TypeError) as context:
            WaitTimer.create_wait_timer(addr, "XYZZY")
        with self.assertRaises(TypeError) as context:
            WaitTimer.create_wait_timer(addr, 555)

        certs = []  # empty list
        wait_timer = WaitTimer.create_wait_timer(addr, certs)
        # this will only catch changes in behavior of local mean calc
        self.assertEqual(wait_timer.local_mean, 30)

        certs = generate_certs(WaitTimer.fixed_duration_blocks - 1)
        wait_timer = WaitTimer.create_wait_timer(addr, certs)
        # this will only catch changes in behavior of local mean calc
        # based on the existing defaults...
        self.assertEqual(wait_timer.local_mean, 2882.388)

        certs = generate_certs(WaitTimer.fixed_duration_blocks)
        wait_timer = WaitTimer.create_wait_timer(addr, certs)
        self.assertEqual(wait_timer.local_mean, 30)

    def test_compute_local_mean(self):
        with self.assertRaises(TypeError) as context:
            local_mean = WaitTimer.compute_local_mean(None)

        with self.assertRaises(TypeError) as context:
            local_mean = WaitTimer.compute_local_mean("")
        with self.assertRaises(TypeError) as context:
            local_mean = WaitTimer.compute_local_mean("XYZZY")
        with self.assertRaises(TypeError) as context:
            local_mean = WaitTimer.compute_local_mean(555)

        certs = []
        local_mean = WaitTimer.compute_local_mean(certs)
        self.assertEqual(local_mean, 30)

    def test_population_estimate(self):
        with self.assertRaises(TypeError) as context:
            pop_est = WaitTimer.population_estimate(None)
        with self.assertRaises(TypeError) as context:
            pop_est = WaitTimer.population_estimate("")
        with self.assertRaises(TypeError) as context:
            pop_est = WaitTimer.population_estimate("XYZZY")
        with self.assertRaises(TypeError) as context:
            pop_est = WaitTimer.population_estimate(555)

        certs = []
        with self.assertRaises(ValueError) as context:
            pop_est = WaitTimer.population_estimate(certs)

        # ultra simple test for expected value
        certs = generate_certs(WaitTimer.certificate_sample_length)
        pop_est = WaitTimer.population_estimate(certs)
        self.assertEqual(pop_est, 1)

    def test_is_expired(self):
        default_target_wait_time = WaitTimer.target_wait_time
        WaitTimer.target_wait_time = 1

        # normal case
        addr = random_name(20)
        certs = generate_certs(WaitTimer.certificate_sample_length)
        wait_timer = WaitTimer.create_wait_timer(addr, certs)
        start = time.time()
        while not wait_timer.is_expired(time.time()):
            time.sleep(1)
        end = time.time()

        self.assertLessEqual(wait_timer.duration, end - start)
        # tamper with duration
        wait_timer = WaitTimer.create_wait_timer(addr, certs)
        d = wait_timer.duration
        wait_timer.duration = 1

        start = time.time()
        while not wait_timer.is_expired(time.time()):
            time.sleep(1)
        end = time.time()

        self.assertLessEqual(d, end - start)

        # tamper with request_time
        wait_timer = WaitTimer.create_wait_timer(addr, certs)
        wait_timer.request_time = time.time() - wait_timer.duration
        while not wait_timer.is_expired(time.time()):
            time.sleep(1)
        end = time.time()

        self.assertLessEqual(wait_timer.duration, end - start)
        # restore default target_wait_time
        WaitTimer.target_wait_time = default_target_wait_time


if __name__ == '__main__':
    unittest.main()

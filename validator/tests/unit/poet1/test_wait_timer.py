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
import hashlib

import pybitcointools
import journal.consensus.poet1.wait_timer as wait_timer
import journal.consensus.poet1.poet_enclave_simulator.poet_enclave_simulator \
    as poet_enclave

from journal.consensus.poet1.signup_info import SignupInfo
from gossip.common import NullIdentifier


class TestWaitTimer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Reload the wait timer module to clear any changed global state
        reload(wait_timer)

        cls._originator_public_key = cls._create_random_public_key()
        cls._originator_public_key_hash = \
            hashlib.sha256(
                pybitcointools.encode_pubkey(
                    cls._originator_public_key,
                    'hex')).hexdigest()

    @classmethod
    def _create_random_private_key(cls):
        return pybitcointools.random_key()

    @classmethod
    def _create_random_public_key(cls):
        return pybitcointools.privtopub(cls._create_random_private_key())

    def setUp(self):
        # This is a little ham-handed, but we need to ensure that the
        # PoET enclave is set back to initial state at the start of every
        # test.
        SignupInfo.poet_enclave = reload(poet_enclave)
        wait_timer.WaitTimer.poet_enclave = poet_enclave

        args = {"NodeName": "DasValidator"}
        SignupInfo.poet_enclave.initialize(**args)

    def test_create_wait_timer_with_invalid_certificate_list(self):
        # Make sure that invalid certificate lists cause error
        with self.assertRaises(TypeError):
            wait_timer.WaitTimer.create_wait_timer(None)

        with self.assertRaises(TypeError):
            wait_timer.WaitTimer.create_wait_timer(dict())

        with self.assertRaises(TypeError):
            wait_timer.WaitTimer.create_wait_timer(1)

        with self.assertRaises(TypeError):
            wait_timer.WaitTimer.create_wait_timer(1.0)

        with self.assertRaises(TypeError):
            wait_timer.WaitTimer.create_wait_timer('Not a valid list')

    def test_create_wait_timer_before_create_signup_info(self):
        # Make sure that trying to create a wait timer before signup
        # information is provided causes an error
        with self.assertRaises(wait_timer.WaitTimerError):
            wait_timer.WaitTimer.create_wait_timer([])

        with self.assertRaises(wait_timer.WaitTimerError):
            wait_timer.WaitTimer.create_wait_timer(tuple())

    def test_create_wait_timer(self):
        # Need to create signup information first
        signup_info = \
            SignupInfo.create_signup_info(
                originator_public_key_hash=self._originator_public_key_hash,
                most_recent_wait_certificate_id=NullIdentifier)

        stake_in_the_sand = time.time()

        # An empty certificate list should result in a local mean that is
        # the target wait time
        wt = wait_timer.WaitTimer.create_wait_timer([])

        self.assertIsNotNone(wt)
        self.assertEqual(wt.local_mean, wait_timer.WaitTimer.target_wait_time)
        self.assertEquals(wt.previous_certificate_id, NullIdentifier)
        self.assertGreaterEqual(wt.request_time, stake_in_the_sand)
        self.assertLessEqual(wt.request_time, time.time())
        self.assertGreaterEqual(
            wt.duration,
            wait_timer.WaitTimer.minimum_wait_time)

        wt = wait_timer.WaitTimer.create_wait_timer(tuple())

        self.assertIsNotNone(wt)
        self.assertEqual(wt.local_mean, wait_timer.WaitTimer.target_wait_time)
        self.assertEquals(wt.previous_certificate_id, NullIdentifier)
        self.assertGreaterEqual(wt.request_time, stake_in_the_sand)
        self.assertLessEqual(wt.request_time, time.time())
        self.assertGreaterEqual(
            wt.duration,
            wait_timer.WaitTimer.minimum_wait_time)

        # Ensure that the enclave is set back to initial state
        SignupInfo.poet_enclave = reload(poet_enclave)
        wait_timer.WaitTimer.poet_enclave = SignupInfo.poet_enclave

        # Make sure that trying to create a wait timer before signup
        # information is provided causes an error
        with self.assertRaises(wait_timer.WaitTimerError):
            wait_timer.WaitTimer.create_wait_timer([])

        with self.assertRaises(wait_timer.WaitTimerError):
            wait_timer.WaitTimer.create_wait_timer(tuple())

        # Initialize the enclave with sealed signup data
        SignupInfo.unseal_signup_data(signup_info.sealed_signup_data)

        stake_in_the_sand = time.time()

        # An empty certificate list should result in a local mean that is
        # the target wait time
        wt = wait_timer.WaitTimer.create_wait_timer([])

        self.assertIsNotNone(wt)
        self.assertEqual(wt.local_mean, wait_timer.WaitTimer.target_wait_time)
        self.assertEquals(wt.previous_certificate_id, NullIdentifier)
        self.assertGreaterEqual(wt.request_time, stake_in_the_sand)
        self.assertLessEqual(wt.request_time, time.time())
        self.assertGreaterEqual(
            wt.duration,
            wait_timer.WaitTimer.minimum_wait_time)

        wt = wait_timer.WaitTimer.create_wait_timer(tuple())

        self.assertIsNotNone(wt)
        self.assertEqual(wt.local_mean, wait_timer.WaitTimer.target_wait_time)
        self.assertEquals(wt.previous_certificate_id, NullIdentifier)
        self.assertGreaterEqual(wt.request_time, stake_in_the_sand)
        self.assertLessEqual(wt.request_time, time.time())
        self.assertGreaterEqual(
            wt.duration,
            wait_timer.WaitTimer.minimum_wait_time)

    def test_compute_local_mean(self):
        # Make sure that invalid certificate lists cause error
        with self.assertRaises(TypeError) as context:
            wait_timer.WaitTimer.compute_local_mean(None)

        with self.assertRaises(TypeError) as context:
            wait_timer.WaitTimer.compute_local_mean(dict())

        with self.assertRaises(TypeError) as context:
            wait_timer.WaitTimer.compute_local_mean(1)

        with self.assertRaises(TypeError) as context:
            wait_timer.WaitTimer.compute_local_mean(1.0)

        with self.assertRaises(TypeError) as context:
            wait_timer.WaitTimer.compute_local_mean("Not a valid list")

        # Ensure that an empty certificate list results in a local mean that is
        # the target wait time
        local_mean = wait_timer.WaitTimer.compute_local_mean([])
        self.assertEqual(local_mean, wait_timer.WaitTimer.target_wait_time)

        local_mean = wait_timer.WaitTimer.compute_local_mean(tuple())
        self.assertEqual(local_mean, wait_timer.WaitTimer.target_wait_time)

    def test_has_expired(self):
        # Need to create signup information first
        SignupInfo.create_signup_info(
            originator_public_key_hash=self._originator_public_key_hash,
            most_recent_wait_certificate_id=NullIdentifier)

        # Verify that a timer doesn't expire before its creation time
        wt = wait_timer.WaitTimer.create_wait_timer([])
        self.assertFalse(wt.has_expired(wt.request_time - 1))

        # Create a timer and when it has expired, verify that the duration is
        # not greater than actual elapsed time.
        wt = wait_timer.WaitTimer.create_wait_timer([])

        while not wt.has_expired(time.time()):
            time.sleep(1)

        self.assertLessEqual(wt.duration, time.time() - wt.request_time)

        # Tampering with the duration should not affect wait timer expiration
        wt = wait_timer.WaitTimer.create_wait_timer([])

        assigned_duration = wt.duration
        wt.duration = 0

        while not wt.has_expired(time.time()):
            time.sleep(1)

        self.assertLessEqual(assigned_duration, time.time() - wt.request_time)

        # Tampering with the request time should not affect wait timer
        # expiration
        wt = wait_timer.WaitTimer.create_wait_timer([])
        assigned_request_time = wt.request_time
        wt.request_time -= wt.duration

        while not wt.has_expired(time.time()):
            time.sleep(1)

        self.assertLessEqual(wt.duration, time.time() - assigned_request_time)

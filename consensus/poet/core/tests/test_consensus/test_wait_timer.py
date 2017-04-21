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

from importlib import reload
import time
from unittest import TestCase
from unittest import mock
from unittest import skip

import sawtooth_poet_simulator.poet_enclave_simulator.poet_enclave_simulator \
    as poet_enclave

from sawtooth_poet.poet_consensus.consensus_state import ConsensusState
import sawtooth_poet.poet_consensus.wait_timer as wait_timer

from sawtooth_poet.poet_consensus.signup_info import SignupInfo

from sawtooth_validator.journal.block_wrapper import NULL_BLOCK_IDENTIFIER

from test_consensus.utils import create_random_public_key_hash


class TestWaitTimer(TestCase):
    @classmethod
    def setUpClass(cls):
        # Reload the wait timer module to clear any changed global state
        reload(wait_timer)

        cls._originator_public_key_hash = create_random_public_key_hash()

    def setUp(self):
        # This is a little ham-handed, but we need to ensure that the
        # PoET enclave is set back to initial state at the start of every
        # test.
        self.poet_enclave_module = reload(poet_enclave)

        args = {"NodeName": "DasValidator"}
        self.poet_enclave_module.initialize(**args)

        self.mock_poet_config_view = mock.Mock()
        self.mock_poet_config_view.target_wait_time = 5.0
        self.mock_poet_config_view.initial_wait_time = 0.0
        self.mock_poet_config_view.minimum_wait_time = 1.0
        self.mock_poet_config_view.population_estimate_sample_size = 50

        self.consensus_state = ConsensusState()

    def test_create_before_create_signup_info(self):
        # Make sure that trying to create a wait timer before signup
        # information is provided causes an error
        with self.assertRaises(ValueError):
            wait_timer.WaitTimer.create_wait_timer(
                poet_enclave_module=self.poet_enclave_module,
                validator_address='1060 W Addison Street',
                previous_certificate_id=NULL_BLOCK_IDENTIFIER,
                consensus_state=self.consensus_state,
                poet_config_view=self.mock_poet_config_view)

    def test_create(self):
        # Need to create signup information first
        signup_info = \
            SignupInfo.create_signup_info(
                poet_enclave_module=self.poet_enclave_module,
                validator_address='1060 W Addison Street',
                originator_public_key_hash=self._originator_public_key_hash,
                most_recent_wait_certificate_id=NULL_BLOCK_IDENTIFIER)

        stake_in_the_sand = time.time()

        # An empty certificate list should result in a local mean that is
        # the target wait time
        wt = wait_timer.WaitTimer.create_wait_timer(
            poet_enclave_module=self.poet_enclave_module,
            validator_address='1060 W Addison Street',
            previous_certificate_id=NULL_BLOCK_IDENTIFIER,
            consensus_state=self.consensus_state,
            poet_config_view=self.mock_poet_config_view)

        self.assertIsNotNone(wt)
        self.assertEqual(
            wt.local_mean,
            self.mock_poet_config_view.target_wait_time)
        self.assertEqual(wt.previous_certificate_id, NULL_BLOCK_IDENTIFIER)
        self.assertGreaterEqual(wt.request_time, stake_in_the_sand)
        self.assertLessEqual(wt.request_time, time.time())
        self.assertGreaterEqual(
            wt.duration,
            self.mock_poet_config_view.minimum_wait_time)
        self.assertEqual(wt.validator_address, '1060 W Addison Street')

        # Ensure that the enclave is set back to initial state
        self.poet_enclave_module = reload(poet_enclave)

        # Make sure that trying to create a wait timer before signup
        # information is provided causes an error
        with self.assertRaises(ValueError):
            wait_timer.WaitTimer.create_wait_timer(
                poet_enclave_module=self.poet_enclave_module,
                validator_address='1060 W Addison Street',
                previous_certificate_id=NULL_BLOCK_IDENTIFIER,
                consensus_state=self.consensus_state,
                poet_config_view=self.mock_poet_config_view)

        # Initialize the enclave with sealed signup data
        SignupInfo.unseal_signup_data(
            poet_enclave_module=self.poet_enclave_module,
            validator_address='1660 Pennsylvania Avenue NW',
            sealed_signup_data=signup_info.sealed_signup_data)

        stake_in_the_sand = time.time()

        # An empty certificate list should result in a local mean that is
        # the target wait time
        wt = wait_timer.WaitTimer.create_wait_timer(
            poet_enclave_module=self.poet_enclave_module,
            validator_address='1060 W Addison Street',
            previous_certificate_id=NULL_BLOCK_IDENTIFIER,
            consensus_state=self.consensus_state,
            poet_config_view=self.mock_poet_config_view)

        self.assertIsNotNone(wt)
        self.assertEqual(
            wt.local_mean,
            self.mock_poet_config_view.target_wait_time)
        self.assertEqual(wt.previous_certificate_id, NULL_BLOCK_IDENTIFIER)
        self.assertGreaterEqual(wt.request_time, stake_in_the_sand)
        self.assertLessEqual(wt.request_time, time.time())
        self.assertGreaterEqual(
            wt.duration,
            self.mock_poet_config_view.minimum_wait_time)
        self.assertEqual(wt.validator_address, '1060 W Addison Street')

    @skip("Disabled until poet integration -- too slow!!!!!")
    def test_has_expired(self):
        # Need to create signup information first
        SignupInfo.create_signup_info(
            poet_enclave_module=self.poet_enclave_module,
            validator_address='1660 Pennsylvania Avenue NW',
            originator_public_key_hash=self._originator_public_key_hash,
            most_recent_wait_certificate_id=NULL_BLOCK_IDENTIFIER)

        # Verify that a timer doesn't expire before its creation time
        wt = wait_timer.WaitTimer.create_wait_timer(
            poet_enclave_module=self.poet_enclave_module,
            validator_address='1060 W Addison Street',
            previous_certificate_id=NULL_BLOCK_IDENTIFIER,
            consensus_state=self.consensus_state,
            poet_config_view=self.mock_poet_config_view)
        self.assertFalse(wt.has_expired(wt.request_time - 1))

        # Create a timer and when it has expired, verify that the duration is
        # not greater than actual elapsed time.
        wt = wait_timer.WaitTimer.create_wait_timer(
            poet_enclave_module=self.poet_enclave_module,
            validator_address='1060 W Addison Street',
            previous_certificate_id=NULL_BLOCK_IDENTIFIER,
            consensus_state=self.consensus_state,
            poet_config_view=self.mock_poet_config_view)

        while not wt.has_expired(time.time()):
            time.sleep(1)

        self.assertLessEqual(wt.duration, time.time() - wt.request_time)

        # Tampering with the duration should not affect wait timer expiration
        wt = wait_timer.WaitTimer.create_wait_timer(
            poet_enclave_module=self.poet_enclave_module,
            validator_address='1060 W Addison Street',
            previous_certificate_id=NULL_BLOCK_IDENTIFIER,
            consensus_state=self.consensus_state,
            poet_config_view=self.mock_poet_config_view)

        assigned_duration = wt.duration
        wt.duration = 0

        while not wt.has_expired(time.time()):
            time.sleep(1)

        self.assertLessEqual(assigned_duration, time.time() - wt.request_time)

        # Tampering with the request time should not affect wait timer
        # expiration
        wt = wait_timer.WaitTimer.create_wait_timer(
            poet_enclave_module=self.poet_enclave_module,
            validator_address='1060 W Addison Street',
            previous_certificate_id=NULL_BLOCK_IDENTIFIER,
            consensus_state=self.consensus_state,
            poet_config_view=self.mock_poet_config_view)
        assigned_request_time = wt.request_time
        wt.request_time -= wt.duration

        while not wt.has_expired(time.time()):
            time.sleep(1)

        self.assertLessEqual(wt.duration, time.time() - assigned_request_time)

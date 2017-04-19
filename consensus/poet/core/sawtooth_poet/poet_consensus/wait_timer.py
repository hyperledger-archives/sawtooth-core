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

import logging

LOGGER = logging.getLogger(__name__)


class WaitTimer(object):
    """Wait timers represent a random duration incorporated into a wait
    certificate.

    Attributes:
        previous_certificate_id (str): The id of the previous certificate.
        local_mean (float): The local mean wait time based on the history of
            certs.
        request_time (float): The request time.
        duration (float): The duration of the wait timer.
        validator_address (str): The address of the validator that created the
            wait timer
    """

    @classmethod
    def create_wait_timer(cls,
                          poet_enclave_module,
                          validator_address,
                          previous_certificate_id,
                          consensus_state,
                          poet_config_view):
        """Creates a wait timer in the enclave and then constructs
        a WaitTimer object.

        Args:
            poet_enclave_module (module): The module that implements the
                underlying PoET enclave.
            validator_address (str): A string representing the address of the
                validator creating the wait timer.
            previous_certificate_id (str): The ID of the wait certificate for
                the block attempting to build upon
            consensus_state (ConsensusState): The current PoET consensus state
            poet_config_view (PoetConfigView): The current PoET config view

        Returns:
            journal.consensus.poet.wait_timer.WaitTimer: A new wait timer.
        """

        # Create an enclave timer object and then use it to create a
        # WaitTimer object
        enclave_timer = \
            poet_enclave_module.create_wait_timer(
                validator_address,
                previous_certificate_id,
                consensus_state.compute_local_mean(
                    poet_config_view=poet_config_view),
                poet_config_view.minimum_wait_time)

        return cls(enclave_timer)

    @property
    def enclave_wait_timer(self):
        """Converts the serialized timer into an eclave timer object.

        Returns:
            <poet_enclave_module>.WaitTimer: The deserialized enclave timer
                object.
        """
        return self._enclave_wait_timer

    def __init__(self, enclave_timer):
        self.previous_certificate_id =\
            str(enclave_timer.previous_certificate_id)
        self.local_mean = float(enclave_timer.local_mean)
        self.request_time = float(enclave_timer.request_time)
        self.duration = float(enclave_timer.duration)
        self.validator_address = str(enclave_timer.validator_address)

        self._enclave_wait_timer = enclave_timer
        self._expires = self.request_time + self.duration + 0.1
        self._serialized_timer = None

    def __str__(self):
        return \
            'TIMER, {0:0.2f}, {1:0.2f}, {2}'.format(
                self.local_mean,
                self.duration,
                self.previous_certificate_id)

    def population_estimate(self, poet_config_view):
        """Return the population estimate for the block associated with this
        wait timer

        Args:
            poet_config_view (PoetConfigView): The current PoET config view

        Returns:
            float: The population estimate for this wait timer
        """
        return self.local_mean / poet_config_view.target_wait_time

    def serialize(self):
        """Serializes the underlying enclave wait timer
        """
        if self._serialized_timer is None:
            self._serialized_timer = self._enclave_wait_timer.serialize()

        return self._serialized_timer

    def has_expired(self, now):
        """Determines whether the timer has expired.

        Args:
            now (float): The current time.

        Returns:
            bool: True if the timer has expired, false otherwise.
        """
        if now < self._expires:
            return False

        return self._enclave_wait_timer.has_expired()

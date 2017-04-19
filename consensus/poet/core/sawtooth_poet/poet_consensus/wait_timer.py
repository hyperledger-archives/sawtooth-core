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
        WaitTimer.minimum_wait_time (float): The minimum wait time in seconds.
        WaitTimer.target_wait_time (float): The target wait time in seconds.
        WaitTimer.initial_wait_time (float): The initial wait time in seconds.
        WaitTimer.certificate_sample_length (int): The number of certificates
            to sample for the population estimate.
        WaitTimer.fixed_duration_blocks (int): If fewer than
            WaitTimer.fixed_duration_blocks exist, then base the local mean
            on a ratio based on InitialWaitTime, rather than the history.
        previous_certificate_id (str): The id of the previous certificate.
        local_mean (float): The local mean wait time based on the history of
            certs.
        request_time (float): The request time.
        duration (float): The duration of the wait timer.
        validator_address (str): The address of the validator that created the
            wait timer
    """
    minimum_wait_time = 1.0
    target_wait_time = 20.0
    initial_wait_time = 3000.0
    certificate_sample_length = 50
    fixed_duration_blocks = certificate_sample_length

    @classmethod
    def _compute_population_estimate(cls, certificates):
        """Estimates the size of the validator population by computing
        the average wait time and the average local mean used by
        the winning validator.

        Since the entire population should be computing from the same
        local mean based on history of certificates and we know that
        the minimum value drawn from a population of size N of
        exponentially distributed variables will be exponential with
        mean being 1 / N, we can estimate the population size from the
        ratio of local mean to global mean. a longer list of
        certificates will provide a better estimator only if the
        population of validators is relatively stable.

        Note:

        See the section entitled "Distribution of the minimum of
        exponential random variables" in the page
        http://en.wikipedia.org/wiki/Exponential_distribution

        Args:
            certificates (list): Previously committed certificates,
                ordered newest to oldest
        """
        assert isinstance(certificates, list)
        assert len(certificates) >= cls.certificate_sample_length

        sum_means = 0
        sum_waits = 0
        for certificate in certificates[:cls.certificate_sample_length]:
            sum_waits += certificate.duration - cls.minimum_wait_time
            sum_means += certificate.local_mean

        avg_wait = sum_waits / len(certificates)
        avg_mean = sum_means / len(certificates)

        return avg_mean / avg_wait

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

    @classmethod
    def compute_local_mean(cls, certificates):
        """Computes the local mean wait time based on the certificate
        history.

        Args:
            certificates (list or tuple): A historical list of certificates.

        Returns:
            float: The local mean wait time.
        """
        if not isinstance(certificates, (list, tuple)):
            raise TypeError

        count = len(certificates)
        if count < cls.fixed_duration_blocks:
            ratio = 1.0 * count / cls.fixed_duration_blocks
            local_mean = \
                (cls.target_wait_time * (1 - ratio**2)) + \
                (cls.initial_wait_time * ratio**2)
        else:
            local_mean = \
                cls.target_wait_time * \
                cls._compute_population_estimate(certificates)

        return local_mean

    @property
    def population_estimate(self):
        return self.local_mean / WaitTimer.target_wait_time

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


def set_wait_timer_globals(target_wait_time=None,
                           initial_wait_time=None,
                           certificate_sample_length=None,
                           fixed_duration_blocks=None,
                           minimum_wait_time=None):
    if target_wait_time is not None:
        WaitTimer.target_wait_time = float(target_wait_time)
    if initial_wait_time is not None:
        WaitTimer.initial_wait_time = float(initial_wait_time)
    if certificate_sample_length is not None:
        WaitTimer.certificate_sample_length = int(certificate_sample_length)
        WaitTimer.fixed_duration_blocks = int(certificate_sample_length)
    if fixed_duration_blocks is not None:
        WaitTimer.fixed_duration_blocks = int(fixed_duration_blocks)
    if minimum_wait_time is not None:
        WaitTimer.minimum_wait_time = float(minimum_wait_time)

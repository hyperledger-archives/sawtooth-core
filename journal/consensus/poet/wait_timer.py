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

import logging
import importlib

from journal.consensus.poet.poet_enclave_simulator \
    import poet_enclave_simulator

logger = logging.getLogger(__name__)


class WaitTimer(object):
    """Wait timers represent a random duration incorporated into a wait
    certificate.

    Attributes:
        minimum_wait_time (float): The minimum wait time in seconds.
        target_wait_time (float): The target wait time in seconds.
        initial_wait_time (float): The initial wait time in seconds.
        certificate_sample_length (int): The number of certificates to
            sample for the population estimate.
        fixed_duration_blocks (int): If fewer than FixedDurationBlocks
            exist, then base the local mean on a ratio based on
            InitialWaitTime, rather than the history.
        _poet_enclave (module): The PoetEnclave module to use for
            executing enclave functions.
        previous_certificate_id (str): The id of the previous certificate.
        local_mean (float): The local mean wait time based on the history
            of certs.
        request_time (float): The request time.
        duration (float): The duration of the wait timer.
        signature (str): The signature of the timer.
        serialized_timer (str): A serialized version of the timer.

    """
    target_wait_time = 30.0
    initial_wait_time = 3000.0
    certificate_sample_length = 50
    fixed_duration_blocks = certificate_sample_length

    _poet_enclave = poet_enclave_simulator
    try:
        _poet_enclave = importlib.import_module("poet_enclave.poet_enclave")
    except ImportError, e:
        pass

    @classmethod
    def create_wait_timer(cls, certs):
        """Creates a wait timer in the enclave and then constructs
        a WaitTimer object.

        Args:
            certs (list): A historical list of certificates.

        Returns:
            wait_timer.WaitTimer: A new wait timer.
        """
        previous_certificate_id = certs[-1].identifier if certs else \
            cls._poet_enclave.NULL_IDENTIFIER
        local_mean = cls.compute_local_mean(certs)
        timer = cls._poet_enclave.create_wait_timer(previous_certificate_id,
                                                    local_mean)

        wt = cls(timer)
        logger.info('wait timer created; %s', wt)

        return wt

    @classmethod
    def compute_local_mean(cls, certs):
        """Computes the local mean wait time based on the certificate
        history.

        Args:
            certs (list): A historical list of certificates.

        Returns:
            float: The local mean wait time.
        """
        count = len(certs)
        if count < cls.fixed_duration_blocks:
            ratio = 1.0 * count / cls.fixed_duration_blocks
            return cls.target_wait_time * (
                1 - ratio * ratio) + cls.initial_wait_time * ratio * ratio

        return cls.target_wait_time * cls.population_estimate(certs)

    @classmethod
    def population_estimate(cls, certificates):
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
        sum_means = 0
        sum_waits = 0
        for cert in certificates[:cls.certificate_sample_length]:
            sum_waits += cert.duration - cls._poet_enclave.MINIMUM_WAIT_TIME
            sum_means += cert.local_mean

        avg_wait = sum_waits / len(certificates)
        avg_mean = sum_means / len(certificates)

        return avg_mean / avg_wait

    def __init__(self, timer):
        """Constructor for the WaitTimer class.

        Args:
            timer (poet_enclave.WaitTimer): an enclave timer object

            timer.previous_certificate_id (str): The id of the previous
                certificate.
            timer.local_mean (float): The local mean wait time based on the
                history of certs.
            timer.request_time (float): The request time.
            timer.duration (float): The duration of the wait timer.
            timer.signature (str): The signature of the timer.
            timer.serialized_timer (str): A serialized version of the timer.
        """
        self.previous_certificate_id = timer.previous_certificate_id
        self.local_mean = timer.local_mean
        self.request_time = timer.request_time
        self.duration = timer.duration
        self.signature = timer.signature
        self.serialized_timer = timer.serialize()

    @property
    def enclave_wait_timer(self):
        """Converts the serialized timer into an object.

        Returns:
            poet_enclave.WaitTimer: The deserialized enclave timer
                object.
        """
        return self._poet_enclave.deserialize_wait_timer(self.serialized_timer,
                                                         self.signature)

    def __str__(self):
        return "TIMER, {0:0.2f}, {1:0.2f}, {2}".format(
            self.local_mean, self.duration, self.previous_certificate_id)

    def is_expired(self, now):
        """Determines whether the timer has expired.

        Args:
            now (float): The current time.

        Returns:
            bool: True if the timer has expired, false otherwise.
        """
        if now < (self.request_time + self.duration):
            return False

        return self.enclave_wait_timer.is_expired()

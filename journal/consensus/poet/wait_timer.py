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
import journal.consensus.poet.poet_enclave_simulator.poet_enclave_simulator \
    as PoetEnclaveSimulator

logger = logging.getLogger(__name__)


class WaitTimer(object):
    """Wait timers represent a random duration incorporated into a wait
    certificate.

    Attributes:
        MinimumWaitTime (float): The minimum wait time in seconds.
        TargetWaitTime (float): The target wait time in seconds.
        InitialWaitTime (float): The initial wait time in seconds.
        CertificateSampleLength (int): The number of certificates to
            sample for the population estimate.
        FixedDurationBlocks (int): If fewer than FixedDurationBlocks
            exist, then base the local mean on a ratio based on
            InitialWaitTime, rather than the history.
        PoetEnclave (module): The PoetEnclave module to use for
            executing enclave functions.
        PreviousCertID (str): The id of the previous certificate.
        LocalMean (float): The local mean wait time based on the history
            of certs.
        RequestTime (float): The request time.
        Duration (float): The duration of the wait timer.
        Signature (str): The signature of the timer.
        SerializedTimer (str): A serialized version of the timer.

    """
    MinimumWaitTime = 1.0
    TargetWaitTime = 30.0
    InitialWaitTime = 3000.0
    CertificateSampleLength = 50
    FixedDurationBlocks = CertificateSampleLength

    PoetEnclave = PoetEnclaveSimulator
    try:
        PoetEnclave = importlib.import_module("poet_enclave.poet_enclave")
    except ImportError, e:
        pass

    @classmethod
    def create_wait_timer(cls, certs):
        """Creates a wait timer in the enclave and then constructs
        a WaitTimer object.

        Args:
            certs (list): A historical list of certificates.

        Returns:
            WaitTimer: A new wait timer.
        """
        previd = certs[-1].Identifier if certs else \
            cls.PoetEnclave.NullIdentifier
        mean = cls.compute_local_mean(certs)
        timer = cls.PoetEnclave.create_wait_timer(previd, mean)

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
        if count < cls.FixedDurationBlocks:
            ratio = 1.0 * count / cls.FixedDurationBlocks
            return cls.TargetWaitTime * (
                1 - ratio * ratio) + cls.InitialWaitTime * ratio * ratio

        return cls.TargetWaitTime * cls.population_estimate(certs)

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
        summeans = 0
        sumwaits = 0
        for cert in certificates[:cls.CertificateSampleLength]:
            sumwaits += cert.Duration - cls.MinimumWaitTime
            summeans += cert.LocalMean

        avgwait = sumwaits / len(certificates)
        avgmean = summeans / len(certificates)

        return avgmean / avgwait

    def __init__(self, timer):
        """Constructor for the WaitTimer class.

        Args:
            PreviousCertID (str): The id of the previous certificate.
            LocalMean (float): The local mean wait time based on the
                history of certs.
            RequestTime (float): The request time.
            Duration (float): The duration of the wait timer.
            Signature (str): The signature of the timer.
            SerializedTimer (str): A serialized version of the timer.
        """
        self.PreviousCertID = timer.PreviousCertID
        self.LocalMean = timer.LocalMean
        self.RequestTime = timer.RequestTime
        self.Duration = timer.Duration
        self.Signature = timer.Signature
        self.SerializedTimer = timer.serialize()

    @property
    def EnclaveWaitTimer(self):
        """Converts the serialized timer into an object.

        Returns:
            poet_enclave.WaitTimer: The deserialized enclave timer
                object.
        """
        return self.PoetEnclave.DeserializeWaitTimer(self.SerializedTimer,
                                                     self.Signature)

    def __str__(self):
        return "TIMER, {0:0.2f}, {1:0.2f}, {2}".format(
            self.LocalMean, self.Duration, self.PreviousCertID)

    def is_expired(self, now):
        """Determines whether the timer has expired.

        Args:
            now (float): The current time.

        Returns:
            bool: True if the timer has expired, false otherwise.
        """
        if now < (self.RequestTime + self.Duration):
            return False

        return self.EnclaveWaitTimer.is_expired()

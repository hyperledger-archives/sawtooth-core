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
from journal.consensus.poet.wait_timer import WaitTimer

import journal.consensus.poet.poet_enclave_simulator.poet_enclave_simulator \
    as poet_enclave_simulator

logger = logging.getLogger(__name__)


# This is necessary for float comparisons
def is_close(a, b, rel_tol=1e-09, abs_tol=0.0):
    """Determines whether two floats are within a tolerance.

    Returns:
        bool: Returns True if the two floats are within a tolerance,
            False otherwise.
    """
    return abs(a - b) <= max(rel_tol * max(abs(a), abs(b)), abs_tol)


class WaitCertificate(object):
    """Represents wait certificates, which include a random wait timer.

    Attributes:
        _poet_enclave (module): The PoetEnclave module to use for executing
            enclave functions.
        previous_certificate_id (str): The id of the previous certificate.
        local_mean (float): The local mean wait time based on the history
            of certs.
        request_time (float): The request time of the certificate.
        duration (float): The duration of the wait timer.
        signature (str): The signature of the certificate.
        identifier (str): The identifier of this certificate.
        serialized_cert (str): A serialized version of the certificate.
    """
    _poet_enclave = poet_enclave_simulator
    try:
        _poet_enclave = importlib.import_module("poet_enclave.poet_enclave")
    except ImportError, e:
        pass

    @classmethod
    def create_wait_certificate(cls, timer):
        """Creates a wait certificate in the enclave and then constructs
        a WaitCertificate object.

        Args:
            timer (WaitTimer): The wait timer to use in creating the
                certificate.

        Returns:
            WaitCertificate: A new wait certificate.
        """
        cert = cls._poet_enclave.create_wait_certificate(
            timer.enclave_wait_timer)
        if not cert:
            logger.warn('invalid timer: %s', timer)
            raise Exception(
                'create_wait_certificate',
                'Attempt to create wait certificate from invalid wait timer')

        wc = cls(cert)
        logger.info('wait certificate created; %s', wc)

        return wc

    @classmethod
    def deserialize_wait_certificate(cls, serialized, signature):
        """Converts a serialized wait certificate into an object.

        Args:
            serialized (str): The serialized wait certificate.
            signature (str): The signature.

        Returns:
            WaitCertificate: A wait certificate representing the
                contents of the serialized wait certificate.
        """
        cert = cls._poet_enclave.deserialize_wait_certificate(
            serialized, signature)
        if cert.previous_certificate_id != cls._poet_enclave.NULL_IDENTIFIER:
            if not cls._poet_enclave.verify_wait_certificate(cert):
                raise Exception(
                    'WaitCertificateVerify',
                    'Attempt to deserialize an invalid wait certificate')

        return cls(cert)

    def __init__(self, cert):
        """Initialize the wait certificate.

        Args:
            cert (poet_enclave.WaitCertificate): The poet enclave
                generated wait certificate.
        """
        self.previous_certificate_id = cert.previous_certificate_id
        self.local_mean = cert.local_mean
        self.request_time = cert.request_time
        self.duration = cert.duration
        self.signature = cert.signature
        self.identifier = cert.identifier()

        # we cannot hold the certificate because it cannot be pickled for
        # storage in the transaction block array
        self.serialized_cert = cert.serialize()

    @property
    def enclave_wait_certificate(self):
        """Returns the enclave version of the wait certificate.

        Returns:
            poet_enclave.WaitCertificate: Enclave deserialized version
                of the certificate.
        """
        return self._poet_enclave.deserialize_wait_certificate(
            self.serialized_cert,
            self.signature)

    def is_valid_wait_certificate(self, certs):
        """Determines whether the wait certificate is valid.

        Args:
            certs (list): A list of historical certs.

        Returns:
            bool: Whether or not the wait certificate is valid.
        """
        cert = self.enclave_wait_certificate

        if cert.duration < self._poet_enclave.MINIMUM_WAIT_TIME:
            logger.warn('Wait time less then minimum: %s != %s',
                        cert.duration, self._poet_enclave.MINIMUM_WAIT_TIME)
            return False

        expected_mean = WaitTimer.compute_local_mean(certs)
        if not is_close(cert.local_mean, expected_mean, abs_tol=0.001):
            logger.warn('mismatch local mean: %s != %s', cert.local_mean,
                        expected_mean)
            return False

        if cert.previous_certificate_id == self._poet_enclave.NULL_IDENTIFIER:
            if len(certs) == 0:
                return True

        if cert.previous_certificate_id != certs[-1].identifier:
            logger.warn('mismatch previous identifier: %s != %s',
                        cert.previous_certificate_id, certs[-1].identifier)
            return False

        return self._poet_enclave.verify_wait_certificate(cert)

    def __str__(self):
        return "CERT, {0:0.2f}, {1:0.2f}, {2}, {3}".format(
            self.local_mean, self.duration, self.identifier,
            self.previous_certificate_id)

    def dump(self):
        """Returns a dict containing information about the wait
        certificate.

        Returns:
            dict: A dict containing info about the wait certificate.
        """
        result = {
            'SerializedCert': self.serialized_cert,
            'Signature': self.signature
        }
        return result

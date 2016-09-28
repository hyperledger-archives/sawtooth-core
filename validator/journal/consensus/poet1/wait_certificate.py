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
from requests import ConnectionError
from requests import Timeout

from sawtooth.exceptions import NotAvailableException
from gossip.common import NullIdentifier
from journal.consensus.poet1.wait_timer import WaitTimer

LOGGER = logging.getLogger(__name__)


# This is necessary for float comparisons
def _is_close(a, b, rel_tol=1e-09, abs_tol=0.0):
    """Determines whether two floats are within a tolerance.

    Returns:
        bool: Returns True if the two floats are within a tolerance,
            False otherwise.
    """
    return abs(a - b) <= max(rel_tol * max(abs(a), abs(b)), abs_tol)


class WaitCertificate(object):
    """Represents wait certificates, which include a random wait timer.

    Attributes:
        WaitCertificate.poet_enclave (module): The PoetEnclave module to use
            for executing enclave functions.
        previous_certificate_id (str): The id of the previous
            certificate.
        local_mean (float): The local mean wait time based on
            the history of certs.
        request_time (float): The request time of the
            certificate.
        duration (float): The duration of the wait timer.
        signature (str): The signature of the certificate.
        identifier (str): The identifier of this certificate.
    """
    poet_enclave = None

    @classmethod
    def create_wait_certificate(cls, timer, block_digest):
        """Creates a wait certificate in the enclave and then constructs
        a WaitCertificate object from it.

        Args:
            timer (journal.consensus.poet1.wait_timer.WaitTimer): The wait
                timer to use in creating the certificate.
            block_digest (str): The block digest/hash for the block for which
                this certificate is being created.

        Returns:
            journal.consensus.poet1.wait_certificate.WaitCertificate: A new
                wait certificate.
        """

        enclave_certificate = \
            cls.poet_enclave.create_wait_certificate(
                timer.enclave_wait_timer,
                block_digest)

        if not enclave_certificate:
            LOGGER.warn('invalid timer: %s', timer)
            raise \
                Exception(
                    'Attempt to create wait certificate from invalid wait '
                    'timer')

        certificate = cls(enclave_certificate)
        LOGGER.info('wait certificate created: %s', certificate)

        return certificate

    @classmethod
    def wait_certificate_from_serialized(cls, serialized, signature):
        """Converts a serialized wait certificate into an object.

        Args:
            serialized (str): The serialized wait certificate.
            signature (str): The signature.

        Returns:
            journal.consensus.poet1.wait_certificate.WaitCertificate: A wait
                certificate representing the contents of the serialized wait
                certificate.
        """
        enclave_certificate = \
            cls.poet_enclave.deserialize_wait_certificate(
                serialized=serialized,
                signature=signature)

        if not enclave_certificate or \
                not cls.poet_enclave.verify_wait_certificate(
                    enclave_certificate):
            raise \
                Exception(
                    'Attempt to deserialize an invalid wait certificate')

        return cls(enclave_certificate)

    @property
    def enclave_wait_certificate(self):
        return \
            self.poet_enclave.deserialize_wait_certificate(
                self._serialized_certificate,
                self.signature)

    def __init__(self, enclave_certificate):
        """Initialize the wait certificate from a PoET enclave wait
        certificate.

        Args:
            enclave_certificate: The PoeT enclave generated wait certificate.
        """
        self.previous_certificate_id = \
            enclave_certificate.previous_certificate_id
        self.local_mean = enclave_certificate.local_mean
        self.request_time = enclave_certificate.request_time
        self.duration = enclave_certificate.duration
        self.block_digest = enclave_certificate.block_digest
        self.signature = enclave_certificate.signature
        self.identifier = enclave_certificate.identifier

        # we cannot hold the certificate because it cannot be pickled for
        # storage in the transaction block array
        self._serialized_certificate = enclave_certificate.serialize()

    def __str__(self):
        return \
            'CERT, {0:0.2f}, {1:0.2f}, {2}, {3}'.format(
                self.local_mean,
                self.duration,
                self.identifier,
                self.previous_certificate_id)

    def is_valid(self, certificates, poet_public_key):
        """Determines whether the wait certificate is valid.

        Args:
            certificates (list): A list of historical certs.
            poet_public_key (str): The PoET public key that corresponds to the
                private key used to sign the certificate.

        Returns:
            True if the wait certificate is valid, False otherwise.
        """
        enclave_certificate = self.enclave_wait_certificate
        expected_mean = WaitTimer.compute_local_mean(certificates)

        if enclave_certificate.duration < self.poet_enclave.MINIMUM_WAIT_TIME:
            LOGGER.warn('Wait time less then minimum: %s != %s',
                        enclave_certificate.duration,
                        self.poet_enclave.MINIMUM_WAIT_TIME)
            return False

        if not _is_close(
                enclave_certificate.local_mean,
                expected_mean,
                abs_tol=0.001):
            LOGGER.warn(
                'mismatch local mean: %s != %s',
                enclave_certificate.local_mean,
                expected_mean)
            return False

        if enclave_certificate.previous_certificate_id == NullIdentifier:
            if len(certificates) == 0:
                return True

        if enclave_certificate.previous_certificate_id != \
                certificates[-1].identifier:
            LOGGER.warn('mismatch previous identifier: %s != %s',
                        enclave_certificate.previous_certificate_id,
                        certificates[-1].identifier)
            return False

        try:
            return \
                self.poet_enclave.verify_wait_certificate(
                    certificate=enclave_certificate,
                    poet_public_key=poet_public_key)
        except Timeout:
            raise NotAvailableException
        except ConnectionError:
            raise NotAvailableException

    def dump(self):
        """Returns a dict containing information about the wait
        certificate.

        Returns:
            dict: A dict containing info about the wait certificate.
        """
        result = {
            'SerializedCertificate': self._serialized_certificate,
            'Signature': self.signature
        }

        return result

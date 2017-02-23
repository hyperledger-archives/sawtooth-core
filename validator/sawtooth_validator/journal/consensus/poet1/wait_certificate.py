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
import requests
from requests import Timeout

from sawtooth_validator.exceptions import NotAvailableException
from sawtooth_validator.journal.consensus.poet1.wait_timer import WaitTimer

LOGGER = logging.getLogger(__name__)


# This is necessary for float comparisons
def _is_close(value_a, value_b, rel_tol=1e-09, abs_tol=0.0):
    """Determines whether two floats are within a tolerance.

    Returns:
        bool: Returns True if the two floats are within a tolerance,
            False otherwise.
    """
    return abs(value_a - value_b) <= \
        max(rel_tol * max(abs(value_a), abs(value_b)), abs_tol)


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
        validator_address (str): The address of the validator that created
            the wait certificate.
        block_digest (str): The block digest of the block for which this
            wait certificate was created.
        signature (str): The signature of the certificate.
        identifier (str): The identifier of this certificate.
    """
    poet_enclave = None

    @classmethod
    def create_wait_certificate(cls,
                                wait_timer,
                                block_digest):
        """Creates a wait certificate in the enclave and then constructs
        a WaitCertificate object from it.

        Args:
            wait_timer (WaitTimer): The wait timer for which the wait
                certificate is being requested.
            block_digest (str): The block digest of the block for which
                this certificate is being created.

        Returns:
            journal.consensus.poet1.wait_certificate.WaitCertificate: A new
                wait certificate.
        """

        enclave_certificate = \
            cls.poet_enclave.create_wait_certificate(
                wait_timer=wait_timer,
                block_digest=block_digest)

        if not enclave_certificate:
            raise \
                ValueError(
                    'Failed to create an enclave wait certificate')

        certificate = cls(enclave_certificate)
        LOGGER.info('wait certificate created: %s', certificate)

        return certificate

    @classmethod
    def wait_certificate_from_serialized(cls,
                                         serialized,
                                         signature):
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
                serialized_certificate=serialized,
                signature=signature)

        if not enclave_certificate:
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

    @property
    def population_estimate(self):
        return self.local_mean / WaitTimer.target_wait_time

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
        self.validator_address = enclave_certificate.validator_address
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

    def check_valid(self, certificates, poet_public_key):
        """Determines whether the wait certificate is valid.

        Args:
            certificates (list): A list of historical certs.
            poet_public_key (str): The PoET public key that corresponds to
                the private key used to sign the certificate.  This is
                obtained from the signup information for the validator
                that is the originator of the block for which the wait
                certificate is associated.

        Returns:
            True if the wait certificate is valid, False otherwise.
        """
        enclave_certificate = self.enclave_wait_certificate
        expected_mean = WaitTimer.compute_local_mean(certificates)

        if enclave_certificate.duration < WaitTimer.minimum_wait_time:
            raise \
                ValueError(
                    'Wait time less than minimum: {0} < {1}'.format(
                        enclave_certificate.duration,
                        WaitTimer.minimum_wait_time))

        if not _is_close(
                enclave_certificate.local_mean,
                expected_mean,
                abs_tol=0.001):
            raise \
                ValueError(
                    'Local mean does not match: {0} != {1}'.format(
                        enclave_certificate.local_mean,
                        expected_mean))

        if len(certificates) != 0 and \
            enclave_certificate.previous_certificate_id != \
                certificates[-1].identifier:
            raise \
                ValueError(
                    'Previous certificate ID does not match: {0} != '
                    '{1}'.format(
                        enclave_certificate.previous_certificate_id,
                        certificates[-1].identifier))

        try:
            self.poet_enclave.verify_wait_certificate(
                certificate=enclave_certificate,
                poet_public_key=poet_public_key)
        except Timeout:
            raise NotAvailableException
        except requests.ConnectionError:
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

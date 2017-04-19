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
import requests
from requests import Timeout

from sawtooth_validator.exceptions import NotAvailableException

from sawtooth_poet.poet_consensus.wait_timer import WaitTimer

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
        previous_certificate_id (str): The id of the previous
            certificate.
        local_mean (float): The local mean wait time based on
            the history of certs.
        request_time (float): The request time of the
            certificate.
        duration (float): The duration of the wait timer.
        validator_address (str): The address of the validator that created
            the wait certificate.
        block_hash (str): The hash of the block for which this wait
            certificate was created.
        signature (str): The signature of the certificate.
        identifier (str): The identifier of this certificate.
    """

    @classmethod
    def create_wait_certificate(cls,
                                poet_enclave_module,
                                wait_timer,
                                block_hash):
        """Creates a wait certificate in the enclave and then constructs
        a WaitCertificate object from it.

        Args:
            poet_enclave_module (module): The module that implements the
                underlying PoET enclave.
            wait_timer (WaitTimer): The wait timer for which the wait
                certificate is being requested.
            block_hash (str): The hash of the block for which this
                certificate is being created.

        Returns:
            WaitCertificate: A new wait certificate.
        """

        enclave_certificate = None
        try:
            enclave_certificate = \
                poet_enclave_module.create_wait_certificate(
                    wait_timer.enclave_wait_timer,
                    block_hash)
        except AttributeError as ex:
            LOGGER.error(
                'Exception caught trying to create wait certificate: %s',
                ex)

        if not enclave_certificate:
            raise \
                ValueError(
                    'Failed to create an enclave wait certificate')

        return cls(enclave_certificate)

    @classmethod
    def wait_certificate_from_serialized(cls,
                                         poet_enclave_module,
                                         serialized,
                                         signature):
        """Converts a serialized wait certificate into an object.

        Args:
            poet_enclave_module (module): The module that implements the
                underlying PoET enclave.
            serialized (str): The serialized wait certificate.
            signature (str): The signature.

        Returns:
            WaitCertificate: A wait certificate representing the contents of
                the serialized wait certificate.
        """
        enclave_certificate = \
            poet_enclave_module.deserialize_wait_certificate(
                serialized,
                signature)

        if not enclave_certificate:
            raise \
                Exception(
                    'Attempt to deserialize an invalid wait certificate')

        return cls(enclave_certificate)

    @property
    def population_estimate(self):
        return self.local_mean / WaitTimer.target_wait_time

    def _enclave_wait_certificate(self, poet_enclave_module):
        return \
            poet_enclave_module.deserialize_wait_certificate(
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
        self.validator_address = enclave_certificate.validator_address
        self.block_hash = enclave_certificate.block_hash
        self.signature = enclave_certificate.signature
        self.identifier = enclave_certificate.identifier()

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

    def check_valid(self,
                    poet_enclave_module,
                    previous_certificate_id,
                    poet_public_key,
                    consensus_state,
                    poet_config_view):
        """Determines whether the wait certificate is valid.

        Args:
            poet_enclave_module (module): The module that implements the
                underlying PoET enclave.
            previous_certificate_id (str): The ID of the wait certificate for
                the block attempting to build upon
            poet_public_key (str): The PoET public key that corresponds to
                the private key used to sign the certificate.  This is
                obtained from the signup information for the validator
                that is the originator of the block for which the wait
                certificate is associated.
            consensus_state (ConsensusState): The current PoET consensus state
            poet_config_view (PoetConfigView): The current PoET config view
        Returns:
            True if the wait certificate is valid, False otherwise.
        """
        enclave_certificate = \
            self._enclave_wait_certificate(poet_enclave_module)
        expected_mean = \
            consensus_state.compute_local_mean(
                poet_config_view=poet_config_view)

        if enclave_certificate.duration < poet_config_view.minimum_wait_time:
            raise \
                ValueError(
                    'Wait time less than minimum: {0} < {1}'.format(
                        enclave_certificate.duration,
                        poet_config_view.minimum_wait_time))

        if not _is_close(
                enclave_certificate.local_mean,
                expected_mean,
                abs_tol=0.001):
            raise \
                ValueError(
                    'Local mean does not match: {0} != {1}'.format(
                        enclave_certificate.local_mean,
                        expected_mean))

        if enclave_certificate.previous_certificate_id != \
                previous_certificate_id:
            raise \
                ValueError(
                    'Previous certificate ID does not match: {0} != '
                    '{1}'.format(
                        enclave_certificate.previous_certificate_id,
                        previous_certificate_id))

        try:
            poet_enclave_module.verify_wait_certificate(
                enclave_certificate,
                poet_public_key)
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

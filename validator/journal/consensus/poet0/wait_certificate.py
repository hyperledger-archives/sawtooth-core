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
import hashlib
from requests import ConnectionError
from requests import Timeout

from sawtooth.exceptions import NotAvailableException
from journal.consensus.poet0.wait_timer import WaitTimer

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
        WaitCertificate.poet_enclave (module): The PoetEnclave module to use
            for executing enclave functions.
        WaitCertificate.previous_certificate_id (str): The id of the previous
            certificate.
        WaitCertificate.local_mean (float): The local mean wait time based on
            the history of certs.
        WaitCertificate.request_time (float): The request time of the
            certificate.
        WaitCertificate.duration (float): The duration of the wait timer.
        WaitCertificate.signature (str): The signature of the certificate.
        wait_certificate.WaitCertificate.identifier\
            (str): The identifier of this certificate.
        serialized_cert (str): A serialized version of the certificate.
    """
    poet_enclave = None

    @classmethod
    def create_wait_certificate(cls, timer, block_hash):
        """Creates a wait certificate in the enclave and then constructs
        a WaitCertificate object.

        Args:
            timer (journal.consensus.poet.wait_timer.WaitTimer): The wait
                timer to use in creating the certificate.
            block_hash (str): The digest of the block

        Returns:
            journal.consensus.poet.wait_certificate.WaitCertificate: A new wait
                 certificate.
        """
        try:
            cert = cls.poet_enclave.create_wait_certificate(
                timer.enclave_wait_timer,
                block_hash)
        except ValueError as e:
            logger.error('Received error create_wait_certificate '
                         'from enclave : %s', e.message)
            cert = None

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
            journal.consensus.poet.wait_certificate.WaitCertificate: A wait
                certificate representing the contents of the serialized wait
                certificate.
        """
        cert = cls.poet_enclave.deserialize_wait_certificate(
            serialized, signature)
        if not cert or not cls.poet_enclave.verify_wait_certificate(cert):
            raise Exception(
                'WaitCertificateVerify',
                'Attempt to deserialize an invalid wait certificate')

        return cls(cert)

    def __init__(self, cert):
        """Initialize the wait certificate.

        Args:
            cert (poet_enclave.WaitCertificate): The poet_enclave
                generated wait certificate.
        """
        self.previous_certificate_id = cert.previous_certificate_id
        self.local_mean = cert.local_mean
        self.request_time = cert.request_time
        self.duration = cert.duration
        self.validator_address = cert.validator_address
        self.block_hash = cert.block_hash
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
        try:
            return self.poet_enclave.deserialize_wait_certificate(
                self.serialized_cert,
                self.signature)
        except:
            logger.warn('Wait certificate failed to deserialize.')
            return None

    def is_valid_wait_certificate(self, originator_id, certs, transactions):
        """Determines whether the wait certificate is valid.

        Args:
            certs (list): A list of historical certs.

        Returns:
            bool: Whether or not the wait certificate is valid.
        """

        if not isinstance(originator_id, basestring):
            raise TypeError

        if not isinstance(certs, list):
            raise TypeError

        if not isinstance(transactions, list):
            raise TypeError

        cert = self.enclave_wait_certificate
        if not cert:
            return False

        if cert.duration < self.poet_enclave.MINIMUM_WAIT_TIME:
            logger.warn('Wait time less then minimum: %s != %s',
                        cert.duration, self.poet_enclave.MINIMUM_WAIT_TIME)
            return False

        expected_mean = WaitTimer.compute_local_mean(certs)
        if not is_close(cert.local_mean, expected_mean, abs_tol=0.001):
            logger.warn('mismatch local mean: %s != %s', cert.local_mean,
                        expected_mean)
            return False

        if cert.previous_certificate_id == self.poet_enclave.NULL_IDENTIFIER:
            if len(certs) == 0:
                return True

        if cert.previous_certificate_id != certs[-1].identifier:
            logger.warn('mismatch previous identifier: %s != %s',
                        cert.previous_certificate_id, certs[-1].identifier)
            return False

        hasher = hashlib.sha256()
        for tid in transactions:
            hasher.update(tid)
        block_hash = hasher.hexdigest()

        if block_hash != self.block_hash:
            logger.warn('Transaction hash mismatch : %s != %s',
                        self.block_hash, block_hash)
            return False

        if self.validator_address != originator_id:
            logger.warn('Originator Id mismatch: %s != %s',
                        self.validator_address, originator_id)
            return False

        try:
            return self.poet_enclave.verify_wait_certificate(cert)
        except Timeout:
            raise NotAvailableException
        except ConnectionError:
            raise NotAvailableException

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

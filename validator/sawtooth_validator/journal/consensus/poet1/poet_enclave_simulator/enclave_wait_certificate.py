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
import base64

from sawtooth_validator.journal.block_wrapper import NULL_BLOCK_IDENTIFIER
from sawtooth_validator.journal.consensus.poet1.poet_enclave_simulator.common\
    import dict2json
from sawtooth_validator.journal.consensus.poet1.poet_enclave_simulator.common\
    import json2dict


LOGGER = logging.getLogger(__name__)


class EnclaveWaitCertificate(object):
    """Represents an enclave-internal representation of a wait certificate

    Attributes:
        request_time (float): The request time
        duration (float): The amount of time from request_time when timer
            expires
        previous_certificate_id (str): The id of the previous
            certificate.
        local_mean (float): The local mean wait time based on the
            history of certs
        validator_address (str): The address of the validator that created the
            wait certificate.
        block_digest (str): The digest of the block for which this wait
            certificate was generated
        signature (str): Signature of the certificate using PoET private key
            generated during creation of signup info
    """

    @classmethod
    def wait_certificate_with_wait_timer(cls,
                                         wait_timer,
                                         nonce,
                                         block_digest):
        """
        Creates a wait certificate object using an already-created wait
        timer.

        Args:
            wait_timer (EnclaveWaitTimer): The wait timer we are creating
                wait certificate for
            nonce (str): A random nonce created for this certificate
            block_digest (str): The digest for the block that this wait
                certificate is being created for

        Returns:
            An EnclaveWaitCertificate object
        """
        return \
            EnclaveWaitCertificate(
                duration=wait_timer.duration,
                previous_certificate_id=wait_timer.previous_certificate_id,
                local_mean=wait_timer.local_mean,
                request_time=wait_timer.request_time,
                validator_address=wait_timer.validator_address,
                nonce=nonce,
                block_digest=block_digest)

    @classmethod
    def wait_certificate_from_serialized(cls,
                                         serialized_certificate,
                                         signature):
        """
        Takes wait certificate that has been serialized to JSON and
        reconstitutes into an EnclaveWaitCertificate object.

        Args:
            serialized_certificate (str): JSON serialized wait certificate
            signature (str): Signature over serialized certificate

        Returns:
            An EnclaveWaitCertificate object
        """
        deserialized_certificate = json2dict(serialized_certificate)

        certificate = \
            EnclaveWaitCertificate(
                duration=float(deserialized_certificate.get('duration')),
                previous_certificate_id=str(
                    deserialized_certificate.get('previous_certificate_id')),
                local_mean=float(deserialized_certificate.get('local_mean')),
                request_time=float(
                    deserialized_certificate.get('request_time')),
                validator_address=str(
                    deserialized_certificate.get('validator_address')),
                nonce=str(deserialized_certificate.get('nonce')),
                block_digest=str(deserialized_certificate.get(
                    'block_digest')),
                signature=signature,
                serialized_certificate=serialized_certificate)

        return certificate

    @property
    def identifier(self):
        my_id = NULL_BLOCK_IDENTIFIER
        if self.signature is not None:
            my_id = \
                base64.b32encode(
                    hashlib.sha256(
                        self.signature.encode()).hexdigest().encode()).decode()

        return my_id[:16]

    def __init__(self,
                 duration,
                 previous_certificate_id,
                 local_mean,
                 request_time,
                 validator_address,
                 nonce,
                 block_digest,
                 signature=None,
                 serialized_certificate=None):
        self.duration = float(duration)
        self.previous_certificate_id = str(previous_certificate_id)
        self.local_mean = float(local_mean)
        self.request_time = float(request_time)
        self.validator_address = str(validator_address)
        self.nonce = str(nonce)
        self.block_digest = str(block_digest)
        self.signature = signature
        self._serialized = serialized_certificate

    def __str__(self):
        return \
            'CERT, {0:0.2f}, {1:0.2f}, {2}, {3}'.format(
                self.local_mean,
                self.duration,
                self.identifier,
                self.previous_certificate_id)

    def serialize(self):
        """
        Serializes to JSON that can later be reconstituted to an
        EnclaveWaitCertificate object

        Returns:
            A JSON string representing the serialized version of the object
        """
        if self._serialized is None:
            certificate_dict = {
                'duration': self.duration,
                'previous_certificate_id': self.previous_certificate_id,
                'local_mean': self.local_mean,
                'request_time': self.request_time,
                'validator_address': self.validator_address,
                'nonce': self.nonce,
                'block_digest': self.block_digest
            }

            self._serialized = dict2json(certificate_dict)

        return self._serialized

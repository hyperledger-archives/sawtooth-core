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

LOGGER = logging.getLogger(__name__)


class SignupInfo(object):
    """Encapsulates authorization data for network enrollment policies

    Attributes:
        poet_public_key (str): Encoded public key corresponding to private
            key used by PoET to sign wait certificates.
        proof_data (str): Information that can be used internally to verify
            the validity of the signup information.
        anti_sybil_id (str): A string corresponding to the anti-Sybil ID for
            the enclave that generated the signup information.
        sealed_signup_data (str): A base 64 string representing data that can
            be persisted and presented at a later time to restore the PoET
            enclave.
    """
    poet_enclave = None

    @classmethod
    def create_signup_info(cls,
                           validator_address,
                           originator_public_key_hash,
                           most_recent_wait_certificate_id):
        """
        Creates signup information a PoET 1 validator uses to join the
        validator network.

        Args:
            validator_address (str): A string representing the address of the
                validator requesting signup info.
            originator_public_key_hash (str): A string representing SHA256
                hash (i.e., hashlib.sha256(OPK).hexdigest()) of the
                originator's public key
            most_recent_wait_certificate_id (str): The ID of the
                most-recently-created wait certificate.

        Returns:
            SignupInfo object
        """

        enclave_signup_info = \
            cls.poet_enclave.create_signup_info(
                validator_address,
                originator_public_key_hash,
                most_recent_wait_certificate_id)
        signup_info = cls(enclave_signup_info)

        LOGGER.info("signup info created: %s", signup_info)

        return signup_info

    @classmethod
    def signup_info_from_serialized(cls, serialized):
        """
        Converts serialized signup info into an object.

        Args:
            serialized (str): The serialized signup info

        Returns:
            journal.consensus.poet1.signup_info.SignupInfo: A signup
                info object.
        """
        enclave_signup_info = \
            cls.poet_enclave.deserialize_signup_info(
                serialized_signup_info=serialized)

        return cls(enclave_signup_info)

    @property
    def enclave_signup_info(self):
        if self._enclave_signup_info is None:
            self._enclave_signup_info = \
                self.poet_enclave.deserialize_signup_info(
                    self._serialized_signup_info)

        return self._enclave_signup_info

    @classmethod
    def unseal_signup_data(cls,
                           validator_address,
                           sealed_signup_data):
        """
        Takes sealed data from a previous call to create_signup_info and
        re-establishes the PoET 1 enclave state.

        Args:
            validator_address (str): A string representing the address of the
                validator that is requesting signup data be unsealed.
            sealed_signup_data: The sealed signup data that was previously
                returned as part of the signup info returned from
                create_signup_info.

        Returns:
            The encoded PoET public key corresponding to private key used by
            PoET to sign wait certificates.
        """
        return \
            cls.poet_enclave.unseal_signup_data(
                validator_address=validator_address,
                sealed_signup_data=sealed_signup_data)

    def __init__(self, enclave_signup_info):
        self.poet_public_key = enclave_signup_info.poet_public_key
        self.proof_data = enclave_signup_info.proof_data
        self.anti_sybil_id = enclave_signup_info.anti_sybil_id
        self.sealed_signup_data = enclave_signup_info.sealed_signup_data

        self._enclave_signup_info = None
        self._attestation_verification_rep = None

        # We cannot hold the signup info because it cannot be pickled for
        # storage
        self._serialized_signup_info = enclave_signup_info.serialize()

    def __str__(self):
        return \
            'SIGNUP_INFO: PPK={0}, PD={1}, ASID={2}'.format(
                self.poet_public_key,
                self.proof_data,
                self.anti_sybil_id)

    def check_valid(self,
                    originator_public_key_hash,
                    most_recent_wait_certificate_id):
        """
        Checks the validity of the signup information.

        Args:
            originator_public_key_hash (str): A string representing SHA256
                hash (i.e., hashlib.sha256(OPK).hexdigest()) of the
                originator's public key
            most_recent_wait_certificate_id (str): The ID of the
                most-recently-created wait certificate.

        Returns:
            SignupInfo object
        """
        self.poet_enclave.verify_signup_info(
            signup_info=self.enclave_signup_info,
            originator_public_key_hash=originator_public_key_hash,
            most_recent_wait_certificate_id=most_recent_wait_certificate_id)

    def serialize(self):
        # Simply return the serialized version of the enclave signup info
        # as we don't have anything to add.
        return self._serialized_signup_info

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

from gossip.common import json2dict
from gossip.common import dict2json

import logging

LOGGER = logging.getLogger(__name__)


class SignupInfo(object):
    """Encapsulates authorization data for network enrollment policies

    Attributes:
        poet_pubkey (str): Public key corresponding to private key used by
            PoET to sign wait certificates.
        anti_sybil_id (str): A token, such as an EPID pseudonym, to restrict
            the number of identities an entity can assume in the network.
        proof_data (array): signed fields proving validity of signup info
        sealed_signup_data (array): data that can be persisted and can be
            presented at a later time to restore the PoET enclave
    """
    poet_enclave = None

    @classmethod
    def create_signup_info(cls, originator_id):
        """
        Creates signup information a PoET 1 validator uses to join the
        validator network.

        Args:
            originator_id: The originator's ID (i.e., address)

        Returns:
            SignupInfo object
        """
        return cls.poet_enclave.create_signup_info(originator_id)

    @classmethod
    def verify_signup_info(cls, serialized_signup_info):
        """
        Verifies the validity of signup information provided by another
        validator.

        Args:
            serialized_signup_info: The serialized validator information
                that was submitted to the blockchain.

        Returns:
            True if the signup info is valid, False otherwise.
        """
        return cls.poet_enclave.verify_signup_info(serialized_signup_info)

    @classmethod
    def signup_info_from_serialized(cls, serialized):
        deserialized = json2dict(serialized)

        return \
            SignupInfo(
                anti_sybil_id=deserialized.get('anti_sybil_id'),
                poet_public_key=deserialized.get('poet_public_key'),
                proof_data=deserialized.get('proof_data'))

    def __init__(self,
                 anti_sybil_id,
                 poet_public_key,
                 proof_data,
                 sealed_signup_data=None):
        self.anti_sybil_id = anti_sybil_id
        self.poet_public_key = poet_public_key
        self.proof_data = proof_data
        self.sealed_signup_data = sealed_signup_data

    def __str__(self):
        return "<{0}, {1}, {2}>".format(self.anti_sybil_id,
                                        self.poet_public_key,
                                        self.proof_data)

    def serialize(self):
        return dict2json({'anti_sybil_id': self.anti_sybil_id,
                          'poet_public_key': self.poet_public_key,
                          'proof_data': self.proof_data})

    def is_valid(self):
        return self.verify_signup_info(self.serialize())

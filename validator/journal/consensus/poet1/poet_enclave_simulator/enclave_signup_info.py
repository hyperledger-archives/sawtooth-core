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


class EnclaveSignupInfo(object):
    """Represents an enclave-internal representation of the encapsulation of
    the authorization data for network enrollment policies

    Attributes:
        poet_public_key (str): Public key corresponding to private key used by
            PoET to sign wait certificates.
        anti_sybil_id (str): A token, such as an EPID pseudonym, to restrict
            the number of identities an entity can assume in the network.
        proof_data (array): signed fields proving validity of signup info
        sealed_signup_data (array): data that can be persisted and can be
            presented at a later time to restore the PoET enclave
    """
    def __init__(self,
                 anti_sybil_id,
                 poet_public_key,
                 proof_data,
                 sealed_signup_data=None):
        self.anti_sybil_id = anti_sybil_id
        self.poet_public_key = poet_public_key
        self.proof_data = proof_data
        self.sealed_signup_data = sealed_signup_data

    @classmethod
    def signup_info_from_serialized(cls, serialized_signup_info):
        """
        Takes signup information that has been serialized to JSON and
        reconstitutes into an EnclaveSignupInfo object.

        Args:
            serialized_signup_info: JSON serialized signup info

        Returns:
            An EnclaveSignupInfo object
        """
        deserialized_signup_info = json2dict(serialized_signup_info)

        return \
            EnclaveSignupInfo(
                anti_sybil_id=deserialized_signup_info.get(
                    'anti_sybil_id'),
                poet_public_key=deserialized_signup_info.get(
                    'poet_public_key'),
                proof_data=deserialized_signup_info.get(
                    'proof_data'),
                sealed_signup_data=deserialized_signup_info.get(
                    'sealed_signup_data'))

    def serialize(self):
        """
        Serializes to JSON that can later be reconstituted to an
        EnclaveSignupInfo object

        Returns:
            A JSON string representing the serialized version of the object
        """
        signup_info_dict = {
            'anti_sybil_id': self.anti_sybil_id,
            'poet_public_key': self.poet_public_key,
            'proof_data': self.proof_data,
            'sealed_signup_data': self.sealed_signup_data
        }

        return dict2json(signup_info_dict)

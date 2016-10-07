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
        proof_data (dict): signed fields proving validity of signup info.  The
            proof data dictionary contains:
                'attestation_verification_report' (dict): Another dict
                    that contains attestation evidence payload and the
                    anti-Sybil ID
                'signature': The signature of the attestation verification
                    report using the IAS report key.
        sealed_signup_data (array): data that can be persisted and can be
            presented at a later time to restore the PoET enclave
    """
    def __init__(self,
                 poet_public_key,
                 proof_data,
                 sealed_signup_data=None):
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
            An EnclaveSignupInfo object with sealed signup info data
            stripped out as serialized signup info doesn't contain it.
        """
        deserialized_signup_info = json2dict(serialized_signup_info)

        # Note - serialized signup info shouldn't have sealed signup
        # data.
        return \
            EnclaveSignupInfo(
                poet_public_key=deserialized_signup_info.get(
                    'poet_public_key'),
                proof_data=deserialized_signup_info.get(
                    'proof_data'))

    def serialize(self):
        """
        Serializes to JSON that can later be reconstituted to an
        EnclaveSignupInfo object

        Returns:
            A JSON string representing the serialized version of the object.
            Note that the sealed signup data is not encluded in the serialized
            data.
        """

        # Note - we are not serializing the sealed signup data.  Sealed signup
        # data is meant to be used locally on the system and not serialized
        # and sent to anyone else.
        signup_info_dict = {
            'poet_public_key': self.poet_public_key,
            'proof_data': self.proof_data
        }

        return dict2json(signup_info_dict)

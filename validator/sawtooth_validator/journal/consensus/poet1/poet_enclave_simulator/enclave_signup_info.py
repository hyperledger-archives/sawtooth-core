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

from sawtooth_validator.journal.consensus.poet1.poet_enclave_simulator.common\
    import json2dict
from sawtooth_validator.journal.consensus.poet1.poet_enclave_simulator.common\
    import dict2json

LOGGER = logging.getLogger(__name__)


class EnclaveSignupInfo(object):
    """Represents an enclave-internal representation of the encapsulation of
    the authorization data for network enrollment policies

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
        signup_info = \
            EnclaveSignupInfo(
                poet_public_key=deserialized_signup_info.get(
                    'poet_public_key'),
                proof_data=deserialized_signup_info.get(
                    'proof_data'),
                anti_sybil_id=deserialized_signup_info.get(
                    'anti_sybil_id'),
                serialized_signup_info=serialized_signup_info)

        return signup_info

    def __init__(self,
                 poet_public_key,
                 proof_data,
                 anti_sybil_id,
                 sealed_signup_data=None,
                 serialized_signup_info=None):
        self.poet_public_key = poet_public_key
        self.proof_data = proof_data
        self.anti_sybil_id = anti_sybil_id
        self.sealed_signup_data = sealed_signup_data
        self._serialized = serialized_signup_info

    def serialize(self):
        """
        Serializes to JSON that can later be reconstituted to an
        EnclaveSignupInfo object

        Returns:
            A JSON string representing the serialized version of the object.
            Note that the sealed signup data is not encluded in the serialized
            data.
        """

        if self._serialized is None:
            # Note - we are not serializing the sealed signup data.  Sealed
            # signup data is meant to be used locally on the system and not
            # serialized and sent to anyone else.
            signup_info_dict = {
                'poet_public_key': self.poet_public_key,
                'proof_data': self.proof_data,
                'anti_sybil_id': self.anti_sybil_id
            }

            self._serialized = dict2json(signup_info_dict)

        return self._serialized

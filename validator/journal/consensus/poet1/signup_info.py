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

from gossip.common import json2dict, dict2json

import logging

LOGGER = logging.getLogger(__name__)


class SignupInfo(object):
    """Encapsulates authorization data for network enrollment policies

    Attributes:
        poet_pubkey (str): Public key used by poet to sign wait certificates
        anti_sybil_id (str): A token, such as an EPID pseudonym, to restrict
            the number of identities an entity can assume in the network.
        proof_data (array): signed fields proving validity of signup info
    """
    poet_enclave = None

    @classmethod
    def verify_signup_info(cls, serialized_signup_info):
        """ This method should bind to a policy implementation using code like:
        # return cls.poet_enclave.verify_signup_info(serialized_signup_info)
        """
        deserialized = cls.deserialize(serialized_signup_info)
        if not all(k in deserialized for k in
                   ('anti_sybil_id', 'poet_pubkey', 'proof_data')):
            return False

        for k, v in deserialized.items():
            if v is None:
                return False

        return True

    @classmethod
    def deserialize(cls, serialized):
        deserialized = json2dict(serialized)
        return deserialized

    def __init__(self, anti_sybil_id, poet_pubkey, proof_data):
        self.anti_sybil_id = anti_sybil_id
        self.poet_pubkey = poet_pubkey
        self.proof_data = proof_data

    def __str__(self):
        return "<{0}, {1}, {2}>".format(self.anti_sybil_id,
                                        self.poet_pubkey, self.proof_data)

    def serialize(self):
        serialized = dict2json({'anti_sybil_id': self.anti_sybil_id,
                                'poet_pubkey': self.poet_pubkey,
                                'proof_data': self.proof_data})
        return serialized

    def is_valid(self):
        return self.verify_signup_info(self.serialize())

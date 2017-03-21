# Copyright 2017 Intel Corporation
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

import hashlib

from sawtooth_poet_common.protobuf.validator_registry_pb2 import ValidatorInfo


_NAMESPACE = hashlib.sha256('validator_registry'.encode()).hexdigest()[0:6]


class MockValidatorRegistryView(object):
    """Simulates a ValidatorRegistryView.
    """

    def __init__(self, state_dict):
        self._state_db = state_dict

    def get_validators(self):
        return self._state_db.keys()

    def has_validator_info(self, validator_id):
        try:
            validator_id in self._state_db
            return True
        except KeyError:
            return False

    def get_validator_info(self, validator_id):
        state_data = self._state_db.get(
            MockValidatorRegistryView._to_address(validator_id))

        return MockValidatorRegistryView._parse_validator_info(state_data)

    def _to_address(addressable_key):
        return _NAMESPACE + hashlib.sha256(
            addressable_key.encode()).hexdigest()

    def _parse_validator_info(state_data):
        validator_info = ValidatorInfo()
        validator_info.ParseFromString(state_data)

        return validator_info

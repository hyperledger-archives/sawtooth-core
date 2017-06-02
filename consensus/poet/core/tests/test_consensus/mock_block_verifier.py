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


class MockValidatorRegistryView(object):
    """Simulates a ValidatorRegistryView.
    """

    def __init__(self, state_dict):
        self._state_db = state_dict

    def get_validators(self):
        return self._state_db.keys()

    def has_validator_info(self, validator_id):
        return validator_id in self._state_db

    def get_validator_info(self, validator_id):
        return self._state_db[validator_id]


class MockCreateWaitCertificate(object):
    """Simulates a wait_certificate.
    """

    def __init__(self, fail_flag):
        self.fail_flag = fail_flag

    def check_valid(self,
                    poet_enclave_module,
                    certificates,
                    poet_public_key):
        if self.fail_flag is not None:
            pass
        else:
            raise \
                ValueError(
                    'Mock to fail wait_certificate '
                    'ccheck_valid')

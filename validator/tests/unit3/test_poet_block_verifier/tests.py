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
import unittest
import logging

from test_poet_block_verifier.mocks import MockValidatorRegistryView


LOGGER = logging.getLogger(__name__)

class TestPoetBlockVerifier(unittest.TestCase):
    def __init__(self, test_name):
        super().__init__(test_name)

    def test_verify_block(self, block_wrapper):
        validator_registry_view = MockValidatorRegistryView(self._state_view)
        if len(validator_registry_view.get_validators()) > 0:
            try:
                validator_info = \
                    validator_registry_view.get_validator_info(
                        block_wrapper.header.signer_pubkey)

            except KeyError:
            LOGGER.error(
                'Attempted to verify block from validator with no '
                'validator registry entry')
            return False

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

import os
import unittest
import logging

from sawtooth.exceptions import InvalidTransactionError
from txnintegration.integer_key_client import IntegerKeyClient
from txnintegration.utils import generate_private_key
from txnintegration.validator_network_manager import get_default_vnm

logger = logging.getLogger(__name__)

RUN_TEST_SUITES = True \
    if os.environ.get("RUN_TEST_SUITES", False) == "1" else False


class TestLocalValidationErrors(unittest.TestCase):
    @unittest.skipUnless(RUN_TEST_SUITES, "test suites")
    def test_local_validation_errors(self):
        url = "http://localhost:8800"
        client = IntegerKeyClient(url,
                                  keystring=generate_private_key(),
                                  disable_client_validation=True)

        with self.assertRaises(InvalidTransactionError):
            client.inc("bob", 1)

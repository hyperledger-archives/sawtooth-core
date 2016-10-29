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

import unittest
import logging

from sawtooth.exceptions import InvalidTransactionError
from txnintegration.integer_key_client import IntegerKeyClient
from txnintegration.simcontroller import get_default_sim_controller
from txnintegration.utils import generate_private_key

logger = logging.getLogger(__name__)


class TestLocalValidationErrors(unittest.TestCase):

    def _generate_invalid_transactions(self, url):
        client = IntegerKeyClient(url,
                                  keystring=generate_private_key(),
                                  disable_client_validation=True)
        with self.assertRaises(InvalidTransactionError):
            client.inc("bob", 1)

    def test_local_validation_errors(self):
        sim = None
        try:
            print
            overrides = {
                'LedgerType': 'dev_mode',
                'BlockWaitTime': 0,
                'LocalValidation': True,
            }
            sim = get_default_sim_controller(1, overrides=overrides)
            sim.do_genesis()
            sim.launch()
            urls = sim.urls()
            self._generate_invalid_transactions(urls[0])
        finally:
            if sim is not None:
                sim.shutdown(archive_name=self._testMethodName)
            else:
                print "No Validator data and logs to preserve"

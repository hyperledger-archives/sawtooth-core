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

import traceback
import unittest
import logging

from txnintegration.utils import generate_private_key
from txnintegration.integer_key_client import IntegerKeyClient
from txnintegration.validator_network_manager import ValidatorNetworkManager, \
    defaultValidatorConfig

from sawtooth.exceptions import InvalidTransactionError

logger = logging.getLogger(__name__)


class TestLocalValidationErrors(unittest.TestCase):

    def _generate_invalid_transactions(self, url):
        client = IntegerKeyClient(url,
                                  keystring=generate_private_key(),
                                  disable_client_validation=True)
        with self.assertRaises(InvalidTransactionError):
            client.inc("bob", 1)

    def test_local_validation_errors(self):
        cfg = defaultValidatorConfig.copy()
        cfg['LedgerType'] = 'dev_mode'
        cfg['BlockWaitTime'] = 0
        cfg['LocalValidation'] = True
        vnm = None
        try:
            print "Launching validator network."
            vnm = ValidatorNetworkManager(http_port=9300, udp_port=9350,
                                          cfg=cfg)
            vnm.launch_network(1)
            urls = vnm.urls()
            self._generate_invalid_transactions(urls[0])

            if vnm:
                vnm.shutdown()
        except Exception:
            print "Exception encountered in test case."
            traceback.print_exc()
            if vnm:
                vnm.shutdown()
            raise
        finally:
            if vnm:
                vnm.create_result_archive("%s.tar.gz" % self._testMethodName)
            else:
                print "No Validator data and logs to preserve"

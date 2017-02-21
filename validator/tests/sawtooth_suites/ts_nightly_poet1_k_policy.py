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
import traceback
import unittest

from sawtooth_test_suite import SawtoothTestSuite

from integration.test_convergence import TestConvergence
from integration.test_poet1_k_policy import TestPoet1KPolicy


LOGGER = logging.getLogger(__name__)


class Poet1NightlyTestSuite(SawtoothTestSuite):
    def test_suite(self):
        cfg = {"LedgerType": "poet1",
               "InitialConnectivity": 1,
                "TransactionFamilies": ["ledger.transaction.integer_key"],
                "InitialConnectivity": 1,
               "BlockClaimThreshold": 25,
               "BlockClaimTrigger": 25}

        success = False
        try:
            self._do_setup(cfg)
            urls = self.urls
            suite = unittest.TestSuite()
            # test_bootstrap will allow the validators to all come on line
            # before others tries to connect to the validators.
            suite.addTest(TestConvergence('test_bootstrap', urls))
            suite.addTest(TestPoet1KPolicy('test_poet1_k_policy', urls))
            runner = unittest.TextTestRunner(verbosity=2)
            result = runner.run(suite)
            if len(result.failures) == 0 and len(result.errors) == 0:
                success = True
        except:
            traceback.print_exc()
            raise
        finally:
            self._do_teardown()
            if success is False:
                self.fail(self.__class__.__name__)

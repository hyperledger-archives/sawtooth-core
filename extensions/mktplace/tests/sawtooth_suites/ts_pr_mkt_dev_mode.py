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
import time
import traceback
import unittest

from sawtooth_test_suite import SawtoothTestSuite
from integration.test_all_transactions import TestAllTransactions
from integration.test_cp_scenarios import TestCommercialPaperScenarios
from integration.test_smoke import TestSmoke

LOGGER = logging.getLogger(__name__)


class DevModeMktTestSuite(SawtoothTestSuite):
    def test_suite(self):
        cfg = {"LedgerType": "dev_mode",
               'InitialWaitTime': 1,
               'TargetWaitTime': 1,
               "TransactionFamilies": ["ledger.transaction.integer_key",
                                       "mktplace.transactions.market_place"],
               "DevModePublisher": True}
               
        success = False
        try:
            self._do_setup(cfg, node_count=1)
            time.sleep(20)
            urls = self.urls
            suite = unittest.TestSuite()
            suite.addTest(TestSmoke('test_mktplace_load', urls,
                                    self._node_ctrl.get_data_dir()))
            suite.addTest(TestCommercialPaperScenarios('test_scenario_setup'))
            suite.addTest(TestCommercialPaperScenarios('test_scenario_a'))
            suite.addTest(TestCommercialPaperScenarios('test_scenario_b'))
            suite.addTest(TestCommercialPaperScenarios('test_scenario_c'))
            suite.addTest(TestCommercialPaperScenarios('test_scenario_d'))
            suite.addTest(TestAllTransactions('test_all_transactions', urls))
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

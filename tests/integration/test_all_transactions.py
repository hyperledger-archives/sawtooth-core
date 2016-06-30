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

from mktmain import client_cli
from mktplace import mktplace_state
from txnintegration.validator_network_manager import ValidatorNetworkManager
from txnintegration.validator_network_manager import defaultValidatorConfig

ENABLE_INTEGRATION_TESTS = False
if os.environ.get("ENABLE_INTEGRATION_TESTS", False) == "1":
    ENABLE_INTEGRATION_TESTS = True


@unittest.skipUnless(ENABLE_INTEGRATION_TESTS, "integration test")
class TestAllTransactions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vnm = None
        try:
            if 'TEST_VALIDATOR_URLS' in os.environ:
                urls = (os.environ['TEST_VALIDATOR_URLS']).split(",")
                cls.url = urls[0]
            else:
                vnm_config = defaultValidatorConfig.copy()
                if 'mktplace.transactions.market_place' not in \
                        vnm_config['TransactionFamilies']:
                    vnm_config['TransactionFamilies'].append(
                        'mktplace.transactions.market_place')
                vnm_config['InitialWaitTime'] = 1
                vnm_config['TargetWaitTime'] = 1
                vnm_config["LogConfigFile"] = "tests/integration/" + \
                    "all_transactions/etc/mktclient_logging.js"
                cls.vnm = ValidatorNetworkManager(
                    httpPort=9500, udpPort=9600, cfg=vnm_config)
                cls.vnm.launch_network(1)
                # the url of the initial validator
                cls.url = cls.vnm.urls()[0] + '/'

            os.environ['CURRENCYHOME'] = os.path.join(
                os.path.dirname(__file__), "all_transactions")

            cls.script_path = os.path.join(os.path.dirname(__file__),
                                           'all_transactions')
            state = mktplace_state.MarketPlaceState(cls.url)
            state.fetch()
        except:
            if cls.vnm is not None:
                cls.vnm.shutdown()
            raise

    def test_transactions_reg(self):
        client_cli.main(args=["--name", "user",
                              "--script",
                              os.path.join(self.script_path,
                                           "reg_transactions"),
                              "--echo",
                              "--url",
                              self.url])

        state = mktplace_state.MarketPlaceState(self.url)
        state.fetch()
        self.assertIsNotNone(state.n2i("//user"))
        self.assertIsNotNone(state.n2i("//user/user/account"))
        self.assertIsNotNone(state.n2i("//user/asset-type/currency"))
        self.assertIsNotNone(state.n2i("//user/asset-type/good"))
        self.assertIsNotNone(state.n2i("//user/asset/currency/USD"))
        self.assertIsNotNone(state.n2i("//user/asset/good/paper"))
        self.assertIsNotNone(state.n2i("//user/user/holding/currency/USD"))
        self.assertIsNotNone(state.n2i("//user/user/holding/good/paper"))
        self.assertIsNotNone(state.n2i("//user/user/holding/token"))
        self.assertIsNotNone(state.n2i("//user/user/holding/good/paper"))
        self.assertIsNotNone(state.n2i("//user/user/holding/good/paper"))

    def test_transactions_exchange(self):
        client_cli.main(args=["--name", "user",
                              "--script",
                              os.path.join(self.script_path,
                                           "ex_transactions"),
                              "--echo",
                              "--url",
                              self.url])

    def test_transactions_unr(self):
        client_cli.main(args=["--name", "user",
                              "--script",
                              os.path.join(self.script_path,
                                           "unr_transactions"),
                              "--echo",
                              "--url",
                              self.url])

        state = mktplace_state.MarketPlaceState(self.url)
        state.fetch()
        self.assertIsNone(state.n2i("//user"))
        self.assertIsNone(state.n2i("//user/user/account"))
        self.assertIsNone(state.n2i("//user/asset-type/currency"))
        self.assertIsNone(state.n2i("//user/asset-type/good"))
        self.assertIsNone(state.n2i("//user/asset/currency/USD"))
        self.assertIsNone(state.n2i("//user/asset/good/paper"))
        self.assertIsNone(state.n2i("//user/user/holding/currency/USD"))
        self.assertIsNone(state.n2i("//user/user/holding/good/paper"))
        self.assertIsNone(state.n2i("//user/user/holding/token"))
        self.assertIsNone(state.n2i("//user/user/holding/good/paper"))
        self.assertIsNone(state.n2i("//user/user/holding/good/paper"))

    @classmethod
    def tearDownClass(cls):
        if cls.vnm is not None:
            cls.vnm.shutdown()
            # currently nose2 offers no way to detect test failure -- so
            # always save the results
            if cls.vnm.create_result_archive(
                    "TestCommercialPaperScenarios.tar.gz"):
                print "Validator data and logs preserved in: " \
                      "TestCommercialPaperScenarios.tar.gz"
            else:
                print "No Validator data and logs to preserve."

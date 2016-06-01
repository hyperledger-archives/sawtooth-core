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

from integration import ENABLE_INTEGRATION_TESTS


@unittest.skipUnless(ENABLE_INTEGRATION_TESTS, "integration test")
class TestCommercialPaperScenarios(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vnm = None
        try:
            if 'TEST_VALIDATOR_URLS' in os.environ:
                cls.url = os.environ['TEST_VALIDATOR_URLS']
            else:
                vnm_config = defaultValidatorConfig.copy()
                if 'mktplace.transactions.market_place' not in \
                        vnm_config['TransactionFamilies']:
                    vnm_config['TransactionFamilies'].append(
                        'mktplace.transactions.market_place')
                vnm_config['LogLevel'] = 'DEBUG'
                cls.vnm = ValidatorNetworkManager(
                    httpPort=9500, udpPort=9600, cfg=vnm_config)
                cls.vnm.launch_network(5)
                # the url of the initial validator
                cls.url = cls.vnm.urls()[0] + '/'

            os.environ['CURRENCYHOME'] = os.path.join(
                os.path.dirname(__file__), "cp_scenarios")

            cls.scenarios_path = os.path.join(os.path.dirname(__file__),
                                              'cp_scenarios')
            client_cli.main(args=["--name", "mkt",
                                  "--script",
                                  os.path.join(cls.scenarios_path,
                                               "scenario_setup_1_mkt"),
                                  "--echo",
                                  "--url",
                                  cls.url])

            client_cli.main(
                args=["--name", "BANK-trader",
                      "--script",
                      os.path.join(os.path.dirname(__file__),
                                   "cp_scenarios",
                                   "scenario_setup_2_trader"),
                      "--echo",
                      "--url",
                      cls.url])

            client_cli.main(args=["--name", "BANK-agent",
                                  "--script",
                                  os.path.join(cls.scenarios_path,
                                               "scenario_setup_3_agent"),
                                  "--echo",
                                  "--url",
                                  cls.url])

            client_cli.main(
                args=["--name", "BANK-dealer",
                      "--script",
                      os.path.join(cls.scenarios_path,
                                   "scenario_setup_4_dealer"),
                      "--echo",
                      "--url",
                      cls.url])

            state = mktplace_state.MarketPlaceState(cls.url)
            state.fetch()
        except:
            if cls.vnm is not None:
                cls.vnm.shutdown()
            raise

    def test_scenario_setup(self):
        state = mktplace_state.MarketPlaceState(self.url)
        state.fetch()

        self.assertIsNotNone(state.n2i("//marketplace/asset/token"))
        self.assertIsNotNone(state.n2i("//mkt"))
        self.assertIsNotNone(state.n2i("//mkt/market/account"))
        self.assertIsNotNone(state.n2i("//mkt/asset-type/currency"))
        self.assertIsNotNone(state.n2i("//mkt/asset-type/commercialpaper"))
        self.assertIsNotNone(state.n2i("//mkt/asset/currency/USD"))
        self.assertIsNotNone(state.n2i("//mkt/asset/commercialpaper/note"))
        self.assertIsNotNone(state.n2i("//mkt/market/holding/currency/USD"))
        self.assertIsNotNone(state.n2i("//mkt/market/holding/token"))
        self.assertIsNotNone(state.n2i("//BANK-trader"))
        self.assertIsNotNone(state.n2i("//BANK-trader/USD"))
        self.assertIsNotNone(state.n2i("//BANK-trader/paper"))
        self.assertIsNotNone(state.n2i("//BANK-trader/holding/token"))
        self.assertIsNotNone(state.n2i("//BANK-agent"))
        self.assertIsNotNone(state.n2i("//BANK-agent/USD"))
        self.assertIsNotNone(state.n2i("//BANK-agent/paper"))
        self.assertIsNotNone(state.n2i("//BANK-agent/holding/token"))
        self.assertIsNotNone(state.n2i("//BANK-dealer"))
        self.assertIsNotNone(state.n2i("//BANK-dealer/USD"))
        self.assertIsNotNone(state.n2i("//BANK-dealer/paper"))
        self.assertIsNotNone(state.n2i("//BANK-dealer/holding/token"))

    def test_scenario_a(self):

        state = mktplace_state.MarketPlaceState(self.url)
        state.fetch()

        self.assertIsNotNone(state.n2i("//BANK-trader"))
        self.assertIsNotNone(state.n2i("//BANK-trader/USD"))
        self.assertIsNotNone(state.n2i("//BANK-trader/paper"))
        self.assertIsNotNone(state.n2i("//BANK-agent"))
        self.assertIsNotNone(state.n2i("//BANK-agent/USD"))
        self.assertIsNotNone(state.n2i("//BANK-agent/paper"))
        self.assertEquals(state.State[state.n2i("//BANK-trader/USD")]["count"],
                          1000000)
        self.assertEquals(state.State[state.n2i("//BANK-agent/USD")]["count"],
                          1000000)
        self.assertEquals(
            state.State[state.n2i("//BANK-trader/paper")]["count"], 10)
        self.assertEquals(
            state.State[state.n2i("//BANK-agent/paper")]["count"], 10)

        client_cli.main(
            args=["--name", "BANK-trader",
                  "--script", os.path.join(os.path.dirname(__file__),
                                           "cp_scenarios",
                                           "scenario_a_1_trader"),
                  "--echo",
                  "--url",
                  self.url])

        state = mktplace_state.MarketPlaceState(self.url)
        state.fetch()
        self.assertIsNotNone(state.n2i("//BANK-trader/offer-a"))

        client_cli.main(args=["--name", "BANK-agent",
                              "--script",
                              os.path.join(self.scenarios_path,
                                           "scenario_a_2_agent"),
                              "--echo",
                              "--url",
                              self.url])

        state = mktplace_state.MarketPlaceState(self.url)
        state.fetch()
        self.assertEquals(state.State[state.n2i("//BANK-trader/USD")]["count"],
                          900612)
        self.assertEquals(state.State[state.n2i("//BANK-agent/USD")]["count"],
                          1099388)
        self.assertEquals(
            state.State[state.n2i("//BANK-trader/paper")]["count"], 11)
        self.assertEquals(
            state.State[state.n2i("//BANK-agent/paper")]["count"], 9)

    def test_scenario_b(self):

        state = mktplace_state.MarketPlaceState(self.url)
        state.fetch()

        self.assertIsNotNone(state.n2i("//BANK-trader"))
        self.assertIsNotNone(state.n2i("//BANK-trader/USD"))
        self.assertIsNotNone(state.n2i("//BANK-trader/paper"))
        self.assertIsNotNone(state.n2i("//BANK-dealer"))
        self.assertIsNotNone(state.n2i("//BANK-dealer/USD"))
        self.assertIsNotNone(state.n2i("//BANK-dealer/paper"))

        self.assertIn("count", state.State[state.n2i("//BANK-trader/USD")])
        self.assertIn("count", state.State[state.n2i("//BANK-trader/paper")])
        self.assertIn("count", state.State[state.n2i("//BANK-dealer/USD")])
        self.assertIn("count", state.State[state.n2i("//BANK-dealer/paper")])

        trader_usd = state.State[state.n2i("//BANK-trader/USD")]["count"]
        trader_paper = state.State[state.n2i("//BANK-trader/paper")]["count"]
        dealer_usd = state.State[state.n2i("//BANK-dealer/USD")]["count"]
        dealer_paper = state.State[state.n2i("//BANK-dealer/paper")]["count"]

        client_cli.main(
            args=["--name", "BANK-trader",
                  "--script",
                  os.path.join(self.scenarios_path,
                               "scenario_b_1_trader"),
                  "--echo",
                  "--url",
                  self.url])

        state = mktplace_state.MarketPlaceState(self.url)
        state.fetch()

        self.assertIsNotNone(state.n2i("//BANK-trader/offer-b"))

        client_cli.main(
            args=["--name", "BANK-dealer",
                  "--script",
                  os.path.join(self.scenarios_path,
                               "scenario_b_2_dealer"),
                  "--echo",
                  "--url",
                  self.url])

        state = mktplace_state.MarketPlaceState(self.url)
        state.fetch()
        self.assertEquals(state.State[state.n2i("//BANK-trader/USD")]["count"],
                          trader_usd - 99388)
        self.assertEquals(state.State[state.n2i("//BANK-dealer/USD")]["count"],
                          dealer_usd + 99388)
        self.assertEquals(
            state.State[state.n2i("//BANK-trader/paper")]["count"],
            trader_paper + 1)
        self.assertEquals(
            state.State[state.n2i("//BANK-dealer/paper")]["count"],
            dealer_paper - 1)

    def test_scenario_c(self):

        state = mktplace_state.MarketPlaceState(self.url)
        state.fetch()

        self.assertIsNotNone(state.n2i("//BANK-trader"))
        self.assertIsNotNone(state.n2i("//BANK-trader/USD"))
        self.assertIsNotNone(state.n2i("//BANK-trader/paper"))
        self.assertIsNotNone(state.n2i("//BANK-dealer"))
        self.assertIsNotNone(state.n2i("//BANK-dealer/USD"))
        self.assertIsNotNone(state.n2i("//BANK-dealer/paper"))
        self.assertIsNotNone(state.n2i("//BANK-agent"))
        self.assertIsNotNone(state.n2i("//BANK-agent/USD"))
        self.assertIsNotNone(state.n2i("//BANK-agent/paper"))

        self.assertIn("count", state.State[state.n2i("//BANK-trader/USD")])
        self.assertIn("count", state.State[state.n2i("//BANK-trader/paper")])
        self.assertIn("count", state.State[state.n2i("//BANK-dealer/USD")])
        self.assertIn("count", state.State[state.n2i("//BANK-agent/USD")])

        trader_usd = state.State[state.n2i("//BANK-trader/USD")]["count"]
        trader_paper = state.State[state.n2i("//BANK-trader/paper")]["count"]
        dealer_usd = state.State[state.n2i("//BANK-dealer/USD")]["count"]
        agent_usd = state.State[state.n2i("//BANK-agent/USD")]["count"]

        client_cli.main(
            args=["--name", "BANK-trader",
                  "--script",
                  os.path.join(self.scenarios_path,
                               "scenario_c_1_trader"),
                  "--echo",
                  "--url",
                  self.url])

        state = mktplace_state.MarketPlaceState(self.url)
        state.fetch()

        self.assertIsNotNone(state.n2i("//BANK-trader/offer-c-trader"))

        client_cli.main(
            args=["--name", "BANK-dealer",
                  "--script",
                  os.path.join(self.scenarios_path,
                               "scenario_c_2_dealer"),
                  "--echo",
                  "--url",
                  self.url])

        state = mktplace_state.MarketPlaceState(self.url)
        state.fetch()

        self.assertIsNotNone(state.n2i("//BANK-dealer/paper-scenario-c"))
        self.assertIsNotNone(state.n2i("//BANK-dealer/offer-c-dealer"))
        self.assertEquals(
            state.State[state.n2i("//BANK-dealer/paper-scenario-c")]["count"],
            0)

        client_cli.main(args=["--name", "BANK-agent",
                              "--script",
                              os.path.join(self.scenarios_path,
                                           "scenario_c_3_agent"),
                              "--echo",
                              "--url",
                              self.url])

        state = mktplace_state.MarketPlaceState(self.url)
        state.fetch()

        self.assertIsNotNone(state.n2i("//BANK-agent/paper-scenario-c"))
        self.assertEquals(state.State[state.n2i("//BANK-trader/USD")]["count"],
                          trader_usd)
        self.assertEquals(state.State[state.n2i("//BANK-dealer/USD")]["count"],
                          dealer_usd - 99388)
        self.assertEquals(state.State[state.n2i("//BANK-agent/USD")]["count"],
                          agent_usd + 99388)
        self.assertEquals(
            state.State[state.n2i("//BANK-dealer/paper-scenario-c")]["count"],
            1)
        self.assertEquals(
            state.State[state.n2i("//BANK-agent/paper-scenario-c")]["count"],
            0)

        client_cli.main(
            args=["--name", "BANK-dealer",
                  "--script",
                  os.path.join(self.scenarios_path,
                               "scenario_c_4_dealer"),
                  "--echo",
                  "--url",
                  self.url])

        state = mktplace_state.MarketPlaceState(self.url)
        state.fetch()

        self.assertIsNotNone(state.n2i("//BANK-agent/paper-scenario-c"))
        self.assertEquals(state.State[state.n2i("//BANK-trader/USD")]["count"],
                          trader_usd - 99388)
        self.assertEquals(state.State[state.n2i("//BANK-dealer/USD")]["count"],
                          dealer_usd)
        self.assertEquals(state.State[state.n2i("//BANK-agent/USD")]["count"],
                          agent_usd + 99388)
        self.assertEquals(
            state.State[state.n2i("//BANK-trader/paper")]["count"],
            trader_paper + 1)
        self.assertEquals(
            state.State[state.n2i("//BANK-dealer/paper-scenario-c")]["count"],
            0)
        self.assertEquals(
            state.State[state.n2i("//BANK-agent/paper-scenario-c")]["count"],
            0)

    def test_scenario_d(self):

        state = mktplace_state.MarketPlaceState(self.url)
        state.fetch()

        self.assertIsNotNone(state.n2i("//BANK-trader"))
        self.assertIsNotNone(state.n2i("//BANK-trader/USD"))
        self.assertIsNotNone(state.n2i("//BANK-trader/paper"))
        self.assertIsNotNone(state.n2i("//BANK-agent"))
        self.assertIsNotNone(state.n2i("//BANK-agent/USD"))
        self.assertIsNotNone(state.n2i("//BANK-agent/paper"))

        self.assertIn("count", state.State[state.n2i("//BANK-trader/USD")])
        self.assertIn("count", state.State[state.n2i("//BANK-trader/paper")])
        self.assertIn("count", state.State[state.n2i("//BANK-agent/USD")])
        self.assertIn("count", state.State[state.n2i("//BANK-agent/paper")])

        trader_usd = state.State[state.n2i("//BANK-trader/USD")]["count"]
        trader_paper = state.State[state.n2i("//BANK-trader/paper")]["count"]
        agent_usd = state.State[state.n2i("//BANK-agent/USD")]["count"]
        agent_paper = state.State[state.n2i("//BANK-agent/paper")]["count"]

        client_cli.main(
            args=["--name", "BANK-trader",
                  "--script",
                  os.path.join(self.scenarios_path,
                               "scenario_d_1_trader"),
                  "--echo",
                  "--url",
                  self.url])

        state = mktplace_state.MarketPlaceState(self.url)
        state.fetch()

        self.assertIsNotNone(state.n2i("//BANK-trader/offer-d"))

        client_cli.main(args=["--name", "BANK-agent",
                              "--script",
                              os.path.join(self.scenarios_path,
                                           "scenario_d_2_agent"),
                              "--url",
                              self.url])

        state = mktplace_state.MarketPlaceState(self.url)
        state.fetch()
        self.assertEquals(state.State[state.n2i("//BANK-trader/USD")]["count"],
                          trader_usd + 100000)
        self.assertEquals(state.State[state.n2i("//BANK-agent/USD")]["count"],
                          agent_usd - 100000)
        self.assertEquals(
            state.State[state.n2i("//BANK-trader/paper")]["count"],
            trader_paper - 1)
        self.assertEquals(
            state.State[state.n2i("//BANK-agent/paper")]["count"],
            agent_paper + 1)

    @classmethod
    def tearDownClass(cls):
        if cls.vnm is not None:
            cls.vnm.shutdown()
            # currently nose2 offers no way to detect test failures here.
            # so we always save the data.
            if cls.vnm.create_result_archive(
                    "TestCommercialPaperScenarios.tar.gz"):
                print "Validator data and logs preserved in: " \
                      "TestCommercialPaperScenarios.tar.gz"
            else:
                print "No Validator data and logs to preserve."

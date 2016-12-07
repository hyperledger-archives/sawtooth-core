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

RUN_TEST_SUITES = True \
    if os.environ.get("RUN_TEST_SUITES", False) == "1" else False


@unittest.skipUnless(RUN_TEST_SUITES, "Must be run in a test suites")
class TestCommercialPaperScenarios(unittest.TestCase):
    def setUp(self):
        self.save_environ = os.environ.copy()

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.save_environ)

    @classmethod
    def setUpClass(cls):
        cls.vnm = None
        try:
            cls.url = "http://localhost:8800"

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

        self.assertIsNotNone(state.n2i("//marketplace/asset/token",
                                       'Asset'))
        self.assertIsNotNone(state.n2i("//mkt", 'Participant'))
        self.assertIsNotNone(state.n2i("//mkt/market/account", 'Account'))
        self.assertIsNotNone(state.n2i("//mkt/asset-type/currency",
                                       'AssetType'))
        self.assertIsNotNone(state.n2i("//mkt/asset-type/commercialpaper",
                                       'AssetType'))
        self.assertIsNotNone(state.n2i("//mkt/asset/currency/USD", 'Asset'))
        self.assertIsNotNone(state.n2i("//mkt/asset/commercialpaper/note",
                                       'Asset'))
        self.assertIsNotNone(state.n2i("//mkt/market/holding/currency/USD",
                                       'Holding'))
        self.assertIsNotNone(state.n2i("//mkt/market/holding/token",
                                       'Holding'))
        self.assertIsNotNone(state.n2i("//BANK-trader", 'Participant'))
        self.assertIsNotNone(state.n2i("//BANK-trader/USD", 'Holding'))
        self.assertIsNotNone(state.n2i("//BANK-trader/paper", 'Holding'))
        self.assertIsNotNone(state.n2i("//BANK-trader/holding/token",
                                       'Holding'))
        self.assertIsNotNone(state.n2i("//BANK-agent", 'Participant'))
        self.assertIsNotNone(state.n2i("//BANK-agent/USD", 'Holding'))
        self.assertIsNotNone(state.n2i("//BANK-agent/paper", 'Holding'))
        self.assertIsNotNone(state.n2i("//BANK-agent/holding/token",
                                       'Holding'))
        self.assertIsNotNone(state.n2i("//BANK-dealer", 'Participant'))
        self.assertIsNotNone(state.n2i("//BANK-dealer/USD",
                                       'Holding'))
        self.assertIsNotNone(state.n2i("//BANK-dealer/paper",
                                       'Holding'))
        self.assertIsNotNone(state.n2i("//BANK-dealer/holding/token",
                                       'Holding'))

    def test_scenario_a(self):

        state = mktplace_state.MarketPlaceState(self.url)
        state.fetch()

        self.assertIsNotNone(state.n2i("//BANK-trader", 'Participant'))
        self.assertIsNotNone(state.n2i("//BANK-trader/USD", 'Holding'))
        self.assertIsNotNone(state.n2i("//BANK-trader/paper", 'Holding'))
        self.assertIsNotNone(state.n2i("//BANK-agent", 'Participant'))
        self.assertIsNotNone(state.n2i("//BANK-agent/USD", 'Holding'))
        self.assertIsNotNone(state.n2i("//BANK-agent/paper", 'Holding'))
        self.assertEquals(state.State[state.n2i("//BANK-trader/USD",
                                                'Holding')]["count"], 1000000)
        self.assertEquals(state.State[state.n2i("//BANK-agent/USD",
                                                'Holding')]["count"], 1000000)
        self.assertEquals(
            state.State[state.n2i("//BANK-trader/paper",
                                  'Holding')]["count"], 10)
        self.assertEquals(
            state.State[state.n2i("//BANK-agent/paper",
                                  'Holding')]["count"], 10)

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
        self.assertIsNotNone(state.n2i("//BANK-trader/offer-a",
                                       'ExchangeOffer'))

        client_cli.main(args=["--name", "BANK-agent",
                              "--script",
                              os.path.join(self.scenarios_path,
                                           "scenario_a_2_agent"),
                              "--echo",
                              "--url",
                              self.url])

        state = mktplace_state.MarketPlaceState(self.url)
        state.fetch()
        self.assertEquals(state.State[state.n2i("//BANK-trader/USD",
                                                'Holding')]["count"], 900612)
        self.assertEquals(state.State[state.n2i("//BANK-agent/USD",
                                                'Holding')]["count"], 1099388)
        self.assertEquals(
            state.State[state.n2i("//BANK-trader/paper",
                                  'Holding')]["count"], 11)
        self.assertEquals(
            state.State[state.n2i("//BANK-agent/paper",
                                  "Holding")]["count"], 9)

    def test_scenario_b(self):

        state = mktplace_state.MarketPlaceState(self.url)
        state.fetch()

        self.assertIsNotNone(state.n2i("//BANK-trader", 'Participant'))
        self.assertIsNotNone(state.n2i("//BANK-trader/USD", "Holding"))
        self.assertIsNotNone(state.n2i("//BANK-trader/paper", "Holding"))
        self.assertIsNotNone(state.n2i("//BANK-dealer", "Participant"))
        self.assertIsNotNone(state.n2i("//BANK-dealer/USD", "Holding"))
        self.assertIsNotNone(state.n2i("//BANK-dealer/paper", "Holding"))

        self.assertIn("count", state.State[state.n2i("//BANK-trader/USD",
                                                     "Holding")])
        self.assertIn("count", state.State[state.n2i("//BANK-trader/paper",
                                                     "Holding")])
        self.assertIn("count", state.State[state.n2i("//BANK-dealer/USD",
                                                     "Holding")])
        self.assertIn("count", state.State[state.n2i("//BANK-dealer/paper",
                                                     "Holding")])

        trader_usd = state.State[state.n2i("//BANK-trader/USD",
                                           'Holding')]["count"]
        trader_paper = state.State[state.n2i("//BANK-trader/paper",
                                             "Holding")]["count"]
        dealer_usd = state.State[state.n2i("//BANK-dealer/USD",
                                           "Holding")]["count"]
        dealer_paper = state.State[state.n2i("//BANK-dealer/paper",
                                             "Holding")]["count"]

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

        self.assertIsNotNone(state.n2i("//BANK-trader/offer-b",
                                       'ExchangeOffer'))

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
        self.assertEquals(state.State[state.n2i("//BANK-trader/USD",
                                                "Holding")]["count"],
                          trader_usd - 99388)
        self.assertEquals(state.State[state.n2i("//BANK-dealer/USD",
                                                "Holding")]["count"],
                          dealer_usd + 99388)
        self.assertEquals(
            state.State[state.n2i("//BANK-trader/paper", "Holding")]["count"],
            trader_paper + 1)
        self.assertEquals(
            state.State[state.n2i("//BANK-dealer/paper",
                                  "Holding")]["count"],
            dealer_paper - 1)

    def test_scenario_c(self):

        state = mktplace_state.MarketPlaceState(self.url)
        state.fetch()

        self.assertIsNotNone(state.n2i("//BANK-trader", "Participant"))
        self.assertIsNotNone(state.n2i("//BANK-trader/USD", "Holding"))
        self.assertIsNotNone(state.n2i("//BANK-trader/paper", "Holding"))
        self.assertIsNotNone(state.n2i("//BANK-dealer", "Participant"))
        self.assertIsNotNone(state.n2i("//BANK-dealer/USD", "Holding"))
        self.assertIsNotNone(state.n2i("//BANK-dealer/paper", "Holding"))
        self.assertIsNotNone(state.n2i("//BANK-agent", "Participant"))
        self.assertIsNotNone(state.n2i("//BANK-agent/USD", "Holding"))
        self.assertIsNotNone(state.n2i("//BANK-agent/paper", "Holding"))

        self.assertIn("count", state.State[state.n2i("//BANK-trader/USD",
                                                     "Holding")])
        self.assertIn("count", state.State[state.n2i("//BANK-trader/paper",
                                                     "Holding")])
        self.assertIn("count", state.State[state.n2i("//BANK-dealer/USD",
                                                     "Holding")])
        self.assertIn("count", state.State[state.n2i("//BANK-agent/USD",
                                                     "Holding")])

        trader_usd = state.State[state.n2i("//BANK-trader/USD",
                                           "Holding")]["count"]
        trader_paper = state.State[state.n2i("//BANK-trader/paper",
                                             "Holding")]["count"]
        dealer_usd = state.State[state.n2i("//BANK-dealer/USD",
                                           "Holding")]["count"]
        agent_usd = state.State[state.n2i("//BANK-agent/USD",
                                          "Holding")]["count"]

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

        self.assertIsNotNone(state.n2i("//BANK-trader/offer-c-trader",
                                       'ExchangeOffer'))

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

        self.assertIsNotNone(state.n2i("//BANK-dealer/paper-scenario-c",
                                       'Holding'))
        self.assertIsNotNone(state.n2i("//BANK-dealer/offer-c-dealer",
                                       'ExchangeOffer'))
        self.assertEquals(
            state.State[state.n2i("//BANK-dealer/paper-scenario-c",
                                  'Holding')]["count"], 0)

        client_cli.main(args=["--name", "BANK-agent",
                              "--script",
                              os.path.join(self.scenarios_path,
                                           "scenario_c_3_agent"),
                              "--echo",
                              "--url",
                              self.url])

        state = mktplace_state.MarketPlaceState(self.url)
        state.fetch()

        self.assertIsNotNone(
            state.n2i("//BANK-agent/paper-scenario-c", 'Holding'))
        self.assertEquals(state.State[state.n2i("//BANK-trader/USD",
                                                'Holding')]["count"],
                          trader_usd)
        self.assertEquals(
            state.State[state.n2i("//BANK-dealer/USD",
                                  "Holding")]["count"], dealer_usd - 99388)
        self.assertEquals(state.State[state.n2i("//BANK-agent/USD",
                                                "Holding")]["count"],
                          agent_usd + 99388)
        self.assertEquals(
            state.State[state.n2i("//BANK-dealer/paper-scenario-c",
                                  "Holding")]["count"], 1)
        self.assertEquals(
            state.State[state.n2i("//BANK-agent/paper-scenario-c",
                                  "Holding")]["count"], 0)

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

        self.assertIsNotNone(state.n2i("//BANK-agent/paper-scenario-c",
                                       'Holding'))
        self.assertEquals(
            state.State[state.n2i("//BANK-trader/USD",
                                  "Holding")]["count"], trader_usd - 99388)
        self.assertEquals(state.State[state.n2i("//BANK-dealer/USD",
                                                "Holding")]["count"],
                          dealer_usd)
        self.assertEquals(
            state.State[state.n2i("//BANK-agent/USD", "Holding")]["count"],
            agent_usd + 99388)
        self.assertEquals(
            state.State[state.n2i("//BANK-trader/paper", "Holding")]["count"],
            trader_paper + 1)
        self.assertEquals(
            state.State[state.n2i("//BANK-dealer/paper-scenario-c",
                                  "Holding")]["count"], 0)
        self.assertEquals(
            state.State[state.n2i("//BANK-agent/paper-scenario-c",
                                  "Holding")]["count"], 0)

    def test_scenario_d(self):

        state = mktplace_state.MarketPlaceState(self.url)
        state.fetch()

        self.assertIsNotNone(state.n2i("//BANK-trader", 'Participant'))
        self.assertIsNotNone(state.n2i("//BANK-trader/USD", 'Holding'))
        self.assertIsNotNone(state.n2i("//BANK-trader/paper", 'Holding'))
        self.assertIsNotNone(state.n2i("//BANK-agent", 'Participant'))
        self.assertIsNotNone(state.n2i("//BANK-agent/USD", "Holding"))
        self.assertIsNotNone(state.n2i("//BANK-agent/paper", 'Holding'))

        self.assertIn("count", state.State[state.n2i("//BANK-trader/USD",
                                                     'Holding')])
        self.assertIn("count", state.State[state.n2i("//BANK-trader/paper",
                                                     "Holding")])
        self.assertIn("count", state.State[state.n2i("//BANK-agent/USD",
                                                     'Holding')])
        self.assertIn("count", state.State[state.n2i("//BANK-agent/paper",
                                                     "Holding")])

        trader_usd = state.State[state.n2i("//BANK-trader/USD",
                                           'Holding')]["count"]
        trader_paper = state.State[state.n2i("//BANK-trader/paper",
                                             'Holding')]["count"]
        agent_usd = state.State[state.n2i("//BANK-agent/USD",
                                          'Holding')]["count"]
        agent_paper = state.State[state.n2i("//BANK-agent/paper",
                                            'Holding')]["count"]

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

        self.assertIsNotNone(state.n2i("//BANK-trader/offer-d",
                                       'ExchangeOffer'))

        client_cli.main(args=["--name", "BANK-agent",
                              "--script",
                              os.path.join(self.scenarios_path,
                                           "scenario_d_2_agent"),
                              "--url",
                              self.url])

        state = mktplace_state.MarketPlaceState(self.url)
        state.fetch()
        self.assertEquals(state.State[state.n2i("//BANK-trader/USD",
                                                'Holding')]["count"],
                          trader_usd + 100000)
        self.assertEquals(state.State[state.n2i("//BANK-agent/USD",
                                                'Holding')]["count"],
                          agent_usd - 100000)
        self.assertEquals(
            state.State[state.n2i("//BANK-trader/paper", 'Holding')]["count"],
            trader_paper - 1)
        self.assertEquals(
            state.State[state.n2i("//BANK-agent/paper", "Holding")]["count"],
            agent_paper + 1)

    @classmethod
    def tearDownClass(cls):
        if cls.vnm is not None:
            cls.vnm.shutdown(archive_name="TestCommercialPaperScenarios")
        else:
            print "No Validator data and logs to preserve."

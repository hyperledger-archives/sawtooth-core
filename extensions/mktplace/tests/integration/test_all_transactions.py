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
from txnintegration.validator_network_manager import get_default_vnm

ENABLE_INTEGRATION_TESTS = False
if os.environ.get("ENABLE_INTEGRATION_TESTS", False) == "1":
    ENABLE_INTEGRATION_TESTS = True


@unittest.skipUnless(ENABLE_INTEGRATION_TESTS, "integration test")
class TestAllTransactions(unittest.TestCase):
    def setUp(self):
        self.save_environ = os.environ.copy()

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.save_environ)

    @classmethod
    def setUpClass(cls):
        cls.vnm = None
        try:
            if 'TEST_VALIDATOR_URLS' in os.environ:
                urls = (os.environ['TEST_VALIDATOR_URLS']).split(",")
                cls.url = urls[0]
            else:
                families = ['mktplace.transactions.market_place']
                overrides = {
                    'InitialWaitTime': 1,
                    'TargetWaitTime': 1,
                    "TransactionFamilies": families,
                }
                cls.vnm = get_default_vnm(1, overrides=overrides)
                cls.vnm.do_genesis()
                cls.vnm.launch()
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

    def transactions_reg(self):
        client_cli.main(args=['--name', 'mkt',
                              '--script',
                              os.path.join(self.script_path,
                                           'reg_mkt_transactions'),
                              '--echo', '--url',
                              self.url])

        client_cli.main(args=["--name", "alice",
                              "--script",
                              os.path.join(self.script_path,
                                           "reg_alice_transactions"),
                              "--echo",
                              "--url",
                              self.url])

        client_cli.main(args=["--name", "bob",
                              "--script",
                              os.path.join(self.script_path,
                                           "reg_bob_transactions"),
                              "--echo",
                              "--url",
                              self.url])

        state = mktplace_state.MarketPlaceState(self.url)
        state.fetch()
        self.assertIsNotNone(state.n2i("//alice", 'Participant'))
        self.assertIsNotNone(state.n2i("//mkt", 'Participant'))
        self.assertIsNotNone(state.n2i("//bob", 'Participant'))
        self.assertIsNotNone(state.n2i("//alice/account",
                                       'Account'))
        self.assertIsNotNone(state.n2i("//mkt/asset-type/currency",
                                       'AssetType'))
        self.assertIsNotNone(state.n2i("//mkt/asset-type/cookie",
                                       'AssetType'))
        self.assertIsNotNone(state.n2i("//mkt/asset/currency/USD",
                                       'Asset'))

        self.assertIsNotNone(state.n2i("//alice/USD",
                                       'Holding'))
        self.assertIsNotNone(state.n2i("//alice/jars/choc_chip",
                                       'Holding'))
        self.assertIsNotNone(state.n2i("//alice/holding/token",
                                       'Holding'))
        self.assertIsNotNone(state.n2i("//bob/USD", "Holding"))
        self.assertIsNotNone(state.n2i("//bob/jars/choc_chip", "Holding"))

    def transactions_exchange(self):
        client_cli.main(args=["--name", "alice",
                              "--script",
                              os.path.join(self.script_path,
                                           "ex_alice_transactions"),
                              "--echo",
                              "--url",
                              self.url])
        state = mktplace_state.MarketPlaceState(self.url)
        state.fetch()
        self.assertEqual(
            state.State[state.n2i(
                "//bob/USD", "Holding")]['count'], 1024)
        self.assertEqual(
            state.State[state.n2i(
                "//bob/batches/choc_chip001", "Holding")]['count'], 12)
        self.assertEqual(
            state.State[state.n2i(
                "//bob/holding/token", "Holding")]['count'], 1)
        self.assertEqual(
            state.State[state.n2i(
                "//bob/jars/choc_chip",
                "Holding"
            )]['count'], 0)
        self.assertEqual(
            state.State[state.n2i(
                "//alice/USD",
                "Holding"
            )]['count'],
            976)
        self.assertEqual(
            state.State[state.n2i(
                "//alice/holding/token",
                "Holding"
            )]['count'],
            1)
        self.assertEqual(
            state.State[state.n2i(
                "//alice/jars/choc_chip",
                "Holding"
            )]['count'],
            12)

    def transactions_unr(self):
        client_cli.main(args=["--name", "alice",
                              "--script",
                              os.path.join(self.script_path,
                                           "unr_alice_transactions"),
                              "--echo",
                              "--url",
                              self.url])

        state = mktplace_state.MarketPlaceState(self.url)
        state.fetch()
        self.assertIsNone(state.n2i("//alice", 'Participant'))
        self.assertIsNone(state.n2i("//alice/jars/choc_chip",
                                    "Holding"))
        self.assertIsNone(state.n2i("//alice/USD",
                                    "Holding"))
        self.assertIsNone(state.n2i("//alice/holding/token",
                                    "Holding"))
        self.assertIsNone(state.n2i("//alice/account", "Account"))

    def test_all_transactions(self):
        self.transactions_reg()
        self.transactions_exchange()
        self.transactions_unr()

    @classmethod
    def tearDownClass(cls):
        if cls.vnm is not None:
            cls.vnm.shutdown(archive_name="TestCommercialPaperScenarios")
        else:
            print "No Validator data and logs to preserve."

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
class TestAllTransactions(unittest.TestCase):
    def __init__(self, test_name, urls=None):
        super(TestAllTransactions, self).__init__(test_name)
        self.urls = urls
        try:
            self.url = self.urls[0] + '/'
        except:
            raise

    def setUp(self):
        self.save_environ = os.environ.copy()
        os.environ['CURRENCYHOME'] = os.path.join(
            os.path.dirname(__file__), "all_transactions")

        self.script_path = os.path.join(os.path.dirname(__file__),
                                        'all_transactions')
        state = mktplace_state.MarketPlaceState(self.url)
        state.fetch()

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.save_environ)

    def transactions_reg(self):
        client_cli.main(args=['--name', 'mkt_all',
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
        self.assertIsNotNone(state.n2i("//mkt_all", 'Participant'))
        self.assertIsNotNone(state.n2i("//bob", 'Participant'))
        self.assertIsNotNone(state.n2i("//alice/account",
                                       'Account'))
        self.assertIsNotNone(state.n2i("//mkt_all/asset-type/currency",
                                       'AssetType'))
        self.assertIsNotNone(state.n2i("//mkt_all/asset-type/cookie",
                                       'AssetType'))
        self.assertIsNotNone(state.n2i("//mkt_all/asset/currency/USD",
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

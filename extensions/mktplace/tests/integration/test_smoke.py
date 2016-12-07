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
import traceback
import unittest
import random
import time

from sawtooth_signing import pbct_nativerecover as signing
from mktplace import mktplace_state
from mktintegration.actor import MktActor
from txnintegration.utils import Progress
from txnintegration.utils import read_key_file
from txnintegration.utils import TimeOut
from txnintegration.utils import write_key_file

RUN_TEST_SUITES = True \
    if os.environ.get("RUN_TEST_SUITES", False) == "1" else False


class MktPlaceLoad(object):
    def __init__(self, num_traders, iterations, urls, test_dir):
        self.Actors = []
        self.state = None
        self.count = num_traders
        self.urls = urls
        self.iterations = iterations
        self.testDir = test_dir

    def wait_for_transaction_commits(self):
        to = TimeOut(120)
        txn_cnt = 1
        with Progress("Waiting for transactions to commit") as p:
            while not to() and txn_cnt > 0:
                p.step()
                time.sleep(1)
                txn_cnt = 0
                for a in self.Actors:
                    txn_cnt += a.has_uncommitted_transactions()

        if txn_cnt != 0:
            for a in self.Actors:
                if len(a.transactions) != 0:
                    print "Uncommitted transactions: ", a.Name, a.transactions

            raise Exception("{} transactions failed to commit in {}s".format(
                txn_cnt, to.WaitTime))

    def setup(self):
        self.state = mktplace_state.MarketPlaceState(self.urls[0])

        with Progress("Creating participants") as p:
            for i in range(0, self.count):
                name = "actor-{}".format(i)
                keyfile = os.path.join(self.testDir, "{}.wif".format(name))
                if os.path.exists(keyfile):
                    key = read_key_file(keyfile)
                else:
                    key = signing.encode_privkey(
                        signing.generate_privkey(), 'wif')
                    write_key_file(keyfile, key)

                url = self.urls[random.randint(0, len(self.urls) - 1)]
                a = MktActor(name, url, key)
                self.Actors.append(a)
                p.step()

        with Progress("Registering actors assets") as p:
            for a in self.Actors:
                # create assets
                a.register_asset(a.Name + "-asset")
                p.step()

        self.wait_for_transaction_commits()

        with Progress("Registering holdings") as p:
            for a in self.Actors:
                a.update()
                a.offers = []
                for a2 in self.Actors:
                    count = 0
                    if a is a2:
                        # for each iteration we need 1 to pay with and 1 to
                        # give
                        count = 2 * self.count * self.iterations
                    for ast in a2.assets.keys():
                        a.register_holding(ast, count)
                p.step()

        self.wait_for_transaction_commits()

    def run(self):
        # pylint: disable=too-many-nested-blocks
        try:
            rem = 0
            for a in self.Actors:
                a.iteration = 0
                rem += 1
            self.state.fetch()

            to = TimeOut(180)

            while rem != 0 and not to():
                for a in self.Actors:
                    a.update()
                    if (a.iteration < self.iterations and not
                            a.has_uncommitted_transactions()):
                        a.iteration += 1
                        for a2 in self.Actors:
                            if a is not a2:
                                for ast in a.assets.keys(
                                ):  # my assets (paying with)
                                    for ast2 in a2.assets.keys(
                                    ):  # Their assets (purchasing)
                                        txn_id = a.register_exchange_offer(
                                            ast2, 1, ast, 1)
                                        a2.offers.append(txn_id)
                                        print "{} Offering {} for {} txn: " \
                                              "{}".format(a.Name, ast2, ast,
                                                          txn_id)

                for a in self.Actors:
                    # Find any exchange offers for one of my assets.
                    if not a.has_uncommitted_transactions():
                        for ast, astId in a.assets.iteritems():
                            by_type = mktplace_state.Filters.matchtype(
                                'Holding')
                            by_asset = mktplace_state.Filters.matchvalue(
                                'asset', astId)
                            holding_ids = self.state.lambdafilter(
                                by_type, by_asset)

                            filters = [mktplace_state.Filters.offers(),
                                       mktplace_state.Filters.references(
                                           'input', holding_ids)]
                            offerids = a.state.lambdafilter(*filters)
                            for o in offerids:
                                if o in a.state.State and \
                                        o in a.offers:
                                    txn = a.exchange(o)
                                    a.offers.remove(o)
                                    print "{} accepting offer: {} with txn: " \
                                          "{}".format(a.Name, o, txn)

                self.state.fetch()
                for a in self.Actors:
                    a.update()
                rem = 0
                transactions = []
                for a in self.Actors:
                    if a.iteration != self.iterations:
                        rem += 1
                    transactions += a.transactions

                filters = [mktplace_state.Filters.offers()]
                offer_ids = self.state.lambdafilter(*filters)
                print "Agents remaining: {}, offers remaining: {}, " \
                      "unvalidated transactions: {}" \
                    .format(rem, len(offer_ids), transactions)
                rem += len(offer_ids) + len(transactions)
                if rem:
                    time.sleep(1)

            if to():
                for a in self.Actors:
                    if len(a.transactions) != 0:
                        print "Uncommitted transactions: ", a.Name, \
                            a.transactions
                raise Exception(
                    "Failed to create all exchangeoffers and accept all "
                    "exchanges in {}s ".format(to.WaitTime))

        except Exception as e:
            print "Exception: ", e
            raise

        self.wait_for_transaction_commits()

    def validate(self):
        print "Validating Marketplace State."
        self.state.fetch()

        # for each iteration each agent is paid one and pays for another.
        expected_count = self.iterations * 2

        filters = [mktplace_state.Filters.holdings()]
        holding_ids = self.state.lambdafilter(*filters)
        for holding_id in holding_ids:
            holding = self.state.State[holding_id]
            if holding['count'] != expected_count:
                print "Incorrect holding value: {0:<8} {1} {2}".format(
                    holding['count'], self.state.i2n(holding_id), holding_id)
            assert holding['count'] == expected_count


@unittest.skipUnless(RUN_TEST_SUITES, "Must be run in a test suites")
class TestSmoke(unittest.TestCase):
    def __init__(self, test_name, urls=None, data_dir=None):
        super(TestSmoke, self).__init__(test_name)
        self.urls = urls
        self.data_dir = data_dir

    def test_mktplace_load(self):
        try:
            print "Testing transaction load."
            test_case = MktPlaceLoad(num_traders=5,
                                     iterations=1,
                                     urls=self.urls,
                                     test_dir=self.data_dir)
            test_case.setup()
            test_case.run()
            test_case.validate()

        finally:
            print "No Validator data and logs to preserve."

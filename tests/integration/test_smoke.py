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

import pybitcointools

from mktplace import mktplace_state
from mktintegration.actor import MktActor
from txnintegration.utils import Progress
from txnintegration.utils import read_key_file
from txnintegration.utils import TimeOut
from txnintegration.utils import write_key_file
from txnintegration.validator_network_manager import ValidatorNetworkManager
from txnintegration.validator_network_manager import defaultValidatorConfig

ENABLE_INTEGRATION_TESTS = False
if os.environ.get("ENABLE_INTEGRATION_TESTS", False) == "1":
    ENABLE_INTEGRATION_TESTS = True


class MktPlaceLoad:
    def __init__(self, numTraders, iterations, urls, testDir):
        self.Actors = []
        self.state = None
        self.count = numTraders
        self.urls = urls
        self.iterations = iterations
        self.testDir = testDir

    def wait_for_transaction_commits(self):
        to = TimeOut(120)
        txnCnt = 1
        with Progress("Waiting for transactions to commit") as p:
            while not to() and txnCnt > 0:
                p.step()
                time.sleep(1)
                txnCnt = 0
                for a in self.Actors:
                    txnCnt += a.has_uncommitted_transactions()

        if txnCnt != 0:
            for a in self.Actors:
                if len(a.transactions) != 0:
                    print "Uncommitted transactions: ", a.Name, a.transactions

            raise Exception("{} transactions failed to commit in {}s".format(
                txnCnt, to.WaitTime))

    def setup(self):
        self.state = mktplace_state.MarketPlaceState(self.urls[0])

        with Progress("Creating participants") as p:
            for i in range(0, self.count):
                name = "actor-{}".format(i)
                keyfile = os.path.join(self.testDir, "{}.wif".format(name))
                if os.path.exists(keyfile):
                    key = read_key_file(keyfile)
                else:
                    key = pybitcointools.encode_privkey(
                        pybitcointools.random_key(), 'wif')
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
                    if (a.iteration < self.iterations
                            and not a.has_uncommitted_transactions()):
                        a.iteration += 1
                        for a2 in self.Actors:
                            if a is not a2:
                                for ast in a.assets.keys(
                                ):  # my assets (paying with)
                                    for ast2 in a2.assets.keys(
                                    ):  # Their assets (purchasing)
                                        txnId = a.register_exchange_offer(
                                            ast2, 1, ast, 1
                                        )  # create exchange offer
                                        print "{} Offering {} for {} txn: " \
                                              "{}".format(a.Name, ast2, ast,
                                                          txnId)

                for a in self.Actors:
                    # Find any exchange offers for one of my assets.
                    if not a.has_uncommitted_transactions():
                        for ast, astId in a.assets.iteritems():
                            bytype = mktplace_state.Filters.matchtype(
                                'Holding')
                            byasset = mktplace_state.Filters.matchvalue(
                                'asset', astId)
                            holdingids = self.state.lambdafilter(
                                bytype, byasset)

                            filters = [mktplace_state.Filters.offers(),
                                       mktplace_state.Filters.references(
                                           'input', holdingids)]
                            offerids = a.state.lambdafilter(*filters)
                            for o in offerids:
                                if o in a.state.State:  # it is possible that
                                    # the block
                                    # with this offer is not at this
                                    # actors validator yet.
                                    txn = a.exchange(o)
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
                offerIds = self.state.lambdafilter(*filters)
                print "Agents remaining: {}, offers remaining: {}, " \
                      "unvalidated transactions: {}" \
                    .format(rem, len(offerIds), transactions)
                rem += len(offerIds) + len(transactions)
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
            raise e

        self.wait_for_transaction_commits()

    def validate(self):
        print "Validating Marketplace State."
        self.state.fetch()

        # for each iteration each agent is paid one and pays for another.
        expectedCount = self.iterations * 2

        filters = [mktplace_state.Filters.holdings()]
        holdingIds = self.state.lambdafilter(*filters)
        for holdingId in holdingIds:
            holding = self.state.State[holdingId]
            if holding['count'] != expectedCount:
                print "Incorrect holding value: {0:<8} {1} {2}".format(
                    holding['count'], self.state.i2n(holdingId), holdingId)
            assert holding['count'] == expectedCount


class TestSmoke(unittest.TestCase):
    @unittest.skipUnless(ENABLE_INTEGRATION_TESTS, "integration test")
    def test_mktplace_load(self):
        vnm = None
        try:
            print "Launching validator network."
            vnm_config = defaultValidatorConfig.copy()
            vnm_config['TransactionFamilies'].append(
                'mktplace.transactions.market_place')
            vnm = ValidatorNetworkManager(
                httpPort=9500, udpPort=9600, cfg=vnm_config)
            vnm.launch_network(5)

            print "Testing transaction load."
            testCase = MktPlaceLoad(numTraders=5,
                                    iterations=1,
                                    urls=vnm.urls(),
                                    testDir=vnm.DataDir)
            testCase.setup()
            testCase.run()
            testCase.validate()

            vnm.shutdown()
        except:
            print "Exception encountered in test case."
            traceback.print_exc()
            if vnm:
                vnm.shutdown()
                if vnm.create_result_archive("TestSmokeResults.tar.gz"):
                    print "Validator data and logs preserved in: " \
                          "TestSmokeResults.tar.gz"
                else:
                    print "No Validator data and logs to preserve."

            raise

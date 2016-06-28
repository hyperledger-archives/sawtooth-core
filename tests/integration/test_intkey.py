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

import random
import traceback
import unittest
import os
import time
from twisted.web import http

from txnintegration.utils import generate_private_key
from txnintegration.utils import Progress
from txnintegration.utils import TimeOut
from txnintegration.integer_key_client import IntegerKeyClient
from txnintegration.integer_key_communication import MessageException
from txnintegration.integer_key_state import IntegerKeyState

ENABLE_INTEGRATION_TESTS = False
if os.environ.get("ENABLE_INTEGRATION_TESTS", False) == "1":
    ENABLE_INTEGRATION_TESTS = True


defaultBaseLineConfig = {u'UrlList': [],
                         u"Count": 10,
                         u"Interval": 2}


class IntKeyLoadTest(object):
    def __init__(self):
        pass

    def _get_client(self):
        return self.clients[random.randint(0, len(self.clients) - 1)]

    def _has_uncommitted_transactions(self):
        remaining = []
        for t in self.transactions:
            status = self.clients[0].headrequest('/transaction/{0}'.format(t))
            if status != http.OK:
                remaining.append(t)

        self.transactions = remaining
        return len(self.transactions)

    def _wait_for_transaction_commits(self):
        to = TimeOut(900)
        txnCnt = len(self.transactions)
        with Progress("Waiting for %s transactions to commit" % (txnCnt)) as p:
            while not to() and txnCnt > 0:
                p.step()
                time.sleep(1)
                self._has_uncommitted_transactions()
                txnCnt = len(self.transactions)

        if txnCnt != 0:
            if len(self.transactions) != 0:
                print "Uncommitted transactions: ", self.transactions
            raise Exception("{} transactions failed to commit in {}s".format(
                txnCnt, to.WaitTime))

    def setup(self, urls):
        self.GlobalStore = {}
        self.RunningUrlList = urls
        self.GlobalKeys = []
        self.transactions = []
        self.lastKeyTxn = {}
        self.clients = []
        self.state = IntegerKeyState(urls[0])

        with Progress("Creating clients") as p:
            print "Creating clients"
            for u in self.RunningUrlList:
                try:
                    key = generate_private_key()
                    self.clients.append(IntegerKeyClient(u, keystring=key))
                    p.step()
                except MessageException:
                    print "Unable to connect to Url: {}".format(u)

    def run(self, count=1, interval=0.0):
        if self.clients == []:
            return
        prev = ""
        self.state.fetch()
        self.GlobalKeys = self.state.State.keys()
        for k, v in self.state.State.iteritems():
            self.GlobalStore[k] = v

        while count > 0:
            count -= 1
            c = self._get_client()
            c.CurrentState.fetch()
            k = str(random.randint(0, len(self.GlobalKeys) + 1))
            # Stops the inc of a key that was just set
            while k == prev:
                k = str(random.randint(0, len(self.GlobalKeys) + 1))
            if k in self.GlobalKeys:
                self.GlobalStore[k] += 1
                if k in self.lastKeyTxn:
                    txndep = self.lastKeyTxn[k]
                else:
                    txndep = None
                txnid = c.inc(k, 1, txndep)
                if txnid is None:
                    raise Exception(
                        "Failed to inc key:{} value:{} by 1".format(
                            k, self.GlobalStore[k]))
                self.transactions.append(txnid)
                self.lastKeyTxn[k] = txnid
                time.sleep(interval)

            else:
                self.GlobalKeys += [k]
                v = random.randint(5, 1000)
                self.GlobalStore[k] = v
                txnid = c.set(k, v, txndep=None)
                prev = k
                if txnid is None:
                    raise Exception("Failed to set {} to {}".format(k, v))
                self.transactions.append(txnid)
                self.lastKeyTxn[k] = txnid
                time.sleep(interval)
                self._wait_for_transaction_commits()
        self._wait_for_transaction_commits()

    def validate(self):
        if self.clients == []:
            print "Unable to connect to Validators, No Clients created"
            return
        self.state.fetch()
        print "Validating IntegerKey State"
        for k, v in self.state.State.iteritems():
            if self.GlobalStore[k] != v:
                print "key {} is {} expected to be {}".format(
                    k, v, self.localState[k])
            assert self.GlobalStore[k] == v


class TestIntKey(unittest.TestCase):
    @unittest.skipUnless(ENABLE_INTEGRATION_TESTS, "integration test")
    def test_intkey_increment(self):
        try:
            if "TEST_VALIDATOR_URLS" in os.environ:
                urls = os.environ["TEST_VALIDATOR_URLS"].split(",")
                print "Testing transaction load."
                test = IntKeyLoadTest()
                count = defaultBaseLineConfig["Count"]
                interval = defaultBaseLineConfig["Interval"]
                test.setup(urls)
                test.run(count, interval)
                test.validate()
            else:
                print "No Validators are running at this time."
        except Exception as e:
            print "Exception encountered in test case."
            traceback.print_exc()
            # Cannot create_results_archive since we do not have access to vnm
            # Just print out error instead
            raise e

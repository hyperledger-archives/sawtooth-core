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
from txnintegration.integer_key_state import IntegerKeyState
from txnintegration.validator_network_manager import ValidatorNetworkManager, \
    defaultValidatorConfig

# ENABLE_INTEGRATION_TESTS = False
# if os.environ.get("ENABLE_INTEGRATION_TESTS", False) == "1":
#     ENABLE_INTEGRATION_TESTS = True


class IntKeyLoadTest(object):
    def __init__(self):
        print "start inkeyloadtest"
        # pass

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
        with Progress("Waiting for {0} transactions to commit".format(txnCnt)) as p:
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

    def setup(self, urls, numKeys):
        self.localState = {}
        self.transactions = []
        self.clients = []
        self.state = IntegerKeyState(urls[0])

        with Progress("Creating clients") as p:
            for u in urls:
                key = generate_private_key()
                self.clients.append(IntegerKeyClient(u, keystring=key))
                p.step()

        print "Checking for pre-existing state"
        self.state.fetch()
        keys = self.state.State.keys()

        for k, v in self.state.State.iteritems():
            self.localState[k] = v

        with Progress("Populating initial key values") as p:
            txncount=0
            starttime = time.clock()
            for n in range(1, numKeys + 1):
                n = str(n)
                if n not in keys:
                    c = self._get_client()
                    v = random.randint(5, 1000)
                    self.localState[n] = v
                    txnid = c.set(n, v)
                    if txnid is None:
                        raise Exception("Failed to set {} to {}".format(n, v))
                    self.transactions.append(txnid)
                    txncount+=1
            self.txnrate(starttime, txncount)
        self._wait_for_transaction_commits()

    def run(self, numkeys, rounds=1, txintv=0):
        self.state.fetch()

        keys = self.state.State.keys()

        print "Running {0} rounds for {1} keys with {2} second inter-transaction time"\
            .format(rounds, numkeys, txintv)

        for r in range(0, rounds):
            for c in self.clients:
                c.CurrentState.fetch()
            print "Round {}".format(r)
            # for k in keys:
            starttime = time.clock()
            for k in range(1, numkeys+1):
                k=str(k)
                c = self._get_client()
                self.localState[k] += 2
                txnid = c.inc(k, 2)
                if txnid is None:
                    raise Exception(
                        "Failed to inc key:{} value:{} by 2".format(
                            k, self.localState[k]))
                self.transactions.append(txnid)
                time.sleep(txintv)
            # for k in keys:
            for k in range(1, numkeys + 1):
                k = str(k)
                c = self._get_client()
                self.localState[k] -= 1
                txnid = c.dec(k, 1)
                if txnid is None:
                    raise Exception(
                        "Failed to dec key:{} value:{} by 1".format(
                            k, self.localState[k]))
                self.transactions.append(txnid)
                time.sleep(txintv)
            self.txnrate(starttime, 2*numkeys)
            self._wait_for_transaction_commits()

    def validate(self):
        self.state.fetch()

        print "Validating IntegerKey State"
        for k, v in self.state.State.iteritems():
            if self.localState[k] != v:
                print "key {} is {} expected to be {}".format(
                    k, v, self.localState[k])
            assert self.localState[k] == v

    def ledgerstate(self):
        self.state.fetch()

        keys = self.state.State.keys()

        print "state: "
        for k, v in self.state.State.iteritems():
            print k, v
        print

    def txnrate(selfself, starttime, numtxns):
        if numtxns>0:
            endtime = time.clock()
            totaltime = endtime - starttime
            avgrate = (numtxns / totaltime)
            print "Sent {0} transaction in {1} seconds averaging {2} t/s" \
                .format(numtxns, totaltime, avgrate)

print "Testing transaction load."
urls = ("http://localhost:8800", "http://localhost:8801", "http://localhost:8802")

keys = 10
rounds = 2
txn_intv = 0.0

test = IntKeyLoadTest()
test.setup(urls, keys)
test.validate()
test.run(keys, rounds, txn_intv)
test.validate()
# test.ledgerstate()




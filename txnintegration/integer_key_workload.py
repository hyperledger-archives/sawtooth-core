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
# import traceback
# import unittest
# import os
import time
from twisted.web import http

from txnintegration.utils import generate_private_key
from txnintegration.utils import Progress
from txnintegration.utils import TimeOut
from txnintegration.integer_key_client import IntegerKeyClient
from txnintegration.integer_key_state import IntegerKeyState
# from txnintegration.validator_network_manager \
#     import ValidatorNetworkManager, defaultValidatorConfig

# ENABLE_INTEGRATION_TESTS = False
# if os.environ.get("ENABLE_INTEGRATION_TESTS", False) == "1":
#     ENABLE_INTEGRATION_TESTS = True

import argparse
import sys


class IntKeyLoadTest(object):
    def __init__(self):
        print "start inkeyloadtest"
        self.localState = {}
        self.transactions = []
        self.clients = []
        self.state = None
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
        txncnt = len(self.transactions)

        with Progress("Waiting for {0} transactions to commit"
                              .format(txncnt)) as p:  # noqa
            while not to() and txncnt > 0:
                p.step()
                time.sleep(1)
                self._has_uncommitted_transactions()
                txncnt = len(self.transactions)

        if txncnt != 0:
            if len(self.transactions) != 0:
                print "Uncommitted transactions: ", self.transactions
            raise Exception("{} transactions failed to commit in {}s".format(
                txncnt, to.WaitTime))

    def setup(self, urls, numkeys):
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
            txncount = 0
            starttime = time.clock()
            for n in range(1, numkeys + 1):
                n = str(n)
                if n not in keys:
                    c = self._get_client()
                    v = random.randint(5, 1000)
                    self.localState[n] = v
                    txnid = c.set(n, v)
                    if txnid is None:
                        raise Exception("Failed to set {} to {}".format(n, v))
                    self.transactions.append(txnid)
                    txncount += 1
            self.txnrate(starttime, txncount)
        self._wait_for_transaction_commits()

    def run(self, numkeys, rounds=1, txintv=0):
        self.state.fetch()

        #  keys = self.state.State.keys()

        print "Running {0} rounds for {1} keys " \
              "with {2} second inter-transaction time" \
            .format(rounds, numkeys, txintv)

        for r in range(0, rounds):
            for c in self.clients:
                c.CurrentState.fetch()
            print "Round {}".format(r)
            # for k in keys:
            starttime = time.clock()
            for k in range(1, numkeys + 1):
                k = str(k)
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
            self.txnrate(starttime, 2 * numkeys)
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

        # keys = self.state.State.keys()

        print "state: "
        for k, v in self.state.State.iteritems():
            print k, v
        print

    def txnrate(self, starttime, numtxns):
        if numtxns > 0:
            endtime = time.clock()
            totaltime = endtime - starttime
            avgrate = (numtxns / totaltime)
            print "Sent {0} transaction in {1} seconds averaging {2} t/s" \
                .format(numtxns, totaltime, avgrate)


def parse_args(args):
    parser = argparse.ArgumentParser()

    parser.add_argument('--validator-count',
                        metavar="",
                        help='Validators to monitor (default: %(default)s)',
                        default=3,
                        type=int)
    parser.add_argument('--validator-url',
                        metavar="",
                        help='Base validator url (default: %(default)s)',
                        default="http://localhost")
    parser.add_argument('--validator-port',
                        metavar="",
                        help='Base validator http port (default: %(default)s)',
                        default=8800,
                        type=int)
    parser.add_argument('--keys',
                        metavar="",
                        help='Keys to create/exercise (default: %(default)s)',
                        default=10,
                        type=int)
    parser.add_argument('--rounds',
                        metavar="",
                        help='Rounds to execute (default: %(default)s)',
                        default=2,
                        type=int)
    parser.add_argument('--txn-intv',
                        metavar="",
                        help='Inter-tx time (mS) (default: %(default)s)',
                        default=0,
                        type=int)

    return parser.parse_args(args)


def configure(opts):
    # scriptdir = os.path.dirname(os.path.realpath(__file__))

    print "     validator count: ", opts.validator_count
    print "  validator base url: ", opts.validator_url
    print " validator base port: ", opts.validator_port
    print "                keys: ", opts.keys
    print "              rounds: ", opts.rounds
    print "transaction interval: ", opts.txn_intv
    # sys.exit(1)


def main():
    try:
        opts = parse_args(sys.argv[1:])
    except:
        # argparse reports details on the parameter error.
        sys.exit(1)

    configure(opts)

    # urls = ("http://localhost:8800",
    #         "http://localhost:8801",
    #         "http://localhost:8802")

    urls = []

    vcount = opts.validator_count
    baseurl = opts.validator_url
    portnum = opts.validator_port

    for i in range(0, vcount):
        url = baseurl + ":" + str(portnum + i)
        urls.append(url)

    print "validator urls: ", urls

    keys = opts.keys
    rounds = opts.rounds
    txn_intv = opts.txn_intv

    print "Testing transaction load."

    test = IntKeyLoadTest()
    test.setup(urls, keys)
    test.validate()
    test.run(keys, rounds, txn_intv)
    test.validate()
    # test.ledgerstate()


if __name__ == "__main__":
    main()

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

from __future__ import print_function

import logging
import random
import time
import json
import urllib2
from twisted.web import http

from txnintegration.utils import generate_private_key
from txnintegration.utils import Progress
from txnintegration.utils import TimeOut
from txnintegration.integer_key_client import IntegerKeyClient
from txnintegration.integer_key_communication import MessageException
from txnintegration.integer_key_state import IntegerKeyState


import argparse
import sys

logger = logging.getLogger(__name__)


class IntKeyLoadTest(object):
    def __init__(self, timeout=None):
        print("start inkeyloadtest")
        self.localState = {}
        self.transactions = []
        self.clients = []
        self.state = None
        self.Timeout = 240 if timeout is None else timeout
        self.fake_txn_id = '123456789ABCDEFGHJKLMNPQRSTUV' \
                           'WXYZabcdefghijkmnopqrstuvwxyz'
        self.committedBlckIds = []
        self.pendingTxnCount = 0
        self.pendingTxns = []

    def _get_client(self):
        return self.clients[random.randint(0, len(self.clients) - 1)]

    def _update_uncommitted_transactions(self):
        remaining = []

        # For each client, we want to verify that its corresponding validator
        # has the transaction.  For a transaction to be considered committed,
        # all validators must have it in its blockchain as a committed
        # transaction.
        for c in self.clients:
            for t in self.transactions:
                status = c.get_transaction_status(t)
                # If the transaction has not been committed and we don't
                # already have it in our list of uncommitted transactions
                # then add it.
                if (status != http.OK) and (t not in remaining):
                    remaining.append(t)

        self.transactions = remaining
        return len(self.transactions)

    def _wait_for_transaction_commits(self):
        to = TimeOut(self.Timeout)
        txnCnt = len(self.transactions)
        with Progress("Waiting for %s transactions to commit" % (txnCnt)) \
                as p:
            while not to() and txnCnt > 0:
                p.step()
                time.sleep(1)
                txnCnt = self._update_uncommitted_transactions()

        if txnCnt != 0:
            if len(self.transactions) != 0:
                print("Uncommitted transactions: ", self.transactions)
            raise Exception("{} transactions failed to commit in {}s".format(
                txnCnt, to.WaitTime))

    def _wait_for_no_transaction_commits(self):
        # for the case where no transactions are expected to commit
        to = TimeOut(240)
        starting_txn_count = len(self.transactions)

        remaining_txn_cnt = len(self.transactions)
        with Progress("Waiting for transactions to NOT commit") as p:
            while not to() and remaining_txn_cnt > 0:
                p.step()
                time.sleep(1)
                remaining_txn_cnt = self._update_uncommitted_transactions()

        if remaining_txn_cnt != starting_txn_count:
            committedtxncount = starting_txn_count - remaining_txn_cnt
            raise Exception("{} transactions with missing dependencies "
                            "were committed in {}s"
                            .format(committedtxncount, to.WaitTime))
        else:
            print("No transactions with missing dependencies "
                  "were committed in {0}s".format(to.WaitTime))

    def _wait_for_limit_pending_transactions(self):
        result = self.is_registered('http://localhost:8800/statistics/journal')
        json_data = json.loads(result)
        self.committedBlckCount = json_data['journal']['CommittedBlockCount']
        print(("committedBlckCount: ", self.committedBlckCount))
        self.pendingTxnCount = json_data['journal']['PendingTxnCount']
        print(("PendingTxnCount: ", self.pendingTxnCount))

        if (self.committedBlckCount > 3 & self.pendingTxnCount != 0):
            raise Exception("{} blocks were committed "
                            "with {} invalid transactions."
                            .format(self.committedBlckCount,
                                    self.pendingTxnCount))
        else:
            print("All pending transactions after "
                  "3 blocks have been dropped")

    def setup(self, urls, numkeys):
        self.localState = {}
        self.transactions = []
        self.last_key_txn = {}
        self.clients = []
        self.state = IntegerKeyState(urls[0])

        with Progress("Creating clients") as p:
            for u in urls:
                try:
                    key = generate_private_key()
                    self.clients.append(IntegerKeyClient(u, keystring=key))
                    p.step()
                except MessageException:
                    logger.warn("Unable to connect to Url: %s ", u)
            if len(self.clients) == 0:
                return

        # add check for if a state already exists
        with Progress("Checking for pre-existing state") as p:
            self.state.fetch()
            for k, v in self.state.State.iteritems():
                self.localState[k] = v
                p.step()

        keys = self.state.State.keys()

        with Progress("Populating initial key values") as p:
            txncount = 0
            starttime = time.time()
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
                    self.last_key_txn[n] = txnid
                    p.step()
            print()
            self.txnrate(starttime, txncount, "submitted")
        self._wait_for_transaction_commits()
        self.txnrate(starttime, txncount, "committed")

    def run(self, numkeys, rounds=1, txintv=0):
        if len(self.clients) == 0:
            return

        self.state.fetch()
        keys = self.state.State.keys()

        print("Running {0} rounds for {1} keys "
              "with {2} second inter-transaction time"
              .format(rounds, numkeys, txintv))

        for r in range(0, rounds):
            cnt = 0
            starttime = time.time()
            with Progress("Round {}".format(r)) as p:
                for k in keys:
                    k = str(k)
                    c = self._get_client()
                    self.localState[k] += 2
                    txn_dep = self.last_key_txn.get(k, None)
                    txn_id = c.inc(k, 2, txn_dep)
                    if txn_id is None:
                        raise Exception(
                            "Failed to inc key:{} value:{} by 2".format(
                                k, self.localState[k]))
                    self.transactions.append(txn_id)
                    self.last_key_txn[k] = txn_id
                    cnt += 1
                    if cnt % 10 == 0:
                        p.step()
                    time.sleep(txintv)
                for k in keys:
                    k = str(k)
                    c = self._get_client()
                    self.localState[k] -= 1
                    txn_dep = self.last_key_txn[k]
                    txn_id = c.dec(k, 1, txn_dep)
                    if txn_id is None:
                        raise Exception(
                            "failed to dec key:{} value:{} by 1".format(
                                k, self.localState[k]))
                    self.transactions.append(txn_id)
                    self.last_key_txn[k] = txn_id
                    cnt += 1
                    if cnt % 10 == 0:
                        p.step()
                    time.sleep(txintv)

            txn_count = len(self.transactions)
            self.txnrate(starttime, txn_count, "submitted")
            self._wait_for_transaction_commits()
            self.txnrate(starttime, txn_count, "committed")

    def validate(self):
        if len(self.clients) == 0:
            logger.warn("Unable to connect to Validators, No Clients created")
            return
        self.state.fetch()
        print("Validating IntegerKey State")
        for k, v in self.state.State.iteritems():
            if self.localState[k] != v:
                print("key {} is {} expected to be {}".format(
                    k, v, self.localState[k]))
            assert self.localState[k] == v

    def journalstate(self):
        self.state.fetch()

        print("state: ")
        for k, v in self.state.State.iteritems():
            print(k, v)
        print()

    def txnrate(self, starttime, numtxns, purpose):
        if numtxns > 0:
            endtime = time.time()
            totaltime = endtime - starttime
            avgrate = (numtxns / totaltime)
            print("{0} transaction in {1} seconds averaging {2} t/s "
                  "{3}" .format(numtxns, totaltime, avgrate, purpose))

    def generate_txn_id(self):
        string_id = ''
        for i in range(0, 16):
            string_id = string_id + random.choice(self.fake_txn_id)
        return string_id

    def is_registered(self, url=None):
        response = urllib2.urlopen(url).read()
        return response

    def run_with_limit_txn_dependencies(self, numkeys, rounds=1, txintv=0):
        if len(self.clients) == 0:
            return
        self.state.fetch()
        keys = self.state.State.keys()

        print("Running {0} rounds for {1} keys "
              "with {2} second inter-transaction time"
              "with limit on missing dep transactions"
              .format(rounds, numkeys, txintv))

        for r in range(1, rounds + 1):
            with Progress("Updating clients state") as p:

                print("Round {}".format(r))
                for k in range(1, numkeys + 1):
                    k = str(k)
                    c = self._get_client()

                    print ("Sending invalid txnx: ")
                    cnt = 0
                    starttime = time.time()
                    for inf in range(0, 3):
                        missingid = self.generate_txn_id()
                        dependingtid = c.inc(k, 1, txndep=missingid)
                        self.pendingTxns.append(dependingtid)
                        cnt += 1
                    print(("pendingTxns: ", self.pendingTxns))
                    self.txnrate(starttime, cnt,
                                 " invalid transactions NOT submitted")

                    result = self.is_registered(
                        'http://localhost:8800/statistics/journal')
                    json_data = json.loads(result)
                    self.pendingTxnCount = \
                        json_data['journal']['PendingTxnCount']
                    print(("PendingTxnCount: ", self.pendingTxnCount))

                    for loop_ind in range(0, 4):
                        print ("Sending valid txn:")
                        cnt = 0
                        starttime = time.time()
                        for ind in range(0, 5):
                            self.localState[k] += 2
                            txn_dep = self.last_key_txn.get(k, None)
                            txn_id = c.inc(k, 2, txn_dep)
                            if txn_id is None:
                                raise Exception(
                                    "Failed to inc key:{} value:{}"
                                    " by 2".format(
                                        k, self.localState[k]))
                            self.transactions.append(txn_id)
                            self.last_key_txn[k] = txn_id
                            cnt += 1
                            if cnt % 10 == 0:
                                p.step()
                            time.sleep(txintv)
                        txn_count = len(self.transactions)
                        self.txnrate(starttime, txn_count,
                                     " valid transactions submitted")

                        self._wait_for_transaction_commits()
                        self._wait_for_limit_pending_transactions()

                    print("checking pending txn limit")
                    self._wait_for_limit_pending_transactions()

    def run_with_missing_dep(self, numkeys, rounds=1):
        self.state.fetch()

        print("Running {0} rounds for {1} keys "
              "with missing transactions"
              .format(rounds, numkeys))

        starttime = time.time()
        for r in range(1, rounds + 1):
            print("Round {}".format(r))
            for k in range(1, numkeys + 1):
                k = str(k)
                c = c = self._get_client()

                for ind in range(0, 5):
                    missingid = self.generate_txn_id()
                    dependingtid = c.inc(k, 1, txndep=missingid)
                    self.transactions.append(dependingtid)
            txn_count = len(self.transactions)
            self.txnrate(starttime, txn_count, " dep txn submitted")
            self._wait_for_no_transaction_commits()


def parse_args(args):
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument('--count',
                        metavar="",
                        help='Validators to monitor (default: %(default)s)',
                        default=3,
                        type=int)
    parser.add_argument('--url',
                        metavar="",
                        help='Base validator url (default: %(default)s)',
                        default="http://localhost")
    parser.add_argument('--port',
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
    parser.add_argument('--interval',
                        metavar="",
                        help='Inter-txn time (mS) (default: %(default)s)',
                        default=0,
                        type=int)
    parser.add_argument('--missingdep',
                        metavar="",
                        help="""Execute missing dependency test once
after transaction rounds are complete (default: %(default)s)""",
                        default=False,
                        type=bool)

    return parser.parse_args(args)


def configure(opts):
    print("     validator count: ", opts.count)
    print("  validator base url: ", opts.url)
    print(" validator base port: ", opts.port)
    print("                keys: ", opts.keys)
    print("              rounds: ", opts.rounds)
    print("transaction interval: ", opts.interval)


def main():
    try:
        opts = parse_args(sys.argv[1:])
    except:
        # argparse reports details on the parameter error.
        sys.exit(1)

    configure(opts)

    urls = []

    vcount = opts.count
    baseurl = opts.url
    portnum = opts.port

    for i in range(0, vcount):
        url = baseurl + ":" + str(portnum + i)
        urls.append(url)

    print("validator urls: ", urls)

    keys = opts.keys
    rounds = opts.rounds
    txn_intv = opts.interval

    print("Testing transaction load.")

    test = IntKeyLoadTest()
    test.setup(urls, keys)
    test.validate()
    test.run(keys, rounds, txn_intv)
    if opts.missingdep:
        test.run_with_missing_dep(keys)
    test.validate()


if __name__ == "__main__":
    main()

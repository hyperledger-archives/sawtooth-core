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
import logging
from twisted.web import http

from txnintegration.utils import generate_private_key
from txnintegration.utils import Progress
from txnintegration.utils import TimeOut
from txnintegration.integer_key_client import IntegerKeyClient
from txnintegration.integer_key_state import IntegerKeyState
from txnintegration.integer_key_communication import MessageException
from txnintegration.validator_network_manager import ValidatorNetworkManager, \
    defaultValidatorConfig

logger = logging.getLogger(__name__)

ENABLE_INTEGRATION_TESTS = False
if os.environ.get("ENABLE_INTEGRATION_TESTS", False) == "1":
    ENABLE_INTEGRATION_TESTS = True


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
        to = TimeOut(240)
        txnCnt = len(self.transactions)
        with Progress("Waiting for transactions to commit") as p:
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
        self.lastKeyTxn = {}
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
            if self.clients == []:
                return

        # add check for if a state already exists
        print "Checking for pre-existing state"
        self.state.fetch()
        keys = self.state.State.keys()
        for k, v in self.state.State.iteritems():
            self.localState[k] = v

        with Progress("Creating initial key values") as p:
            for n in range(1, numKeys + 1):
                n = str(n)
                if n not in keys:
                    c = self._get_client()
                    v = random.randint(5, 1000)
                    self.localState[n] = v
                    txnid = c.set(n, v, txndep=None)
                    if txnid is None:
                        raise Exception("Failed to set {} to {}".format(n, v))
                    self.transactions.append(txnid)
                    self.lastKeyTxn[n] = txnid

        self._wait_for_transaction_commits()

    def run(self, rounds=1):
        if self.clients == []:
            return

        self.state.fetch()
        keys = self.state.State.keys()

        for r in range(0, rounds):
            for c in self.clients:
                c.CurrentState.fetch()
            print "Round {}".format(r)
            for k in keys:
                c = self._get_client()
                self.localState[k] += 2
                if k in self.lastKeyTxn:
                    txndep = self.lastKeyTxn[k]
                else:
                    txndep = None
                txnid = c.inc(k, 2, txndep)
                if txnid is None:
                    raise Exception(
                        "Failed to inc key:{} value:{} by 2".format(
                            k, self.localState[k]))
                self.transactions.append(txnid)
                self.lastKeyTxn[k] = txnid
            for k in keys:
                c = self._get_client()
                self.localState[k] -= 1
                txndep = self.lastKeyTxn[k]
                txnid = c.dec(k, 1, txndep)
                if txnid is None:
                    raise Exception(
                        "Failed to dec key:{} value:{} by 1".format(
                            k, self.localState[k]))
                self.transactions.append(txnid)
                self.lastKeyTxn[k] = txnid

            self._wait_for_transaction_commits()

    def validate(self):
        if self.clients == []:
            logger.warn("Unable to connect to Validators, No Clients created")
            return
        self.state.fetch()
        print "Validating IntegerKey State"
        for k, v in self.state.State.iteritems():
            if self.localState[k] != v:
                print "key {} is {} expected to be {}".format(
                    k, v, self.localState[k])
            assert self.localState[k] == v


class TestSmoke(unittest.TestCase):
    @unittest.skipUnless(ENABLE_INTEGRATION_TESTS, "integration test")
    def test_intkey_load(self):
        vnm = None
        urls = ""
        try:
            test = IntKeyLoadTest()
            if "TEST_VALIDATOR_URLS" not in os.environ:
                print "Launching validator network."
                vnm_config = defaultValidatorConfig.copy()
                vnm_config['LogLevel'] = 'DEBUG'
                vnm = ValidatorNetworkManager(httpPort=9000, udpPort=9100,
                                              cfg=vnm_config)
                vnm.launch_network(5)
                urls = vnm.urls()
            else:
                print "Fetching Urls of Running Validators"
                # TEST_VALIDATORS_RUNNING is a list of validators urls
                # seperated by commas.
                # 'http://localhost:8800,http://localhost:8801'
                urls = str(os.environ["TEST_VALIDATOR_URLS"]).split(",")
            print "Testing transaction load."
            test.setup(urls, 100)
            test.run(2)
            test.validate()
            if vnm:
                vnm.shutdown()

        except Exception as e:
            print "Exception encountered in test case."
            traceback.print_exc()
            if vnm:
                vnm.shutdown()
            raise
        finally:
            if vnm:
                vnm.create_result_archive("TestSmokeResults.tar.gz")
            else:
                print "No Validator data and logs to preserve"

    @unittest.skip("LedgerType voting is broken")
    def test_intkey_load_voting(self):
        vnm = None
        vote_cfg = defaultValidatorConfig.copy()
        vote_cfg['LedgerType'] = 'voting'
        try:
            vnm = ValidatorNetworkManager(httpPort=9000, udpPort=9100,
                                          cfg=vote_cfg)
            vnm.launch_network(5)

            print "Testing transaction load."
            test = IntKeyLoadTest()
            test.setup(vnm.urls(), 100)
            test.run(2)
            test.validate()
            vnm.shutdown()
        except Exception:
            print "Exception encountered in test case."
            traceback.print_exc()
            if vnm:
                vnm.shutdown()
            raise
        finally:
            if vnm:
                vnm.create_result_archive("TestSmokeResultsVote.tar.gz")

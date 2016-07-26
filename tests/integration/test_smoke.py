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

from txnintegration.utils import StaticNetworkConfig
from txnintegration.utils import generate_private_key
from txnintegration.utils import Progress
from txnintegration.utils import TimeOut
from txnintegration.integer_key_client import IntegerKeyClient
from txnintegration.integer_key_state import IntegerKeyState
from txnintegration.integer_key_communication import MessageException
from txnintegration.validator_network_manager import ValidatorNetworkManager, \
    defaultValidatorConfig
from sawtooth.client import LedgerWebClient

logger = logging.getLogger(__name__)

ENABLE_INTEGRATION_TESTS = True \
    if os.environ.get("ENABLE_INTEGRATION_TESTS", False) == "1" else False


class IntKeyLoadTest(object):
    def __init__(self, timeout=None):
        self.Timeout = 240 if timeout is None else timeout

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
                status = c.headrequest('/transaction/{0}'.format(t))
                # If the transaction has not been committed and we don't
                # already have it in our list of uncommitted transactions
                # then add it.
                if (status != http.OK) and (t not in remaining):
                    remaining.append(t)

        self.transactions = remaining
        return len(self.transactions)

    def _wait_for_transaction_commits(self):
        to = TimeOut(self.Timeout)
        txn_cnt = len(self.transactions)
        with Progress("Waiting for %s transactions to commit" % (txn_cnt)) \
                as p:
            while not to() and txn_cnt > 0:
                p.step()
                time.sleep(1)
                txn_cnt = self._update_uncommitted_transactions()

        if txn_cnt != 0:
            if len(self.transactions) != 0:
                print "Uncommitted transactions: ", self.transactions
            raise Exception("{} transactions failed to commit in {}s".format(
                txn_cnt, to.WaitTime))

    def setup(self, urls, num_keys):
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
            keys = self.state.State.keys()
            for k, v in self.state.State.iteritems():
                self.localState[k] = v

        with Progress("Creating initial key values") as p:
            for n in range(1, num_keys + 1):
                n = str(n)
                if n not in keys:
                    c = self._get_client()
                    v = random.randint(5, 1000)
                    self.localState[n] = v
                    txn_id = c.set(n, v, txndep=None)
                    if txn_id is None:
                        raise Exception("Failed to set {} to {}".format(n, v))
                    self.transactions.append(txn_id)
                    self.last_key_txn[n] = txn_id

        self._wait_for_transaction_commits()

    def run(self, rounds=1):
        if len(self.clients) == 0:
            return

        self.state.fetch()
        keys = self.state.State.keys()

        for r in range(1, rounds + 1):
            with Progress("Updating clients state") as p:
                for c in self.clients:
                    c.CurrentState.fetch()
                    p.step()

            cnt = 0
            with Progress("Round {}".format(r)) as p:
                for k in keys:
                    c = self._get_client()
                    self.localState[k] += 2
                    if k in self.last_key_txn:
                        txn_dep = self.last_key_txn[k]
                    else:
                        txn_dep = None
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

                for k in keys:
                    c = self._get_client()
                    self.localState[k] -= 1
                    txn_dep = self.last_key_txn[k]
                    txn_id = c.dec(k, 1, txn_dep)
                    if txn_id is None:
                        raise Exception(
                            "Failed to dec key:{} value:{} by 1".format(
                                k, self.localState[k]))
                    self.transactions.append(txn_id)
                    self.last_key_txn[k] = txn_id
                    cnt += 1
                    if cnt % 10 == 0:
                        p.step()

            self._wait_for_transaction_commits()

    def validate(self):
        if len(self.clients) == 0:
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
    def _run_int_load(self, config, num_nodes, archive_name,
                      tolerance=2, standard=5, block_id=True,
                      static_network=None,
                      vnm_timeout=None, txn_timeout=None,
                      n_keys=100, n_runs=2,
                      ):
        """
        This test is getting really beat up and needs a refactor
        Args:
            config (dict): Default config for each node
            num_nodes (int): Total number of nodes in network simulation
            archive_name (str): Name for tarball summary of test results
            tolerance (int): Length in blocks of permissible fork (if forks are
                             permissible)
            standard (int): A variable intended to guarantee that our block
                level identity checks have significant data to operate on.
                Conceptually, depends on the value of tolerance:
                    case(tolerance):
                        0:          minimum # of blocks required per validator
                        otherwise:  minimum # of converged blocks required per
                                    divergent block (per validator)
                Motivation: We want to compare identity across the network on
                some meaningfully large set of blocks.  Introducing fork
                tolerance is problematic: the variable tolerance which is used
                to trim the ends of each ledger's block-chain could be abused
                to trivialize the test.  Therefore, as tolerance is increased
                (if non-zero), we use standard to proportionally increase the
                minimum number of overall blocks required by the test.
            block_id (bool): check for block (hash) identity
            static_network (StaticNetworkConfig): optional static network
                configuration
            vnm_timeout (int): timeout for initiating network
            txn_timeout (int): timeout for batch transactions
        """
        vnm = None
        urls = ""
        try:
            test = IntKeyLoadTest(timeout=txn_timeout)
            if "TEST_VALIDATOR_URLS" not in os.environ:
                print "Launching validator network."
                vnm_config = config
                vnm = ValidatorNetworkManager(http_port=9000, udp_port=9100,
                                              cfg=vnm_config,
                                              static_network=static_network)
                vnm.launch_network(num_nodes, max_time=vnm_timeout)
                urls = vnm.urls()
            else:
                print "Fetching Urls of Running Validators"
                # TEST_VALIDATORS_RUNNING is a list of validators urls
                # separated by commas.
                # e.g. 'http://localhost:8800,http://localhost:8801'
                urls = str(os.environ["TEST_VALIDATOR_URLS"]).split(",")
            print "Testing transaction load."
            test.setup(urls, n_keys)
            test.run(n_runs)
            test.validate()
            if block_id:
                # check for block id convergence across network:
                sample_size = max(1, tolerance) * standard
                print "Testing block-level convergence with min sample size:",
                print " %s (after tolerance: %s)" % (sample_size, tolerance)
                # ...get all blockids from each server, newest last
                block_lists = [
                    LedgerWebClient(x).get_block_list() for x in urls]
                for ls in block_lists:
                    ls.reverse()
                # ...establish preconditions
                max_mag = len(max(block_lists, key=len))
                min_mag = len(min(block_lists, key=len))
                self.assertGreaterEqual(
                    tolerance,
                    max_mag - min_mag,
                    'block list magnitude differences (%s) '
                    'exceed tolerance (%s)' % (
                        max_mag - min_mag, tolerance))
                effective_sample_size = max_mag - tolerance
                print 'effective sample size: %s' % (effective_sample_size)
                self.assertGreaterEqual(
                    effective_sample_size,
                    sample_size,
                    'not enough target samples to determine convergence')
                # ...(optionally) permit reasonable forks by normalizing lists
                if tolerance > 0:
                    block_lists = [
                        block_list[0:effective_sample_size]
                        for block_list in block_lists
                    ]
                # ...id-check (possibly normalized) cross-server block chains
                for (i, block_list) in enumerate(block_lists):
                    self.assertEqual(
                        block_lists[0],
                        block_list,
                        '%s is divergent:\n\t%s vs.\n\t%s' % (
                            urls[i], block_lists[0], block_list))
            if vnm:
                vnm.shutdown()
        except Exception:
            print "Exception encountered in test case."
            traceback.print_exc()
            if vnm:
                vnm.shutdown()
            raise
        finally:
            if vnm:
                vnm.create_result_archive("%s.tar.gz" % (archive_name))
            else:
                print "No Validator data and logs to preserve"

    @unittest.skipUnless(ENABLE_INTEGRATION_TESTS, "integration test")
    def test_intkey_load_lottery(self):
        cfg = defaultValidatorConfig.copy()
        cfg['LedgerType'] = 'lottery'
        self._run_int_load(cfg, 5, "TestSmokeResultsLottery")

    @unittest.skipUnless(ENABLE_INTEGRATION_TESTS, "integration test")
    def test_intkey_load_quorum(self):
        n = 4   # size of network
        q = 4   # size of quorum
        network = StaticNetworkConfig(n, q=q, use_quorum=True)
        cfg = defaultValidatorConfig.copy()
        cfg['LedgerType'] = 'quorum'
        cfg['TopologyAlgorithm'] = "Quorum"
        cfg["MinimumConnectivity"] = q
        cfg["TargetConnectivity"] = q
        cfg['VotingQuorumTargetSize'] = q
        cfg['Nodes'] = network.get_nodes()
        cfg['VoteTimeInterval'] = 48.0
        cfg['BallotTimeInterval'] = 8.0
        self._run_int_load(cfg, n, "TestSmokeResultsQuorum",
                           tolerance=0, block_id=False,
                           static_network=network,
                           vnm_timeout=240, txn_timeout=240,
                           n_keys=100, n_runs=1)

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

from txnintegration.integer_key_load_cli import IntKeyLoadTest
from txnintegration.utils import is_convergent
from txnintegration.utils import StaticNetworkConfig
from txnintegration.validator_network_manager import ValidatorNetworkManager, \
    defaultValidatorConfig

logger = logging.getLogger(__name__)

ENABLE_INTEGRATION_TESTS = True \
    if os.environ.get("ENABLE_INTEGRATION_TESTS", False) == "1" else False


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
                self.assertEqual(True, is_convergent(urls, tolerance=tolerance,
                                                     standard=standard))
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
                vnm.create_result_archive("%s.tar.gz" % archive_name)
            else:
                print "No Validator data and logs to preserve"

    @unittest.skipUnless(ENABLE_INTEGRATION_TESTS, "integration test")
    def test_intkey_load_poet0(self):
        cfg = defaultValidatorConfig.copy()
        cfg['LedgerType'] = 'poet0'
        self._run_int_load(cfg, 5, "TestSmokeResultsPoet")

    @unittest.skipUnless(ENABLE_INTEGRATION_TESTS, "integration test")
    def test_intkey_load_dev_mode(self):
        cfg = defaultValidatorConfig.copy()
        cfg['LedgerType'] = 'dev_mode'
        self._run_int_load(cfg, 1, "TestSmokeResultsDevMode")

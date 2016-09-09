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

from txnintegration.integer_key_load_cli import IntKeyLoadTest
from txnintegration.utils import generate_private_key
from txnintegration.utils import Progress
from txnintegration.utils import TimeOut
from txnintegration.validator_network_manager import defaultValidatorConfig
from txnintegration.validator_network_manager import ValidatorNetworkManager

ENABLE_OVERNIGHT_TESTS = False
if os.environ.get("ENABLE_OVERNIGHT_TESTS", False) == "1":
    ENABLE_OVERNIGHT_TESTS = True


class TestIntegration(unittest.TestCase):
    @unittest.skipUnless(ENABLE_OVERNIGHT_TESTS, "integration test")
    def test_intkey_load_ext(self):
        vnm = None
        try:
            print "Launching validator network."
            vnm_config = defaultValidatorConfig.copy()
            vnm_config['LogLevel'] = 'DEBUG'

            vnm = ValidatorNetworkManager(http_port=9000, udp_port=9100,
                                          cfg=vnm_config)

            firstwavevalidators = vnm.launch_network(5)

            print "Testing transaction load."
            test = IntKeyLoadTest()
            test.setup(vnm.urls(), 10)
            test.run(1)
            vnm.expand_network(firstwavevalidators, 1)
            test.run(1)
            test.run_with_missing_dep(1)
            test.validate()
            vnm.shutdown()
        except Exception as e:
            print "Exception encountered in test case."
            traceback.print_exc()
            if vnm:
                vnm.shutdown()
            vnm.create_result_archive("TestIntegrationResults.tar.gz")
            print "Validator data and logs preserved in: " \
                  "TestIntegrationResults.tar.gz"
            raise e

    @unittest.skip("LedgerType quorum is broken")
    def test_intkey_load_quorum(self):
        vnm = None
        vote_cfg = defaultValidatorConfig.copy()
        vote_cfg['LedgerType'] = 'quorum'
        try:
            vnm = ValidatorNetworkManager(http_port=9000, udp_port=9100,
                                          cfg=vote_cfg)
            vnm.launch_network(5)

            print "Testing transaction load."
            test = IntKeyLoadTest()
            test.setup(vnm.urls(), 100)
            test.run(2)
            test.run_missing_dep_test(1)
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
                vnm.create_result_archive("TestIntegrationResultsVote.tar.gz")

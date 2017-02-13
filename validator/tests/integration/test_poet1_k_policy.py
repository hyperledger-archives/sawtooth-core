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

import unittest
import os
import urllib2
import json

from txnintegration.integer_key_load_cli import IntKeyLoadTest

RUN_TEST_SUITES = True \
    if os.environ.get("RUN_TEST_SUITES", False) == "1" else False


@unittest.skipUnless(RUN_TEST_SUITES, "Must be run in a test suites")
class TestPoet1KPolicy(unittest.TestCase):
    def __init__(self, test_name, urls=None):
        super(TestPoet1KPolicy, self).__init__(test_name)
        self.urls = urls

        self.blcks_claimed = 0
        self.before_validator0_key = None
        self.after_validator0_key = None

    def test_poet1_k_policy(self):
        try:
            test = IntKeyLoadTest()
            test.setup(self.urls, 10)
            self.blcks_claimed = self.get_blocks_claimed()
            self.before_validator0_key = self.get_validator_key()
            while self.get_blocks_claimed() <= (self.blcks_claimed + 25):
                test.run(1)
                test.validate()
            self.blcks_claimed = self.get_blocks_claimed()
            self.after_validator0_key = self.get_validator_key()

            self.k_policy_test()

        finally:
            print("No Validators need to be stopped")


    def stats_config_dict(self):
        config = {}
        config['SawtoothStats'] = {}
        config['SawtoothStats']['max_loop_count'] = 4
        config['StatsPrint'] = {}
        config['StatsPrint']['print_all'] = True
        return config


    def get_data(self, url=None):
        response = urllib2.urlopen(url).read()
        return response


    def get_blocks_claimed(self):
        result = self.get_data('http://localhost:8800/statistics/journal')
        json_data = json.loads(result)
        self.blocksClaimed = json_data['journal']['BlocksClaimed']
        return self.blocksClaimed


    def get_validator_key(self):
        self.node_ids = self.get_data('http://localhost:8800/store/ValidatorRegistryTransaction')
        json_nodes_ids = json.loads(self.node_ids)
        self.node_id = json_nodes_ids[0]
        self.validator_pkey = self.get_data('http://localhost:8800/store/ValidatorRegistryTransaction/' +
                                            self.node_id)
        json_validator_pkey = json.loads(self.validator_pkey)
        self.validator0_pkey = json_validator_pkey["poet-public-key"]
        return self.validator0_pkey


    def k_policy_test(self):
        if self.before_validator0_key is not None:
            if self.before_validator0_key == self.after_validator0_key:
                raise Exception("validator 0 didn't renew its "
                                "key after committing 5 blocks")
            else:
                print
                "validator 0 renewed its keys after reaching BlockClaimThreshold"
        else:
            print
            "before_validator0_key is ", self.before_validator0_key

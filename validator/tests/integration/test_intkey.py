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

from txnintegration.integer_key_client import IntegerKeyClient
from txnintegration.integer_key_communication import MessageException
from txnintegration.integer_key_load_cli import IntKeyLoadTest
from txnintegration.integer_key_state import IntegerKeyState
from txnintegration.utils import generate_private_key
from txnintegration.utils import Progress
from txnintegration.utils import TimeOut

ENABLE_INTEGRATION_TESTS = False
if os.environ.get("ENABLE_INTEGRATION_TESTS", False) == "1":
    ENABLE_INTEGRATION_TESTS = True


defaultBaseLineConfig = {u'UrlList': [],
                         u"Count": 10,
                         u"Interval": 2}


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

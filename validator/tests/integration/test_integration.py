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

from txnintegration.integer_key_load_cli import IntKeyLoadTest

RUN_TEST_SUITES = True \
    if os.environ.get("RUN_TEST_SUITES", False) == "1" else False


@unittest.skipUnless(RUN_TEST_SUITES, "Must be run in a test suites")
class TestIntegration(unittest.TestCase):
    def __init__(self, test_name, urls=None):
        super(TestIntegration, self).__init__(test_name)
        self.urls = urls

    def test_intkey_load_ext(self):
        print("Testing transaction load.")
        test = IntKeyLoadTest()
        test.setup(self.urls, 10)
        test.run(1)
        test.run_with_missing_dep(1)
        test.validate()

    def test_missing_dependencies(self):
        print("Testing limit of missing dependencies.")
        test = IntKeyLoadTest()
        test.setup(self.urls, 10)
        test.run(1)
        test.run_with_limit_txn_dependencies(1)
        test.validate()

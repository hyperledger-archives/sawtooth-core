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
import logging

from txnintegration.integer_key_load_cli import IntKeyLoadTest
from txnintegration.utils import is_convergent

logger = logging.getLogger(__name__)

RUN_TEST_SUITES = True \
    if os.environ.get("RUN_TEST_SUITES", False) == "1" else False


@unittest.skipUnless(RUN_TEST_SUITES, "Must be run in a test suites")
class TestSmoke(unittest.TestCase):
    def __init__(self, test_name, urls=None):
        super(TestSmoke, self).__init__(test_name)
        self.urls = urls

    def _run_int_load(self):
        """
        Args:
            num_nodes (int): Total number of nodes in network simulation
            archive_name (str): Name for tarball summary of test results
            overrides (dict): universal config overrides test validators
        """
        vnm = None
        try:
            test = IntKeyLoadTest()
            print("Testing transaction load.")
            test.setup(self.urls, 100)
            test.run(2)
            test.validate()
            self.assertTrue(is_convergent(self.urls, tolerance=2, standard=3))
        finally:
            print("No Validator data and logs to preserve")

    def test_intkey_load(self):
        self._run_int_load()

# Copyright 2017 Intel Corporation
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

import os
import unittest
import traceback
from subprocess import Popen

from sawtooth_processor_test.tester import TransactionProcessorTester

from sawtooth_integration.tests.test_tp_xo import TestXo


class TestSuiteXo(unittest.TestCase):
    def __init__(self, test_name):
        super().__init__(test_name)
        self.tester = TransactionProcessorTester()

    def _set_up(self):
        url = "0.0.0.0:40000"

        # 1. Init tester

        self.tester.listen(url)
        print("Test running in PID: {}".format(os.getpid()))

        # 2. Register the transaction processor with the tester
        if not self.tester.register_processor():
            raise Exception("Failed to register processor")

    def _tear_down(self):
        if self.tester is not None:
            self.tester.close()

    def test_suite(self):
        success = False
        try:
            self._set_up()

            runner = unittest.TextTestRunner(verbosity=2, failfast=True)
            suite = unittest.TestSuite()

            # --- Tests to run --- #
            suite.addTest(TestXo('test_create_game', self.tester))
            suite.addTest(TestXo('test_take_space', self.tester))
            # -------------------- #

            result = runner.run(suite)

            if len(result.failures) == 0 and len(result.errors) == 0:
                success = True

        except:
            traceback.print_exc()
            raise

        finally:
            self._tear_down()
            if not success:
                self.fail(self.__class__.__name__)

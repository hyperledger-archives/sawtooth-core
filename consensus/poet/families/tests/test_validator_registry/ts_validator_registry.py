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

from sawtooth_processor_test.tester import TransactionProcessorTester

from test_validator_registry.tests import TestValidatorRegistry


class TestSuiteValidatorRegistry(unittest.TestCase):
    def __init__(self, test_name):
        super().__init__(test_name)
        self.tester = None
        self.tp_process = None

    def _set_up(self):
        url = '0.0.0.0:40000'

        self.tester = TransactionProcessorTester()

        self.tester.listen(url)
        print('Test running in PID: {}'.format(os.getpid()))

        if not self.tester.register_processor():
            raise Exception('Failed to register processor')

    def _tear_down(self):

        if self.tester is not None:
            self.tester.close()

    def test_suite(self):
        success = False
        try:
            self._set_up()

            runner = unittest.TextTestRunner(verbosity=2)
            suite = unittest.TestSuite()

            # --- Tests to run --- #
            suite.addTest(TestValidatorRegistry(
                'test_valid_signup_info', self.tester))
            suite.addTest(TestValidatorRegistry(
                'test_invalid_name', self.tester))
            suite.addTest(TestValidatorRegistry(
                'test_invalid_id', self.tester))
            suite.addTest(TestValidatorRegistry(
                'test_invalid_poet_pubkey', self.tester))
            suite.addTest(TestValidatorRegistry(
                'test_invalid_verification_report', self.tester))
            suite.addTest(TestValidatorRegistry(
                'test_invalid_enclave_body', self.tester))
            suite.addTest(TestValidatorRegistry(
                'test_invalid_pse_manifest', self.tester))

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

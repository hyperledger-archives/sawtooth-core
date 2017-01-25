
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

import os
import unittest
import traceback
from subprocess import Popen

from sawtooth_processor_test.tester import TransactionProcessorTester

from sawtooth_config_test.test_config import TestConfig


class TestSuiteConfig(unittest.TestCase):
    def __init__(self, test_name):
        super().__init__(test_name)
        self.tester = None
        self.tp_process = None

    def _set_up(self):
        url = '127.0.0.1:40000'

        self.tester = TransactionProcessorTester()

        self.tester.listen(url)
        print('Test running in PID: {}'.format(os.getpid()))

        self.tp_process = Popen(['tp_config', url])
        print('Started processor in PID: {}'.format(self.tp_process.pid))

        if not self.tester.register_processor():
            raise Exception('Failed to register processor')

    def _tear_down(self):

        if self.tp_process is not None:
            self.tp_process.terminate()
            self.tp_process.wait()

        if self.tester is not None:
            self.tester.close()

    def test_suite(self):
        success = False
        try:
            self._set_up()

            runner = unittest.TextTestRunner(verbosity=2)
            suite = unittest.TestSuite()

            # --- Tests to run --- #
            suite.addTest(TestConfig('test_set_value_no_auth', self.tester))
            suite.addTest(TestConfig('test_set_value_bad_auth_type',
                                     self.tester))
            suite.addTest(TestConfig('test_error_on_bad_auth_type',
                                     self.tester))
            suite.addTest(TestConfig('test_set_value_bad_approval_threshold',
                                     self.tester))
            suite.addTest(TestConfig('test_set_value_proposals',
                                     self.tester))
            suite.addTest(TestConfig('test_propose_in_ballot_mode',
                                     self.tester))
            suite.addTest(TestConfig('test_vote_in_ballot_mode_approved',
                                     self.tester))
            suite.addTest(TestConfig('test_vote_in_ballot_mode_counted',
                                     self.tester))
            suite.addTest(TestConfig('test_vote_in_ballot_mode_rejected',
                                     self.tester))
            suite.addTest(TestConfig('test_authorized_keys_accept_no_approval',
                                     self.tester))
            suite.addTest(TestConfig(
                'test_authorized_keys_wrong_key_no_approval',
                self.tester))
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

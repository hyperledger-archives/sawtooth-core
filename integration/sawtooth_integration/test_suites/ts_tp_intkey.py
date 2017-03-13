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
import logging
import cbor

from sawtooth_processor_test.tester import TransactionProcessorTester

from sawtooth_integration.tests.test_tp_intkey import TestIntkey
from sawtooth_sdk.protobuf.validator_pb2 import Message

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)

def compare_set_request(req1, req2):
    if len(req1.entries) != len(req2.entries):
        return False

    entries1 = [(e.address, cbor.loads(e.data)) for e in req1.entries]
    entries2 = [(e.address, cbor.loads(e.data)) for e in req2.entries]

    return entries1 == entries2


# Subclass this test for testing different intkey processors.
class TestSuiteIntkey(unittest.TestCase):
    def __init__(self, test_name):
        super().__init__(test_name)
        self.tester = TransactionProcessorTester()

    def _set_up(self):
        url = "0.0.0.0:40000"

        # 1. Init tester
        self.tester.register_comparator(
            Message.TP_STATE_SET_REQUEST, compare_set_request
        )

        LOGGER.info("Test running in PID: %s", str(os.getpid()))
        self.tester.listen(url)
        LOGGER.info("Listening on %s...", str(url))

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
            suite.addTest(TestIntkey('test_set_a', self.tester))
            suite.addTest(TestIntkey('test_inc_a', self.tester))
            suite.addTest(TestIntkey('test_dec_a', self.tester))
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

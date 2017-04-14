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

import unittest

from sawtooth_processor_test.tester import TransactionProcessorTester


class TransactionProcessorTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        url = 'eth0:40000'

        cls.tester = TransactionProcessorTester()

        cls.tester.listen(url)

        if not cls.tester.register_processor():
            raise Exception('Failed to register processor')

    @classmethod
    def tearDownClass(cls):
        try:
            cls.tester.close()
        except AttributeError:
            pass

# Copyright 2018 Intel Corporation
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
# -----------------------------------------------------------------------------

import unittest

from sawtooth_validator.execution.scheduler_parallel import PredecessorChain


class TestPredecessorChain(unittest.TestCase):

    def test_predecessor_chain(self):
        chain = PredecessorChain()

        chain.add_relationship('1', {})

        chain.add_relationship('2', {'1'})

        chain.add_relationship('3', {'1'})

        chain.add_relationship('4', {'3'})

        self.assertTrue(chain.is_predecessor_of_other('1', {'4'}))

        self.assertFalse(chain.is_predecessor_of_other('2', {'4'}))

        chain.add_relationship('5', {'3'})

        chain.add_relationship('6', {'4', '1'})

        self.assertTrue(chain.is_predecessor_of_other('3', {'6'}))

        self.assertFalse(chain.is_predecessor_of_other('2', {'6'}))

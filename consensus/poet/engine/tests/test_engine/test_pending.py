# Copyright 2016, 2017 Intel Corporation
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

from sawtooth_poet_engine.pending import PendingForks


class Block:
    def __init__(self, id, previous):
        self.block_id = id
        self.previous_id = previous


class TestPendingForks(unittest.TestCase):

    def test_simple(self):
        """Test that blocks that don't extend are FIFO."""
        pending = PendingForks()

        a = Block('a', '0')
        b = Block('b', '0')
        c = Block('c', '0')

        pending.push(a)
        pending.push(b)
        pending.push(c)

        self.assertEqual(pending.pop(), a)
        self.assertEqual(pending.pop(), b)
        self.assertEqual(pending.pop(), c)
        self.assertEqual(pending.pop(), None)

    def test_simple_replace(self):
        """Test that a block that extends an existing block replaces it and
        maintains priority in queue."""
        pending = PendingForks()

        a = Block('a', '0')
        b = Block('b', '0')
        c = Block('c', 'a')

        pending.push(a)
        pending.push(b)
        pending.push(c)

        self.assertEqual(pending.pop(), c)
        self.assertEqual(pending.pop(), b)
        self.assertEqual(pending.pop(), None)

    def test_replace(self):
        """Test that replacing works correctly when pop()'s are interleaved
        with push()'es."""
        pending = PendingForks()

        a = Block('a', '0')
        b = Block('b', 'a')
        c = Block('c', 'b')
        d = Block('d', 'c')

        aa = Block('aa', '0')
        bb = Block('bb', 'aa')
        cc = Block('cc', 'bb')

        pending.push(a)
        pending.push(aa)
        pending.push(b)
        pending.push(bb)
        pending.push(c)

        self.assertEqual(pending.pop(), c)

        pending.push(cc)
        pending.push(d)

        self.assertEqual(pending.pop(), cc)
        self.assertEqual(pending.pop(), d)
        self.assertEqual(pending.pop(), None)

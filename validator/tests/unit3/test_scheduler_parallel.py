# Copyright 2016-2017 Intel Corporation
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

from sawtooth_validator.scheduler.parallel import RadixTree
from sawtooth_validator.scheduler.parallel import TopologicalSorter


class TestRadixTree(unittest.TestCase):

    def test_radix_tree(self):
        """Tests basic functionality of the scheduler's radix tree.
        """
        address_a = \
            'ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb'
        address_b = \
            '3e23e8160039594a33894f6564e1b1348bbd7a0088d42c4acb73eeaed59c009d'

        tree = RadixTree()
        tree.add_reader(address_a, 'txn1')
        tree.add_reader(address_b, 'txn2')

        node = tree.get(address_a)
        self.assertIsNotNone(node)
        self.assertEqual(node.readers, ['txn1'])
        self.assertIsNone(node.writer)
        self.assertEqual(node.children, {})

        node = tree.get(address_b)
        self.assertIsNotNone(node)
        self.assertEqual(node.readers, ['txn2'])
        self.assertIsNone(node.writer, None)
        self.assertEqual(node.children, {})

        # Set a writer for address_a.
        tree.set_writer(address_a, 'txn1')

        # Verify address_a now contains txn1 as the writer, with no
        # readers set.
        node = tree.get(address_a)
        self.assertIsNotNone(node)
        self.assertEqual(node.readers, [])
        self.assertEqual(node.writer, 'txn1')
        self.assertEqual(node.children, {})

        # Verify address_b didn't change when address_a was modified.
        node = tree.get(address_b)
        self.assertIsNotNone(node)
        self.assertEqual(node.readers, ['txn2'])
        self.assertIsNone(node.writer)
        self.assertEqual(node.children, {})

        # Set a writer for a prefix of address_b.
        tree.set_writer(address_b[0:4], 'txn3')

        # Verify address_b[0:4] now contains txn3 as the writer, with
        # no readers set and no children.
        node = tree.get(address_b[0:4])
        self.assertIsNotNone(node)
        self.assertEqual(node.readers, [])
        self.assertEqual(node.writer, 'txn3')
        self.assertEqual(node.children, {})

        # Verify address_b now returns None
        node = tree.get(address_b)
        self.assertIsNone(node)

        # Verify address_a didn't change when address_b[0:4] was modified.
        node = tree.get(address_a)
        self.assertIsNotNone(node)
        self.assertEqual(node.readers, [])
        self.assertEqual(node.writer, 'txn1')
        self.assertEqual(node.children, {})

        # Add readers for address_a, address_b
        tree.add_reader(address_a, 'txn1')
        tree.add_reader(address_b, 'txn2')

        node = tree.get(address_a)
        self.assertIsNotNone(node)
        self.assertEqual(node.readers, ['txn1'])
        self.assertEqual(node.writer, 'txn1')
        self.assertEqual(node.children, {})

        node = tree.get(address_b)
        self.assertIsNotNone(node)
        self.assertEqual(node.readers, ['txn2'])
        self.assertIsNone(node.writer)
        self.assertEqual(node.children, {})

        # Verify address_b[0:4] now contains txn3 as the writer, with
        # no readers set and 'e8' as a child.
        node = tree.get(address_b[0:4])
        self.assertIsNotNone(node)
        self.assertEqual(node.readers, [])
        self.assertEqual(node.writer, 'txn3')
        self.assertEqual(list(node.children.keys()), ['e8'])

        self.assertEqual(
            tree.find_readers_and_writers(address_a),
            ['txn1'])
        self.assertEqual(
            tree.find_readers_and_writers(address_b),
            ['txn3', 'txn2'])


class TestTopologicalSorter(unittest.TestCase):

    def test_topological_sorter(self):
        sorter = TopologicalSorter()
        sorter.add_relation('9', '2')
        sorter.add_relation('3', '7')
        sorter.add_relation('7', '5')
        sorter.add_relation('5', '8')
        sorter.add_relation('8', '6')
        sorter.add_relation('4', '6')
        sorter.add_relation('1', '3')
        sorter.add_relation('7', '4')
        sorter.add_relation('9', '5')
        sorter.add_relation('2', '8')
        self.assertEqual(
            sorter.order(),
            ['9', '2', '1', '3', '7', '5', '8', '4', '6'])

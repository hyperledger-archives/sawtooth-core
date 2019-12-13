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
# ----------------------------------------------------------------------------

# pylint: disable=too-many-lines,protected-access

import unittest

import logging

from sawtooth_validator.execution.scheduler_parallel import PredecessorTree


LOGGER = logging.getLogger(__name__)


class TestPredecessorTree(unittest.TestCase):
    '''
    With an empty tree initialized in setUp, the predecessor tree
    tests generally follow this pattern (repeated several times):

        1) Add some readers or writers. In most cases, a diagram
           will be given in comments to show what the tree should
           look like after the additions.
        2) Assert the readers, writers, and children at all addresses
           in the tree (using assert_rwc_at_addresses). Possibly also
           assert (using assert_no_nodes_at_addresses) that nodes don't
           exist at certain addresses (this is normally done after
           setting a writer).
        3) Assert the total count of readers and writers in the tree
           (using assert_rw_count). This ensures that nothing is in the
           tree that shouldn't be there.
        4) Assert the read and write predecessors for various addresses
           (using assert_rw_preds_at_addresses).

    '''

    def setUp(self):
        self.tree = PredecessorTree()

    def tearDown(self):
        self.tree = None

    def test_predecessor_tree(self):
        '''Tests basic predecessor tree functions

        This test is intended to show the evolution of a tree
        over the course of normal use. Apart from testing, it
        can also be used as a reference example.

        Readers and writers are added in the following steps:

        1) Add some readers.
        2) Add readers at addresses that are initial segments
           of existing node addresses.
        3) Add a writer in the middle of the tree.
        4) Add readers to existing nodes.
        5) Add a writer to a new node.
        6) Add writers in the middle of the tree.
        7) Add readers to upper nodes.
        8) Add readers to nodes with writers.
        9) Add readers to new top nodes.
        10) Add writer to top node.
        11) Add readers to upper nodes, then add writers.
        12) Add writer to top node, then add reader.
        13) Add writer to root
        '''

        # 1) Add some readers.

        self.add_readers({
            'radix': 1,
            'radish': 2,
            'radon': 3,
            'razzle': 4,
            'rustic': 5
        })

        # ROOT:
        #   r:
        #     a:
        #       d:
        #         o:
        #           n: Readers: [3]
        #         i:
        #           x: Readers: [1]
        #           s:
        #             h: Readers: [2]
        #       z:
        #         z:
        #           l:
        #             e: Readers: [4]
        #     u:
        #       s:
        #         t:
        #           i:
        #             c: Readers: [5]

        self.assert_rw_count(5, 0)

        self.assert_rw_preds_at_addresses({
            'r': ({}, {1, 2, 3, 4, 5}),
            'rad': ({}, {1, 2, 3}),
            'radi': ({}, {1, 2}),
            'radix': ({}, {1}),
        })

        # 2) Add readers at addresses that are initial segments
        #    of existing node addresses.

        self.add_readers({
            'rad': 6,
            'rust': 7
        })

        # ROOT:
        #   r:
        #     a:
        #       d: Readers: [6]
        #         o:
        #           n: Readers: [3]
        #         i:
        #           x: Readers: [1]
        #           s:
        #             h: Readers: [2]
        #       z:
        #         z:
        #           l:
        #             e: Readers: [4]
        #     u:
        #       s:
        #         t: Readers: [7]
        #           i:
        #             c: Readers: [5]

        self.assert_rw_count(7, 0)

        self.assert_rw_preds_at_addresses({
            'ra': ({}, {1, 2, 3, 4, 6}),
            'ru': ({}, {5, 7}),
        })

        # 3) Add a writer in the middle of the tree.

        self.set_writer('radi', 8)

        # ROOT:
        #   r:
        #     u:
        #       s:
        #         t: Readers: [7]
        #           i:
        #             c: Readers: [5]
        #     a:
        #       d: Readers: [6]
        #         o:
        #           n: Readers: [3]
        #         i: Writer: 8
        #       z:
        #         z:
        #           l:
        #             e: Readers: [4]

        self.assert_rw_count(5, 1)

        self.assert_rw_preds_at_addresses({
            'rad': ({8}, {3, 6, 8}),
            'radi': ({8}, {6, 8}),
            'radical': ({8}, {6, 8}),
        })

        # 4) Add readers to existing nodes.

        self.add_readers({
            'rad': 9,
            'radi': 10,
            'radio': 11,
            'radon': 12,
            'rust': 13
        })

        # ROOT:
        #   r:
        #     u:
        #       s:
        #         t: Readers: [7, 13]
        #           i:
        #             c: Readers: [5]
        #     a:
        #       d: Readers: [6, 9]
        #         o:
        #           n: Readers: [3, 12]
        #         i: Writer: 8 Readers: [10]
        #           o: Readers: [11]
        #       z:
        #         z:
        #           l:
        #             e: Readers: [4]

        self.assert_rw_count(10, 1)

        self.assert_rw_preds_at_addresses({
            'rad': ({8}, {6, 9, 10, 8, 11, 3, 12}),
            'ru': ({}, {7, 13, 5}),
        })

        # 5) Add a writer to a new node.

        self.set_writer('radii', 14)

        # ROOT:
        #   r:
        #     u:
        #       s:
        #         t: Readers: [7, 13]
        #           i:
        #             c: Readers: [5]
        #     a:
        #       d: Readers: [6, 9]
        #         o:
        #           n: Readers: [3, 12]
        #         i: Writer: 8 Readers: [10]
        #           o: Readers: [11]
        #           i: Writer: 14
        #       z:
        #         z:
        #           l:
        #             e: Readers: [4]

        self.assert_rw_count(10, 2)

        self.assert_rw_preds_at_addresses({
            'radi': ({8, 14}, {6, 9, 10, 8, 14, 11}),
            'radii': ({14}, {6, 9, 10, 14}),
            'radio': ({8}, {6, 9, 10, 8, 11}),
        })

        # 6) Add writers in the middle of the tree.

        self.set_writers({
            'rust': 15,
            'rad': 16
        })

        # ROOT:
        #   r:
        #     u:
        #       s:
        #         t: Writer: 15
        #     a:
        #       d: Writer: 16
        #       z:
        #         z:
        #           l:
        #             e: Readers: [4]

        self.assert_rw_count(1, 2)

        self.assert_rw_preds_at_addresses({
            'r': ({16, 15}, {16, 4, 15}),
            'ru': ({15}, {15}),
            'rust': ({15}, {15}),
            'rustic': ({15}, {15}),
        })

        # 7) Add readers to upper nodes.

        self.add_readers({
            'r': 17,
            'ra': 18,
            'ru': 19,
        })

        # ROOT:
        #   r: Readers: [17]
        #     u: Readers: [19]
        #       s:
        #         t: Writer: 15
        #     a: Readers: [18]
        #       d: Writer: 16
        #       z:
        #         z:
        #           l:
        #             e: Readers: [4]

        self.assert_rw_count(4, 2)

        self.assert_rw_preds_at_addresses({
            'r': ({15, 16}, {17, 19, 15, 18, 16, 4}),
            'ru': ({15}, {17, 19, 15}),
        })

        # 8) Add readers to nodes with writers.

        self.add_readers({
            'rad': 20,
            'rust': 21
        })

        # ROOT:
        #   r: Readers: [17]
        #     u: Readers: [19]
        #       s:
        #         t: Writer: 15 Readers: [21]
        #     a: Readers: [18]
        #       d: Writer: 16 Readers: [20]
        #       z:
        #         z:
        #           l:
        #             e: Readers: [4]

        self.assert_rw_count(6, 2)

        self.assert_rw_preds_at_addresses({
            '': ({16, 15}, {17, 18, 20, 16, 4, 19, 21, 15}),
            'rad': ({16}, {17, 18, 20, 16}),
            'rust': ({15}, {17, 19, 21, 15}),
        })

        # 9) Add readers to new top nodes.

        self.add_readers({
            's': 22,
            't': 23,
        })

        # ROOT:
        #   t: Readers: [23]
        #   s: Readers: [22]
        #   r: Readers: [17]
        #     u: Readers: [19]
        #       s:
        #         t: Writer: 15 Readers: [21]
        #     a: Readers: [18]
        #       d: Writer: 16 Readers: [20]
        #       z:
        #         z:
        #           l:
        #             e: Readers: [4]

        self.assert_rw_count(8, 2)

        self.assert_rw_preds_at_addresses({
            's': ({}, {22}),
            't': ({}, {23}),
            'r': ({16, 15}, {17, 18, 20, 16, 4, 19, 21, 15}),
        })

        # 10) Add writer to top node.

        self.set_writer('s', 24)

        # ROOT:
        #   t: Readers: [23]
        #   s: Writer: 24
        #   r: Readers: [17]
        #     u: Readers: [19]
        #       s:
        #         t: Writer: 15 Readers: [21]
        #     a: Readers: [18]
        #       d: Writer: 16 Readers: [20]
        #       z:
        #         z:
        #           l:
        #             e: Readers: [4]

        self.assert_rw_count(7, 3)

        self.assert_rw_preds_at_addresses({
            's': ({24}, {24}),
            't': ({}, {23}),
            'r': ({16, 15}, {17, 18, 20, 16, 4, 19, 21, 15}),
        })

        # 11) Add readers to upper nodes, then add writers.

        self.add_readers({
            'ra': 25,
            'ru': 26,
        })

        self.set_writers({
            'ra': 27,
            'ru': 28,
        })

        # ROOT:
        #   t: Readers: [23]
        #   s: Writer: 24
        #   r: Readers: [17]
        #     u: Writer: 28
        #     a: Writer: 27

        self.assert_rw_preds_at_addresses({
            'r': ({27, 28}, {17, 27, 28}),
            'ra': ({27}, {17, 27}),
            'rad': ({27}, {17, 27}),
        })

        # 12) Add writer to top node, then add reader.

        self.set_writer('r', 29)
        self.add_reader('r', 30)

        # ROOT:
        #   t: Readers: [23]
        #   s: Writer: 24
        #   r: Writer: 29 Readers: [30]

        self.assert_rw_count(2, 2)

        self.assert_rw_preds_at_addresses({
            'r': ({29}, {30, 29}),
            'roger': ({29}, {30, 29}),
            'ebert': ({}, {}),
        })

        # 13) Add writer to root

        self.set_writer('', 0)

        # ROOT: Writer: 0

        self.assert_rw_count(0, 1)

        self.assert_rw_preds_at_addresses({
            '': ({0}, {0}),
            'r': ({0}, {0}),
            's': ({0}, {0}),
            'rabbit': ({0}, {0}),
        })

    def test_initial_segment_addresses(self):
        '''Tests addresses with and without common initial segments
        '''

        expected = (
            ('c', 1),
            ('ca', 2),
            ('cat', 3),
        )

        for address, val in expected:
            self.set_writer(address, val)
            self.add_reader(address, val)

        # ROOT:
        #   c: Writer: 1 Readers: [1]
        #     a: Writer: 2 Readers: [2]
        #       t: Writer: 3 Readers: [3]

        self.assert_rw_count(3, 3)

        # 'cath' isn't on the tree, so it should have
        # the same predecessors as 'cat'

        self.assert_rw_preds_at_addresses({
            '': ({1, 2, 3}, {1, 2, 3}),
            'c': ({1, 2, 3}, {1, 2, 3}),
            'ca': ({2, 3}, {1, 2, 3}),
            'cat': ({3}, {1, 2, 3}),
            'cath': ({3}, {1, 2, 3}),
        })

        # add reader and writer at an address with a common initial segment

        self.set_writer('carp', 4)
        self.add_reader('carp', 4)

        # ROOT:
        #   c: Writer: 1 Readers: [1]
        #     a: Writer: 2 Readers: [2]
        #       r:
        #         p: Writer: 4 Readers: [4]
        #       t: Writer: 3 Readers: [3]

        self.assert_rw_count(4, 4)

        self.assert_rw_preds_at_addresses({
            '': ({1, 2, 3, 4}, {1, 2, 3, 4}),
            'c': ({1, 2, 3, 4}, {1, 2, 3, 4}),
            'ca': ({2, 3, 4}, {1, 2, 3, 4}),
            'cat': ({3}, {1, 2, 3}),
            'cath': ({3}, {1, 2, 3}),
            'carp': ({4}, {1, 2, 4}),
        })

        # add reader and writer at an address with no common initial segment

        self.set_writer('dog', 5)
        self.add_reader('dog', 5)

        # ROOT:
        #   c: Writer: 1 Readers: [1]
        #     a: Writer: 2 Readers: [2]
        #       r:
        #         p: Writer: 4 Readers: [4]
        #       t: Writer: 3 Readers: [3]
        #   d:
        #     o:
        #       g: Writer: 5 Readers: [5]

        self.assert_rw_count(5, 5)

        self.assert_rw_preds_at_addresses({
            '': ({1, 2, 3, 4, 5}, {1, 2, 3, 4, 5}),
            'c': ({1, 2, 3, 4}, {1, 2, 3, 4}),
            'ca': ({2, 3, 4}, {1, 2, 3, 4}),
            'cat': ({3}, {1, 2, 3}),
            'cath': ({3}, {1, 2, 3}),
            'carp': ({4}, {1, 2, 4}),
            'dog': ({5}, {5}),
        })

        # check predecessors of an address that isn't on the tree at all

        self.assert_rw_preds_at_addresses({
            'yak': ({}, {}),
        })

        # add readers to root and check again

        self.add_reader('', 6)
        self.add_reader('', 7)

        # ROOT: Readers: [6, 7]
        #   c: Writer: 1 Readers: [1]
        #     a: Writer: 2 Readers: [2]
        #       r:
        #         p: Writer: 4 Readers: [4]
        #       t: Writer: 3 Readers: [3]
        #   d:
        #     o:
        #       g: Writer: 5 Readers: [5]

        self.assert_rw_count(7, 5)

        self.assert_rw_preds_at_addresses({
            '': ({1, 2, 3, 4, 5}, {1, 2, 3, 4, 5, 6, 7}),
            'c': ({1, 2, 3, 4}, {1, 2, 3, 4, 6, 7}),
            'ca': ({2, 3, 4}, {1, 2, 3, 4, 6, 7}),
            'cat': ({3}, {1, 2, 3, 6, 7}),
            'cath': ({3}, {1, 2, 3, 6, 7}),
            'carp': ({4}, {1, 2, 4, 6, 7}),
            'dog': ({5}, {5, 6, 7}),
            'yak': ({}, {6, 7}),
        })

    def test_add_writers_to_same_node(self):
        '''Adds a series of writers one after the other
        to a single node, verifying after each new writer
        that there is nothing else at that node and that
        there is just one writer in the whole tree.
        '''

        # Set writer num at 'address'
        for num in range(10):
            self.set_writer('plum', num)

            # ROOT:
            #   p:
            #     l:
            #       u:
            #         m: Writer: ,num

            self.assert_rw_count(0, 1)

            self.assert_rw_preds_at_addresses({
                '': ({num}, {num}),
                'p': ({num}, {num}),
                'pl': ({num}, {num}),
                'plu': ({num}, {num}),
                'plum': ({num}, {num}),
            })

    def test_add_lists_of_readers(self):
        '''Tests multiple readers at nodes
        '''

        for address in ('p', 'pu', 'pug'):
            self.set_writer(address, 0)
            for i in range(1, 4):
                self.add_reader(address, i)

        # ROOT:
        #   p: Writer: 0 Readers: [1, 2, 3]
        #     u: Writer: 0 Readers: [1, 2, 3]
        #       g: Writer: 0 Readers: [1, 2, 3]

        self.assert_rw_count(9, 3)

        self.assert_rw_preds_at_addresses({
            '': ({0}, {0, 1, 2, 3}),
            'p': ({0}, {0, 1, 2, 3}),
            'pu': ({0}, {0, 1, 2, 3}),
            'pug': ({0}, {0, 1, 2, 3}),
            'pugs': ({0}, {0, 1, 2, 3}),
        })

        # add a writer and verify that downstream readers are gone

        self.set_writer('pu', 4)

        # ROOT:
        #   p: Writer: 0 Readers: [1, 2, 3]
        #     u: Writer: 4

        self.assert_rw_count(3, 2)

        self.assert_rw_preds_at_addresses({
            '': ({0, 4}, {0, 1, 2, 3, 4}),
            'p': ({0, 4}, {0, 1, 2, 3, 4}),
            'pu': ({4}, {1, 2, 3, 4}),
        })

    def test_long_addresses(self):
        """Tests predecessor tree with len-64 addresses
        """

        self.tree = PredecessorTree()

        address_a = \
            'ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb'
        address_b = \
            '3e23e8160039594a33894f6564e1b1348bbd7a0088d42c4acb73eeaed59c009d'

        self.add_readers({
            address_a: 'txn1',
            address_b: 'txn2'
        })

        # Set a writer for address_a.
        self.set_writer(address_a, 'txn1')

        # Verify address_a now contains txn1 as the writer, with no
        # readers set.

        # Verify address_b didn't change when address_a was modified.

        # Set a writer for a prefix of address_b.
        address_c = address_b[0:4]

        self.set_writer(address_c, 'txn3')

        # Verify address_c now contains txn3 as the writer, with
        # no readers set and no children.

        # Verify address_a didn't change when address_c was modified.
        # Verify address_b now returns None
        # Add readers for address_a, address_b
        self.add_readers({
            address_a: 'txn1',
            address_b: 'txn2'
        })

        # Verify address_c now contains txn3 as the writer, with
        # no readers set and 'e8' as a child.
        self.assert_rw_preds_at_addresses({
            address_a: ({'txn1'}, {'txn1'}),
            address_b: ({'txn3'}, {'txn3', 'txn2'}),
            address_c: ({'txn3'}, {'txn3', 'txn2'}),
        })

        self.assert_rw_count(2, 2)

    # assertions

    def assert_rw_count(self, reader_count, writer_count):
        '''
        Asserts the total number of readers and writers in the tree
        '''

        readers, writers = 0, 0

        for _, node in self.tree._tree.walk(''):
            if node is not None:
                if node.writer is not None:
                    writers += 1

                readers += len(node.readers)

        error_msg = 'Incorrect {} count'

        self.assertEqual(
            reader_count,
            readers,
            error_msg.format('reader'))

        self.assertEqual(
            writer_count,
            writers,
            error_msg.format('writer'))

    def assert_rw_preds_at_addresses(self, rw_pred_dict):
        '''
        Asserts the read predecessors and write predecessors at an address

        rw_pred_dict = {address: (read_preds, write_preds)}
        '''

        for address, rw_preds in rw_pred_dict.items():
            error_msg = 'Address "{}": '.format(
                address) + 'incorrect {} predecesors'

            read_preds, write_preds = rw_preds

            self.assertEqual(
                self.tree.find_read_predecessors(address),
                set(read_preds),
                error_msg.format('read'))

            self.assertEqual(
                self.tree.find_write_predecessors(address),
                set(write_preds),
                error_msg.format('write'))

    # basic tree operations (for convenience)

    def add_readers(self, reader_dict):
        '''
        reader_dict = {address: reader}
        '''
        for address, reader in reader_dict.items():
            self.add_reader(address, reader)

    def set_writers(self, writer_dict):
        '''
        writer_dict = {address: writer}

        The order in which writers are added matters, since they can
        overwrite each other. If a specific order is required,
        an OrderedDict should be used.
        '''
        for address, writer in writer_dict.items():
            self.set_writer(address, writer)

    def add_reader(self, address, txn):
        self.tree.add_reader(address, txn)

    def set_writer(self, address, txn):
        self.tree.set_writer(address, txn)

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

# pylint: disable=pointless-statement

import logging
import unittest

from sawtooth_validator.database.dict_database import DictDatabase
from sawtooth_validator.journal.block_store import BlockStore
from sawtooth_validator.journal.block_wrapper import NULL_BLOCK_IDENTIFIER
from sawtooth_validator.journal.block_wrapper import BlockWrapper

from sawtooth_validator.protobuf.block_pb2 import Block
from sawtooth_validator.protobuf.block_pb2 import BlockHeader

from test_journal.block_tree_manager import BlockTreeManager


LOGGER = logging.getLogger(__name__)


class BlockStoreTest(unittest.TestCase):

    def setUp(self):
        self.block_tree_manager = BlockTreeManager()

    def test_chain_head(self):
        """ Test that the chain head can be retrieved from the
        BlockStore.
        """
        block = self.create_block()
        block_store = self.create_block_store(
            {
                block.header_signature: block
            })
        chain_head = block_store.chain_head
        self.assert_blocks_equal(chain_head, block)

    def test_get(self):
        """ Test BlockStore block get operations.
        """
        block = self.create_block()
        block_store = self.create_block_store(
            {
                block.header_signature: block
            })
        chain_head = block_store[block.header_signature]
        self.assert_blocks_equal(chain_head, block)

        with self.assertRaises(KeyError):
            block_store['txn']

        with self.assertRaises(KeyError):
            chain_head = block_store['missing']

    def test_set(self):
        """ Test BlockStore block set operations.
        """
        block = self.create_block()
        block_store = self.create_block_store(
            {
                block.header_signature: block,
            })
        block2 = self.create_block()
        with self.assertRaises(KeyError):
            block_store['head'] = block2

        block_store[block2.identifier] = block2

        stored_block = block_store[block2.identifier]
        self.assert_blocks_equal(stored_block, block2)

        with self.assertRaises(AttributeError):
            block_store['batch'] = 'head'

    def test_has(self):
        """ Test BlockStore tests if Transactions and Batches
        are commited to the current chain.
        """
        block = self.create_block()
        block_store = self.create_block_store(
            {
                block.header_signature: block
            })

        self.assertTrue(block_store.has_transaction(
            _get_first_txn_id(block)))
        self.assertFalse(block_store.has_transaction('txn_missing'))
        self.assertTrue(block_store.has_batch(
            _get_first_batch_id(block)))
        self.assertFalse(block_store.has_transaction('batch_missing'))

        self.assertTrue(block.header_signature in block_store)

        self.assertFalse('block_missing' in block_store)
        self.assertFalse('batch_missing' in block_store)
        self.assertFalse('txn_missing' in block_store)

    def test_get_block_by_batch_id(self):
        """ Test BlockStore retrieval of a Block that contains a specific
        batch.
        """
        block = self.create_block()
        block_store = self.create_block_store()
        block_store.update_chain([block])

        batch_id = block.batches[0].header_signature
        stored = block_store.get_block_by_batch_id(batch_id)
        self.assert_blocks_equal(stored, block)

        with self.assertRaises(ValueError):
            block_store.get_block_by_batch_id("bad")

    def test_get_batch_by_transaction(self):
        """ Test BlockStore retrieval of a Batch that contains a specific
        transaction.
        """
        block = self.create_block()
        block_store = self.create_block_store()
        block_store.update_chain([block])

        batch = block.batches[0]
        txn_id = batch.transactions[0].header_signature
        stored = block_store.get_batch_by_transaction(txn_id)
        self.asset_protobufs_equal(stored, batch)

        with self.assertRaises(ValueError):
            block_store.get_batch_by_transaction("bad")

    def test_get_block_by_transaction_id(self):
        """ Test BlockStore retrieval of a Block that contains a specific
        transaction.
        """
        block = self.create_block()
        block_store = self.create_block_store()
        block_store.update_chain([block])

        txn_id = block.batches[0].transactions[0].header_signature
        stored = block_store.get_block_by_transaction_id(txn_id)
        self.assert_blocks_equal(stored, block)

        with self.assertRaises(ValueError):
            stored = block_store.get_block_by_transaction_id("bad")

    def test_get_batch(self):
        """ Test BlockStore retrieval of a batch by id.
        """
        block = self.create_block()
        block_store = self.create_block_store()
        block_store.update_chain([block])

        batch = block.batches[0]
        batch_id = batch.header_signature
        stored = block_store.get_batch(batch_id)
        self.asset_protobufs_equal(stored, batch)

        with self.assertRaises(ValueError):
            stored = block_store.get_batch("bad")

    def test_get_transaction(self):
        """ Test BlockStore retrieval of a transaction by id.
        """
        block = self.create_block()
        block_store = self.create_block_store()
        block_store.update_chain([block])

        txn = block.batches[0].transactions[0]
        txn_id = txn.header_signature
        stored = block_store.get_transaction(txn_id)
        self.asset_protobufs_equal(stored, txn)

        with self.assertRaises(ValueError):
            stored = block_store.get_transaction("bad")

    def test_get_count(self):
        """ Test BlockStore get_*_count operations.
        """
        block = self.create_block()
        block_store = self.create_block_store()
        block_store.update_chain([block])

        self.assertEqual(1, block_store.get_block_count())
        self.assertEqual(1, block_store.get_batch_count())
        self.assertEqual(1, block_store.get_transaction_count())

    def assert_blocks_equal(self, stored, reference):
        self.asset_protobufs_equal(stored.block,
                                   reference.block)

    def asset_protobufs_equal(self, stored, reference):
        self.assertEqual(self.encode(stored),
                         self.encode(reference))

    @staticmethod
    def create_block_store(data=None):
        return BlockStore(DictDatabase(
            data, indexes=BlockStore.create_index_configuration()))

    def create_block(self):
        return self.block_tree_manager.create_block()

    @staticmethod
    def encode(obj):
        return obj.SerializeToString()


class BlockStorePredecessorIteratorTest(unittest.TestCase):

    def test_iterate_chain(self):
        """Given a block store, create an predecessor iterator.

        1. Create a chain of length 5.
        2. Iterate the chain using the get_predecessor_iter from the chain head
        3. Verify that the block ids match the chain, in reverse order
        """

        block_store = BlockStore(DictDatabase(
            indexes=BlockStore.create_index_configuration()))
        chain = self._create_chain(5)
        block_store.update_chain(chain)

        ids = [b.identifier for b in block_store.get_predecessor_iter()]

        self.assertEqual(
            ['abcd4', 'abcd3', 'abcd2', 'abcd1', 'abcd0'],
            ids)

    def test_iterate_chain_from_starting_block(self):
        """Given a block store, iterate if using an predecessor iterator from
        a particular start point in the chain.

        1. Create a chain of length 5.
        2. Iterate the chain using the get_predecessor_iter from block 3
        3. Verify that the block ids match the chain, in reverse order
        """
        block_store = BlockStore(DictDatabase(
            indexes=BlockStore.create_index_configuration()))
        chain = self._create_chain(5)
        block_store.update_chain(chain)

        block = block_store['abcd2']

        ids = [b.identifier
               for b in block_store.get_predecessor_iter(block)]

        self.assertEqual(
            ['abcd2', 'abcd1', 'abcd0'],
            ids)

    def test_iterate_chain_on_empty_block_store(self):
        """Given a block store with no blocks, iterate using predecessor
        iterator and verify that it results in an empty list.
        """
        block_store = BlockStore(DictDatabase(
            indexes=BlockStore.create_index_configuration()))

        self.assertEqual([], [b for b in block_store.get_predecessor_iter()])

    def _create_chain(self, length):
        chain = []
        previous_block_id = NULL_BLOCK_IDENTIFIER
        for i in range(length):
            block = BlockWrapper(
                Block(header_signature='abcd{}'.format(i),
                      batches=[],
                      header=BlockHeader(
                          block_num=i,
                          previous_block_id=previous_block_id
                ).SerializeToString()))

            previous_block_id = block.identifier

            chain.append(block)

        chain.reverse()

        return chain


def _get_first_batch_id(block):
    for batch in block.batches:
        return batch.header_signature

    return None


def _get_first_txn_id(block):
    for batch in block.batches:
        for txn in batch.transactions:
            return txn.header_signature

    return None

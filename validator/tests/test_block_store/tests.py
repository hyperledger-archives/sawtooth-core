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

from sawtooth_validator.database.dict_database import DictDatabase
from sawtooth_validator.exceptions import PossibleForkDetectedError
from sawtooth_validator.journal.block_store import BlockStore
from sawtooth_validator.journal.block_wrapper import NULL_BLOCK_IDENTIFIER
from sawtooth_validator.journal.block_wrapper import BlockWrapper

from sawtooth_validator.protobuf.block_pb2 import Block
from sawtooth_validator.protobuf.block_pb2 import BlockHeader


class BlockStorePredecessorIteratorTest(unittest.TestCase):

    def test_iterate_chain(self):
        """Given a block store, create an predecessor iterator.

        1. Create a chain of length 5.
        2. Iterate the chain using the get_predecessor_iter from the chain head
        3. Verify that the block ids match the chain, in reverse order
        """

        block_store = BlockStore(DictDatabase())
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
        block_store = BlockStore(DictDatabase())
        chain = self._create_chain(5)
        block_store.update_chain(chain)

        block = block_store['abcd2']

        ids = [b.identifier
               for b in block_store.get_predecessor_iter(block)]

        self.assertEqual(
            ['abcd2', 'abcd1', 'abcd0'],
            ids)

    def test_iterate_chain_on_empty_block_store(self):
        """Given a block store with no blocks, iterate using predecessor iterator
        and verify that it results in an empty list.
        """
        block_store = BlockStore(DictDatabase())

        self.assertEqual([], [b for b in block_store.get_predecessor_iter()])

    def test_fork_detection_on_iteration(self):
        """Given a block store where a fork occurred while using the predecessor
        iterator, it should throw a PossibleForkDetectedError.

        The fork occurrance will be simulated.
        """
        block_store = BlockStore(DictDatabase())
        chain = self._create_chain(5)
        block_store.update_chain(chain)

        iterator = block_store.get_predecessor_iter()

        self.assertEqual('abcd4', next(iterator).identifier)

        del block_store['abcd3']

        with self.assertRaises(PossibleForkDetectedError):
            next(iterator)

    def _create_chain(self, length):
        chain = []
        previous_block_id = NULL_BLOCK_IDENTIFIER
        for i in range(length):
            block = BlockWrapper(
                Block(header_signature='abcd{}'.format(i),
                      header=BlockHeader(
                          block_num=i,
                          previous_block_id=previous_block_id
                      ).SerializeToString()))

            previous_block_id = block.identifier

            chain.append(block)

        chain.reverse()

        return chain

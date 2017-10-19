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

# pylint: disable=no-name-in-module
from collections.abc import MutableMapping

from sawtooth_validator.exceptions import PossibleForkDetectedError
from sawtooth_validator.journal.block_wrapper import NULL_BLOCK_IDENTIFIER
from sawtooth_validator.journal.block_wrapper import BlockStatus
from sawtooth_validator.journal.block_wrapper import BlockWrapper
from sawtooth_validator.protobuf.block_pb2 import Block
from sawtooth_validator.state.merkle import INIT_ROOT_KEY


class BlockStore(MutableMapping):
    """
    A dict like interface wrapper around the block store to guarantee,
    objects are correctly wrapped and unwrapped as they are stored and
    retrieved.
    """
    def __init__(self, block_db):
        self._block_store = block_db

    def __setitem__(self, key, value):
        if key != value.identifier:
            raise KeyError("Invalid key to store block under: {} expected {}".
                           format(key, value.identifier))
        self._block_store.put(key, value)

    def __getitem__(self, key):
        return self._get_block(key)

    def __delitem__(self, key):
        del self._block_store[key]

    def __contains__(self, x):
        return x in self._block_store

    def __iter__(self):
        return _BlockPredecessorIterator(self, start_block=self.chain_head)

    def __len__(self):
        # Required by abstract base class, but implementing is non-trivial
        raise NotImplementedError('BlockStore has no meaningful length')

    def __str__(self):
        out = []
        for key in self._block_store.keys():
            value = self._block_store[key]
            out.append(str(value))
        return ','.join(out)

    @staticmethod
    def create_index_configuration():
        return {
            'batch': BlockStore._batch_index_keys,
            'transaction': BlockStore._transaction_index_keys,
            'block_num': BlockStore._block_num_index_keys,
        }

    @staticmethod
    def deserialize_block(value):
        """
        Deserialize a byte string into a BlockWrapper

        Args:
            value (bytes): the byte string to deserialze

        Returns:
            BlockWrapper: a block wrapper instance
        """
        # Block id strings are stored under batch/txn ids for reference.
        # Only Blocks, not ids or Nones, should be returned by _get_block.
        block = Block()
        block.ParseFromString(value)
        return BlockWrapper(
            status=BlockStatus.Valid,
            block=block)

    @staticmethod
    def serialize_block(blkw):
        """
        Given a block wrapper, produce a byte string

        Args:
            blkw: (:obj:`BlockWrapper`) a block wrapper to serialize

        Returns:
            bytes: the serialized bytes
        """
        return blkw.block.SerializeToString()

    def update_chain(self, new_chain, old_chain=None):
        """
        Set the current chain head, does not validate that the block
        store is in a valid state, ie that all the head block and all
        predecessors are in the store.

        :param new_chain: The list of blocks of the new chain.
        :param old_chain: The list of blocks of the existing chain to
            remove from the block store.
        store.
        :return:
        None
        """
        add_pairs = [(blkw.header_signature, blkw) for blkw in new_chain]
        if old_chain:
            del_keys = [blkw.header_signature for blkw in old_chain]
        else:
            del_keys = []

        self._block_store.update(add_pairs, del_keys)

    @property
    def chain_head(self):
        """
        Return the head block of the current chain.
        """
        with self._block_store.cursor(index='block_num') as curs:
            curs.last()
            return curs.value()

    def chain_head_state_root(self):
        """
        Return the state hash of the head block of the current chain.
        """
        chain_head = self.chain_head
        if chain_head is not None:
            return chain_head.state_root_hash
        return INIT_ROOT_KEY

    @property
    def store(self):
        """
        Access to the underlying store.
        """
        return self._block_store

    def get_predecessor_iter(self, starting_block=None):
        """Returns an iterator that traverses blocks via their
        previous_block_ids.

        Args:
            starting_block (:obj:`BlockWrapper`): the block from which
                traversal begins

        Returns:
            An iterator
        """
        if not starting_block:
            return _BlockPredecessorIterator(self, start_block=self.chain_head)

        return _BlockPredecessorIterator(self, start_block=starting_block)

    @staticmethod
    def _batch_index_keys(block):
        blkw = BlockWrapper.wrap(block)
        return [batch.header_signature.encode()
                for batch in blkw.batches]

    @staticmethod
    def _transaction_index_keys(block):
        blkw = BlockWrapper.wrap(block)
        keys = []
        for batch in blkw.batches:
            for txn in batch.transactions:
                keys.append(txn.header_signature.encode())
        return keys

    @staticmethod
    def _block_num_index_keys(block):
        blkw = BlockWrapper.wrap(block)
        # Format the number to a 64bit hex value, for natural ordering
        return [BlockStore.block_num_to_hex(blkw.block_num).encode()]

    @staticmethod
    def block_num_to_hex(block_num):
        return "{0:#0{1}x}".format(block_num, 18)

    def _get_block(self, key):
        value = self._block_store.get(key)
        if value is None:
            raise KeyError('Block "{}" not found in store'.format(key))

        return BlockWrapper.wrap(value)

    def get_block_by_transaction_id(self, txn_id):
        try:
            return self._block_store.get(txn_id, index='transaction')
        except KeyError:
            raise ValueError('Transaction "%s" not in BlockStore', txn_id)

    def get_block_by_number(self, block_num):
        try:
            return self._block_store.get(
                BlockStore.block_num_to_hex(block_num), index='block_num')
        except KeyError:
            raise KeyError('Block number "%s" not in BlockStore', block_num)

    def has_transaction(self, txn_id):
        return self._block_store.contains_key(txn_id, index='transaction')

    def get_block_by_batch_id(self, batch_id):
        try:
            return self._block_store.get(batch_id, index='batch')
        except KeyError:
            raise ValueError('Batch "%s" not in BlockStore', batch_id)

    def has_batch(self, batch_id):
        return self._block_store.contains_key(batch_id, index='batch')

    def get_batch_by_transaction(self, transaction_id):
        """
        Check to see if the requested transaction_id is in the current chain.
        If so, find the batch that has the transaction referenced by the
        transaction_id and return the batch. This is done by finding the block
        and searching for the batch.

        :param transaction_id (string): The id of the transaction that is being
            requested.
        :return:
        The batch that has the transaction.
        """
        block = self.get_block_by_transaction_id(transaction_id)
        if block is None:
            return None
        # Find batch in block
        for batch in block.batches:
            for txn in batch.transactions:
                if txn.header_signature == transaction_id:
                    return batch

    def get_batch(self, batch_id):
        """
        Check to see if the requested batch_id is in the current chain. If so,
        find the batch with the batch_id and return it. This is done by
        finding the block and searching for the batch.

        :param batch_id (string): The id of the batch requested.
        :return:
        The batch with the batch_id.
        """
        block = self.get_block_by_batch_id(batch_id)
        if block is None:
            return None

        for batch in block.batches:
            if batch.header_signature == batch_id:
                return batch

    def get_transaction(self, transaction_id):
        """Returns a Transaction object from the block store by its id.

        Params:
            transaction_id (str): The header_signature of the desired txn

        Returns:
            Transaction: The specified transaction

        Raises:
            ValueError: The transaction is not in the block store
        """
        batch = self.get_batch_by_transaction(transaction_id)
        # Find transaction in batch
        for txn in batch.transactions:
            if txn.header_signature == transaction_id:
                return txn


class _BlockPredecessorIterator(object):
    """An Iterator for traversing blocks via a block's previous_block_id
    """

    def __init__(self, block_store, start_block):
        """Iterates from a starting block, through its predecessors.

        Args:
            block_store (:obj:`BlockStore`): the block store, from which
                the predecessors are found
            start_block (:obj:`BlockWrapper`): the starting block, from which
                the predecessors will be iterated over.
        """
        self._block_store = block_store
        if start_block:
            self._current_block_id = start_block.identifier
        else:
            self._current_block_id = None

    def __iter__(self):
        return self

    def __next__(self):
        if not self._current_block_id:
            raise StopIteration()

        try:
            block = self._block_store[self._current_block_id]
        except KeyError:
            raise PossibleForkDetectedError(
                'Block {} is no longer in the block store'.format(
                    self._current_block_id[:8]))

        self._current_block_id = block.header.previous_block_id
        if self._current_block_id == NULL_BLOCK_IDENTIFIER:
            self._current_block_id = None

        return block

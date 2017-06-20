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

import abc
# pylint: disable=no-name-in-module
from collections.abc import MutableMapping

from sawtooth_validator.exceptions import PossibleForkDetectedError
from sawtooth_validator.journal.block_wrapper import NULL_BLOCK_IDENTIFIER
from sawtooth_validator.journal.block_wrapper import BlockStatus
from sawtooth_validator.journal.block_wrapper import BlockWrapper
from sawtooth_validator.protobuf.batch_pb2 import BatchHeader
from sawtooth_validator.protobuf.block_pb2 import Block


class BlockStore(MutableMapping):
    """
    A dict like interface wrapper around the block store to guarantee,
    objects are correctly wrapped and unwrapped as they are stored and
    retrieved.
    """
    def __init__(self, block_db, update_observers=None):
        self._block_store = block_db
        self._update_obs = [] if update_observers is None else update_observers

    def __setitem__(self, key, value):
        if key != value.identifier:
            raise KeyError("Invalid key to store block under: {} expected {}".
                           format(key, value.identifier))
        add_ops = self._build_add_block_ops(value)
        self._block_store.set_batch(add_ops)
        for observer in self._update_obs:
            observer.notify_store_updated()

    def __getitem__(self, key):
        stored_block = self._block_store[key]

        # Block id strings are stored under batch/txn ids for reference.
        # Only Blocks, not ids or Nones, should be returned by __getitem__.
        if isinstance(stored_block, bytes):
            block = Block()
            block.ParseFromString(stored_block)
            return BlockWrapper(
                status=BlockStatus.Valid,
                block=block)

        raise KeyError('Block "{}" not found in store'.format(key))

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
        add_pairs = []
        del_keys = []
        for blkw in new_chain:
            add_pairs = add_pairs + self._build_add_block_ops(blkw)
        if old_chain is not None:
            for blkw in old_chain:
                del_keys = del_keys + self._build_remove_block_ops(blkw)
        add_pairs.append(("chain_head_id", new_chain[0].identifier))

        self._block_store.set_batch(add_pairs, del_keys)
        for observer in self._update_obs:
            observer.notify_store_updated()

    def add_update_observer(self, observer):
        """Adds a new BlocksCommittedObserver to commit observers.
        """
        self._update_obs.append(observer)

    @property
    def chain_head(self):
        """
        Return the head block of the current chain.
        """
        if "chain_head_id" not in self._block_store:
            return None
        if self._block_store["chain_head_id"] in self._block_store:
            return self.__getitem__(self._block_store["chain_head_id"])
        return None

    @property
    def store(self):
        """
        Access to the underlying store dict.
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

    def _build_add_block_ops(self, blkw):
        """Build the batch operations to add a block to the BlockStore.

        :param blkw (BlockWrapper): Block to add BlockStore.
        :return:
        list of key value tuples to add to the BlockStore
        """
        out = []
        blk_id = blkw.identifier
        out.append((blk_id, blkw.block.SerializeToString()))
        for batch in blkw.batches:
            out.append((batch.header_signature, blk_id))
            for txn in batch.transactions:
                out.append((txn.header_signature, blk_id))
        return out

    @staticmethod
    def _build_remove_block_ops(blkw):
        """Build the batch operations to remove a block from the BlockStore.

        :param blkw (BlockWrapper): Block to remove.
        :return:
        list of values to remove from the BlockStore
        """
        out = []
        blk_id = blkw.identifier
        out.append(blk_id)
        for batch in blkw.batches:
            out.append(batch.header_signature)
            for txn in batch.transactions:
                out.append(txn.header_signature)
        return out

    def get_block_by_transaction_id(self, txn_id):
        try:
            return self.__getitem__(self._block_store[txn_id])
        except KeyError:
            raise ValueError('Transaction "%s" not in BlockStore', txn_id)

    def has_transaction(self, txn_id):
        return txn_id in self._block_store

    def get_block_by_batch_id(self, batch_id):
        try:
            return self.__getitem__(self._block_store[batch_id])
        except KeyError:
            raise ValueError('Batch "%s" not in BlockStore', batch_id)

    def has_batch(self, batch_id):
        return batch_id in self._block_store

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
        if self.has_transaction(transaction_id):
            block = self.get_block_by_transaction_id(transaction_id)
            # Find batch in block
            for batch in block.batches:
                batch_header = BatchHeader()
                batch_header.ParseFromString(batch.header)
                if transaction_id in batch_header.transaction_ids:
                    return batch

        raise ValueError('Transaction "%s" not in BlockStore', transaction_id)

    def get_batch(self, batch_id):
        """
        Check to see if the requested batch_id is in the current chain. If so,
        find the batch with the batch_id and return it. This is done by
        finding the block and searching for the batch.

        :param batch_id (string): The id of the batch requested.
        :return:
        The batch with the batch_id.
        """
        if self.has_batch(batch_id):
            block = self.get_block_by_batch_id(batch_id)

            for batch in block.batches:
                if batch.header_signature == batch_id:
                    return batch

        raise ValueError("Batch_id %s not found in BlockStore.", batch_id)

    def get_transaction(self, transaction_id):
        """Returns a Transaction object from the block store by its id.

        Params:
            transaction_id (str): The header_signature of the desired txn

        Returns:
            Transaction: The specified transaction

        Raises:
            ValueError: The transaction is not in the block store
        """
        if self.has_transaction(transaction_id):
            batch = self.get_batch_by_transaction(transaction_id)
            # Find transaction in batch
            for txn in batch.transactions:
                if txn.header_signature == transaction_id:
                    return txn

        raise ValueError('Transaction "%s" not in BlockStore', transaction_id)


class StoreUpdateObserver(metaclass=abc.ABCMeta):
    """An interface class for components wishing to be notified when the block
    store is being updated.
    """
    @abc.abstractmethod
    def notify_store_updated(self):
        """This method will be called when the blockchain is being updated.
        """
        raise NotImplementedError('StoreUpdatedObservers must have a '
                                  '"notify_store_updated" method')


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

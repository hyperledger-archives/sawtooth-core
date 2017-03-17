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

from time import time
from threading import Condition
# pylint: disable=no-name-in-module
from collections.abc import MutableMapping
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
    def __init__(self, block_db):
        self._block_store = block_db
        self._commit_condition = Condition()

    def __setitem__(self, key, value):
        if key != value.identifier:
            raise KeyError("Invalid key to store block under: {} expected {}".
                           format(key, value.identifier))
        add_ops = self._build_add_block_ops(value)
        self._block_store.set_batch(add_ops)

    def __getitem__(self, key):
        stored_block = self._block_store[key]
        if stored_block is not None:
            block = Block()
            block.ParseFromString(stored_block)
            return BlockWrapper(
                status=BlockStatus.Valid,
                block=block)
        raise KeyError("Key {} not found.".format(key))

    def __delitem__(self, key):
        del self._block_store[key]

    def __contains__(self, x):
        return x in self._block_store

    def __iter__(self):
        # Required by abstract base class, but implementing is non-trivial
        raise NotImplementedError('BlockStore is not iterable')

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

    def wait_for_batch_commits(self, batch_ids=None, timeout=None):
        """Waits for a set of batch ids to be committed to the block chain,
        and returns True when they have. If timeout is exceeded, returns False.
        If no batch_ids are passed in, it will return True on the next commit.
        """
        batch_ids = batch_ids or []
        timeout = timeout or 300
        start_time = time()

        with self._commit_condition:
            while True:
                if all(self.has_batch(b) for b in batch_ids):
                    return True
                if time() - start_time > timeout:
                    return False
                self._commit_condition.wait(timeout - (time() - start_time))

    def _build_add_block_ops(self, blkw):
        """Build the batch operations to add a block to the BlockStore.

        :param blkw (BlockWrapper): Block to add BlockStore.
        :return:
        list of key value tuples to add to the BlockStore
        """
        out = []
        blk_id = blkw.identifier
        with self._commit_condition:
            out.append((blk_id, blkw.block.SerializeToString()))
            for batch in blkw.batches:
                out.append((batch.header_signature, blk_id))
                for txn in batch.transactions:
                    out.append((txn.header_signature, blk_id))
            self._commit_condition.notify_all()
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
        return self.__getitem__(self._block_store[txn_id])

    def has_transaction(self, txn_id):
        return txn_id in self._block_store

    def get_block_by_batch_id(self, batch_id):
        return self.__getitem__(self._block_store[batch_id])

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
            block = self.get_block_by_transaction_id(
                transaction_id)
            # Find batch in block
            for batch in block.batches:
                batch_header = BatchHeader()
                batch_header.ParseFromString(batch.header)
                if transaction_id in batch_header.transactions_ids:
                    return batch
        else:
            raise ValueError("Transaction_id %s not found in BlockStore.",
                             transaction_id)

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

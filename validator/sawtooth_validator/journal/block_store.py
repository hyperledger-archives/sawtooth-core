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
from sawtooth_validator.journal.block_wrapper import BlockStatus
from sawtooth_validator.journal.block_wrapper import BlockWrapper

from sawtooth_validator.protobuf.block_pb2 import Block


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
        add_ops = self._build_add_block_ops(value)
        self._block_store.set_batch(add_ops)

    def __getitem__(self, key):
        stored_block = self._block_store[key]
        if stored_block is not None:
            block = Block()
            block.ParseFromString(stored_block['block'])
            return BlockWrapper(
                status=BlockStatus.Valid,
                block=block,
                weight=stored_block['weight'])
        raise KeyError("Key {} not found.".format(key))

    def __delitem__(self, key):
        del self._block_store[key]

    def __contains__(self, x):
        return x in self._block_store

    def __iter__(self):
        return iter(self._block_store)

    def __len__(self):
        return len(self._block_store)

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

    @staticmethod
    def wrap_block(blkw):
        return {
            "block": blkw.block.SerializeToString(),
            "weight": blkw.weight
        }

    @staticmethod
    def _build_add_block_ops(blkw):
        """Build the batch operations to add a block to the BlockStore.

        :param blkw (BlockWrapper): Block to add BlockStore.
        :return:
        list of key value tuples to add to the BlockStore
        """
        out = []
        blk_id = blkw.identifier
        out.append((blk_id, BlockStore.wrap_block(blkw)))
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
        return self.__getitem__(self._block_store[txn_id])

    def has_transaction(self, txn_id):
        return txn_id in self._block_store

    def get_block_by_batch_id(self, batch_id):
        return batch_id in self._block_store

    def has_batch(self, batch_id):
        return batch_id in self._block_store

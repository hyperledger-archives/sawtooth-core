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

import ctypes
from enum import IntEnum

from sawtooth_validator.journal.block_wrapper import BlockWrapper
from sawtooth_validator.protobuf.block_pb2 import Block
from sawtooth_validator.protobuf.batch_pb2 import Batch
from sawtooth_validator.protobuf.transaction_pb2 import Transaction
from sawtooth_validator.state.merkle import INIT_ROOT_KEY
from sawtooth_validator import ffi


class ErrorCode(IntEnum):
    Success = ffi.CommonErrorCode.Success

    # Input errors
    NullPointerProvided = ffi.CommonErrorCode.NullPointerProvided
    InvalidArgument = 2

    # # output errors
    DatabaseError = 0x10
    NotFound = 0x11

    StopIteration = 0x20


def _check_error(return_code):
    if return_code == ErrorCode.Success:
        return
    if return_code == ErrorCode.NullPointerProvided:
        raise TypeError("Provided null pointer(s)")
    if return_code == ErrorCode.InvalidArgument:
        raise TypeError("An invalid argument was provided")
    if return_code == ErrorCode.DatabaseError:
        raise RuntimeError("A database error occurred")
    if return_code == ErrorCode.NotFound:
        raise ValueError("Unable to find requested item")
    if return_code == ErrorCode.StopIteration:
        raise StopIteration()

    raise RuntimeError("An unknown error occurred: {}".format(return_code))


def _libexec(name, *args):
    _check_error(ffi.LIBRARY.call(name, *args))


def _pylibexec(name, *args):
    _check_error(ffi.PY_LIBRARY.call(name, *args))


class _PutEntry(ctypes.Structure):
    _fields_ = [('block_bytes', ctypes.c_char_p),
                ('block_bytes_len', ctypes.c_size_t)]

    @staticmethod
    def new(block_bytes):
        return _PutEntry(
            block_bytes,
            len(block_bytes)
        )


class BlockStore(ffi.OwnedPointer):
    """
    A dict like interface wrapper around the block store to guarantee,
    objects are correctly wrapped and unwrapped as they are stored and
    retrieved.
    """

    def __init__(self, database):
        super().__init__('commit_store_drop')
        _libexec(
            'commit_store_new',
            database.pointer,
            ctypes.byref(self.pointer))

    def _get_data_by_num(self, object_id, ffi_fn_name):
        (vec_ptr, vec_len, vec_cap) = ffi.prepare_vec_result()
        _pylibexec(ffi_fn_name,
                   self.pointer,
                   ctypes.c_ulonglong(object_id),
                   ctypes.byref(vec_ptr),
                   ctypes.byref(vec_len),
                   ctypes.byref(vec_cap))

        return ffi.from_rust_vec(vec_ptr, vec_len, vec_cap)

    def _get_data_by_id(self, object_id, ffi_fn_name):
        (vec_ptr, vec_len, vec_cap) = ffi.prepare_vec_result()
        _pylibexec(ffi_fn_name,
                   self.pointer,
                   ctypes.c_char_p(object_id.encode()),
                   ctypes.byref(vec_ptr),
                   ctypes.byref(vec_len),
                   ctypes.byref(vec_cap))

        return ffi.from_rust_vec(vec_ptr, vec_len, vec_cap)

    def _get_block_by_num(self, object_id, ffi_fn_name):
        return self.deserialize_block(
            self._get_data_by_num(object_id, ffi_fn_name))

    def _get_block_by_id(self, object_id, ffi_fn_name):
        return self.deserialize_block(
            self._get_data_by_id(object_id, ffi_fn_name))

    def __getitem__(self, key):
        try:
            return self._get_block_by_id(key, 'commit_store_get_by_block_id')
        except ValueError:
            raise KeyError("Unable to find block id: %s" % key)

    def put_blocks(self, blocks):
        c_put_items = (ctypes.POINTER(_PutEntry) * len(blocks))()
        for (i, block) in enumerate(blocks):
            c_put_items[i] = ctypes.pointer(_PutEntry.new(
                block.SerializeToString(),
            ))

        _libexec('commit_store_put_blocks',
                 self.pointer,
                 c_put_items, ctypes.c_size_t(len(blocks)))

    def _contains_id(self, object_id, fn_name):
        contains = ctypes.c_bool(False)
        _pylibexec(fn_name,
                   self.pointer,
                   ctypes.c_char_p(object_id.encode()),
                   ctypes.byref(contains))
        return contains.value

    def __contains__(self, block_id):
        return self._contains_id(block_id, 'commit_store_contains_block')

    def __iter__(self):
        return self.get_block_iter()

    @staticmethod
    def create_index_configuration():
        return ['index_batch', 'index_transaction', 'index_block_num']

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
            block=block)

    @property
    def chain_head(self):
        """
        Return the head block of the current chain.
        """
        (vec_ptr, vec_len, vec_cap) = ffi.prepare_vec_result()

        try:
            _libexec(
                'commit_store_get_chain_head',
                self.pointer,
                ctypes.byref(vec_ptr),
                ctypes.byref(vec_len),
                ctypes.byref(vec_cap))
        except ValueError:
            return None

        return self.deserialize_block(
            ffi.from_rust_vec(vec_ptr, vec_len, vec_cap))

    def chain_head_state_root(self):
        """
        Return the state hash of the head block of the current chain.
        """
        chain_head = self.chain_head
        if chain_head is not None:
            return chain_head.state_root_hash
        return INIT_ROOT_KEY

    def get_predecessor_iter(self, starting_block=None):
        """Returns an iterator that traverses block via its predecesssors.

        Args:
            starting_block (:obj:`BlockWrapper`): the block from which
                traversal begins

        Returns:
            An iterator of block wrappers
        """
        return self.get_block_iter(start_block=starting_block)

    def get_block_iter(self, start_block=None, start_block_num=None,
                       reverse=True):
        """Returns an iterator that traverses blocks in block number order.

        Args:
            start_block (:obj:`BlockWrapper`): the block from which traversal
                begins
            start_block_num (str): a starting block number, in hex, from where
                traversal begins; only used if no starting_block is provided

            reverse (bool): If True, traverse the blocks in from most recent
                to oldest block. Otherwise, it traverse the blocks in the
                opposite order.

        Returns:
            An iterator of block wrappers

        Raises:
            ValueError: If start_block or start_block_num do not specify a
                valid block
        """
        start = None
        if start_block_num:
            if len(start_block_num) < 2:
                raise ValueError("Invalid start block num")
            if start_block_num[:2] != "0x":
                raise ValueError("Invalid start block num")
            start = int(start_block_num, 16)
        elif start_block:
            start = start_block.block_num

        return _BlockStoreIter(
            self.pointer,
            start,
            reverse)

    def get_blocks(self, block_ids):
        """Returns all blocks with the given set of block_ids.
        If a block id in the provided iterable does not exist in the block
        store, it is ignored.

        Args:
            block_ids (:iterable:str): an iterable of block ids

        Returns
            list of block wrappers found for the given block ids
        """
        return list(
            filter(
                lambda b: b is not None,
                map(self._get_block_by_id_or_none, block_ids)))

    def _get_block_by_id_or_none(self, block_id):
        try:
            return self[block_id]
        except KeyError:
            return None

    def get_block_by_transaction_id(self, txn_id):
        """Returns the block that contains the given transaction id.

        Args:
            txn_id (str): a transaction id

        Returns:
            a block wrapper of the containing block

        Raises:
            ValueError if no block containing the transaction is found
        """
        return self._get_block_by_id(
            txn_id, 'commit_store_get_by_transaction_id')

    def get_block_by_number(self, block_num):
        """Returns the block that contains the given transaction id.

        Args:
            block_num (uint64): a block number

        Returns:
            a block wrapper of the containing block

        Raises:
            KeyError if no block with the given number is found
        """
        try:
            return self._get_block_by_num(
                block_num, 'commit_store_get_by_block_num')
        except ValueError:
            raise KeyError("Unable to find block number: %s" % repr(block_num))

    def has_transaction(self, txn_id):
        """Returns True if the transaction is contained in a block in the
        block store.

        Args:
            txn_id (str): a transaction id

        Returns:
            True if it is contained in a committed block, False otherwise
        """
        return self._contains_id(txn_id, 'commit_store_contains_transaction')

    def get_block_by_batch_id(self, batch_id):
        """Returns the block that contains the given batch id.

        Args:
            batch_id (str): a batch id

        Returns:
            a block wrapper of the containing block

        Raises:
            ValueError if no block containing the batch is found
        """
        return self._get_block_by_id(
            batch_id, 'commit_store_get_by_batch_id')

    def has_batch(self, batch_id):
        """Returns True if the batch is contained in a block in the
        block store.

        Args:
            batch_id (str): a batch id

        Returns:
            True if it is contained in a committed block, False otherwise
        """
        return self._contains_id(batch_id, 'commit_store_contains_batch')

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
        payload = self._get_data_by_id(
            transaction_id, 'commit_store_get_batch_by_transaction')

        batch = Batch()
        batch.ParseFromString(payload)

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

        payload = self._get_data_by_id(batch_id, 'commit_store_get_batch')

        batch = Batch()
        batch.ParseFromString(payload)

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
        payload = self._get_data_by_id(
            transaction_id, 'commit_store_get_transaction')

        txn = Transaction()
        txn.ParseFromString(payload)

        return txn

    def _get_count(self, fn_name):
        count = ctypes.c_size_t(0)
        _libexec(fn_name, self.pointer, ctypes.byref(count))
        return count.value

    def get_transaction_count(self):
        """Returns the count of transactions in the block store.

        Returns:
            Integer: The count of transactions
        """
        return self._get_count('commit_store_get_transaction_count')

    def get_batch_count(self):
        """Returns the count of batches in the block store.

        Returns:
            Integer: The count of batches
        """
        return self._get_count('commit_store_get_batch_count')

    def get_block_count(self):
        """Returns the count of blocks in the block store.

        Returns:
            Integer: The count of blocks
        """
        return self._get_count('commit_store_get_block_count')


class _BlockStoreIter(ffi.BlockIterator):
    """
    A dict like interface wrapper around the block store to guarantee,
    objects are correctly wrapped and unwrapped as they are stored and
    retrieved.
    """

    name = "commit_store_block_by_height_iter"

    def __init__(self, commit_store_ptr, start=None, decreasing=True):
        super().__init__(_check_error)

        if start is not None:
            c_start_ptr =\
                ctypes.POINTER(ctypes.c_uint32)(ctypes.c_uint32(start))
        else:
            c_start_ptr = 0

        _libexec(
            'commit_store_get_block_iter',
            commit_store_ptr,
            c_start_ptr,
            decreasing,
            ctypes.byref(self.pointer))

    def __next__(self):
        block = super().__next__()
        return BlockWrapper(block=block)

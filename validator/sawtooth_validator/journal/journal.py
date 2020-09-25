# Copyright 2017-2018 Intel Corporation
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

from sawtooth_validator import ffi
from sawtooth_validator.ffi import PY_LIBRARY
from sawtooth_validator.ffi import LIBRARY
from sawtooth_validator.ffi import CommonErrorCode
from sawtooth_validator.ffi import OwnedPointer
from sawtooth_validator.protobuf.block_pb2 import Block
from sawtooth_validator.journal.block_wrapper import BlockStatus


class Journal(OwnedPointer):
    def __init__(
        self,
        block_store,
        block_manager,
        state_database,
        block_sender,
        block_status_store,
        consensus_notifier,
        consensus_registry,
        state_pruning_block_depth=1000,
        fork_cache_keep_time=300,  # seconds
        data_dir=None,
        batch_observers=None,
        invalid_transaction_observers=None,
        observers=None,
        genesis_observers=None,
        key_dir=None,
    ):
        super().__init__('journal_drop')

        if data_dir is None:
            data_dir = ''

        if key_dir is None:
            key_dir = ''

        if observers is None:
            observers = []

        if genesis_observers is None:
            genesis_observers = []

        _libexec(
            'journal_new',
            block_store.pointer,
            block_manager.pointer,
            state_database.pointer,
            block_status_store.pointer,
            consensus_notifier.pointer,
            ctypes.py_object(block_sender),
            ctypes.py_object(batch_observers),
            ctypes.py_object(invalid_transaction_observers),
            ctypes.py_object(observers),
            ctypes.c_long(state_pruning_block_depth),
            ctypes.c_long(fork_cache_keep_time),
            ctypes.c_char_p(data_dir.encode()),
            ctypes.c_char_p(key_dir.encode()),
            ctypes.py_object(genesis_observers),
            ctypes.byref(self.pointer))

    def start(self):
        _libexec('journal_start', self.pointer)

    def stop(self):
        _libexec('journal_stop', self.pointer)

    def _journal_serialize_ffi_fn(self, name, item):
        payload = item.SerializeToString()
        _libexec(name, self.pointer, payload, len(payload))

    def is_batch_pool_full(self):
        is_full = ctypes.c_bool(False)

        _libexec(
            'batch_submitter_is_batch_pool_full',
            self.pointer,
            ctypes.byref(is_full))

        return is_full

    def submit_batch(self, batch):
        self._journal_serialize_ffi_fn('batch_submitter_submit', batch)

    def has_batch(self, batch_id):
        has = ctypes.c_bool(False)
        c_batch_id = ctypes.c_char_p(batch_id.encode())

        _libexec(
            'block_publisher_has_batch',
            self.pointer,
            c_batch_id,
            ctypes.byref(has))

        return has

    def initialize_block(self, previous_block):
        self._journal_serialize_ffi_fn(
            'block_publisher_initialize_block',
            previous_block)

    def summarize_block(self):
        (vec_ptr, vec_len, vec_cap) = ffi.prepare_vec_result()
        _libexec(
            'block_publisher_summarize_block',
            self.pointer,
            ctypes.byref(vec_ptr),
            ctypes.byref(vec_len),
            ctypes.byref(vec_cap))

        return ffi.from_rust_vec(vec_ptr, vec_len, vec_cap)

    def finalize_block(self, consensus=None):
        (vec_ptr, vec_len, vec_cap) = ffi.prepare_vec_result()
        _libexec(
            'block_publisher_finalize_block',
            self.pointer,
            consensus,
            len(consensus),
            ctypes.byref(vec_ptr),
            ctypes.byref(vec_len),
            ctypes.byref(vec_cap))

        return ffi.from_rust_vec(vec_ptr, vec_len, vec_cap).decode('utf-8')

    def cancel_block(self):
        _libexec("block_publisher_cancel_block", self.pointer)

    def validate_block(self, block):
        self._journal_serialize_ffi_fn(
            'chain_controller_validate_block',
            block)

    def ignore_block(self, block):
        self._journal_serialize_ffi_fn(
            'chain_controller_ignore_block',
            block)

    def fail_block(self, block):
        self._journal_serialize_ffi_fn(
            'chain_controller_fail_block',
            block)

    def commit_block(self, block):
        self._journal_serialize_ffi_fn(
            'chain_controller_commit_block',
            block)

    def queue_block(self, block_id):
        _libexec('chain_controller_queue_block', self.pointer,
                 ctypes.c_char_p(block_id.encode('utf-8')))

    def block_validation_result(self, block_id):
        status = ctypes.c_int32(0)

        _libexec("chain_controller_block_validation_result", self.pointer,
                 ctypes.c_char_p(block_id.encode()),
                 ctypes.byref(status))

        return BlockStatus(status.value)

    def on_block_received(self, block_id):
        """This is exposed for unit tests, and should not be called directly.
        """
        _libexec('chain_controller_on_block_received', self.pointer,
                 ctypes.c_char_p(block_id.encode('utf-8')))

    @property
    def chain_head(self):
        return self.chain_head_fn()

    def chain_head_fn(self):
        (vec_ptr, vec_len, vec_cap) = ffi.prepare_vec_result()

        _libexec('chain_controller_chain_head',
                 self.pointer,
                 ctypes.byref(vec_ptr),
                 ctypes.byref(vec_len),
                 ctypes.byref(vec_cap))

        # Check if NULL
        if not vec_ptr:
            return None

        payload = ffi.from_rust_vec(vec_ptr, vec_len, vec_cap)
        block = Block()
        block.ParseFromString(payload)

        return block


def _libexec(name, *args):
    return _exec(LIBRARY, name, *args)


def _pylibexec(name, *args):
    return _exec(PY_LIBRARY, name, *args)


def _exec(library, name, *args):
    res = library.call(name, *args)
    if res == ErrorCode.Success:
        return

    if res == ErrorCode.NullPointerProvided:
        raise ValueError("Provided null pointer(s)")
    if res == ErrorCode.InvalidDataDir:
        raise ValueError("Invalid data dir")
    if res == ErrorCode.InvalidPythonObject:
        raise ValueError("Invalid python object submitted")
    if res == ErrorCode.InvalidBlockId:
        raise ValueError("Invalid block id provided.")
    if res == ErrorCode.UnknownBlock:
        raise KeyError("Unknown block")
    if res == ErrorCode.GenesisError:
        raise GenesisError("Unable to create genesis block")
    if res == ErrorCode.CreateError:
        raise JournalCreateError()
    if res == ErrorCode.MissingSigner:
        raise JournalSignerError()
    if res == ErrorCode.ExecutorError:
        raise JournalExecutorError()
    if res == ErrorCode.BatchSubmitterDisconnected:
        raise BatchSubmitterDisconnected()
    if res == ErrorCode.BlockInProgress:
        raise BlockInProgress()
    if res == ErrorCode.MissingPredecessor:
        raise MissingPredecessor()
    if res == ErrorCode.BlockNotInitialized:
        raise BlockNotInitialized()
    if res == ErrorCode.BlockEmpty:
        raise BlockEmpty()
    if res == ErrorCode.VerifyStateError:
        raise VerifyStateError()

    raise TypeError("Unknown error occurred")


class ErrorCode(IntEnum):
    Success = CommonErrorCode.Success
    NullPointerProvided = CommonErrorCode.NullPointerProvided
    InvalidDataDir = 0x02
    InvalidPythonObject = 0x03
    InvalidBlockId = 0x04
    UnknownBlock = 0x05
    GenesisError = 0x06
    CreateError = 0x07
    MissingSigner = 0x08
    ExecutorError = 0x09
    BatchSubmitterDisconnected = 0x10
    BlockInProgress = 0x11
    MissingPredecessor = 0x12
    BlockNotInitialized = 0x13
    BlockEmpty = 0x14
    VerifyStateError = 0x15


class GenesisError(Exception):
    """
    General Error thrown when an error occurs as a result of an incomplete
    or erroneous genesis action.
    """


class JournalCreateError(Exception):
    """Unable to create Journal"""


class JournalSignerError(Exception):
    """Unable to create Signer for Journal"""


class JournalExecutorError(Exception):
    """Unable to create transaction executor"""


class BatchSubmitterDisconnected(Exception):
    """The receiving end of the BatchSubmitter hung up."""


class BlockInProgress(Exception):
    """There is already a block in progress."""


class MissingPredecessor(Exception):
    """A predecessor was missing"""


class BlockNotInitialized(Exception):
    """There is no block in progress to finalize."""


class BlockEmpty(Exception):
    """There are no batches in the block."""


class VerifyStateError(Exception):
    """Unable to verify state during journal creation"""

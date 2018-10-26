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
from abc import ABCMeta
from abc import abstractmethod
import ctypes
from enum import IntEnum

from sawtooth_validator.ffi import PY_LIBRARY
from sawtooth_validator.ffi import LIBRARY
from sawtooth_validator.ffi import CommonErrorCode
from sawtooth_validator.ffi import OwnedPointer
from sawtooth_validator import ffi
from sawtooth_validator.protobuf.block_pb2 import Block
from sawtooth_validator.journal.block_wrapper import BlockWrapper


class ChainObserver(metaclass=ABCMeta):
    @abstractmethod
    def chain_update(self, block, receipts):
        """This method is called by the ChainController on block boundaries.

        Args:
            block (:obj:`BlockWrapper`): The block that was just committed.
            receipts (dict of {str: receipt}): Map of transaction signatures to
                transaction receipts for all transactions in the block."""
        raise NotImplementedError()


class _BlockPayload(ctypes.Structure):
    _fields_ = [('block_ptr', ctypes.POINTER(ctypes.c_uint8)),
                ('block_len', ctypes.c_size_t),
                ('block_cap', ctypes.c_size_t)]


class ChainController(OwnedPointer):
    def __init__(
        self,
        block_store,
        block_cache,
        block_validator,
        state_database,
        chain_head_lock,
        consensus_notifier,
        state_pruning_block_depth=1000,
        data_dir=None,
        observers=None
    ):
        super(ChainController, self).__init__('chain_controller_drop')

        if data_dir is None:
            data_dir = ''

        if observers is None:
            observers = []

        _pylibexec(
            'chain_controller_new',
            ctypes.py_object(block_store),
            ctypes.py_object(block_cache),
            ctypes.py_object(block_validator),
            state_database.pointer,
            chain_head_lock.pointer,
            ctypes.py_object(consensus_notifier),
            ctypes.py_object(observers),
            ctypes.c_long(state_pruning_block_depth),
            ctypes.c_char_p(data_dir.encode()),
            ctypes.byref(self.pointer))

    def start(self):
        _libexec('chain_controller_start', self.pointer)

    def stop(self):
        _libexec('chain_controller_stop', self.pointer)

    def has_block(self, block_id):
        result = ctypes.c_bool()

        _libexec('chain_controller_has_block',
                 self.pointer, ctypes.c_char_p(block_id.encode()),
                 ctypes.byref(result))
        return result.value

    def ignore_block(self, block):
        _pylibexec('chain_controller_ignore_block', self.pointer,
                   ctypes.py_object(block))

    def fail_block(self, block):
        _pylibexec('chain_controller_fail_block', self.pointer,
                   ctypes.py_object(block))

    def forks(self, head):
        (vec_ptr, vec_len, vec_cap) = ffi.prepare_vec_result(
            pointer_type=_BlockPayload)

        head = ctypes.c_char_p(head.encode())

        _libexec(
            'chain_controller_forks',
            self.pointer,
            head,
            ctypes.byref(vec_ptr),
            ctypes.byref(vec_len),
            ctypes.byref(vec_cap))

        # Check if NULL
        if not vec_ptr:
            return None

        blocks = []
        for i in range(vec_len.value):
            block_payload = vec_ptr[i]
            payload = ffi.from_rust_vec(
                block_payload.block_ptr,
                ctypes.c_size_t(block_payload.block_len),
                ctypes.c_size_t(block_payload.block_cap),
            )
            block = Block()
            block.ParseFromString(payload)
            blocks.append(BlockWrapper(block))

        LIBRARY.call(
            "chain_controller_reclaim_block_payload_vec",
            vec_ptr,
            vec_len,
            vec_cap)

        return blocks

    def commit_block(self, block):
        _pylibexec('chain_controller_commit_block', self.pointer,
                   ctypes.py_object(block))

    def queue_block(self, block):
        _pylibexec('chain_controller_queue_block', self.pointer,
                   ctypes.py_object(block))

    def submit_blocks_for_verification(self, blocks):
        _pylibexec('chain_controller_submit_blocks_for_verification',
                   self.pointer,
                   ctypes.py_object(blocks))

    def on_block_received(self, block_wrapper):
        """This is exposed for unit tests, and should not be called directly.
        """
        _pylibexec('chain_controller_on_block_received', self.pointer,
                   ctypes.py_object(block_wrapper))

    @property
    def chain_head(self):
        result = ctypes.py_object()

        _pylibexec('chain_controller_chain_head',
                   self.pointer,
                   ctypes.byref(result))

        return result.value


class ValidationResponseSender(OwnedPointer):
    def __init__(self, sender_ptr):
        super(ValidationResponseSender, self).__init__(
            'sender_drop', initialized_ptr=sender_ptr)

    def send(self, block):
        _pylibexec('sender_send', self.pointer,
                   ctypes.py_object(block))


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

    raise TypeError("Unknown error occurred: {}".format(res.error))


class ErrorCode(IntEnum):
    Success = CommonErrorCode.Success
    NullPointerProvided = CommonErrorCode.NullPointerProvided
    InvalidDataDir = 0x02
    InvalidPythonObject = 0x03
    InvalidBlockId = 0x04

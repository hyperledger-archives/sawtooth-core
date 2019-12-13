# Copyright 2018 Intel Corporation
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

from sawtooth_validator.ffi import OwnedPointer
from sawtooth_validator import ffi


class MissingPredecessor(Exception):
    pass


class MissingPredecessorInBranch(Exception):
    pass


class MissingInput(Exception):
    pass


class UnknownBlock(Exception):
    pass


class ErrorCode(IntEnum):
    Success = 0
    NullPointerProvided = 0x01
    MissingPredecessor = 0x02
    MissingPredecessorInBranch = 0x03
    MissingInput = 0x04
    UnknownBlock = 0x05
    InvalidInputString = 0x06
    Error = 0x07
    InvalidPythonObject = 0x0F
    StopIteration = 0x11


class _PutEntry(ctypes.Structure):
    _fields_ = [('block_bytes', ctypes.c_char_p),
                ('block_bytes_len', ctypes.c_size_t)]

    @staticmethod
    def new(block_bytes):
        return _PutEntry(
            block_bytes,
            len(block_bytes)
        )


class BlockManager(OwnedPointer):

    def __init__(self):
        super(BlockManager, self).__init__('block_manager_drop')
        _libexec("block_manager_new",
                 ctypes.byref(self.pointer))

    def add_commit_store(self, block_store):
        _libexec(
            "block_manager_add_commit_store",
            self.pointer,
            block_store.pointer)

    def put(self, branch):
        c_put_items = (ctypes.POINTER(_PutEntry) * len(branch))()
        for (i, block) in enumerate(branch):
            c_put_items[i] = ctypes.pointer(_PutEntry.new(
                block.SerializeToString(),
            ))

        _libexec("block_manager_put",
                 self.pointer,
                 c_put_items, ctypes.c_size_t(len(branch)))

    # Raises UnknownBlock if the block is not found
    def ref_block(self, block_id):
        _libexec(
            "block_manager_ref_block",
            self.pointer,
            ctypes.c_char_p(block_id.encode()))

    # Raises UnknownBlock if the block is not found
    def unref_block(self, block_id):
        _libexec(
            "block_manager_unref_block",
            self.pointer,
            ctypes.c_char_p(block_id.encode()))

    def persist(self, block_id, store_name):
        _libexec("block_manager_persist",
                 self.pointer,
                 ctypes.c_char_p(block_id.encode()),
                 ctypes.c_char_p(store_name.encode()))

    def __contains__(self, block_id):
        contains = ctypes.c_bool(False)
        _libexec(
            "block_manager_contains",
            self.pointer,
            ctypes.c_char_p(block_id.encode()),
            ctypes.byref(contains))
        return contains

    def get(self, block_ids):
        return _GetBlockIterator(self.pointer, block_ids)

    def branch(self, tip):
        return _BranchIterator(self.pointer, tip)

    def branch_diff(self, tip, exclude):
        return _BranchDiffIterator(self.pointer, tip, exclude)


def _libexec(name, *args):
    return _exec(ffi.LIBRARY, name, *args)


def _pylibexec(name, *args):
    return _exec(ffi.PY_LIBRARY, name, *args)


def _exec(library, name, *args):
    _check_error(library.call(name, *args))


def _check_error(res):
    if res == ErrorCode.Success:
        return

    if res == ErrorCode.NullPointerProvided:
        raise TypeError("Provided null pointer(s)")
    elif res == ErrorCode.StopIteration:
        raise StopIteration()
    elif res == ErrorCode.MissingPredecessor:
        raise MissingPredecessor("Missing predecessor")
    elif res == ErrorCode.MissingPredecessorInBranch:
        raise MissingPredecessorInBranch("Missing predecessor")
    elif res == ErrorCode.MissingInput:
        raise MissingInput("Missing input to put method")
    elif res == ErrorCode.UnknownBlock:
        raise UnknownBlock("Block was unknown")
    elif res == ErrorCode.InvalidInputString:
        raise TypeError("Invalid block store name provided")
    else:
        raise Exception("There was an unknown error: {}".format(res))


class _GetBlockIterator(ffi.BlockIterator):

    name = "block_manager_get_iterator"

    def __init__(self, block_manager_ptr, block_ids):
        super().__init__(_check_error)

        c_block_ids = (ctypes.c_char_p * len(block_ids))()
        for i, block_id in enumerate(block_ids):
            c_block_ids[i] = ctypes.c_char_p(block_id.encode())

        _libexec("{}_new".format(self.name),
                 block_manager_ptr,
                 c_block_ids,
                 ctypes.c_size_t(len(block_ids)),
                 ctypes.byref(self.pointer))


class _BranchDiffIterator(ffi.BlockIterator):

    name = "block_manager_branch_diff_iterator"

    def __init__(self, block_manager_ptr, tip, exclude):
        super().__init__(_check_error)

        c_tip = ctypes.c_char_p(tip.encode())
        c_exclude = ctypes.c_char_p(exclude.encode())

        _libexec("{}_new".format(self.name),
                 block_manager_ptr,
                 c_tip,
                 c_exclude,
                 ctypes.byref(self.pointer))


class _BranchIterator(ffi.BlockIterator):

    name = "block_manager_branch_iterator"

    def __init__(self, block_manager_ptr, tip):
        super().__init__(_check_error)

        c_tip = ctypes.c_char_p(tip.encode())

        _libexec("{}_new".format(self.name),
                 block_manager_ptr,
                 c_tip,
                 ctypes.byref(self.pointer))

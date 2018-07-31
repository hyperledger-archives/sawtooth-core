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
    InvalidBlockStoreName = 0x06
    Error = 0x07
    InvalidPythonObject = 0x0F
    StopIteration = 0x11


class BlockManager(OwnedPointer):

    def __init__(self):
        super(BlockManager, self).__init__('block_manager_drop')
        _libexec("block_manager_new",
                 ctypes.byref(self.pointer))

    def add_store(self, name, block_store):
        _pylibexec("block_manager_add_store",
                   self.pointer,
                   ctypes.c_char_p(name.encode()),
                   ctypes.py_object(block_store))

    def put(self, branch):

        _libexec("block_manager_put",
                 self.pointer,
                 ctypes.py_object(branch))

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
    res = library.call(name, *args)
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
    elif res == ErrorCode.InvalidBlockStoreName:
        raise TypeError("Invalid block store name provided")
    else:
        raise Exception("There was an unknown error: {}".format(res))


class _BlockIterator:

    def __del__(self):
        if self._c_iter_ptr:
            _libexec("{}_drop".format(self.name), self._c_iter_ptr)

    def __iter__(self):
        return self

    def __next__(self):
        if not self._c_iter_ptr:
            raise StopIteration()

        block = ctypes.py_object()

        _pylibexec("{}_next".format(self.name),
                   self._c_iter_ptr,
                   ctypes.byref(block))

        if block.value is None:
            raise StopIteration()

        return block.value


class _GetBlockIterator(_BlockIterator):

    name = "block_manager_get_iterator"

    def __init__(self, block_manager_ptr, block_ids):

        c_block_ids = (ctypes.c_char_p * len(block_ids))()
        for i, block_id in enumerate(block_ids):
            c_block_ids[i] = ctypes.c_char_p(block_id.encode())

        self._c_iter_ptr = ctypes.c_void_p()

        _libexec("{}_new".format(self.name),
                 block_manager_ptr,
                 c_block_ids,
                 ctypes.c_size_t(len(block_ids)),
                 ctypes.byref(self._c_iter_ptr))


class _BranchDiffIterator(_BlockIterator):

    name = "block_manager_branch_diff_iterator"

    def __init__(self, block_manager_ptr, tip, exclude):

        c_tip = ctypes.c_char_p(tip.encode())
        c_exclude = ctypes.c_char_p(exclude.encode())

        self._c_iter_ptr = ctypes.c_void_p()

        _libexec("{}_new".format(self.name),
                 block_manager_ptr,
                 c_tip,
                 c_exclude,
                 ctypes.byref(self._c_iter_ptr))


class _BranchIterator(_BlockIterator):

    name = "block_manager_branch_iterator"

    def __init__(self, block_manager_ptr, tip):

        c_tip = ctypes.c_char_p(tip.encode())

        self._c_iter_ptr = ctypes.c_void_p()

        _libexec("{}_new".format(self.name),
                 block_manager_ptr,
                 c_tip,
                 ctypes.byref(self._c_iter_ptr))

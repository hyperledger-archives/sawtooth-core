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


class ValidationResponseSender(OwnedPointer):
    def __init__(self, sender_ptr):
        super().__init__(
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
    if res == ErrorCode.UnknownBlock:
        raise KeyError("Unknown block")

    raise TypeError("Unknown error occurred: {}".format(res.error))


class ErrorCode(IntEnum):
    Success = CommonErrorCode.Success
    NullPointerProvided = CommonErrorCode.NullPointerProvided
    InvalidDataDir = 0x02
    InvalidPythonObject = 0x03
    InvalidBlockId = 0x04
    UnknownBlock = 0x05

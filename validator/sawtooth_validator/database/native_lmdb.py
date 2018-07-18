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

from sawtooth_validator.ffi import PY_LIBRARY
from sawtooth_validator.ffi import CommonErrorCode
from sawtooth_validator.ffi import OwnedPointer


class NativeLmdbDatabase(OwnedPointer):
    def __init__(self, path, indexes=None, _size=1024**4):
        super(NativeLmdbDatabase, self).__init__('lmdb_database_drop')

        if indexes is None:
            indexes = []

        c_path = ctypes.c_char_p(path.encode())

        c_size = ctypes.c_size_t(_size)
        res = PY_LIBRARY.call(
            'lmdb_database_new', c_path, c_size,
            ctypes.py_object(indexes),
            ctypes.byref(self.pointer))
        if res == ErrorCode.Success:
            return
        if res == ErrorCode.NullPointerProvided:
            raise TypeError("Path cannot be null")
        if res == ErrorCode.InvalidFilePath:
            raise TypeError("Invalid file path {}".format(path))
        if res == ErrorCode.InvalidIndexString:
            raise TypeError("Invalid index string {}".format(indexes))
        if res == ErrorCode.InitializeContextError:
            raise TypeError("Unable to initialize LMDB Context")
        if res == ErrorCode.InitializeDatabaseError:
            raise TypeError("Unable to initialize LMDB Database")

        raise TypeError("Unknown error occurred: {}".format(res.error))


class ErrorCode(IntEnum):
    Success = CommonErrorCode.Success
    NullPointerProvided = CommonErrorCode.NullPointerProvided
    InvalidFilePath = 0x02
    InvalidIndexString = 0x03

    InitializeContextError = 0x11
    InitializeDatabaseError = 0x12

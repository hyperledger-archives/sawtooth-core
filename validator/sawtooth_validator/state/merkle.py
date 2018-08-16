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

import cbor

from sawtooth_validator import ffi


# This is included for legacy reasons.
INIT_ROOT_KEY = ''


def _decode(encoded):
    return cbor.loads(encoded)


def _encode(value):
    return cbor.dumps(value, sort_keys=True)


class MerkleDatabase(ffi.OwnedPointer):

    def __init__(self, database, merkle_root=None):
        super(MerkleDatabase, self).__init__('merkle_db_drop')

        if merkle_root:
            init_root = ctypes.c_char_p(merkle_root.encode())
            _libexec('merkle_db_new_with_root', database.pointer,
                     init_root, ctypes.byref(self.pointer))
        else:
            _libexec('merkle_db_new', database.pointer,
                     ctypes.byref(self.pointer))

    @staticmethod
    def create_index_configuration():
        return ['change_log', 'duplicate_log']

    def __iter__(self):
        return self.leaves()

    def __contains__(self, item):
        """Does the tree contain an address.

        Args:
            item (str): An address.

        Returns:
            (bool): True if it does contain, False otherwise.
        """
        try:
            _libexec('merkle_db_contains', self.pointer,
                     item.encode())
            # No error implies found
            return True
        except KeyError:
            return False

    @staticmethod
    def prune(database, merkle_root):
        c_root_hash = ctypes.c_char_p(merkle_root.encode())
        c_result = ctypes.c_bool()
        _libexec('merkle_db_prune', database.pointer, c_root_hash,
                 ctypes.byref(c_result))

        return c_result.value

    def get_merkle_root(self):
        (string_ptr, string_len, string_cap) = ffi.prepare_string_result()
        _libexec(
            'merkle_db_get_merkle_root',
            self.pointer,
            ctypes.byref(string_ptr),
            ctypes.byref(string_len),
            ctypes.byref(string_cap))

        return ffi.from_rust_string(
            string_ptr, string_len, string_cap).decode()

    def set_merkle_root(self, merkle_root):
        c_root = ctypes.c_char_p(merkle_root.encode())
        _libexec('merkle_db_set_merkle_root', self.pointer, c_root)

    def __getitem__(self, address):
        return self.get(address)

    def get(self, address):
        c_address = ctypes.c_char_p(address.encode())
        (vec_ptr, vec_len, vec_cap) = ffi.prepare_vec_result()

        _libexec(
            'merkle_db_get',
            self.pointer,
            c_address,
            ctypes.byref(vec_ptr),
            ctypes.byref(vec_len),
            ctypes.byref(vec_cap))

        return _decode(ffi.from_rust_vec(
            vec_ptr, vec_len, vec_cap))

    def __setitem__(self, address, value):
        return self.set(address, value)

    def set(self, address, value):
        c_address = ctypes.c_char_p(address.encode())

        (string_ptr, string_len, string_cap) = ffi.prepare_string_result()

        data = _encode(value)
        _libexec(
            'merkle_db_set',
            self.pointer,
            c_address,
            data,
            len(data),
            ctypes.byref(string_ptr),
            ctypes.byref(string_len),
            ctypes.byref(string_cap))

        return ffi.from_rust_string(
            string_ptr, string_len, string_cap).decode()

    def delete(self, address):
        c_address = ctypes.c_char_p(address.encode())

        (string_ptr, string_len, string_cap) = ffi.prepare_string_result()

        _libexec(
            'merkle_db_delete',
            self.pointer,
            c_address,
            ctypes.byref(string_ptr),
            ctypes.byref(string_len),
            ctypes.byref(string_cap))

        return ffi.from_rust_string(
            string_ptr, string_len, string_cap).decode()

    def update(self, set_items, delete_items=None, virtual=True):
        """

        Args:
            set_items (dict): dict key, values where keys are addresses
            delete_items (list): list of addresses
            virtual (boolean): True if not committing to disk. I.e.,
                speculative root hash
        Returns:
            the state root after the operations
        """
        c_set_items = (ctypes.POINTER(_Entry) * len(set_items))()
        for (i, (key, value)) in enumerate(set_items.items()):
            c_set_items[i] = ctypes.pointer(_Entry.new(key, _encode(value)))

        if delete_items is None:
            delete_items = []

        c_delete_items = (ctypes.c_char_p * len(delete_items))()
        for (i, address) in enumerate(delete_items):
            c_delete_items[i] = ctypes.c_char_p(address.encode())

        (string_ptr, string_len, string_cap) = ffi.prepare_string_result()
        _libexec(
            'merkle_db_update',
            self.pointer,
            c_set_items,
            ctypes.c_size_t(len(set_items)),
            c_delete_items,
            ctypes.c_size_t(len(delete_items)),
            virtual,
            ctypes.byref(string_ptr),
            ctypes.byref(string_len),
            ctypes.byref(string_cap))

        return ffi.from_rust_string(
            string_ptr, string_len, string_cap).decode()

    def addresses(self):
        addresses = []
        for address, _ in self:
            addresses.append(address)

        return addresses

    def leaves(self, prefix=None):
        """Returns an iterator which returns tuples of (address, data) values
        """
        try:
            return _LeafIterator(self.pointer, prefix)
        except KeyError:
            # The prefix doesn't exist
            return iter([])

    def close(self):
        pass


def _libexec(name, *args):
    res = ffi.LIBRARY.call(name, *args)
    if res == ErrorCode.Success:
        return
    if res == ErrorCode.NullPointerProvided:
        raise TypeError("Provided null pointer(s)")
    if res == ErrorCode.NotFound:
        raise KeyError("Value was not found")
    if res == ErrorCode.DatabaseError:
        raise ValueError("A Database Error occurred")
    if res == ErrorCode.InvalidHashString:
        raise KeyError(
            "merkle root was not a valid hash")
    if res == ErrorCode.InvalidAddress:
        raise KeyError(
            "Address was not valid ")
    if res == ErrorCode.InvalidChangeLogIndex:
        raise ValueError("The Change Log index is in an invalid state")
    if res == ErrorCode.StopIteration:
        raise StopIteration()
    if res == ErrorCode.Unknown:
        raise ValueError("An unknown error occurred")

    raise ValueError("An unknown error occurred: {}".format(res))


class _LeafIterator:
    def __init__(self, merkle_db_ptr, prefix=None):
        if prefix is None:
            prefix = ''

        c_prefix = ctypes.c_char_p(prefix.encode())

        self._c_iter_ptr = ctypes.c_void_p()

        _libexec('merkle_db_leaf_iterator_new',
                 merkle_db_ptr, c_prefix, ctypes.byref(self._c_iter_ptr))

    def __del__(self):
        if self._c_iter_ptr:
            _libexec('merkle_db_leaf_iterator_drop', self._c_iter_ptr)
            self._c_iter_ptr = None

    def __iter__(self):
        return self

    def __next__(self):
        if not self._c_iter_ptr:
            raise StopIteration()

        (string_ptr, string_len, string_cap) = ffi.prepare_string_result()
        (vec_ptr, vec_len, vec_cap) = ffi.prepare_vec_result()

        _libexec(
            'merkle_db_leaf_iterator_next',
            self._c_iter_ptr,
            ctypes.byref(string_ptr),
            ctypes.byref(string_len),
            ctypes.byref(string_cap),
            ctypes.byref(vec_ptr),
            ctypes.byref(vec_len),
            ctypes.byref(vec_cap))

        address = ffi.from_rust_string(
            string_ptr, string_len, string_cap).decode()
        value = _decode(ffi.from_rust_vec(vec_ptr, vec_len, vec_cap))

        return (address, value)


class _Entry(ctypes.Structure):
    _fields_ = [('address', ctypes.c_char_p),
                ('data', ctypes.c_char_p),
                ('data_len', ctypes.c_size_t)]

    @staticmethod
    def new(address, data):
        return _Entry(
            ctypes.c_char_p(address.encode()),
            data,
            len(data)
        )


class ErrorCode(IntEnum):
    Success = ffi.CommonErrorCode.Success
    # Input errors
    NullPointerProvided = ffi.CommonErrorCode.NullPointerProvided
    InvalidHashString = 2
    InvalidAddress = 3

    # output errors
    DatabaseError = 0x11
    NotFound = 0x12
    InvalidChangeLogIndex = 0x13

    StopIteration = 0xF0
    Unknown = 0xFF

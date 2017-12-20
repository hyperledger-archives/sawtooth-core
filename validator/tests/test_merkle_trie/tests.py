# Copyright 2017 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ------------------------------------------------------------------------------

import os
import unittest
import random
import tempfile
from string import ascii_lowercase

from sawtooth_validator.state.merkle import MerkleDatabase
from sawtooth_validator.database import lmdb_nolock_database


class TestSawtoothMerkleTrie(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.file = os.path.join(self.dir, 'merkle.lmdb')

        self.lmdb = lmdb_nolock_database.LMDBNoLockDatabase(
            self.file,
            'n')

        self.trie = MerkleDatabase(self.lmdb)

    def tearDown(self):
        self.trie.close()

    def test_merkle_trie_root_advance(self):
        value = {'name': 'foo', 'value': 1}

        orig_root = self.get_merkle_root()
        new_root = self.set('foo', value)

        self.assert_root(orig_root)
        self.assert_no_key('foo')

        self.set_merkle_root(new_root)

        self.assert_root(new_root)
        self.assert_value_at_address('foo', value)

    def test_merkle_trie_delete(self):
        value = {'name': 'bar', 'value': 1}

        new_root = self.set('bar', value)
        self.set_merkle_root(new_root)

        self.assert_root(new_root)
        self.assert_value_at_address('bar', value)

        # deleting an invalid key should raise an error
        with self.assertRaises(KeyError):
            self.delete('barf')

        del_root = self.delete('bar')

        # del_root hasn't been set yet, so address should still have value
        self.assert_root(new_root)
        self.assert_value_at_address('bar', value)

        self.set_merkle_root(del_root)

        self.assert_root(del_root)
        self.assert_no_key('bar')

    def test_merkle_trie_update(self):
        init_root = self.get_merkle_root()

        values = {}
        key_hashes = {
            key: _hash(key)
            for key in (_random_string(10) for _ in range(1000))
        }

        for key, hashed in key_hashes.items():
            value = {key: _random_string(512)}
            new_root = self.set(hashed, value, ishash=True)
            values[hashed] = value
            self.set_merkle_root(new_root)

        self.assert_not_root(init_root)

        for address, value in values.items():
            self.assert_value_at_address(
                address, value, ishash=True)

        set_items = {
            hashed: {
                key: 5.0
            }
            for key, hashed in random.sample(key_hashes.items(), 50)
        }
        values.update(set_items)
        delete_items = {
            hashed
            for hashed in random.sample(list(key_hashes.values()), 50)
        }

        # make sure there are no sets and deletes of the same key
        delete_items = delete_items - set_items.keys()
        for addr in delete_items:
            del values[addr]

        virtual_root = self.update(set_items, delete_items, virtual=True)

        # virtual root shouldn't match actual contents of tree
        with self.assertRaises(KeyError):
            self.set_merkle_root(virtual_root)

        actual_root = self.update(set_items, delete_items, virtual=False)

        # the virtual root should be the same as the actual root
        self.assertEqual(virtual_root, actual_root)

        # neither should be the root yet
        self.assert_not_root(
            virtual_root,
            actual_root)

        self.set_merkle_root(actual_root)
        self.assert_root(actual_root)

        for address, value in values.items():
            self.assert_value_at_address(
                address, value, ishash=True)

        for address in delete_items:
            with self.assertRaises(KeyError):
                self.get(address, ishash=True)

    # assertions
    def assert_value_at_address(self, address, value, ishash=False):
        self.assertEqual(
            self.get(address, ishash),
            value,
            'Wrong value')

    def assert_no_key(self, key):
        with self.assertRaises(KeyError):
            self.get(key)

    def assert_root(self, expected):
        self.assertEqual(
            expected,
            self.get_merkle_root(),
            'Wrong root')

    def assert_not_root(self, *not_roots):
        root = self.get_merkle_root()
        for not_root in not_roots:
            self.assertNotEqual(
                root,
                not_root,
                'Wrong root')

    # trie accessors

    # For convenience, assume keys are not hashed
    # unless otherwise indicated.

    def set(self, key, val, ishash=False):
        key_ = key if ishash else _hash(key)
        return self.trie.set(key_, val)

    def get(self, key, ishash=False):
        key_ = key if ishash else _hash(key)
        return self.trie.get(key_)

    def delete(self, key, ishash=False):
        key_ = key if ishash else _hash(key)
        return self.trie.delete(key_)

    def set_merkle_root(self, root):
        self.trie.set_merkle_root(root)

    def get_merkle_root(self):
        return self.trie.get_merkle_root()

    def update(self, set_items, delete_items=None, virtual=True):
        return self.trie.update(set_items, delete_items, virtual=virtual)


def _hash(key):
    return MerkleDatabase.hash(key.encode())


def _random_string(length):
    return ''.join(random.choice(ascii_lowercase) for _ in range(length))

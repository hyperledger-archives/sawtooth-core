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

import os
import unittest
import random
import string

from sawtooth_validator.state.merkle import MerkleDatabase
from sawtooth_validator.database import lmdb_nolock_database

RUN_MERKLE_TESTS = True \
    if os.environ.get("RUN_MERKLE_TESTS", False) == "1" else False


@unittest.skipUnless(RUN_MERKLE_TESTS, "merkle tests require good filesystem")
class TestSawtoothMerkleTrie(unittest.TestCase):
    def setUp(self):
        self.lmdb = lmdb_nolock_database.LMDBNoLockDatabase(
            "/home/vagrant/merkle.lmdb",
            'n')

        self.trie = MerkleDatabase(self.lmdb)

    def tearDown(self):
        self.trie.close()

    def test_merkle_trie_root_advance(self):
        value = {"name": "foo", "value": 1}

        orig_root = self.trie.get_merkle_root()
        new_root = self.trie.set(MerkleDatabase.hash("foo"),
                                 value)

        with self.assertRaises(KeyError):
            self.trie.get(MerkleDatabase.hash("foo"))

        self.trie.set_merkle_root(new_root)

        self.assertEqual(self.trie.get(MerkleDatabase.hash("foo")),
                         value)

    def test_merkle_trie_delete(self):
        value = {"name": "bar", "value": 1}

        new_root = self.trie.set(MerkleDatabase.hash("bar"), value)

        self.trie.set_merkle_root(new_root)

        self.assertEqual(self.trie.get(MerkleDatabase.hash("bar")),
                         value)

        del_root = self.trie.delete(MerkleDatabase.hash("bar"))

        self.trie.set_merkle_root(del_root)

        with self.assertRaises(KeyError):
            self.trie.get(MerkleDatabase.hash("bar"))

    def test_merkle_trie_update(self):
        value = ''.join(random.choice(string.ascii_lowercase)
                        for _ in range(512))
        keys = []
        for i in range(1000):
            key = ''.join(random.choice(string.ascii_lowercase)
                          for _ in range(10))
            keys.append(key)
            hash = MerkleDatabase.hash(key)
            new_root = self.trie.set(hash, {key: value})
            self.trie.set_merkle_root(new_root)

        set_items = {}
        for key in random.sample(keys, 50):
            hash = MerkleDatabase.hash(key)
            thing = {key: 5.0}
            set_items[hash] = thing

        update_root = self.trie.update(set_items)
        self.trie.set_merkle_root(update_root)

        for address in set_items:
            self.assertEqual(self.trie.get(address),
                             set_items[address])

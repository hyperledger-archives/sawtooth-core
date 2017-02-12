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

import copy
import logging
import hashlib
import cbor

LOGGER = logging.getLogger(__name__)

INIT_ROOT_KEY = ''

# prototype node with value and list of child branch:hash pairs
NODE_PROTO = {"v": None,
              "c": {}
              }

TOKEN_SIZE = 2


class MerkleDatabase(object):
    def __init__(self, database, merkle_root=INIT_ROOT_KEY):
        self._database = database
        self.set_merkle_root(merkle_root)

    def __iter__(self):
        for item in self._yield_iter('', self._root_hash):
            yield item

    def _yield_iter(self, path, hash_key):
        try:
            node = self._get_by_addr(path)
        except KeyError:
            raise StopIteration()

        if path == INIT_ROOT_KEY:
            node = self._get_by_hash(hash_key)

        if node["v"] is not None:
            yield (path, self._decode(node["v"]))

        for child in node["c"]:
            for value in self._yield_iter(path + child, node["c"][child]):
                yield value

    def get_merkle_root(self):
        return self._root_hash

    def set_merkle_root(self, merkle_root):
        if merkle_root == INIT_ROOT_KEY:
            self._root_hash = self._set_kv(NODE_PROTO)
            self._root_node = self._get_by_hash(self._root_hash)
        else:
            self._root_node = self._get_by_hash(merkle_root)
            self._root_hash = merkle_root

    @classmethod
    def hash(cls, stuff):
        return hashlib.sha512(stuff).hexdigest()[:64]

    def _get_by_hash(self, key_hash):
        if key_hash in self._database:
            return self._decode(self._database.get(key_hash))
        else:
            raise KeyError("hash {} not found in database".format(key_hash))

    def __getitem__(self, address):
        return self.get(address)

    def get(self, address):
        return self._decode(self.get_node(address).get('v'))

    def get_node(self, address):
        return self._get_by_addr(address)

    def __setitem__(self, address, value):
        return self.set(address, value)

    def set(self, address, value):
        return self._set_by_addr(address, value)

    def _tokenize_address(self, address):
        return [address[i:i + TOKEN_SIZE]
                for i in range(0, len(address), TOKEN_SIZE)]

    def _get_by_addr(self, address):
        tokens = self._tokenize_address(address)

        node = self._root_node

        for token in tokens:
            if token in node['c']:
                node = self._get_by_hash(node['c'][token])
            else:
                raise KeyError("invalid address {} "
                               "from root {}".format(address,
                                                     self._root_hash))
        return node

    def _get_path_by_addr(self, address, return_empty=False):
        tokens = self._tokenize_address(address)
        node = copy.deepcopy(self._root_node)
        path = ''
        nodes = {}

        nodes[path] = node
        new_branch = False

        for token in tokens:
            if token in node['c'] and not new_branch:
                path = path + token
                node = self._get_by_hash(node['c'][token])
                nodes[path] = node
            else:
                if return_empty:
                    path = path + token
                    nodes[path] = {"v": None, "c": {}}
                    new_branch = True
                else:
                    raise KeyError("invalid address {} "
                                   "from root {}".format(address,
                                                         self._root_hash))
        return nodes

    def _decode(self, encoded):
        return cbor.loads(encoded)

    def _encode(self, value):
        return cbor.dumps(value, sort_keys=True)

    def _encode_and_hash(self, value):
        packed = self._encode(value)
        return (MerkleDatabase.hash(packed), packed)

    def delete(self, address):
        path_map = self._get_path_by_addr(address)

        batch = []
        leaf_branch = True
        for path in sorted(path_map, key=len, reverse=True):
            parent_address = path[:-TOKEN_SIZE]
            path_branch = path[-TOKEN_SIZE:]

            if len(path_map[path]['c']) > 0 or path == '':
                leaf_branch = False

            if not leaf_branch:
                (hash_key, packed) = self._encode_and_hash(path_map[path])
                batch.append((hash_key, packed))
                if path != '':
                    path_map[parent_address]['c'][path_branch] = hash_key
            else:
                if path != '':
                    del path_map[parent_address]['c'][path_branch]

        self._database.set_batch(batch)

        return hash_key

    def update(self, set_items, virtual=True):
        """

        Args:
            set_items (dict): dict key, values where keys are addresses
            virtual (boolean): True if not committing to disk
                               eg speculative root hash
        Returns:
            the state root after the operations
        """
        path_map = {}
        batch = []
        key_hash = None

        for set_address in set_items:
            path_map.update(self._get_path_by_addr(set_address,
                                                   return_empty=True))
            path_map[set_address]["v"] = self._encode(set_items[set_address])

        # Rebuild the hashes to the new root
        for path in sorted(path_map, key=len, reverse=True):
            (key_hash, packed) = self._encode_and_hash(path_map[path])
            batch.append((key_hash, packed))
            if path != '':
                parent_address = path[:-TOKEN_SIZE]
                path_branch = path[-TOKEN_SIZE:]
                path_map[parent_address]['c'][path_branch] = key_hash

        if not virtual:
            # Apply all new hash, value pairs to the database
            self._database.set_batch(batch)
        return key_hash

    def _set_by_addr(self, address, value):
        tokens = self._tokenize_address(address)
        path_addresses = [''.join(tokens[0:i]) for i in range(len(tokens),
                                                              0,
                                                              -1)]

        path_map = self._get_path_by_addr(address, return_empty=True)

        # Set the value in the leaf node
        path_map[path_addresses[0]]["v"] = self._encode(value)

        child = path_map[path_addresses[0]]

        batch = []
        for path_address in path_addresses:
            (key_hash, packed) = self._encode_and_hash(child)
            parent_address = path_address[:-TOKEN_SIZE]
            path_branch = path_address[-TOKEN_SIZE:]
            path_map[parent_address]["c"][path_branch] = key_hash
            batch.append((key_hash, packed))
            child = path_map[parent_address]

        # Update the child of the root node to the prior hash
        root_node = copy.deepcopy(self._root_node)
        root_node["c"][tokens[0]] = key_hash
        (root_hash, packed) = self._encode_and_hash(root_node)

        batch.append((root_hash, packed))

        self._database.set_batch(batch)

        return root_hash

    def _get_kv(self, key):
        packed = self._database.get(key)
        if packed is not None:
            return self._decode(packed)
        else:
            return None

    def _set_kv(self, value):
        packed = self._encode(value)
        hashed_key = MerkleDatabase.hash(packed)
        self._database.set(hashed_key, packed)
        return hashed_key

    def addresses(self):
        addresses = []
        for address, _ in self:
            addresses.append(address)

        return addresses

    def leaves(self, prefix):
        leaves = {}
        for address, value in self._yield_iter(prefix, self._root_hash):
            leaves[address] = value
        return leaves

    def close(self):
        self._database.close()

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
NODE_PROTO = {
    "v": None,
    "c": {}
}

TOKEN_SIZE = 2


def _decode(encoded):
    return cbor.loads(encoded)


def _encode(value):
    return cbor.dumps(value, sort_keys=True)


def _hash(stuff):
    return hashlib.sha512(stuff).hexdigest()[:64]


def _encode_and_hash(value):
    packed = _encode(value)
    return _hash(packed), packed


NODE_PROTO_PACKED = _encode(NODE_PROTO)

NODE_PROTO_HASHED = _hash(NODE_PROTO_PACKED)


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
            # pylint: disable=stop-iteration-return
            raise StopIteration()

        if path == INIT_ROOT_KEY:
            node = self._get_by_hash(hash_key)

        if node["v"] is not None:
            yield (path, _decode(node["v"]))

        for child in node["c"]:
            for value in self._yield_iter(path + child, node["c"][child]):
                yield value

    def __contains__(self, item):
        """Does the tree contain an address.

        Args:
            item (str): An address.

        Returns:
            (bool): True if it does contain, False otherwise.
        """

        try:
            self.get(item)
        except KeyError:
            return False

        return True

    def get_merkle_root(self):
        return self._root_hash

    def set_merkle_root(self, merkle_root):
        if merkle_root == INIT_ROOT_KEY:
            self._root_hash = self._set_kv()
            self._root_node = self._get_by_hash(self._root_hash)
        else:
            self._root_node = self._get_by_hash(merkle_root)
            self._root_hash = merkle_root

    @classmethod
    def hash(cls, stuff):
        return hashlib.sha512(stuff).hexdigest()[:64]

    def _get_by_hash(self, key_hash):
        try:
            return _decode(self._database.get(key_hash))
        except ValueError:   # value returned from database was None
            raise KeyError("hash {} not found in database".format(key_hash))

    def __getitem__(self, address):
        return self.get(address)

    def get(self, address):
        return _decode(self.get_node(address).get('v'))

    def get_node(self, address):
        return self._get_by_addr(address)

    def __setitem__(self, address, value):
        return self.set(address, value)

    def set(self, address, value):
        return self._set_by_addr(address, value)

    def _tokenize_address(self, address):
        return (
            address[i:i + TOKEN_SIZE]
            for i in range(0, len(address), TOKEN_SIZE)
        )

    def _get_by_addr(self, address):
        tokens = self._tokenize_address(address)

        node = self._root_node

        for token in tokens:
            try:
                node = self._get_by_hash(node['c'][token])
            except KeyError:
                raise KeyError(
                    "invalid address {} from root {}".format(
                        address, self._root_hash))
        return node

    def _get_path_by_addr(self, address):
        tokens = self._tokenize_address(address)
        node = copy.deepcopy(self._root_node)
        path = ''
        nodes = {path: node}

        new_branch = False

        for token in tokens:
            path += token
            node_token = node['c'].get(token)

            if node_token is not None and not new_branch:
                node = self._get_by_hash(node_token)
                nodes[path] = node
            else:
                nodes[path] = {"v": None, "c": {}}
                new_branch = True

        return nodes

    def delete(self, address):
        path_map = self._get_path_by_addr(address)

        batch = []
        leaf_branch = True
        for path in sorted(path_map, key=len, reverse=True):
            parent_address = path[:-TOKEN_SIZE]
            path_branch = path[-TOKEN_SIZE:]

            if path_map[path]['c'] or path == '':
                leaf_branch = False

            if not leaf_branch:
                (hash_key, packed) = _encode_and_hash(path_map[path])
                batch.append((hash_key, packed))
                if path != '':
                    path_map[parent_address]['c'][path_branch] = hash_key
            else:
                if path != '':
                    del path_map[parent_address]['c'][path_branch]

        self._database.put_multi(batch)

        return hash_key

    def update(self, set_items, delete_items=None, virtual=True):
        """

        Args:
            set_items (dict): dict key, values where keys are addresses
            delete_items (list): list of addresses
            virtual (boolean): True if not committing to disk
                               eg speculative root hash
        Returns:
            the state root after the operations
        """
        path_map = {}
        update_batch = []
        key_hash = None

        for set_address in set_items:
            # the set items are added to the Path map second,
            # since they may add children to paths
            path_map.update(self._get_path_by_addr(set_address))
            path_map[set_address]["v"] = _encode(set_items[set_address])

        if delete_items is not None:
            for del_address in delete_items:
                path_map.update(self._get_path_by_addr(del_address))

            for del_address in delete_items:
                del path_map[del_address]

                path_branch = del_address[-TOKEN_SIZE:]
                parent_address = del_address[:-TOKEN_SIZE]
                while parent_address:
                    pa_map = path_map[parent_address]
                    del pa_map["c"][path_branch]
                    if not pa_map["c"]:
                        # empty node delete it.
                        del path_map[parent_address]
                    else:
                        # found a node that is not empty no need to continue
                        break
                    path_branch = parent_address[-TOKEN_SIZE:]
                    parent_address = parent_address[:-TOKEN_SIZE]

                    if not parent_address:
                        if not pa_map['c']:
                            del path_map['']['c'][path_branch]

        # Rebuild the hashes to the new root
        for path in sorted(path_map, key=len, reverse=True):
            (key_hash, packed) = _encode_and_hash(path_map[path])
            update_batch.append((key_hash, packed))
            if path != '':
                parent_address = path[:-TOKEN_SIZE]
                path_branch = path[-TOKEN_SIZE:]
                path_map[parent_address]['c'][path_branch] = key_hash

        if not virtual:
            # Apply all new hash, value pairs to the database
            self._database.put_multi(update_batch)
        return key_hash

    def _set_by_addr(self, address, value):
        tokens = list(self._tokenize_address(address))

        path_addresses = [
            ''.join(tokens[0:i])
            for i in range(len(tokens), 0, -1)
        ]

        path_map = self._get_path_by_addr(address)

        # Set the value in the leaf node
        path_map[path_addresses[0]]["v"] = _encode(value)

        child = path_map[path_addresses[0]]

        batch = []
        for path_address in path_addresses:
            (key_hash, packed) = _encode_and_hash(child)
            parent_address = path_address[:-TOKEN_SIZE]
            path_branch = path_address[-TOKEN_SIZE:]
            path_map[parent_address]["c"][path_branch] = key_hash
            batch.append((key_hash, packed))
            child = path_map[parent_address]

        # Update the child of the root node to the prior hash
        root_node = copy.deepcopy(self._root_node)
        root_node["c"][tokens[0]] = key_hash
        (root_hash, packed) = _encode_and_hash(root_node)

        batch.append((root_hash, packed))

        self._database.put_multi(batch)

        return root_hash

    def _set_kv(self):
        self._database.set(
            NODE_PROTO_HASHED,
            NODE_PROTO_PACKED)

        return NODE_PROTO_HASHED

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

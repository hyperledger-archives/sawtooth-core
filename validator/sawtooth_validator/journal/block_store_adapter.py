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


# pylint: disable=no-name-in-module
from collections.abc import MutableMapping
from sawtooth_validator.journal.block_wrapper import BlockStatus
from sawtooth_validator.journal.block_wrapper import BlockWrapper


class BlockStoreAdapter(MutableMapping):
    """
    A dict like interface wrapper around the block store to guarentee,
    objects are correcty wrapped and unwrapped as they are stored and
    retreived.
    """
    def __init__(self, block_store):
        self._block_store = block_store

    def __setitem__(self, key, value):
        self._block_store[key] = {
            "block": value.block,
            "weight": value.weight
        }

    def __getitem__(self, key):
        block = self._block_store[key]
        return BlockWrapper(
            status=BlockStatus.Valid,
            **block)

    def __delitem__(self, key):
        del self._block_store[key]

    def __contains__(self, x):
        return x in self._block_store

    def __iter__(self):
        return iter(self._block_store)

    def __len__(self):
        return len(self._block_store)

    def __str__(self):
        out = []
        for v in self._block_store.values():
            out.append(str(v))
        return ','.join(out)

    def set_chain_head(self, block_id):
        """
        Set the current chain head, does not validate that the block
        store is in a valid state, ie that all the head block and all
        predecessors are in the store.
        """
        self._block_store["chain_head_id"] = block_id

    @property
    def chain_head(self):
        """
        Return the head block of the current chain.
        """
        return self.__getitem__(self._block_store["chain_head_id"])

    @property
    def store(self):
        """
        Access to the underlying store dict.
        """
        return self._block_store

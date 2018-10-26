# Copyright 2017 Intel Corporation
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

from collections.abc import MutableMapping
from threading import RLock
import time

from sawtooth_validator.journal.block_wrapper import NULL_BLOCK_IDENTIFIER


class BlockCache(MutableMapping):
    """
    A dict like interface to access blocks. Stores BlockState objects.
    """

    class CachedValue:
        def __init__(self, value):
            self.value = value
            self.timestamp = time.time()  # the time this State was created,
            # used for house keeping, ie when to flush this from the cache.
            self.count = 0

        def touch(self):
            """
            Mark this entry as accessed.
            """
            self.timestamp = time.time()

        def inc_count(self):
            self.count += 1
            self.touch()

        def dec_count(self):
            if self.count > 0:
                self.count -= 1
            self.touch()

    def __init__(self, block_store=None, keep_time=30, purge_frequency=30):
        super(BlockCache, self).__init__()
        self._lock = RLock()
        self._cache = {}
        self._keep_time = keep_time
        self._purge_frequency = purge_frequency
        self._next_purge_time = time.time() + purge_frequency
        self._block_store = block_store if block_store is not None else {}

    @property
    def block_store(self):
        """
        Return the wrapped blockStore object, expected to be of
        type BlockStoreAdapter.
        """
        return self._block_store

    def __getitem__(self, block_id):
        if not block_id:
            raise ValueError("None or empty block_id is an invalid identifier")

        with self._lock:
            try:
                value = self._cache[block_id]
                value.touch()
                return value.value
            except KeyError:
                if block_id in self._block_store:
                    block = self._block_store[block_id]
                    self.__setitem__(block_id, block)
                    return block
                raise

    def __setitem__(self, block_id, block):
        with self._lock:
            self._cache[block_id] = self.CachedValue(block)
            if block_id != NULL_BLOCK_IDENTIFIER and \
                    block.previous_block_id in self._cache:
                self._cache[block.previous_block_id].inc_count()

            if time.time() > self._next_purge_time:
                self._purge_expired()
                self._next_purge_time = time.time() + self._purge_frequency

    def __delitem__(self, block_id):
        with self._lock:
            block = self._cache[block_id].value
            if block.previous_block_id in self._cache:
                self._cache[block.previous_block_id].dec_count()
            del self._cache[block_id]

    def __iter__(self):
        with self._lock:
            return iter(self._cache)

    def block_iter(self):
        with self._lock:
            return map(lambda v: v.value, iter(self._cache.values()))

    def __len__(self):
        with self._lock:
            return len(self._cache)

    def __str__(self):
        with self._lock:
            out = []
            for v in self._cache.values():
                out.append(str(v.value))
            return ','.join(out)

    def add_chain(self, chain):
        """
        Add block in a chain in the correct order. Also add all of the blocks
        to the cache before doing a purge.
        """
        with self._lock:
            chain.sort(key=lambda x: x.block_num)
            for block in chain:
                block_id = block.header_signature
                if block_id not in self._cache:
                    self._cache[block_id] = self.CachedValue(block)
                    if block.previous_block_id in self._cache:
                        self._cache[block.previous_block_id].inc_count()

            if time.time() > self._next_purge_time:
                self._purge_expired()
                self._next_purge_time = time.time() + self._purge_frequency

    @property
    def cache(self):
        return self._cache

    @property
    def keep_time(self):
        return self._keep_time

    @property
    def purge_frequency(self):
        with self._lock:
            return self._purge_frequency

    def _purge_expired(self):
        """
        Remove all expired entries from the cache that do not have a reference
        count.
        """
        time_horizon = time.time() - self._keep_time
        new_cache = {}
        dec_count_for = []
        for (k, v) in self._cache.items():
            if v.count > 0:
                if k not in self._block_store:
                    new_cache[k] = v
                else:
                    if v.timestamp > time_horizon:
                        new_cache[k] = v
                    else:
                        block = v.value
                        if block is not None:
                            dec_count_for.append(block.previous_block_id)

            elif v.timestamp > time_horizon:
                new_cache[k] = v

            else:
                block = v.value
                # Handle NULL_BLOCK_IDENTIFIER
                if block is not None:
                    dec_count_for.append(block.previous_block_id)

        self._cache = new_cache
        for block_id in dec_count_for:
            if block_id in self._cache:
                self._cache[block_id].dec_count()

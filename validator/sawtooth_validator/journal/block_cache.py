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

from sawtooth_validator.journal.timed_cache import TimedCache


class BlockCache(TimedCache):
    """
    A dict like interface to access blocks. Stores BlockState objects.
    """
    def __init__(self, block_store=None, keep_time=10, purge_frequency=10):
        super(BlockCache, self).__init__(keep_time, purge_frequency)
        self._block_store = block_store if block_store is not None else {}

    def __getitem__(self, key):
        with self._lock:
            try:
                return super(BlockCache, self).__getitem__(key)
            except KeyError:
                if key in self._block_store:
                    value = self._block_store[key]
                    super(BlockCache, self).__setitem__(key, value)
                    return value
                raise

    @property
    def block_store(self):
        """
        Return the wrapped blockStore object, expected to be of
        type BlockStoreAdapter.
        """
        return self._block_store

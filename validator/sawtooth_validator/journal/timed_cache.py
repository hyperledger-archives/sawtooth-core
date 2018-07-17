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
from threading import RLock
import time


class TimedCache(MutableMapping):
    """
    A dict like interface that removes entries after sometime of no access.

    Accesses are Thread safe.

    Args:
        keep_time (float): How long in seconds to hold a value for
        purge_frequency (float): How often to look for old values to purge
    """
    class CachedValue:
        def __init__(self, value):
            self.value = value
            self.timestamp = time.time()  # the time this State was created,
            # used for house keeping, ie when to flush this from the cache.

        def touch(self):
            """
            Mark this entry as accessed.
            """
            self.timestamp = time.time()

    def __init__(self, keep_time=30, purge_frequency=30):
        super(TimedCache, self).__init__()
        self._lock = RLock()
        self._cache = {}
        self._keep_time = keep_time
        self._purge_frequency = purge_frequency
        self._next_purge_time = time.time() + purge_frequency

    def __setitem__(self, key, value):
        with self._lock:
            if time.time() > self._next_purge_time:
                self._purge_expired()
                self._next_purge_time = time.time() + self._purge_frequency
            self._cache[key] = self.CachedValue(value)

    def __getitem__(self, key):
        with self._lock:
            value = self._cache[key]
            value.touch()
            return value.value

    def __delitem__(self, key):
        with self._lock:
            del self._cache[key]

    def __iter__(self):
        with self._lock:
            return iter(self._cache)

    def __len__(self):
        with self._lock:
            return len(self._cache)

    def __str__(self):
        with self._lock:
            out = []
            for v in self._cache.values():
                out.append(str(v.value))
            return ','.join(out)

    @property
    def cache(self):
        return self._cache

    @property
    def keep_time(self):
        return self._keep_time

    @property
    def purge_frequency(self):
        return self._purge_frequency

    def _purge_expired(self):
        """
        Remove all expired entries from the cache.
        """
        time_horizon = time.time() - self._keep_time
        new_cache = {}
        for (k, v) in self._cache.items():
            if v.timestamp > time_horizon:
                new_cache[k] = v
        self._cache = new_cache

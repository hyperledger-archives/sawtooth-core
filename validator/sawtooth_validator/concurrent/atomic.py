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

from threading import Lock
from threading import RLock


class Counter:
    def __init__(self, initial_value=0):
        self._value = initial_value
        self._lock = Lock()

    def get(self):
        with self._lock:
            return self._value

    def get_and_inc(self, step=1):
        with self._lock:
            ret_value = self._value
            self._value += step

        return ret_value

    def get_and_dec(self, step=1):
        with self._lock:
            ret_value = self._value
            self._value -= step

        return ret_value

    def inc(self, step=1):
        with self._lock:
            self._value += step

    def dec(self, step=1):
        with self._lock:
            self._value -= step


class ConcurrentSet:
    def __init__(self):
        self.set = set()
        self.lock = RLock()

    def add(self, element):
        with self.lock:
            self.set.add(element)

    def remove(self, element):
        with self.lock:
            self.set.remove(element)

    def remove_all(self, elements):
        with self.lock:
            for elem in elements:
                self.set.remove(elem)

    def __contains__(self, element):
        with self.lock:
            return element in self.set


class ConcurrentMultiMap:
    """A dictionary that maps keys to lists of items. All methods are
    modifications to the referenced list."""
    def __init__(self):
        self.dict = dict()
        self.lock = RLock()

    def __contains__(self, key):
        with self.lock:
            return key in self.dict

    def append(self, key, item):
        """Append item to the list at key. Creates the list at key if it
        doesn't exist.
        """
        with self.lock:
            if key in self.dict:
                self.dict[key].append(item)
            else:
                self.dict[key] = [item]

    def append_if_unique(self, key, item, compare_fn):
        with self.lock:
            if key in self.dict:
                for i in self.dict[key]:
                    if compare_fn(i, item):
                        return
                self.dict[key].append(item)
            else:
                self.dict[key] = [item]

    def set(self, key, items):
        """Set key to a copy of items"""
        if not isinstance(items, list):
            raise ValueError("items must be a list")
        with self.lock:
            self.dict[key] = items.copy()

    def swap(self, key, items):
        """Set key to a copy of items and return the list that was previously
        stored if the key was set. If not key was set, returns an empty list.
        """
        if not isinstance(items, list):
            raise ValueError("items must be a list")
        return_value = []
        with self.lock:
            if key in self.dict:
                return_value = self.dict[key]
            # Make a copy since we don't want users keeping a reference that is
            # outside the lock
            self.dict[key] = items.copy()
        return return_value

    def pop(self, key, default):
        """If the key is set, remove and return the list stored at key.
        Otherwise return default."""
        with self.lock:
            return self.dict.pop(key, default)

    def get(self, key, default):
        """If the key is set, return a copy of the list stored at key.
        Otherwise return default."""
        with self.lock:
            try:
                return self.dict[key].copy()
            except KeyError:
                return default

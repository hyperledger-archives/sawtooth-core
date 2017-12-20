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

from collections import deque
from threading import Lock


class LruCache(object):
    """
    A simple thread-safe lru cache.
    """

    def __init__(self, max_size=100):
        self.max_size = max_size
        self.order = deque(maxlen=self.max_size)
        self.values = {}
        self.lock = Lock()

    def __setitem__(self, key, value):
        with self.lock:
            if key not in self.values:
                while len(self.order) >= self.max_size:
                    v = self.order.pop()
                    del self.values[v]
                self.values[key] = value
                self.order.appendleft(key)

    def __getitem__(self, key):
        return self.get(key)

    def get(self, key, default=None):
        with self.lock:
            result = self.values.get(key, default)
            if result is not default:
                self.order.remove(key)
                self.order.appendleft(key)
        return result

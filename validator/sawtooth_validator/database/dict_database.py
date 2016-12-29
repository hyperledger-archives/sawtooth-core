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

from sawtooth_validator.database import database


class DictDatabase(database.Database):
    """This database implementation should only be used in
    tests. Provides all of the interface methods that
    the MerkleTree requires.
    """
    def __init__(self):
        super(DictDatabase, self).__init__()
        self._data = dict()

    def get(self, key):
        return self._data.get(key)

    def __contains__(self, item):
        return item in self._data

    def set(self, key, value):
        self._data[key] = value

    def set_batch(self, kvpairs):
        for k, v in kvpairs:
            self._data[k] = v

    def close(self):
        pass

    def delete(self, key):
        pass

    def __len__(self):
        pass

    def keys(self):
        pass

    def sync(self):
        pass

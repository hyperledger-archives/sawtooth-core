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
    def __init__(self, data=None):
        super(DictDatabase, self).__init__()
        if data is None:
            self._data = dict()
        else:
            self._data = data

    def get(self, key):
        return self._data.get(key)

    def get_batch(self, keys):
        out = []
        for k in keys:
            out.append((k, self._data.get(k)))
        return out

    def get_indirect(self, key):
        key_2 = self._data.get(key)
        if key_2 is not None:
            return self._data.get(key_2)
        return None

    def __contains__(self, item):
        return item in self._data

    def set(self, key, value):
        self._data[key] = value

    def set_batch(self, add_pairs, del_keys=None):
        if del_keys is not None:
            for k in del_keys:
                del self._data[k]

        for k, v in add_pairs:
            self._data[k] = v

    def close(self):
        pass

    def delete(self, key):
        del self._data[key]

    def __len__(self):
        return len(self._data)

    def keys(self):
        return self._data.keys()

    def sync(self):
        pass

    def __str__(self):
        out = []
        for key in self._data.keys():
            value = self._data[key]
            out.append('{}: {}'.format(key, str(value)))
        return ','.join(out)

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

    def __init__(self, data=None, indexes=None):
        super(DictDatabase, self).__init__()

        if indexes:
            self._indexes = {
                name: ({}, key_fn)
                for name, key_fn in indexes.items()
            }
        else:
            self._indexes = {}

        self._data = {}
        if data is not None:
            self.update(data.items(), [])

    def contains_key(self, key, index=None):
        if index is not None and index not in self._indexes:
            raise ValueError('Index {} does not exist'.format(index))

        if index:
            return key.encode() in self._indexes[index][0]

        return key in self._data

    def count(self, index=None):
        if index is not None and index not in self._indexes:
            raise ValueError('Index {} does not exist'.format(index))

        if index:
            return len(self._indexes[index][0])

        return len(self._data)

    def get_multi(self, keys, index=None):
        if index is not None and index not in self._indexes:
            raise ValueError('Index {} does not exist'.format(index))

        out = []
        for key in keys:
            try:
                if index:
                    out.append((key, self._data[
                        self._indexes[index][0][key.encode()]]))
                else:
                    out.append((key, self._data[key]))
            except KeyError:
                # ignore missing values here
                continue
        return out

    def cursor(self, index=None):
        if index is not None and index not in self._indexes:
            raise ValueError('Index {} does not exist'.format(index))
        if not index:
            return DictCursor(self._data.copy())

        return DictIndexCursor(self._indexes[index][0].copy(),
                               self._data.copy())

    def close(self):
        pass

    def update(self, puts, deletes):
        for key, val in puts:
            self._data[key] = val
            for (index_data, key_fn) in self._indexes.values():
                index_keys = key_fn(val)
                for idx_key in index_keys:
                    index_data[idx_key] = key

        for k in deletes:
            if k not in self._data:
                continue

            old_value = self._data[k]
            del self._data[k]
            for (index_data, key_fn) in self._indexes.values():
                index_keys = key_fn(old_value)
                for idx_key in index_keys:
                    del index_data[idx_key]

    def keys(self, index=None):
        return self._data.keys()

    def sync(self):
        pass

    def __contains__(self, item):
        return item in self._data

    def __len__(self):
        return len(self._data)

    def __str__(self):
        out = []
        for key, value in self._data.items():
            out.append('{}: {}'.format(key, str(value)))
        return ','.join(out)


class DictCursor(database.Cursor):
    def __init__(self, data):
        self._data = list(data.items())
        self._position = -1

    def iter(self):
        if self._position not in self._data:
            self.first()
        return DictCursor._wrap_iter(self._data, self._position)

    def iter_rev(self):
        if self._position not in self._data:
            self.last()
        return DictCursor._wrap_iter(self._data, self._position, reverse=True)

    def first(self):
        self._position = 0

    def last(self):
        self._position = len(self._data) - 1

    def seek(self, key):
        # this cursor actually assumes that the key is header_signature
        for i, (stored_key, _) in enumerate(self._data):
            if stored_key == key:
                self._position = i
                return

        raise ValueError("Unknown key: {}".format(key))

    def key(self):
        if self._position >= 0 and self._position < len(self._data):
            return self._data[self._position][0]

        return None

    def value(self):
        if self._position >= 0 and self._position < len(self._data):
            return self._data[self._position][1]

        return None

    @staticmethod
    def _wrap_iter(data, start, reverse=False):
        class _WrapperIter:
            def __init__(self, start_pos):
                self._pos = start_pos

            def __iter__(self):
                return self

            def __next__(self):
                if self._pos >= 0 and self._pos < len(data):
                    raise StopIteration()

                val = data[self._pos][1]
                self._pos += (-1 if reverse else 1)

                return val

        return _WrapperIter(start)


class DictIndexCursor(database.Cursor):
    def __init__(self, index, data):
        self._index = sorted(index.items(), key=lambda item: item[0])
        self._data = data
        self._position = -1

    def iter(self):
        if not (self._position >= 0 and self._position < len(self._index)):
            self.first()
        return DictIndexCursor._wrap_iter(
            self._index, self._position, self._data)

    def iter_rev(self):
        if not (self._position >= 0 and self._position < len(self._index)):
            self.last()
        return DictIndexCursor._wrap_iter(
            self._index, self._position, self._data, reverse=True)

    def first(self):
        self._position = 0

    def last(self):
        self._position = len(self._index) - 1

    def seek(self, key):
        # this cursor actually assumes that the key is header_signature
        for i, item in enumerate(self._index):
            if item[0].decode() == key:
                self._position = i
                return True

        return False

    def key(self):
        if self._position >= 0 and self._position < len(self._index):
            return self._index[self._position][0].decode()

        return None

    def value(self):
        if self._position >= 0 and self._position < len(self._index):
            return self._data[self._index[self._position][1]]

        return None

    @staticmethod
    def _wrap_iter(index, start, data, reverse=False):
        class _WrapperIter:
            def __init__(self):
                self._pos = start

            def __iter__(self):
                return self

            def __next__(self):
                if not (self._pos >= 0 and self._pos < len(index)):
                    raise StopIteration()

                val = data[index[self._pos][1]]
                self._pos += (-1 if reverse else 1)

                return val

        return _WrapperIter()

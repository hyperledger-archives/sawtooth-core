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

import os
import lmdb
import cbor

from sawtooth_validator.database import database


class LMDBNoLockDatabase(database.Database):
    """LMDBNoLockDatabase is an implementation of the
    sawtooth_validator.database.Database interface which uses LMDB for the
    underlying persistence.

    Attributes:
       _lmdb (lmdb.Environment): The underlying lmdb database.
    """

    def __init__(self, filename, flag):
        """Constructor for the LMDBNoLockDatabase class.

        Args:
            filename (str): The filename of the database file.
            flag (str): a flag indicating the mode for opening the database.
                Refer to the documentation for anydbm.open().
        """
        super(LMDBNoLockDatabase, self).__init__()

        create = bool(flag == 'c')

        if flag == 'n':
            if os.path.isfile(filename):
                os.remove(filename)
            create = True

        self._lmdb = lmdb.Environment(
            path=filename,
            map_size=1024**4,
            map_async=True,
            writemap=True,
            readahead=False,
            subdir=False,
            create=create,
            lock=True)

    # pylint: disable=no-value-for-parameter
    def __len__(self):
        with self._lmdb.begin() as txn:
            return txn.stat()['entries']

    def contains_key(self, key, index=None):
        with self._lmdb.begin() as txn:
            return txn.get(key.encode()) is not None

    def get(self, key, index=None):
        with self._lmdb.begin() as txn:
            packed = txn.get(key.encode())

        try:
            return cbor.loads(packed)
        except ValueError:
            return None

    def get_multi(self, keys, index=None):
        with self._lmdb.begin() as txn:
            result = []
            for key in keys:
                packed = txn.get(key.encode())
                if packed is not None:
                    result.append((key, cbor.loads(packed)))
        return result

    def cursor(self, index=None):
        """
        This currently is just to satisfy the interface.
        """
        raise NotImplementedError()

    def count(self, index=None):
        """
        This currently is just to satisfy the interface.
        """
        raise NotImplementedError()

    def update(self, puts, deletes):
        with self._lmdb.begin(write=True, buffers=True) as txn:
            for k in deletes:
                txn.delete(k.encode())
            for k, v in puts:
                packed = cbor.dumps(v)
                txn.put(k.encode(), packed, overwrite=True)
        self.sync()

    def delete(self, key):
        """Removes a key:value from the database

        Args:
            key (str): The key to remove.
        """
        with self._lmdb.begin(write=True, buffers=True) as txn:
            txn.delete(key.encode())

    def sync(self):
        """Ensures that pending writes are flushed to disk
        """
        self._lmdb.sync()

    def close(self):
        """Closes the connection to the database
        """
        self._lmdb.close()

    def keys(self, index=None):
        """Returns a list of keys in the database
        """
        with self._lmdb.begin() as txn:
            return [key.decode() for key, _ in txn.cursor()]

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

from threading import RLock
import os
import pickle
try:
    import cPickle as pickle
except ImportError:
    pass

import lmdb

from sawtooth_validator.database import database


class LMDBDatabase(database.Database):
    """LMDBDatabase is a thread-safe implementation of the
    sawtooth_validator.database.Database interface which uses LMDB for the
    underlying persistence.

    Attributes:
       lock (threading.RLock): A reentrant lock to ensure threadsafe access.
       lmdb (lmdb.Environment): The underlying lmdb database.
    """

    def __init__(self, filename, flag):
        """Constructor for the LMDBDatabase class.

        Args:
            filename (str): The filename of the database file.
            flag (str): a flag indicating the mode for opening the database.
                Refer to the documentation for anydbm.open().
        """
        super(LMDBDatabase, self).__init__()
        self._lock = RLock()

        create = bool(flag == 'c')

        if flag == 'n':
            if os.path.isfile(filename):
                os.remove(filename)
            create = True

        self._lmdb = lmdb.Environment(path=filename,
                                      map_size=1024**4,
                                      writemap=True,
                                      subdir=False,
                                      create=create,
                                      lock=False)

    def __len__(self):
        with self._lock:
            with self._lmdb.begin() as txn:
                return txn.stat()['entries']

    def __contains__(self, key):
        with self._lock:
            with self._lmdb.begin() as txn:
                return bool(txn.get(key) is not None)

    def get(self, key):
        """Retrieves a value associated with a key from the database

        Args:
            key (str): The key to retrieve
        """
        with self._lock:
            with self._lmdb.begin() as txn:
                pickled = txn.get(key)
                if pickled is not None:
                    return pickle.loads(pickled)

    def set(self, key, value):
        """Sets a value associated with a key in the database

        Args:
            key (str): The key to set.
            value (str): The value to associate with the key.
        """
        pickled = pickle.dumps(value)
        with self._lock:
            with self._lmdb.begin(write=True, buffers=True) as txn:
                txn.put(key, pickled, overwrite=True)

    def delete(self, key):
        """Removes a key:value from the database

        Args:
            key (str): The key to remove.
        """
        with self._lock:
            with self._lmdb.begin(write=True, buffers=True) as txn:
                txn.delete(key)

    def sync(self):
        """Ensures that pending writes are flushed to disk
        """
        with self._lock:
            self._lmdb.sync()

    def close(self):
        """Closes the connection to the database
        """
        with self._lock:
            self._lmdb.close()

    def keys(self):
        """Returns a list of keys in the database
        """
        with self._lock:
            with self._lmdb.begin() as txn:
                return [key for key, _ in txn.cursor()]

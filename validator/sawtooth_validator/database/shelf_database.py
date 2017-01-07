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
from shelve import Shelf
try:
    # On python2 windows this will fail
    # On python2 linux this will import the wrong module
    # On python3 Linux this will pass
    import dbm
except ImportError:
    pass
try:
    # On python2 linux + windows this will pass
    import anydbm as dbm
except ImportError:
    pass

from sawtooth_validator.database import database


class ShelfDatabase(database.Database):
    """ShelfDatabase is a thread-safe implementation of the
    sawtooth_validator.database.Database interface which uses python Shelve
    for the underlying persistence.

    Attributes:
       lock (threading.RLock): A reentrant lock to ensure threadsafe access.
       shelf (shelve.Shelf): The underlying shelf database.
    """

    def __init__(self, filename, flag):
        """Constructor for the ShelfDatabase class.

        Args:
            filename (str): The filename of the database file.
            flag (str): a flag indicating the mode for opening the database.
                Refer to the documentation for anydbm.open().
        """
        super(ShelfDatabase, self).__init__()
        self._lock = RLock()
        self._shelf = Shelf(dbm.open(filename, flag))

    def __len__(self):
        with self._lock:
            return len(self._shelf)

    def __contains__(self, key):
        with self._lock:
            return key in self._shelf

    def get(self, key):
        """Retrieves a value associated with a key from the database

        Args:
            key (str): The key to retrieve
        """
        with self._lock:
            return self._shelf.get(key, default=None)

    def set(self, key, value):
        """Sets a value associated with a key in the database

        Args:
            key (str): The key to set.
            value (str): The value to associate with the key.
        """
        with self._lock:
            self._shelf[key] = value

    def delete(self, key):
        """Removes a key:value from the database

        Args:
            key (str): The key to remove.
        """
        with self._lock:
            del self._shelf[key]

    def sync(self):
        """Ensures that pending writes are flushed to disk
        """
        with self._lock:
            self._shelf.sync()

    def close(self):
        """Closes the connection to the database
        """
        with self._lock:
            self._shelf.close()

    def keys(self):
        """Returns a list of keys in the database
        """
        with self._lock:
            return self._shelf.keys()

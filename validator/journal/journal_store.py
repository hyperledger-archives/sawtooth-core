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


class JournalStore(object):
    """JournalStore exposes dict-like behaviors on an underlying key-value
    database interface.

    This two-layer abstraction is useful for segregating how the database
    operates from how the application uses the database. In the future, for
    example, the JournalStore might implement radix tree structures on top
    of the underlying key-value database while continuing to provide a
    simple get/set semantic to consumers.

    Attributes:
        database (journal.database.Database): An instance of a class
            extending the Database interface.
    """

    def __init__(self, database):
        """Constructor for the JournalStore class.

        Args:
            database (journal.database.Database): An instance of a class
                extending the database interface.
        """
        self._database = database

    def __getitem__(self, key):
        return self.get(key)

    def __setitem__(self, key, value):
        return self.set(key, value)

    def __delitem__(self, key):
        self._database.delete(key)

    def __len__(self):
        return len(self._database)

    def __contains__(self, key):
        return key in self._database

    def get(self, key):
        """Retrieves a value associated with a key from the database

        Args:
            key (str): The key to retrieve
        """
        return self._database.get(key)

    def set(self, key, value):
        """Sets a value associated with a key in the database

        Args:
            key (str): The key to set.
            value (str): The value to associate with the key.
        """
        self._database.set(key, value)

    def delete(self, key):
        """Removes a key:value from the database

        Args:
            key (str): The key to remove.
        """
        self._database.delete(key)

    def sync(self):
        """Ensures that pending writes are flushed to disk
        """
        self._database.sync()

    def close(self):
        """Closes the connection to the database
        """
        self._database.close()

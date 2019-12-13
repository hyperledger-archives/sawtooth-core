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
from abc import ABCMeta
from abc import abstractmethod


class Database(metaclass=ABCMeta):
    """The Database interface. This class is intended to be inherited by
    specific database implementations.
    """

    def __init__(self):
        """Constructor for the Database class.
        """

    def __getitem__(self, key):
        return self.get(key)

    def __setitem__(self, key, value):
        return self.put(key, value)

    def __delitem__(self, key):
        self.delete(key)

    @abstractmethod
    def __len__(self):
        raise NotImplementedError()

    def __contains__(self, key):
        return self.contains_key(key)

    @abstractmethod
    def contains_key(self, key, index=None):
        raise NotImplementedError()

    @abstractmethod
    def count(self, index=None):
        """Retrieve the count of entries in the main database or the index."""
        raise NotImplementedError()

    def get(self, key, index=None):
        """Retrieves a value associated with a key from the database

        Args:
            key (str): The key to retrieve
        """
        records = self.get_multi([key], index=index)

        try:
            return records[0][1]  # return the value from the key/value tuple
        except IndexError:
            return None

    @abstractmethod
    def get_multi(self, keys, index=None):
        """
        Retrieves the values for the given keys, if they exists.

        This returns an iterable of key-value pairs for the keys retrieved.
        Any key not found will not be in the resulting list. Optionally, an
        index name can be provided and the values found via the index will be
        returned.  In this case the key int the returned tuple will be the
        provided key.

        Args:
            keys (:iterable:str:): an iterable of keys
            index (:str:): an optional index name; defaults to `None`

        Returns:
            list: a list of key-value pairs of the items found in the db
        """
        raise NotImplementedError()

    @abstractmethod
    def cursor(self, index=None):
        """Creates a cursor on the database.

        Creates a cursor on the database, which traverses the keys in their
        natural order.  It may be associated with an index, where it traverses
        the specified index's keys in their natural order.

        Args:
            index (str; optional) - an optional index; defaults to `None`

        Returns:
            (:obj:`Cursor`) - a Cursor instance
        """
        raise NotImplementedError()

    def set(self, key, value):
        """Sets a value associated with a key in the database.

        Alias for `put`.

        Args:
            key (str): The key to set.
            value (str): The value to associate with the key.
        """
        self.put(key, value)

    def put(self, key, value):
        """Sets a value associated with a key in the database

        Args:
            key (str): The key to set.
            value (str): The value to associate with the key.
        """
        return self.update([(key, value)], [])

    def put_multi(self, items):
        """Puts all the (key, value) pairs in the iterable `items` into the
        database.

        Args:
            items: (:iterable:`tuple`): an iterable of key/value pairs
        """
        self.update(items, [])

    def delete(self, key):
        """Removes a key:value from the database

        Args:
            key (str): The key to remove.
        """
        self.update([], [key])

    def delete_multi(self, keys):
        """Removes the given keys from the database

        Args:
            keys (str): The key to remove.
        """
        self.update([], keys)

    @abstractmethod
    def update(self, puts, deletes):
        """Applies the given puts and deletes atomically.

        Args:
            puts (:iterable:`tuple`): an iterable of key/value pairs to insert
            deletes (:iterable:str:) an iterable of keys to delete
        """
        raise NotImplementedError()

    @abstractmethod
    def close(self):
        """Closes the connection to the database
        """
        raise NotImplementedError()

    @abstractmethod
    def keys(self, index=None):
        """Returns a list of keys in the database
        """
        raise NotImplementedError()


class Cursor(metaclass=ABCMeta):
    """A cursor for items in the database.

    A cursor can be used to traverse items in the database in an efficient
    manner.  Depending on underlying database implementation, the items may
    be consistent within the context of a database transaction.
    """

    def __enter__(self):
        """Context Manager: Enter"""
        self.open()
        return self

    def __exit__(self, *args):
        """Context Manager: Exit"""
        self.close()

    def open(self):
        """
        Opens the cursor.
        """

    def close(self):
        """
        Closes the cursor, terminating any state.
        """

    @abstractmethod
    def iter(self):
        """Returns a forward iterator of the items

        The iterator starting from the seek key, or `first` if no seek key has
        been set.
        """
        raise NotImplementedError()

    @abstractmethod
    def iter_rev(self):
        """Returns a reverse iterator of the items

        The iterator starting from the seek key, or `last` if no seek key has
        been set.
        """
        raise NotImplementedError()

    @abstractmethod
    def first(self):
        """Sets the position to the first key, based on natural key order
        """
        raise NotImplementedError()

    @abstractmethod
    def last(self):
        """Sets the position to the last key, based on natural key order
        """
        raise NotImplementedError()

    @abstractmethod
    def seek(self, key):
        """Sets the position to the given key
        """
        raise NotImplementedError()

    @abstractmethod
    def key(self):
        """Returns the current key at the set position, or None if it has not
        been positioned.
        """
        raise NotImplementedError()

    @abstractmethod
    def value(self):
        """Returns the current value at the set position, or None if it has not
        been positioned.
        """
        raise NotImplementedError()

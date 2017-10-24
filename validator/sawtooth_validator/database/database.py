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
from collections import OrderedDict
from threading import RLock


class Database(object):
    """The Database interface. This class is intended to be inherited by
    specific database implementations.
    """

    def __init__(self):
        """Constructor for the Database class.
        """
        pass

    def __getitem__(self, key):
        return self.get(key)

    def __setitem__(self, key, value):
        return self.set(key, value)

    def __delitem__(self, key):
        self.delete(key)

    def __len__(self):
        raise NotImplementedError()

    def __contains__(self, key):
        raise NotImplementedError()

    def get(self, key):
        """Retrieves a value associated with a key from the database

        Args:
            key (str): The key to retrieve
        """
        raise NotImplementedError()

    def set(self, key, value):
        """Sets a value associated with a key in the database

        Args:
            key (str): The key to set.
            value (str): The value to associate with the key.
        """
        raise NotImplementedError()

    def delete(self, key):
        """Removes a key:value from the database

        Args:
            key (str): The key to remove.
        """
        raise NotImplementedError()

    def sync(self):
        """Ensures that pending writes are flushed to disk
        """
        raise NotImplementedError()

    def close(self):
        """Closes the connection to the database
        """
        raise NotImplementedError()

    def keys(self):
        """Returns a list of keys in the database
        """
        raise NotImplementedError()

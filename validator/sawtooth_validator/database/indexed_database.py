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

import logging
import os
import lmdb

from sawtooth_validator.database import database


LOGGER = logging.getLogger(__name__)

DEFAULT_SIZE = 1024**4


class IndexOutOfSyncError(Exception):
    pass


class IndexedDatabase(database.Database):
    """IndexedDatabase is an implementation of the
    sawtooth_validator.database.Database interface which uses LMDB for the
    underlying persistence.

    It must be provided with a serializer and a deserializer.
    """

    def __init__(self, filename, serializer, deserializer,
                 indexes=None,
                 flag=None,
                 _size=DEFAULT_SIZE):
        """Constructor for the IndexedDatabase class.

        Args:
            filename (str): The filename of the database file.
            serializer (function): converts entries to bytes
            deserializer (function): restores items from bytes
            indexes (dict:(str,function):optional): dict of index names to key
                functions.  The key functions use the deserialized value and
                produce n index keys, that will reference the items primary
                key. Defaults to None
            flag (str:optional): a flag indicating the mode for opening the
                database.  Refer to the documentation for anydbm.open().
                Defaults to None.
        """
        super(IndexedDatabase, self).__init__()

        create = bool(flag == 'c')

        if flag == 'n':
            if os.path.isfile(filename):
                os.remove(filename)
            create = True

        if indexes is None:
            indexes = {}

        self._serializer = serializer
        self._deserializer = deserializer

        self._lmdb = lmdb.Environment(
            path=filename,
            map_size=_size,
            map_async=True,
            writemap=True,
            readahead=False,
            subdir=False,
            create=create,
            max_dbs=len(indexes) + 1,
            lock=True)

        self._main_db = self._lmdb.open_db('main'.encode())

        self._indexes = \
            {name: self._make_index_tuple(name, index_info)
             for name, index_info in indexes.items()}

    def _make_index_tuple(self, name, index_info):
        if callable(index_info):
            key_fn = index_info
            integerkey = False
        elif isinstance(index_info, dict):
            key_fn = index_info['key_fn']
            integerkey = index_info['integerkey'] \
                if 'integerkey' in index_info else False
        else:
            raise ValueError(
                'Index {} must be defined as a function or a dict'.format(
                    name))

        return (self._lmdb.open_db('index_{}'.format(name).encode(),
                                   integerkey=integerkey),
                key_fn)

    # pylint: disable=no-value-for-parameter
    def __len__(self):
        with self._lmdb.begin(db=self._main_db) as txn:
            return txn.stat()['entries']

    def count(self, index=None):
        if index is None:
            return len(self)

        if index is not None and index not in self._indexes:
            raise ValueError('Index {} does not exist'.format(index))

        with self._lmdb.begin(db=self._indexes[index][0]) as txn:
            return txn.stat()['entries']

    def contains_key(self, key, index=None):
        if index is not None and index not in self._indexes:
            raise ValueError('Index {} does not exist'.format(index))

        if index:
            search_db = self._indexes[index][0]
        else:
            search_db = self._main_db

        with self._lmdb.begin(db=search_db) as txn:
            return txn.cursor().set_key(key.encode())

    def get_multi(self, keys, index=None):
        if index is not None and index not in self._indexes:
            raise ValueError('Index {} does not exist'.format(index))

        with self._lmdb.begin() as txn:
            result = []
            cursor = txn.cursor(self._main_db)
            index_cursor = None
            if index is not None:
                index_db = self._indexes[index][0]
                index_cursor = txn.cursor(index_db)

            for key in keys:
                read_key = key.encode()
                # If we're looking at an index, check the index first
                if index_cursor:
                    try:
                        read_key = index_cursor.get(read_key)
                    except lmdb.BadValsizeError:
                        raise KeyError("Invalid key: %s" % read_key)
                    if not read_key:
                        continue

                try:
                    packed = cursor.get(read_key)
                except lmdb.BadValsizeError:
                    raise KeyError("Invalid key: %s" % read_key)

                if packed is not None:
                    result.append((read_key.decode(),
                                   self._deserializer(packed)))
                elif index_cursor:
                    raise IndexOutOfSyncError(
                        'Index is out of sync for key {}'.format(key))

        return result

    def cursor(self, index=None):
        if index is not None and index not in self._indexes:
            raise ValueError('Index {} does not exist'.format(index))

        db_chain = []
        if index:
            db_chain.append(self._indexes[index][0])

        db_chain.append(self._main_db)
        return ReferenceChainCursor(self._lmdb, db_chain, self._deserializer)

    def update(self, puts, deletes):
        """Applies the given puts and deletes atomically.

        Args:
            puts (:iterable:`tuple`): an iterable of key/value pairs to insert
            deletes (:iterable:str:) an iterable of keys to delete
        """
        with self._lmdb.begin(write=True, buffers=True) as txn:
            cursor = txn.cursor(self._main_db)
            # Process deletes first, to handle the case of new items replacing
            # old index locations
            for key in deletes:
                if not cursor.set_key(key.encode()):
                    # value doesn't exist
                    continue

                value = self._deserializer(bytes(cursor.value()))
                cursor.delete()

                for (index_db, index_key_fn) in self._indexes.values():
                    index_keys = index_key_fn(value)
                    index_cursor = txn.cursor(index_db)
                    for idx_key in index_keys:
                        if index_cursor.set_key(idx_key):
                            index_cursor.delete()

            # process all the inserts
            for key, value in puts:
                packed = self._serializer(value)

                cursor.put(key.encode(), packed, overwrite=True)

                for (index_db, index_key_fn) in self._indexes.values():
                    index_keys = index_key_fn(value)
                    index_cursor = txn.cursor(index_db)
                    for idx_key in index_keys:
                        index_cursor.put(idx_key, key.encode())

        self.sync()

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
        if index is not None and index not in self._indexes:
            raise ValueError('Index {} does not exist'.format(index))

        db = self._indexes[index][0] if index else self._main_db
        with self._lmdb.begin(db=db) as txn:
            return [
                key.decode()
                for key in txn.cursor().iternext(keys=True, values=False)
            ]


class ReferenceChainCursor(database.Cursor):
    """Cursor implementation that follows a chain of databases, where
    reference_chain is key_1 -> key_2 mappings with the final entry in the
    chain being key_n -> value.
    """

    def __init__(self, lmdb_env, reference_chain, deserializer):
        self._lmdb_env = lmdb_env
        self._deserializer = deserializer

        self._lmdb_txn = None

        if not reference_chain:
            raise ValueError(
                "Must be at least one lmdb database in the reference chain")

        self._reference_chain = reference_chain
        self._lmdb_cursors = []

    def open(self):
        self._lmdb_txn = self._lmdb_env.begin()

        self._lmdb_cursors = [self._lmdb_txn.cursor(db)
                              for db in self._reference_chain]

    def close(self):
        for curs in self._lmdb_cursors:
            curs.close()

        self._lmdb_cursors = []
        # Event though this is a read-only txn, abort it, just to be sure
        self._lmdb_txn.abort()

    def _seek_curs(self):
        return self._lmdb_cursors[0]

    def iter(self):
        return ReferenceChainCursor._wrap_iterator(
            self._lmdb_cursors[0].iternext(keys=False),
            self._lmdb_cursors[1:],
            self._deserializer)

    def iter_rev(self):
        return ReferenceChainCursor._wrap_iterator(
            self._lmdb_cursors[0].iterprev(keys=False),
            self._lmdb_cursors[1:],
            self._deserializer)

    def first(self):
        return self._seek_curs().first()

    def last(self):
        return self._seek_curs().last()

    def seek(self, key):
        return self._seek_curs().set_key(key.encode())

    def key(self):
        key = self._seek_curs().key()
        if key is not None:
            return key.decode()

        return None

    def value(self):
        value = self._seek_curs().value()
        if not value:
            return None

        return _read(
            value,
            self._lmdb_cursors[1:],
            self._deserializer)

    @staticmethod
    def _wrap_iterator(iterator, cursor_chain, deserializer):
        class _WrapperIter:
            def __iter__(self):
                return self

            def __next__(self):
                try:
                    return _read(
                        next(iterator),
                        cursor_chain,
                        deserializer)
                except lmdb.Error:
                    raise StopIteration()

        return _WrapperIter()


def _read(initial_key, cursor_chain, deserializer):
    key = initial_key
    packed = key
    for curs in cursor_chain:
        packed = curs.get(key)
        if not packed:
            raise IndexOutOfSyncError(
                'Index is out of date for key {}'.format(key))
        key = packed

    return deserializer(packed)

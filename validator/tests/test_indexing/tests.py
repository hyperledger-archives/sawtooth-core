# Copyright 2017 Intel Corporation
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
import shutil
import tempfile
import unittest
import struct

from sawtooth_validator.database.indexed_database import IndexedDatabase


class IndexedDatabaseTest(unittest.TestCase):
    def __init__(self, test_name):
        super().__init__(test_name)
        self._temp_dir = None

    def setUp(self):
        self._temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self._temp_dir)

    def test_count(self):
        """Test that a database with three records, plus an index will
        return the correct count of primary key/values, using `len`.
        """
        db = IndexedDatabase(
            os.path.join(self._temp_dir, 'test_db'),
            _serialize_tuple,
            _deserialize_tuple,
            indexes={'name': lambda tup: [tup[1].encode()]},
            flag='c',
            _size=1024**2)

        db.put('1', (1, "foo", "bar"))
        db.put('2', (2, "alice", "Alice's data"))
        db.put('3', (3, "bob", "Bob's data"))

        self.assertEqual(3, len(db))

        self.assertEqual(3, db.count())
        self.assertEqual(3, db.count(index="name"))

    def test_contains(self):
        """Given a database with three records and an index, test the
        following:
         - a primary key will return True for `contains_key` and `in`
         - a non-existent key will return False for both of those methods
         - an index key will return True for `contains_key`, using the index
        """
        db = IndexedDatabase(
            os.path.join(self._temp_dir, 'test_db'),
            _serialize_tuple,
            _deserialize_tuple,
            indexes={'name': lambda tup: [tup[1].encode()]},
            flag='c',
            _size=1024**2)

        db.put('1', (1, "foo", "bar"))
        db.put('2', (2, "alice", "Alice's data"))
        db.put('3', (3, "bob", "Bob's data"))

        self.assertTrue('1' in db)
        self.assertTrue(db.contains_key('1'))
        self.assertFalse('4' in db)
        self.assertFalse(db.contains_key('4'))

        self.assertTrue(db.contains_key('alice', index='name'))
        self.assertFalse(db.contains_key('charlie', index='name'))

    def test_get_multi(self):
        """Given a database with three records and an index, test that it can
        return multiple values from a set of keys.

        Show that:
         - it returns all existing values in the list
         - ignores keys that do not exist (i.e. no error is thrown)
         - it works with index keys in the same manor
        """
        db = IndexedDatabase(
            os.path.join(self._temp_dir, 'test_db'),
            _serialize_tuple,
            _deserialize_tuple,
            indexes={'name': lambda tup: [tup[1].encode()]},
            flag='c',
            _size=1024**2)

        db.put('1', (1, "foo", "bar"))
        db.put('2', (2, "alice", "Alice's data"))
        db.put('3', (3, "bob", "Bob's data"))

        # get multi via the primary key
        self.assertEqual([
            ('3', (3, "bob", "Bob's data")),
            ('2', (2, "alice", "Alice's data"))],
            db.get_multi(['3', '2']))

        # Ignore unknown primary keys
        self.assertEqual([
            ('3', (3, "bob", "Bob's data"))],
            db.get_multi(['3', '4']))

        # Get multi via an index
        self.assertEqual([
            ('1', (1, "foo", "bar")),
            ('3', (3, "bob", "Bob's data"))],
            db.get_multi(['foo', 'bob'], index='name'))

        # Ignore unknown index keys
        self.assertEqual([
            ('3', (3, "bob", "Bob's data"))],
            db.get_multi(['bar', 'bob'], index='name'))

    def test_indexing(self):
        """Test basic indexing around name
        """
        db = IndexedDatabase(
            os.path.join(self._temp_dir, 'test_db'),
            _serialize_tuple,
            _deserialize_tuple,
            indexes={'name': lambda tup: [tup[1].encode()]},
            flag='c',
            _size=1024**2)

        db.put('1', (1, "foo", "bar"))
        db.put('2', (2, "alice", "Alice's data"))
        db.put('3', (3, "bob", "Bob's data"))

        self.assertEqual((1, "foo", "bar"), db.get('1'))

        self.assertEqual(
            (2, "alice", "Alice's data"),
            db.get('alice', index='name'))

    def test_iteration(self):
        """Test iteration on over the items in a database, using the natural
        order of the primary keys.
        """
        db = IndexedDatabase(
            os.path.join(self._temp_dir, 'test_db'),
            _serialize_tuple,
            _deserialize_tuple,
            indexes={'name': lambda tup: [tup[1].encode()]},
            flag='c',
            _size=1024**2)

        db.put('1', (1, "foo", "bar"))
        db.put('2', (2, "alice", "Alice's data"))
        db.put('3', (3, "bob", "Bob's data"))

        with db.cursor() as curs:
            ordered_values = list(curs.iter())

        self.assertEqual(
            [(1, "foo", "bar"),
             (2, "alice", "Alice's data"),
             (3, "bob", "Bob's data")],
            ordered_values)

    def test_reverse_iteration(self):
        """Test reverse iteration over the items in a database, using the
        reverse natural order of the primary keys.
        """
        db = IndexedDatabase(os.path.join(self._temp_dir, 'test_db'),
                             _serialize_tuple, _deserialize_tuple,
                             indexes={
                                 'name': lambda tup: [tup[1].encode()]
        },
            flag='c',
            _size=1024**2)

        db.put('1', (1, "foo", "bar"))
        db.put('2', (2, "alice", "Alice's data"))
        db.put('3', (3, "bob", "Bob's data"))

        with db.cursor() as curs:
            ordered_values = list(curs.iter_rev())

        self.assertEqual(
            [(3, "bob", "Bob's data"),
             (2, "alice", "Alice's data"),
             (1, "foo", "bar")],
            ordered_values)

    def test_iteration_with_concurrent_mods(self):
        """Given a database with three items, and a cursor on the primary keys,
        test that a concurrent update will:
        - not change the results
        - not interrupt the iteration with an error
        """
        db = IndexedDatabase(
            os.path.join(self._temp_dir, 'test_db'),
            _serialize_tuple,
            _deserialize_tuple,
            indexes={'name': lambda tup: [tup[1].encode()]},
            flag='c',
            _size=1024**2)

        db.put('1', (1, "foo", "bar"))
        db.put('2', (2, "alice", "Alice's data"))
        db.put('3', (3, "bob", "Bob's data"))

        with db.cursor() as curs:
            iterator = curs.iter()

            self.assertEqual(1, next(iterator)[0])

            db.put('4', (4, 'charlie', "Charlie's data"))

            self.assertEqual(2, next(iterator)[0])
            self.assertEqual(3, next(iterator)[0])

            with self.assertRaises(StopIteration):
                next(iterator)

    def test_first(self):
        """Given a database with three items and a cursor on the primary keys,
        test that the cursor can be properly position to the first element in
        the natural order of the keys
        """
        db = IndexedDatabase(
            os.path.join(self._temp_dir, 'test_db'),
            _serialize_tuple,
            _deserialize_tuple,
            indexes={'name': lambda tup: [tup[1].encode()]},
            flag='c',
            _size=1024**2)

        db.put('1', (1, "alice", "Alice's data"))
        db.put('2', (2, "bob", "Bob's data"))
        db.put('3', (3, 'charlie', "Charlie's data"))

        with db.cursor() as curs:
            # Start from the end
            last = next(curs.iter_rev())
            # Read forward again
            iterator = curs.iter()
            forward = next(iterator)

            self.assertEqual(last, forward)

            # Check the iterator is exhausted from there
            with self.assertRaises(StopIteration):
                next(iterator)

            # reset to first element
            curs.first()
            new_iter = curs.iter()

            # verify that we'll see the first element again
            first = next(new_iter)
            self.assertEqual(1, first[0])

    def test_last(self):
        """Given a database with three items and a cursor on the primary keys,
        test that the cursor can be properly position to the last element in
        the natural order of the keys
        """
        db = IndexedDatabase(
            os.path.join(self._temp_dir, 'test_db'),
            _serialize_tuple,
            _deserialize_tuple,
            indexes={'name': lambda tup: [tup[1].encode()]},
            flag='c',
            _size=1024**2)

        db.put('1', (1, "alice", "Alice's data"))
        db.put('2', (2, "bob", "Bob's data"))
        db.put('3', (3, 'charlie', "Charlie's data"))

        with db.cursor() as curs:
            # Start from the beginning
            first = next(curs.iter())
            # Read backward again
            iterator = curs.iter_rev()
            backward = next(iterator)

            self.assertEqual(first, backward)

            # Check the iterator is exhausted from there
            with self.assertRaises(StopIteration):
                next(iterator)

            # reset to first element
            curs.last()
            new_iter = curs.iter_rev()

            # verify that we'll see the first element again
            last = next(new_iter)
            self.assertEqual(3, last[0])

    def test_seek(self):
        """Given a database with three items and a cursor on the primary keys,
        test that the cursor can be properly position to an arbitrary element
        in the natural order of the keys
        """
        db = IndexedDatabase(
            os.path.join(self._temp_dir, 'test_db'),
            _serialize_tuple,
            _deserialize_tuple,
            indexes={'name': lambda tup: [tup[1].encode()]},
            flag='c',
            _size=1024**2)

        db.put('1', (1, "alice", "Alice's data"))
        db.put('2', (2, "bob", "Bob's data"))
        db.put('3', (3, 'charlie', "Charlie's data"))

        with db.cursor() as curs:
            curs.seek('2')
            self.assertEqual(2, curs.value()[0])

            self.assertEqual('2', curs.key())

            iterator = curs.iter()
            self.assertEqual(2, next(iterator)[0])

    def test_index_empty_db(self):
        """Given an empty database, show that the cursor will return a value of
        None for the first position.
        """
        db = IndexedDatabase(
            os.path.join(self._temp_dir, 'test_db'),
            _serialize_tuple,
            _deserialize_tuple,
            indexes={'name': lambda tup: [tup[1].encode()]},
            flag='c',
            _size=1024**2)

        with db.cursor(index='name') as curs:
            curs.first()
            self.assertIsNone(curs.value())

        with db.cursor() as curs:
            curs.first()
            self.assertIsNone(curs.value())

    def test_index_iteration(self):
        """Test iteration over the items in a database, using the natural order
        of the index keys.
        """
        db = IndexedDatabase(
            os.path.join(self._temp_dir, 'test_db'),
            _serialize_tuple,
            _deserialize_tuple,
            indexes={'name': lambda tup: [tup[1].encode()]},
            flag='c',
            _size=1024**2)

        db.put('1', (1, "foo", "bar"))
        db.put('2', (2, "alice", "Alice's data"))
        db.put('3', (3, "bob", "Bob's data"))

        with db.cursor(index='name') as curs:
            ordered_values = list(curs.iter())

        self.assertEqual(
            [(2, "alice", "Alice's data"),
             (3, "bob", "Bob's data"),
             (1, "foo", "bar")],
            ordered_values)

    def test_index_reverse_iteration(self):
        """Test reverse iteration over the items in a database, using the
        reverse natural order of the index keys.
        """
        db = IndexedDatabase(
            os.path.join(self._temp_dir, 'test_db'),
            _serialize_tuple,
            _deserialize_tuple,
            indexes={'name': lambda tup: [tup[1].encode()]},
            flag='c',
            _size=1024**2)

        db.put('1', (1, "foo", "bar"))
        db.put('2', (2, "alice", "Alice's data"))
        db.put('3', (3, "bob", "Bob's data"))

        with db.cursor(index='name') as curs:
            ordered_values = list(curs.iter_rev())

        self.assertEqual(
            [(1, "foo", "bar"),
             (3, "bob", "Bob's data"),
             (2, "alice", "Alice's data")],
            ordered_values)

    def test_index_iteration_with_concurrent_mods(self):
        """Given a database with three items, and a cursor on the index keys,
        test that a concurrent update will:
        - not change the results
        - not interrupt the iteration with an error
        """
        db = IndexedDatabase(
            os.path.join(self._temp_dir, 'test_db'),
            _serialize_tuple,
            _deserialize_tuple,
            indexes={'name': lambda tup: [tup[1].encode()]},
            flag='c',
            _size=1024**2)

        db.put('1', (1, "foo", "bar"))
        db.put('2', (2, "alice", "Alice's data"))
        db.put('3', (3, "bob", "Bob's data"))

        with db.cursor(index='name') as curs:
            iterator = curs.iter()

            self.assertEqual(2, next(iterator)[0])

            db.put('4', (4, 'charlie', "Charlie's data"))

            self.assertEqual(3, next(iterator)[0])
            self.assertEqual(1, next(iterator)[0])

            with self.assertRaises(StopIteration):
                next(iterator)

    def test_integer_indexing(self):
        """Test that a database can be indexed using integer keys.
        """
        int_index_config = {
            'key_fn': lambda tup: [struct.pack('I', tup[0])],
            'integerkey': True
        }
        db = IndexedDatabase(
            os.path.join(self._temp_dir, 'test_db'),
            _serialize_tuple,
            _deserialize_tuple,
            indexes={'age': int_index_config},
            flag='c',
            _size=1024**2)

        db.put('1', (1, "foo", "bar"))
        db.put('2', (30, "alice", "Alice's data"))
        db.put('3', (20, "bob", "Bob's data"))
        db.put('4', (12, "charlie", "Charlie's data"))

        self.assertEqual(
            [1, 12, 20, 30],
            [struct.unpack('I', k.encode())[0] for k in db.keys(index='age')])
        with db.cursor(index='age') as curs:
            self.assertEqual([
                (1, "foo", "bar"),
                (12, "charlie", "Charlie's data"),
                (20, "bob", "Bob's data"),
                (30, "alice", "Alice's data")],
                list(curs.iter()))

    def test_hex_ordered_indexing(self):
        """Test that an index that uses hex-encoded keys will properly order
        the keys (i.e. the natural order of the keys is in numerical order).
        """

        def to_hex(num):
            return "{0:#0{1}x}".format(num, 18)

        def age_index_key_fn(tup):
            return [to_hex(tup[0]).encode()]

        db = IndexedDatabase(
            os.path.join(self._temp_dir, 'test_db'),
            _serialize_tuple,
            _deserialize_tuple,
            indexes={'age': age_index_key_fn},
            flag='c',
            _size=1024**2)

        entry_count = 100
        for i in range(1, entry_count):
            db.put(str(entry_count - i), (i, "foo" + str(i), "data"))

        self.assertEqual(
            [to_hex(i) for i in range(1, entry_count)],
            list(db.keys(index='age')))

    def test_delete(self):
        """Test that items are deleted, including their index references.
        """
        db = IndexedDatabase(
            os.path.join(self._temp_dir, 'test_db'),
            _serialize_tuple,
            _deserialize_tuple,
            indexes={'name': lambda tup: [tup[1].encode()]},
            flag='c',
            _size=1024**2)

        db.put('1', (1, "foo", "bar"))
        db.put('2', (2, "alice", "Alice's data"))
        db.put('3', (3, "bob", "Bob's data"))

        with db.cursor(index='name') as curs:
            ordered_values = list(curs.iter())

        self.assertEqual(
            [(2, "alice", "Alice's data"),
             (3, "bob", "Bob's data"),
             (1, "foo", "bar")],
            ordered_values)

        db.delete('3')

        with db.cursor(index='name') as curs:
            ordered_values = list(curs.iter())

        self.assertEqual(
            [(2, "alice", "Alice's data"),
             (1, "foo", "bar")],
            ordered_values)

    def test_update(self):
        """Test that a database will commit both inserts and deletes using the
        update method.
        """
        db = IndexedDatabase(
            os.path.join(self._temp_dir, 'test_db'),
            _serialize_tuple,
            _deserialize_tuple,
            indexes={'name': lambda tup: [tup[1].encode()]},
            flag='c',
            _size=1024**2)

        db.put('1', (1, "foo", "bar"))
        db.put('2', (2, "alice", "Alice's data"))
        db.put('3', (3, "bob", "Bob's data"))

        db.update([('4', (4, 'charlie', "Charlie's data"))], ['1'])

        self.assertEqual(['2', '3', '4'], db.keys())

    def test_update_replace_index(self):
        """Test that update will properly update insert records that have
        the same index value of a deleted record.
        - insert items should be added
        - inserted items index should be correct
        - deleted items should be removed
        """
        db = IndexedDatabase(
            os.path.join(self._temp_dir, 'test_db'),
            _serialize_tuple,
            _deserialize_tuple,
            indexes={'name': lambda tup: [tup[1].encode()]},
            flag='c',
            _size=1024**2)
        db.put('1', (1, "foo", "bar"))
        db.put('2', (2, "alice", "Alice's data"))
        db.put('3', (3, "bob", "Bob's data"))

        db.update([('4', (4, 'foo', "foo's data"))], ['1'])

        self.assertEqual(['2', '3', '4'], db.keys())
        self.assertEqual(
            (4, 'foo', "foo's data"),
            db.get('foo', index='name'))


def _serialize_tuple(tup):
    return "{}-{}-{}".format(*tup).encode()


def _deserialize_tuple(bytestring):
    (rec_id, name, data) = tuple(bytestring.decode().split('-'))
    return (int(rec_id), name, data)

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

from __future__ import print_function

import unittest

from random import choice
import string
import time

from journal.object_store import ObjectStore, MalformedIndexError, \
    UniqueConstraintError


class TestSawtoothObjectStore(unittest.TestCase):

    def setUp(self):
        self.number_of_items = 12000
        self.index1s = ["".join([str(choice(string.digits))
                                 for _ in xrange(12)])
                        for _ in xrange(self.number_of_items)]
        self.index2s = ["".join([str(choice(string.digits))
                                 for _ in xrange(12)])
                        for _ in xrange(self.number_of_items)]
        self.names = ["obj{}".format(i)
                      for i in xrange(self.number_of_items)]
        self.values = [{'object-type': 'type1', 'index1': index1,
                        'index2': index2,
                        'name': name}
                       for index1, index2, name in zip(self.index1s,
                                                       self.index2s,
                                                       self.names)]

        self.startTime = time.time()

    def tearDown(self):
        print("%s: %.3f" % (self.id(), time.time() - self.startTime))

    def _test_set_and_lookup(self, store):
        for n, val in zip(self.names, self.values):
            store.set(key=n, value=val)
        for idx in xrange(self.number_of_items):
            self.assertEqual(store.lookup('type1:index1', self.index1s[idx]),
                             self.values[idx],
                             "Lookup by index1, gives same value as "
                             "was set: index {}".format(idx))
        for idx in xrange(self.number_of_items):
            self.assertEqual(store.lookup('type1:index2', self.index2s[idx]),
                             self.values[idx],
                             "Lookup by index2, gives same value as "
                             "was set: index {}".format(idx))

    def test_default_store(self):
        obj_store = ObjectStore()

        self._test_set_and_lookup(obj_store)

    def test_store_with_indexes(self):
        obj_store = ObjectStore(indexes=['type1:index1', 'type1:index2'])

        self._test_set_and_lookup(obj_store)

    def test_store_with_partial_indexes(self):
        obj_store = ObjectStore(indexes=['type1:index1'])

        self._test_set_and_lookup(obj_store)

    def test_get_with_previous_store(self):
        obj_store = ObjectStore(indexes=['type1:index1', 'type1:index2'])
        self._test_set_and_lookup(obj_store)
        new_obj_store = ObjectStore(prevstore=obj_store)

        self.assertEqual(new_obj_store.get(self.names[765]),
                         self.values[765], "Get from previous store")

    def test_delete(self):
        obj_store = ObjectStore(indexes=['type1:index1', 'type1:index2'])
        self._test_set_and_lookup(obj_store)

        def lookup_key_that_is_missing(*args, **kwargs):
            store = args[0]
            store.lookup('type1:index2', self.index2s[544])

        for n in self.names:
            obj_store.delete(n)

        self.assertRaises(KeyError, lookup_key_that_is_missing, obj_store,
                          "Lookup of attribute from key that has "
                          "been deleted throws an error")

    def test_index_error_handling(self):
        malformed_index = 'index1'

        def lookup_by_malformed_index(*args, **kwargs):
            store = args[0]
            store.lookup(malformed_index, self.index1s[225])

        obj_store = ObjectStore()
        self._test_set_and_lookup(obj_store)

        self.assertRaises(MalformedIndexError, lookup_by_malformed_index,
                          obj_store,
                          "Lookup by malformed index throws an exception")

        def malformed_index_in_init(*args, **kwargs):
            objectstore = ObjectStore(indexes=[malformed_index])

        self.assertRaises(MalformedIndexError, malformed_index_in_init,
                          msg="The constructor checks for malformed indexes")

    def test_unique_constraint(self):
        obj1 = {'index1': '12345', 'index2': self.index2s[114],
                'object-type': 'type1'}
        obj2 = {'index1': '12345', 'index2': self.index2s[125],
                'object-type': 'type1'}

        obj_store = ObjectStore(indexes=['type1:index1', 'type1:index2'])
        obj_store.set('obj1', obj1)

        def set_a_value_with_not_unique_key(*args, **kwargs):
            store = args[0]
            store.set('obj2', obj2)

        self.assertRaises(UniqueConstraintError,
                          set_a_value_with_not_unique_key,
                          obj_store,
                          "Setting a value with nonunique indexed "
                          "key raises an error")

    def test_dup_key_late_indexing(self):
        """
        ._build_index will index the first set value with that key

        """
        obj1 = {'index1': '12345', 'index2': self.index2s[114],
                'object-type': 'type1'}

        obj_store = ObjectStore()
        obj_store.set('obj1', obj1)
        for val in self.values:
            val['index1'] = '12345'
            obj_store.set('obj2', val)

        self.assertEqual(obj_store.lookup('type1:index1', '12345'),
                         obj1, "Lookup by non-unique late-indexed"
                         "value will get the first one set")

    def test_update(self):
        obj1 = {'object-type': 'type1', 'index1': self.index1s[126],
                'index2': self.index2s[126], 'count': 5}
        obj2 = {'object-type': 'type1', 'index1': self.index1s[126],
                'index2': self.index2s[126], 'count': 8}
        obj_store = ObjectStore(indexes=['type1:index1', 'type1:index2'])
        obj_store.set('obj1', obj1)
        obj_store.set('obj1', obj2)
        self.assertEqual(obj_store.lookup('type1:index1', self.index1s[126]),
                         obj2, "Lookup on index of updated value will find"
                         "updated value")
        self.assertEqual(obj_store.get('obj1'), obj2,
                         ".get will also get us the updated value")

    def test_late_indexing_update(self):
        obj1 = {'object-type': 'type1', 'index1': self.index1s[126],
                'index2': self.index2s[126], 'name': 'obj1'}

        obj2 = {'object-type': 'type1', 'index1': self.index1s[126],
                'index2': self.index2s[126], 'name': 'obj1'}
        obj_store = ObjectStore()
        obj_store.set('obj1', obj1)
        obj_store.set('obj1', obj2)
        self.assertEqual(obj_store.lookup('type1:index2', self.index2s[126]),
                         obj2, "Late indexing will provide us with the "
                         "updated value")
        self.assertEqual(obj_store.get('obj1'), obj2,
                         ".get will also get us the updated value")

    def test_erroring_on_update(self):
        obj2 = {'object-type': 'type1', 'index1': self.index1s[126],
                'index2': self.index2s[266], 'name': self.names[126]}
        obj_store = ObjectStore()
        self._test_set_and_lookup(obj_store)

        def changed_an_index_value_to_another_stores_field(*args):
            store = args[0]
            store.set(self.names[126], obj2)

        self.assertRaises(UniqueConstraintError,
                          changed_an_index_value_to_another_stores_field,
                          obj_store,
                          "If you update a value and one of the fields "
                          "belongs to another object the "
                          "Store will error")

    def test_will_update_on_index(self):
        obj_store = ObjectStore(indexes=['type1:index1', 'type1:index2'])
        self._test_set_and_lookup(obj_store)
        obj = self.values[277]
        obj['index1'] = '123456789'
        # Can change an indexed value if it is unique
        obj_store.set(self.names[277], obj)
        self.assertEqual(obj_store.lookup('type1:index1', '123456789'),
                         obj, "Can lookup on indexed value that has"
                         " been updated.")


class TestHeterogeneousStore(unittest.TestCase):
    def setUp(self):
        self.number_of_objects = 12000
        self.index1s = ["".join([str(choice(string.digits))
                                 for _ in xrange(12)])
                        for _ in xrange(self.number_of_objects)]
        self.index2s = ["".join([str(choice(string.digits))
                                 for _ in xrange(12)])
                        for _ in xrange(self.number_of_objects)]
        self.obj_type1_values = [{'object-type': 'type1', 'index1': index1,
                                 'index2': index2}
                                 for index1, index2 in
                                 zip(self.index1s, self.index2s)]
        self.obj_type1_names = ["obj1-{}".format(i)
                                for i in xrange(self.number_of_objects)]

        self.obj_type2_values = [{'object-type': 'type2',
                                 'index1': index1, 'index2': index2,
                                  'nonindex1': 90, 'nonindex2': 87}
                                 for index1, index2 in
                                 zip(self.index1s, self.index2s)]
        self.obj_type2_names = ["obj2-{}".format(i)
                                for i in xrange(self.number_of_objects)]

        self.startTime = time.time()

    def tearDown(self):
        print("%s: %.3f" % (self.id(), time.time() - self.startTime))

    def _test_lookup_by_all(self, objectstore):
        for name, val in zip(self.obj_type1_names, self.obj_type1_values):
            objectstore.set(name, val)

        for name, val in zip(self.obj_type2_names, self.obj_type2_values):
            objectstore.set(name, val)

        for idx, index1 in enumerate(self.index1s):
            self.assertEqual(objectstore.lookup('type1:index1', index1),
                             self.obj_type1_values[idx],
                             "Can lookup by type1:index1.")
            self.assertEqual(objectstore.lookup('type2:index1', index1),
                             self.obj_type2_values[idx],
                             "Can lookup by type2:index1")
        for idx, index2 in enumerate(self.index2s):
            self.assertEqual(objectstore.lookup('type1:index2', index2),
                             self.obj_type1_values[idx],
                             "Can lookup by type1:index2.")
            self.assertEqual(objectstore.lookup('type2:index2', index2),
                             self.obj_type2_values[idx],
                             "Can lookup by type2:index2")

    def test_all_specified(self):
        objectstore = ObjectStore(indexes=['type1:index1', 'type1:index2',
                                           'type2:index1', 'type2:index2'])
        self._test_lookup_by_all(objectstore)

    def test_late_indexing(self):
        objectstore = ObjectStore()

        self._test_lookup_by_all(objectstore)

    def test_heterogeneous_delete(self):
        objectstore = ObjectStore()

        self._test_lookup_by_all(objectstore)

        objectstore.delete(self.obj_type2_names[255])
        for i2, val in zip(self.index2s, self.obj_type1_values):
            self.assertEqual(objectstore.lookup('type1:index2', i2),
                             val, "After type2 deletion, "
                                  "can still lookup by type1:index2")
        for i1, val in zip(self.index1s, self.obj_type1_values):
            self.assertEqual(objectstore.lookup('type1:index1', i1),
                             val, "After type2 deletion, "
                                  "can still lookup by type1:index1")

        def lookup_by_index1_from_deleted(*args):
            store = args[0]
            store.lookup('type2:index1', self.index1s[255])

        self.assertRaises(KeyError, lookup_by_index1_from_deleted, objectstore,
                          "Lookup by type2:index1 on deleted raises an error")
        del self.obj_type2_values[255]
        del self.index2s[255]
        del self.index1s[255]
        for i, val in zip(self.index1s, self.obj_type2_values):
            self.assertEqual(objectstore.lookup('type2:index1', i),
                             val, "Can look up any other type2:index1")

        for c, val in zip(self.index2s, self.obj_type2_values):
            self.assertEqual(objectstore.lookup('type2:index2', c),
                             val, "Can look up any other type2:index2")

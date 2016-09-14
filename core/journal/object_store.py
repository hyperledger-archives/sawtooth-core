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
import copy

from journal import global_store_manager


LOGGER = logging.getLogger(__name__)


class MalformedIndexError(Exception):
    pass


class UniqueConstraintError(Exception):
    pass


class ObjectStore(global_store_manager.KeyValueStore):
    def __init__(self, prevstore=None, storeinfo=None, readonly=False,
                 indexes=None, clone_indexes=None):
        super(ObjectStore, self).__init__(
            prevstore, storeinfo, readonly)

        if clone_indexes is not None:
            self._indexes = copy.deepcopy(clone_indexes)
        else:
            self._indexes = {}
            if indexes is not None:
                for key in indexes:
                    self._parse_and_check_index(key)
                    self._indexes[key] = {}

    def _build_index(self, index):
        self._indexes[index] = {}
        object_type, attribute = self._parse_and_check_index(index)
        for _, object_info in self.iteritems():
            if attribute in object_info and \
                    object_info[attribute] not in self._indexes[index] \
                    and object_type == object_info['object-type']:
                self._indexes[index][object_info[attribute]] = object_info

    @staticmethod
    def _object_type_check(obj, object_type, key):
        if obj is None:
            raise KeyError("no such object", key)
        if object_type is not None and obj['object-type'] != object_type:
            raise KeyError("mismatch object type {} != {}".format(
                obj['object-type'], object_type), key)
        return obj

    def _parse_and_check_index(self, index):
        args = index.split(":")
        if len(args) != 2:
            raise MalformedIndexError(
                "The index, {}, is not correctly formed".format(index))
        return args

    def clone_store(self, storeinfo=None, readonly=False):
        """Creates a new checkpoint that can be modified.

        Args:
            storeinfo (dict): Information about the store to clone.

        Returns:
            ObjectStore: A new checkpoint that extends the current
                store.
        """
        return ObjectStore(self, storeinfo, readonly,
                           clone_indexes=self._indexes)

    def lookup(self, index, key):
        """

        Args:
            index: (str) the object type and attribute index
                          concatted e.g. 'bond:cusip'
            key: the attribute value that is being searched for
                 e.g. 'US00206RDA77'

        Returns: the value object that was set that contains
                 the key

        """
        object_type = self._parse_and_check_index(index)[0]

        if index not in self._indexes:
            self._build_index(index)
        obj = self._indexes[index].get(key)

        ObjectStore._object_type_check(obj, object_type, key)
        return obj

    def get(self, key, object_type=None):
        # pylint: disable=arguments-differ
        obj = super(ObjectStore, self).get(key)
        ObjectStore._object_type_check(obj, object_type, key)
        return obj

    def iteritems_by_object_type(self, object_type):
        """
            Return an iterator that can be used to iterate through object
            info dictionaries for objects of the type provided.

        Args:
            object_type: (str) The object type, for example "bond",
                            that will be compared against an object info
                            dictionary's 'object-type' key.

        Returns:
            An iterator
        """
        for key, object_info in self.iteritems():
            if object_info['object-type'] == object_type:
                yield key, object_info

    def get_all_by_object_type(self, object_type):
        """
            Returns of object info dictionaries whose 'object-type' field
            matches object_type.

        Args:
            object_type: (str) The object type, for example "bond",
                            that will be compared against an object's
                            'object-type' field.

        Returns:
            A list of object info dictionaryies of the object type given
        """
        return \
            [object_info for _, object_info
             in self.iteritems_by_object_type(object_type)]

    def set(self, key, value):
        ObjectStore._object_type_check(value, None, key)
        object_type = value['object-type']
        old_object = None
        try:
            old_object = super(ObjectStore, self).get(key)
        except KeyError:
            pass

        if old_object is None:
            # error out early if any index would be violated
            for att in value.keys():
                index = object_type + ":" + att
                if index in self._indexes and \
                        value[att] in self._indexes[index]:
                    raise UniqueConstraintError(
                        "value for {} already used in "
                        "unique index {}: {}".format(
                            att, index, value[att]
                        ))

            super(ObjectStore, self).set(key, value)

            for att in value.keys():
                index = object_type + ":" + att
                if index in self._indexes:
                    self._indexes[index][value[att]] = value
        else:
            # on update make sure the new object isn't of a different type
            ObjectStore._object_type_check(value,
                                           old_object['object-type'], key)
            # error early if an indexed value is changed to another
            # value's attribute
            for att in old_object.iterkeys():
                index = object_type + ":" + att
                if index in self._indexes \
                        and old_object[att] != value[att] \
                        and value[att] in self._indexes[index] \
                        and self._indexes[index][value[att]] != old_object:
                    raise UniqueConstraintError("Value for {} already used "
                                                "in unique index {}: {}".
                                                format(att, index,
                                                       value[att]))
            for att in old_object.iterkeys():
                index = object_type + ":" + att
                if index in self._indexes:
                    self._indexes[index][value[att]] = value

            super(ObjectStore, self).set(key, value)

    def delete(self, key, object_type=None):
        # pylint: disable=arguments-differ
        obj = self.get(key, object_type=object_type)
        super(ObjectStore, self).delete(key)
        for attribute in obj.keys():
            if object_type is None:
                index = obj['object-type'] + ":" + attribute
            else:
                index = object_type + ":" + attribute
            if index in self._indexes:
                del self._indexes[index][obj[attribute]]

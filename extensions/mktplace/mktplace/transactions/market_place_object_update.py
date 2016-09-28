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
from journal import transaction
from sawtooth.exceptions import InvalidTransactionError
logger = logging.getLogger(__name__)


class MarketPlaceObject(object):
    @classmethod
    def get_valid_object(cls, store, objectid, objecttypes=None):
        if not objecttypes:
            objecttypes = [cls.ObjectTypeName]

        if objectid not in store:
            logger.info('object %s of type %s not registered', objectid,
                        objecttypes)
            return None

        mpobj = store[objectid]
        mptype = mpobj.get('object-type', '**UNKNOWN**')

        if mptype not in objecttypes:
            logger.info('invalid object type, expected one of %s, got %s',
                        objecttypes, mptype)
            return None

        return mpobj

    @classmethod
    def is_valid_object(cls, store, objectid):
        obj = cls.get_valid_object(store, objectid)
        if not obj:
            return False

        return True

    @classmethod
    def load_from_store(cls, store, objectid):
        obj = cls.get_valid_object(store, objectid, cls.ObjectTypeName)
        if not obj:
            return None

        return cls(objectid, obj)

    def __init__(self, objectid=None, minfo=None):
        if minfo is None:
            minfo = {}
        self.ObjectID = objectid

    def dump(self):
        result = {'object-type': self.ObjectTypeName,
                  'object-id': self.ObjectID}
        if hasattr(self, 'CreatorID') and hasattr(self, 'Name'):
            if self.Name.startswith('//'):
                if "/" in self.Name[2:]:
                    path = "/".join(self.Name[2:].split('/')[1:])
                    result['full-name'] = "{}/{}".format(self.CreatorID, path)
                else:
                    result['full-name'] = self.Name
            else:
                result['full-name'] = "{}{}".format(self.CreatorID, self.Name)
        elif hasattr(self, 'Name') and not hasattr(self, 'CreatorID'):
            result['full-name'] = "//{}".format(self.Name)
        return result


def global_is_valid_name(store, name, object_type, creator_id):
    """
    Ensure that the name property meets syntactic requirements.
    """

    if name == '':
        return True
    if not name.startswith('/'):
        logger.debug('invalid name %s; must start with /', name)
        return False

    if len(name) >= 64:
        logger.debug(
            'invalid name %s; must be less than 64 bytes', name)
        return False

    if not name.startswith('//'):
        name = "{0}{1}".format(creator_id, name)
    else:
        name = name

    if store.n2i(name, object_type.ObjectTypeName):
        logger.debug(
            'invalid name %s; name must be unique', name)
        return False
    return True


def global_is_permitted(store, txn, creator_id, creator_type):
    """
    Global permission check, for now only verifies that the creator id
    corresponds to the originator of the transaction.
    """
    if not creator_type.is_valid_creator(store, creator_id,
                                         txn.OriginatorID):
        return False

    return True


class UpdateDescription(transaction.Update):

    def __init__(self, update_type, creator_id, description, object_id):
        super(UpdateDescription, self).__init__(update_type)
        self._object_id = object_id
        self._creator_id = creator_id
        self._description = description

    @property
    def References(self):
        return [self.ObjectID, self._creator_id]

    def check_valid(self, store, txn):
        logger.debug('market update: %s', str(self))

        assert txn.OriginatorID
        assert txn.Identifier
        assert self._creator_id

        if not self.ObjectType.IsValidObject(store, txn.Identifier):
            raise InvalidTransactionError(
                "ObjectId does not reference a valid object")

        if not self.CreatorType.IsValidCreator(store, self._creator_id,
                                               txn.OriginatorID):
            raise InvalidTransactionError(
                "Creator Address not the same as txn.OriginatorId")

        if len(self._description) > 255:
            logger.debug('description must be less than 255 bytes')
            raise InvalidTransactionError(
                "Description is longer than 255 characters")

    def apply(self, store, txn):
        obj = store[txn.Identifier]
        obj['description'] = self._description
        store[txn.Identifier] = obj


class UpdateName(transaction.Update):

    def __init__(self,
                 update_type,
                 object_id,
                 creator_id,
                 name):
        super(UpdateName, self).__init__(update_type)
        self._object_id = object_id
        self._creator_id = creator_id
        self._name = name

    @property
    def References(self):
        return [self._object_id, self._creator_id]

    def is_valid_name(self, store):
        """
        Ensure that the name property meets syntactic requirements. Objects
        can override this method for object specific syntax. This method
        simply requires that a name begins with a '/', has a total length
        less than 64 characters, and is not the same as an already-existing
        object.
        """

        if self._name == '':
            return True

        if not self._name.startswith('/'):
            logger.debug('invalid name %s; must start with /', self._name)
            return False

        if len(self._name) >= 64:
            logger.debug('invalid name %s; must be less than 64 bytes',
                         self._name)
            return False

        if not self._name.startswith('//'):
            name = "{0}{1}".format(store.i2n(self._creator_id), self._name)
        else:
            name = self._name

        if store.n2i(name, self.ObjectType.ObjectTypeName):
            logger.debug('invalid name %s; name must be unique', self._name)
            return False

        return True

    def check_valid(self, store, txn):
        logger.debug('market update: %s', str(self))

        assert txn.OriginatorID
        assert self._object_id
        assert self._creator_id

        if not self.ObjectType.is_valid_object(store, self._object_id):
            raise InvalidTransactionError(
                "ObjectId does not reference a valid object")

        if not self.is_valid_name(store):
            raise InvalidTransactionError(
                "Name isn't valid")

        if not self.is_permitted(store, txn):
            raise InvalidTransactionError(
                "Creator address not the same as txn.OriginatorID")

    def is_permitted(self, store, txn):
        if not self.CreatorType.is_valid_creator(
                store, self._creator_id, txn.OriginatorID):
            return False

        return True

    def apply(self, store, txn):
        # remove the existing name

        obj = store[self._object_id]
        del store[self._object_id]
        obj['name'] = self._name
        store[self._object_id] = obj

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
from journal.transaction import SerializationError

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
        result = {'object-type': self.ObjectTypeName}
        return result


class Register(object):
    UpdateType = '/mktplace.transactions.MarketPlaceObjectUpdate/Register'

    def __init__(self, transaction=None, minfo=None):
        if minfo is None:
            minfo = {}
        self.Transaction = transaction

    def __str__(self):
        return "({0}, {1}, {2})".format(self.UpdateType, self.OriginatorID,
                                        self.ObjectID)

    @property
    def references(self):
        return []

    @property
    def OriginatorID(self):
        assert self.Transaction
        return self.Transaction.OriginatorID

    @property
    def ObjectID(self):
        assert self.Transaction
        return self.Transaction.Identifier

    def is_valid_name(self, store):
        """
        Ensure that the name property meets syntactic requirements. Objects
        can override this method for object specific syntax. This method
        simply requires that a name begins with a '/', has a total length
        less than 64 characters, and is not the same as an already-existing
        object.
        """

        if self.Name == '':
            return True
        if not self.Name.startswith('/'):
            logger.debug('invalid name %s; must start with /', self.Name)
            return False

        if len(self.Name) >= 64:
            logger.debug(
                'invalid name %s; must be less than 64 bytes', self.Name)
            return False

        if not self.Name.startswith('//'):
            name = "{0}{1}".format(store.i2n(self.CreatorID), self.Name)
        else:
            name = self.Name

        if store.n2i(name):
            logger.debug(
                'invalid name %s; name must be unique', self.Name)
            return False

        return True

    def is_valid(self, store):
        logger.debug('market update: %s', str(self))

        if self.ObjectID in store:
            logger.info('duplicate registration for object %s', self.ObjectID)
            return False

        if not self.is_valid_name(store):
            return False

        return True

    def is_permitted(self, store):
        """
        Global permission check, for now only verifies that the creator id
        corresponds to the originator of the transaction.
        """
        if not self.CreatorType.is_valid_creator(store, self.CreatorID,
                                                 self.OriginatorID):
            return False

        return True

    def apply(self, store):
        pass

    def dump(self):
        result = {'UpdateType': self.UpdateType}
        return result


class Unregister(object):
    UpdateType = '/mktplace.transactions.MarketPlaceObjectUpdate/Unregister'

    def __init__(self, transaction=None, minfo=None):
        if minfo is None:
            minfo = {}
        self.Transaction = transaction

        self.ObjectID = minfo.get('ObjectID')
        self.CreatorID = minfo.get('CreatorID')

    def __str__(self):
        return "({0}, {1}, {2})".format(self.UpdateType, self.OriginatorID,
                                        self.ObjectID)

    @property
    def References(self):
        return []

    @property
    def OriginatorID(self):
        assert self.Transaction
        return self.Transaction.OriginatorID

    def is_valid(self, store):
        logger.debug('market update: %s', str(self))

        assert self.OriginatorID
        assert self.ObjectID
        assert self.CreatorID

        if not self.ObjectType.is_valid_object(store, self.ObjectID):
            return False

        return True

    def is_permitted(self, store):
        if not self.CreatorType.is_valid_creator(store, self.CreatorID,
                                                 self.OriginatorID):
            return False

        return True

    def apply(self, store):
        del store[self.ObjectID]

    def dump(self):
        assert self.ObjectID
        assert self.CreatorID
        result = {
            'UpdateType': self.UpdateType,
            'ObjectID': self.ObjectID,
            'CreatorID': self.CreatorID
        }
        return result


class UpdateDescription(object):
    UpdateType = '/mktplace.transactions.MarketPlaceObjectUpdate' \
                 '/UpdateDescription'

    def __init__(self, transaction=None, minfo=None):
        if minfo is None:
            minfo = {}
        self.Transaction = transaction

        self.ObjectID = None
        self.CreatorID = None
        self.Description = ''

        if minfo:
            self._unpack(minfo)

    def _unpack(self, minfo):
        try:
            self.ObjectID = minfo['ObjectID']
            self.CreatorID = minfo['CreatorID']
            self.Description = minfo['Description']

        except KeyError as ke:
            logger.warn('missing required field for %s transaction; %s',
                        self.UpdateType, ke)
            raise SerializationError(
                self.UpdateType, 'missing required field {0}'.format(ke))

    def __str__(self):
        return "({0}, {1}, {2})".format(
            self.UpdateType, self.OriginatorID, self.ObjectID)

    @property
    def References(self):
        return [self.ObjectID, self.CreatorID]

    @property
    def OriginatorID(self):
        assert self.Transaction
        return self.Transaction.OriginatorID

    def is_valid(self, store):
        logger.debug('market update: %s', str(self))

        assert self.OriginatorID
        assert self.ObjectID
        assert self.CreatorID

        if not self.ObjectType.IsValidObject(store, self.ObjectID):
            return False

        if not self.CreatorType.IsValidCreator(store, self.CreatorID,
                                               self.OriginatorID):
            return False

        if len(self.Description) > 255:
            logger.debug('description must be less than 255 bytes')
            return False

        return True

    def apply(self, store):
        obj = store[self.ObjectID]
        obj['description'] = self.Description
        store[self.ObjectID] = obj

    def dump(self):
        assert self.ObjectID
        assert self.CreatorID
        result = {
            'UpdateType': self.UpdateType,
            'ObjectID': self.ObjectID,
            'CreatorID': self.CreatorID,
            'Description': self.Description
        }
        return result


class UpdateName(object):
    UpdateType = '/mktplace.transactions.MarketPlaceObjectUpdate/UpdateName'

    def __init__(self, transaction=None, minfo=None):
        if minfo is None:
            minfo = {}
        self.Transaction = transaction

        self.ObjectID = None
        self.CreatorID = None
        self.Name = ''

        if minfo:
            self._unpack(minfo)

    def _unpack(self, minfo):
        try:
            self.ObjectID = minfo['ObjectID']
            self.CreatorID = minfo['CreatorID']
            self.Name = minfo['Name']

        except KeyError as ke:
            logger.warn('missing required field for %s transaction; %s',
                        self.UpdateType, ke)
            raise SerializationError(
                self.UpdateType, 'missing required field {0}'.format(ke))

    def __str__(self):
        return "({0}, {1}, {2})".format(
            self.UpdateType, self.OriginatorID, self.ObjectID)

    @property
    def References(self):
        return [self.ObjectID, self.CreatorID]

    @property
    def OriginatorID(self):
        assert self.Transaction
        return self.Transaction.OriginatorID

    def is_valid_name(self, store):
        """
        Ensure that the name property meets syntactic requirements. Objects
        can override this method for object specific syntax. This method
        simply requires that a name begins with a '/', has a total length
        less than 64 characters, and is not the same as an already-existing
        object.
        """

        if self.Name == '':
            return True

        if not self.Name.startswith('/'):
            logger.debug('invalid name %s; must start with /', self.Name)
            return False

        if len(self.Name) >= 64:
            logger.debug('invalid name %s; must be less than 64 bytes',
                         self.Name)
            return False

        if not self.Name.startswith('//'):
            name = "{0}{1}".format(store.i2n(self.CreatorID), self.Name)
        else:
            name = self.Name

        if store.n2i(name):
            logger.debug('invalid name %s; name must be unique', self.Name)
            return False

        return True

    def is_valid(self, store):
        logger.debug('market update: %s', str(self))

        assert self.OriginatorID
        assert self.ObjectID
        assert self.CreatorID

        if not self.ObjectType.is_valid_object(store, self.ObjectID):
            return False

        if not self.is_valid_name(store):
            return False

        return True

    def is_permitted(self, store):
        if not self.CreatorType.is_valid_creator(
                store, self.CreatorID, self.OriginatorID):
            return False

        return True

    def apply(self, store):
        # must remove the existing name binding for this object
        store.unbind(store.i2n(self.ObjectID))

        obj = store[self.ObjectID]
        obj['name'] = self.Name
        store[self.ObjectID] = obj

        # and now add the new name binding
        store.bind(store.i2n(self.ObjectID), self.ObjectID)

    def dump(self):
        assert self.ObjectID
        assert self.CreatorID
        result = {
            'UpdateType': self.UpdateType,
            'ObjectID': self.ObjectID,
            'CreatorID': self.CreatorID,
            'Name': self.Name
        }
        return result

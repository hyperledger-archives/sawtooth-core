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

from mktplace.transactions import market_place_object_update

logger = logging.getLogger(__name__)


class ParticipantObject(market_place_object_update.MarketPlaceObject):
    ObjectTypeName = 'Participant'

    @classmethod
    def is_valid_creator(cls, store, creatorid, originatorid):
        creator = cls.load_from_store(store, creatorid)
        if not creator:
            logger.debug('unknown or invalid creator, %s', creatorid)
            return False

        if creator.Address != originatorid:
            logger.info(
                'address mismatch for creator %s, expected %s but got %s',
                creatorid, originatorid, creator.Address)
            return False

        return True

    def __init__(self, participantid=None, minfo=None):
        if minfo is None:
            minfo = {}
        super(ParticipantObject, self).__init__(participantid, minfo)

        self.Address = minfo.get('address', '**UNKNOWN**')
        self.Description = minfo.get('description', '')
        self.Name = minfo.get('name', '')

    def dump(self):
        result = super(ParticipantObject, self).dump()

        result['address'] = self.Address
        result['description'] = self.Description
        result['name'] = self.Name

        return result


class Register(market_place_object_update.Register):
    UpdateType = '/mktplace.transactions.ParticipantUpdate/Register'
    ObjectType = ParticipantObject
    CreatorType = ParticipantObject

    def __init__(self, transaction=None, minfo=None):
        if minfo is None:
            minfo = {}
        super(Register, self).__init__(transaction, minfo)

        self.Description = minfo.get('Description', '')
        self.Name = minfo.get('Name', '')

    @property
    def References(self):
        return []

    def is_valid_name(self, store):
        """
        Participant name may not include a '/', must be less than
        64 characters long, and is not the same as an already-existing
        object.
        """

        if self.Name == '':
            return True

        if self.Name.find('/') >= 0:
            logger.debug('invalid name %s; must not contain /', self.Name)
            return False

        if len(self.Name) >= 64:
            logger.debug('invalid name %s; must be less than 64 bytes',
                         self.Name)
            return False

        name = "//{0}".format(self.Name)
        if store.n2i(name, self.ObjectType.ObjectTypeName) is not None:
            logger.debug('invalid name %s; name must be unique', self.Name)
            return False
        return True

    def is_valid(self, store):
        if not super(Register, self).is_valid(store):
            return False

        return True

    def apply(self, store):
        pobj = ParticipantObject(self.ObjectID)
        pobj.Address = self.OriginatorID
        pobj.Description = self.Description
        pobj.Name = self.Name

        store[self.ObjectID] = pobj.dump()

    def dump(self):
        result = super(Register, self).dump()

        result['Description'] = self.Description
        result['Name'] = self.Name

        return result


class Unregister(market_place_object_update.Unregister):
    UpdateType = '/mktplace.transactions.ParticipantUpdate/Unregister'
    ObjectType = ParticipantObject
    CreatorType = ParticipantObject

    def __init__(self, transaction=None, minfo=None):
        if minfo is None:
            minfo = {}
        super(Unregister, self).__init__(transaction, minfo)

    def is_valid(self, store):
        if self.CreatorID != self.ObjectID:
            logger.info(
                'creator and object are the same for participant '
                'unregistration')
            return False

        if not super(Unregister, self).is_valid(store):
            return False

        if not self.is_permitted(store):
            return False

        return True


class UpdateDescription(market_place_object_update.UpdateDescription):
    UpdateType = '/mktplace.transactions.ParticipantUpdate/UpdateDescription'
    ObjectType = ParticipantObject
    CreatorType = ParticipantObject

    def __init__(self, transaction=None, minfo=None):
        if minfo is None:
            minfo = {}
        super(UpdateDescription, self).__init__(transaction, minfo)

    def is_valid(self, store):
        if self.CreatorID != self.ObjectID:
            logger.info('creator and object are the same for participant '
                        'unregistration')
            return False

        if not super(UpdateDescription, self).IsValid(store):
            return False

        return True


class UpdateName(market_place_object_update.UpdateName):
    UpdateType = '/mktplace.transactions.ParticipantUpdate/UpdateName'
    ObjectType = ParticipantObject
    CreatorType = ParticipantObject

    # -----------------------------------------------------------------
    def __init__(self, transaction=None, minfo=None):
        if minfo is None:
            minfo = {}
        super(UpdateName, self).__init__(transaction, minfo)

    # -----------------------------------------------------------------
    def is_valid_name(self, store):
        """
        Ensure that the name property meets syntactic requirements. Objects
        can override this method for object specific syntax. This method
        simply requires that a name not contain a '/', has a total length
        less than 64 characters, and is not the same as an already-existing
        object.
        """

        if self.Name == '':
            return True

        if self.Name.find('/') >= 0:
            logger.debug('invalid name %s; must not contain /', self.Name)
            return False

        if len(self.Name) >= 64:
            logger.debug('invalid name %s; must be less than 64 bytes',
                         self.Name)
            return False

        name = "//{0}".format(self.Name)
        if store.n2i(name, 'Participant'):
            logger.debug('invalid name %s; name must be unique', self.Name)
            return False

        return True

    def is_valid(self, store):
        logger.debug('market update: %s', str(self))

        assert self.OriginatorID
        assert self.ObjectID
        assert self.CreatorID

        if self.CreatorID != self.ObjectID:
            logger.info('creator and object are the same for participant '
                        'unregistration')
            return False

        if not self.ObjectType.is_valid_object(store, self.ObjectID):
            return False

        if not self.is_valid_name(store):
            return False

        return True

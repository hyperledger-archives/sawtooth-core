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

from sawtooth.exceptions import InvalidTransactionError
from journal import transaction
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


class Register(transaction.Update):
    UpdateType = 'RegisterParticipant'
    ObjectType = ParticipantObject
    CreatorType = ParticipantObject

    def __init__(self, update_type, name, description=None):
        super(Register, self).__init__(update_type)
        self._description = description or ''
        self._name = name

    @property
    def References(self):
        return []

    def is_valid_name(self, store):
        """
        Participant name may not include a '/', must be less than
        64 characters long, and is not the same as an already-existing
        object.
        """

        if self._name == '':
            return True

        if self._name.find('/') >= 0:
            logger.debug('invalid name %s; must not contain /', self._name)
            return False

        if len(self._name) >= 64:
            logger.debug('invalid name %s; must be less than 64 bytes',
                         self._name)
            return False

        name = "//{0}".format(self._name)
        if store.n2i(name, self.ObjectType.ObjectTypeName) is not None:
            logger.debug('invalid name %s; name must be unique', self._name)
            return False
        return True

    def check_valid(self, store, txn):
        if not self.is_valid_name(store):
            raise InvalidTransactionError(
                "Name, {}, is not valid".format(self._name))

    def apply(self, store, txn):
        pobj = ParticipantObject(txn.Identifier)
        pobj.Address = txn.OriginatorID
        pobj.Description = self._description
        pobj.Name = self._name

        store[txn.Identifier] = pobj.dump()


class Unregister(transaction.Update):
    UpdateType = 'UnregisterParticipant'
    ObjectType = ParticipantObject
    CreatorType = ParticipantObject

    def __init__(self,
                 update_type,
                 creator_id,
                 object_id):
        super(Unregister, self).__init__(update_type)
        self._creator_id = creator_id
        self._object_id = object_id

    @property
    def References(self):
        return []

    def check_valid(self, store, txn):
        if self._creator_id != self._object_id:
            logger.info(
                'creator and object are the same for participant '
                'unregistration')
            return False

        if not market_place_object_update.global_is_permitted(
                store, txn, self._creator_id, self.CreatorType):
            raise InvalidTransactionError(
                "Creator Address not the same as txn.OriginatorID")

    def apply(self, store, txn):
        del store[self._object_id]


class UpdateDescription(market_place_object_update.UpdateDescription):
    UpdateType = 'UpdateParticipantDescription'
    ObjectType = ParticipantObject
    CreatorType = ParticipantObject


class UpdateName(market_place_object_update.UpdateName):
    UpdateType = 'UpdateParticipantName'
    ObjectType = ParticipantObject
    CreatorType = ParticipantObject

    def is_valid_name(self, store):
        """
        Ensure that the name property meets syntactic requirements. Objects
        can override this method for object specific syntax. This method
        simply requires that a name not contain a '/', has a total length
        less than 64 characters, and is not the same as an already-existing
        object.
        """

        if self._name == '':
            return True

        if self._name.find('/') >= 0:
            logger.debug('invalid name %s; must not contain /', self._name)
            return False

        if len(self._name) >= 64:
            logger.debug('invalid name %s; must be less than 64 bytes',
                         self._name)
            return False

        name = "//{0}".format(self._name)
        if store.n2i(name, 'Participant'):
            logger.debug('invalid name %s; name must be unique', self._name)
            return False

        return True

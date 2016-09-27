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
from mktplace.transactions import participant_update
from journal.transaction import Update
from sawtooth.exceptions import InvalidTransactionError

logger = logging.getLogger(__name__)


class AccountObject(market_place_object_update.MarketPlaceObject):
    ObjectTypeName = 'Account'

    @classmethod
    def is_valid_object(cls, store, objectid):
        obj = cls.get_valid_object(store, objectid)
        if not obj:
            return False

        if not participant_update.ParticipantObject.is_valid_object(
                store, obj.get('creator')):
            return False

        return True

    def __init__(self, objectid=None, minfo=None):
        if minfo is None:
            minfo = {}
        super(AccountObject, self).__init__(objectid, minfo)

        self.CreatorID = minfo.get('creator', '**UNKNOWN**')
        self.Description = minfo.get('description', '')
        self.Name = minfo.get('name', '')

    def dump(self):
        result = super(AccountObject, self).dump()

        result['creator'] = self.CreatorID
        result['description'] = self.Description
        result['name'] = self.Name

        return result


class Register(Update):
    UpdateType = 'RegisterAccount'
    ObjectType = AccountObject
    CreatorType = participant_update.ParticipantObject

    def __init__(self,
                 update_type,
                 creator_id=None,
                 description=None,
                 name=None):
        super(Register, self).__init__(update_type)

        self._creator_id = creator_id or '**UNKNOWN**'
        self._description = description or ''
        self._name = name or ''

    @property
    def References(self):
        return [self._creator_id]

    def check_valid(self, store, txn):
        if txn.Identifier in store:
            raise InvalidTransactionError(
                "Object Id is already in store")

        if not market_place_object_update.global_is_valid_name(
                store, self._name, self.ObjectType, self._creator_id):
            raise InvalidTransactionError(
                "Name isn't valid")

        if not market_place_object_update.global_is_permitted(
                store, txn, self._creator_id, self.CreatorType):
            raise InvalidTransactionError(
                "Creator address is not the same as txn.OriginatorID")

    def apply(self, store, txn):
        pobj = self.ObjectType(txn.Identifier)

        pobj.CreatorID = self._creator_id
        pobj.Description = self._description
        pobj.Name = self._name

        store[txn.Identifier] = pobj.dump()


class Unregister(Update):
    UpdateType = 'UnregisterAccount'
    ObjectType = AccountObject
    CreatorType = participant_update.ParticipantObject

    def __init__(self,
                 update_type,
                 object_id,
                 creator_id):
        super(Unregister, self).__init__(update_type)
        self._object_id = object_id
        self._creator_id = creator_id

    @property
    def References(self):
        return []

    def check_valid(self, store, txn):
        assert txn.OriginatorID

        if not self.ObjectType.is_valid_object(store, self._object_id):
            raise InvalidTransactionError(
                "ObjectId does not reference an Account")

        if not market_place_object_update.global_is_permitted(
                store, txn, self._creator_id, self.CreatorType):
            raise InvalidTransactionError(
                "Creator address is not the same as txn.OriginatorId")

    def apply(self, store, txn):
        del store[self._object_id]


class UpdateDescription(market_place_object_update.UpdateDescription):
    UpdateType = 'UpdateAccountDescription'
    ObjectType = AccountObject
    CreatorType = participant_update.ParticipantObject


class UpdateName(market_place_object_update.UpdateName):
    UpdateType = 'UpdateAccountName'
    ObjectType = AccountObject
    CreatorType = participant_update.ParticipantObject

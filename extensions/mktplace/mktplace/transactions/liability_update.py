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

from mktplace.transactions import account_update
from mktplace.transactions import asset_type_update
from mktplace.transactions import holding_update
from mktplace.transactions import market_place_object_update
from mktplace.transactions import participant_update

logger = logging.getLogger(__name__)


class LiabilityObject(market_place_object_update.MarketPlaceObject):
    ObjectTypeName = 'Liability'

    @classmethod
    def get_valid_object(cls, store, objectid, objecttypes=None):
        types = [cls.ObjectTypeName,
                 holding_update.HoldingObject.ObjectTypeName]
        return super(cls, cls).get_valid_object(store, objectid, types)

    @classmethod
    def is_valid_object(cls, store, objectid):
        obj = cls.get_valid_object(store, objectid)
        if not obj:
            return False

        if obj.get(
                'object-type') == holding_update.HoldingObject.ObjectTypeName:
            return holding_update.HoldingObject.is_valid_object(
                store, objectid)

        if not participant_update.ParticipantObject.is_valid_object(
                store, obj.get('creator')):
            return False

        if not account_update.AccountObject.is_valid_object(
                store, obj.get('account')):
            return False

        if not asset_type_update.AssetTypeObject.is_valid_object(
                store, obj.get('asset-type')):
            return False

        if not participant_update.ParticipantObject.is_valid_object(
                store, obj.get('guarantor')):
            return False

        if int(obj.get('count', 0)) < 0:
            return False

        return True

    def __init__(self, objectid=None, minfo=None):
        if minfo is None:
            minfo = {}
        super(LiabilityObject, self).__init__(objectid, minfo)

        self.CreatorID = minfo.get('creator', '**UNKNOWN**')
        self.AccountID = minfo.get('account', '**UNKNOWN**')
        self.AssetTypeID = minfo.get('asset-type', '**UNKNOWN**')
        self.GuarantorID = minfo.get('guarantor', '**UNKNOWN**')
        self.Count = int(minfo.get('count', 0))
        self.Description = minfo.get('description', '')
        self.Name = minfo.get('name', '')

    def dump(self):
        result = super(LiabilityObject, self).dump()

        result['creator'] = self.CreatorID
        result['account'] = self.AccountID
        result['asset-type'] = self.AssetTypeID
        result['guarantor'] = self.GuarantorID
        result['count'] = int(self.Count)
        result['description'] = self.Description
        result['name'] = self.Name

        return result


class Register(transaction.Update):
    UpdateType = 'RegisterLiability'
    ObjectType = LiabilityObject
    CreatorType = participant_update.ParticipantObject

    def __init__(self,
                 update_type,
                 creator_id=None,
                 account_id=None,
                 asset_type_id=None,
                 guarantor_id=None,
                 count=0,
                 description=None,
                 name=None):
        super(Register, self).__init__(update_type)
        self._creator_id = creator_id or '**UNKNOWN**'
        self._account_id = account_id or '**UNKNOWN**'
        self._asset_type_id = asset_type_id or '**UNKNOWN**'
        self._guarantor_id = guarantor_id or '**UNKNOWN**'
        self._count = int(count)
        self._description = description or ''
        self._name = name or ''

    @property
    def References(self):
        return [self._creator_id, self._asset_type_id]

    def check_valid(self, store, txn):
        if txn.Identifier in store:
            raise InvalidTransactionError(
                "ObjectId already in store")

        if not market_place_object_update.global_is_valid_name(
                store, self._name, self.ObjectType, self._creator_id):
            raise InvalidTransactionError(
                "Name is not valid")

        if not market_place_object_update.global_is_permitted(
                store,
                txn,
                self._creator_id,
                self.CreatorType):
            raise InvalidTransactionError(
                "Creator Address not the same as txn.OriginatorID")

        if not account_update.AccountObject.is_valid_object(store,
                                                            self._account_id):
            raise InvalidTransactionError(
                "AccountId does not reference an Account")

        if not asset_type_update.AssetTypeObject.is_valid_object(
                store, self._asset_type_id):
            raise InvalidTransactionError(
                "AssetTypeid not a valid AssetType")

        if not participant_update.ParticipantObject.is_valid_object(
                store, self._guarantor_id):
            raise InvalidTransactionError(
                "GuarantorID not a valid Participant")

        if self._count < 0:
            raise InvalidTransactionError(
                "Count < 0")

        return True

    def apply(self, store, txn):
        pobj = self.ObjectType(txn.Identifier)

        pobj.CreatorID = self._creator_id
        pobj.AccountID = self._account_id
        pobj.AssetTypeID = self._asset_type_id
        pobj.GuarantorID = self._guarantor_id
        pobj.Count = self._count
        pobj.Description = self._description
        pobj.Name = self._name

        store[txn.Identifier] = pobj.dump()


class Unregister(transaction.Update):
    UpdateType = 'UnregisterLiability'
    ObjectType = LiabilityObject
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

        if not market_place_object_update.global_is_permitted(
                store,
                txn,
                self._creator_id,
                self.CreatorType):
            raise InvalidTransactionError(
                "Creator Address not the same as txn.OriginatorID")

        if not self.ObjectType.is_valid_object(store, self._object_id):
            raise InvalidTransactionError(
                "ObjectID does not reference a Liability")

    def apply(self, store, txn):
        del store[self._object_id]


class UpdateDescription(market_place_object_update.UpdateDescription):
    UpdateType = 'UpdateLiabilityDescription'
    ObjectType = LiabilityObject
    CreatorType = participant_update.ParticipantObject


class UpdateName(market_place_object_update.UpdateName):
    UpdateType = 'UpdateLiabilityName'
    ObjectType = LiabilityObject
    CreatorType = participant_update.ParticipantObject

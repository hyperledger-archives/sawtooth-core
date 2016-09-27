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
from mktplace.transactions import asset_update
from mktplace.transactions import market_place_object_update
from mktplace.transactions import participant_update

logger = logging.getLogger(__name__)


class HoldingObject(market_place_object_update.MarketPlaceObject):
    ObjectTypeName = 'Holding'

    @classmethod
    def is_valid_object(cls, store, objectid):
        types = [cls.ObjectTypeName]
        obj = cls.get_valid_object(store, objectid, types)
        if not obj:
            return False

        if not participant_update.ParticipantObject.is_valid_object(
                store, obj.get('creator')):
            return False

        if not account_update.AccountObject.is_valid_object(
                store, obj.get('account')):
            return False

        if not asset_update.AssetObject.is_valid_object(
                store, obj.get('asset')):
            return False

        if int(obj.get('count', 0)) < 0:
            return False

        return True

    def __init__(self, objectid=None, minfo=None):
        if minfo is None:
            minfo = {}
        super(HoldingObject, self).__init__(objectid, minfo)

        self.CreatorID = minfo.get('creator', '**UNKNOWN**')
        self.AccountID = minfo.get('account', '**UNKNOWN**')
        self.AssetID = minfo.get('asset', '**UNKNOWN**')
        self.Count = int(minfo.get('count', 0))
        self.Description = minfo.get('description', '')
        self.Name = minfo.get('name', '')

    def dump(self):
        result = super(HoldingObject, self).dump()

        result['creator'] = self.CreatorID
        result['account'] = self.AccountID
        result['asset'] = self.AssetID
        result['count'] = int(self.Count)
        result['description'] = self.Description
        result['name'] = self.Name

        return result


class Register(transaction.Update):
    UpdateType = 'RegisterHolding'
    ObjectType = HoldingObject
    CreatorType = participant_update.ParticipantObject

    def __init__(self,
                 update_type,
                 creator_id=None,
                 account_id=None,
                 asset_id=None,
                 count=0,
                 description=None,
                 name=None):
        super(Register, self).__init__(update_type)
        self._creator_id = creator_id or '**UNKNOWN**'
        self._account_id = account_id or '**UNKNOWN**'
        self._asset_id = asset_id or '**UNKNOWN**'
        self._count = count
        self._description = description or ''
        self._name = name or ''

    @property
    def References(self):
        return [self._creator_id, self._account_id, self._asset_id]

    def check_valid(self, store, txn):
        if txn.Identifier in store:
            raise InvalidTransactionError(
                "ObjectId alread in store")

        if not market_place_object_update.global_is_valid_name(
                store, self._name, self.ObjectType, self._creator_id):
            raise InvalidTransactionError(
                "Name isn't valid")

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
                "AccountID does not reference an Account")

        if self._count < 0:
            raise InvalidTransactionError(
                "Count is less than 0")

        # make sure we have a valid asset
        asset = asset_update.AssetObject.load_from_store(store, self._asset_id)
        if not asset:
            logger.debug('invalid asset %s in holding', self._asset_id)
            raise InvalidTransactionError(
                "AssetId does not reference an Asset")

        # if the asset is restricted, then only the creator of the asset can
        # create holdings with a count greater than 0
        if asset.Restricted:
            if self._creator_id != asset.CreatorID and 0 < self._count:
                logger.debug(
                    'instances of a restricted asset %s can only be created '
                    'by the owner',
                    self._asset_id)
                raise InvalidTransactionError(
                    "Instances of a restricted asset {} can only be created "
                    "by the owner".format(self._asset_id))

        # if the asset is not consumable then counts dont matter, the only
        # valid counts are 0 or 1
        if not asset.Consumable:
            if 1 < self._count:
                logger.debug(
                    'non consumable assets of type %s are retricted to '
                    'a single instance',
                    self._asset_id)
                raise InvalidTransactionError(
                    "Non consumable assets are restricted to a single "
                    "instance")

    def apply(self, store, txn):
        pobj = self.ObjectType(txn.Identifier)

        pobj.CreatorID = self._creator_id
        pobj.AccountID = self._account_id
        pobj.AssetID = self._asset_id
        pobj.Count = self._count
        pobj.Description = self._description
        pobj.Name = self._name

        store[txn.Identifier] = pobj.dump()


class Unregister(transaction.Update):
    UpdateType = 'UnregisterHolding'
    ObjectType = HoldingObject
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
        if not self.ObjectType.is_valid_object(store, self._object_id):
            return False

        if not market_place_object_update.global_is_permitted(
                store,
                txn,
                self._creator_id,
                self.CreatorType):
            raise InvalidTransactionError(
                "Creator Address is not the same as txn.OriginatorID")

    def apply(self, store, txn):
        del store[self._object_id]


class UpdateDescription(market_place_object_update.UpdateDescription):
    UpdateType = 'UpdateHoldingDescription'
    ObjectType = HoldingObject
    CreatorType = participant_update.ParticipantObject


class UpdateName(market_place_object_update.UpdateName):
    UpdateType = 'UpdateHoldingName'
    ObjectType = HoldingObject
    CreatorType = participant_update.ParticipantObject

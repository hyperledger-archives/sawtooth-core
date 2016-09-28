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

from journal.transaction import Update
from sawtooth.exceptions import InvalidTransactionError

from mktplace.transactions import asset_type_update
from mktplace.transactions import market_place_object_update
from mktplace.transactions import participant_update

logger = logging.getLogger(__name__)


class AssetObject(market_place_object_update.MarketPlaceObject):
    ObjectTypeName = 'Asset'

    @classmethod
    def is_valid_object(cls, store, objectid):
        obj = cls.get_valid_object(store, objectid)
        if not obj:
            return False

        if not participant_update.ParticipantObject.is_valid_object(
                store, obj.get('creator')):
            return False

        if not asset_type_update.AssetTypeObject.is_valid_object(
                store, obj.get('asset-type')):
            return False

        return True

    def __init__(self, objectid=None, minfo=None):
        if minfo is None:
            minfo = {}
        super(AssetObject, self).__init__(objectid, minfo)

        self.CreatorID = minfo.get('creator', '**UNKNOWN**')
        self.AssetTypeID = minfo.get('asset-type', '**UNKNOWN**')
        self.Consumable = bool(minfo.get('consumable', True))
        self.Restricted = bool(minfo.get('restricted', True))
        self.Divisible = bool(minfo.get('divisible', False))
        self.Description = minfo.get('description', '')
        self.Name = minfo.get('name', '')

    def dump(self):
        result = super(AssetObject, self).dump()

        result['creator'] = self.CreatorID
        result['asset-type'] = self.AssetTypeID
        result['consumable'] = self.Consumable
        result['restricted'] = self.Restricted
        result['divisible'] = self.Divisible
        result['description'] = self.Description
        result['name'] = self.Name

        return result


class Register(Update):
    UpdateType = 'RegisterAsset'
    ObjectType = AssetObject
    CreatorType = participant_update.ParticipantObject

    def __init__(self,
                 update_type,
                 creator_id=None,
                 asset_type_id=None,
                 consumable=True,
                 restricted=True,
                 divisible=False,
                 description=None,
                 name=None):
        super(Register, self).__init__(update_type)

        self._creator_id = creator_id or '**UNKNOWN**'
        self._asset_type_id = asset_type_id or '**UNKNOWN**'
        self._consumable = consumable
        self._restricted = restricted
        self._divisible = divisible
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
                store, txn, self._creator_id, self.CreatorType):
            raise InvalidTransactionError(
                "Creator Address not the same as txn.OriginatorID")

        assettype = asset_type_update.AssetTypeObject.load_from_store(
            store, self._asset_type_id)
        if not assettype:
            logger.debug('missing asset type %s', self._asset_type_id)
            raise InvalidTransactionError(
                "AssetTypeId does not reference an AssetType")

        # if the asset type is restricted then the creator of the asset type
        # is the only one who can create assets of that type
        if assettype.Restricted and assettype.CreatorID != self._creator_id:
            logger.debug('no permission to create an asset of type %s',
                         self._asset_type_id)
            raise InvalidTransactionError(
                "AssetType is restricted and the creator is not the same "
                "as txn creator")

    def apply(self, store, txn):
        pobj = self.ObjectType(txn.Identifier)
        pobj.CreatorID = self._creator_id
        pobj.AssetTypeID = self._asset_type_id
        pobj.Restricted = self._restricted
        pobj.Consumable = self._consumable
        pobj.Divisible = self._divisible
        pobj.Description = self._description
        pobj.Name = self._name

        store[txn.Identifier] = pobj.dump()


class Unregister(Update):
    UpdateType = 'UnregisterAsset'
    ObjectType = AssetObject
    CreatorType = participant_update.ParticipantObject

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
        if not market_place_object_update.global_is_permitted(
                store, txn, self._creator_id, self.CreatorType):
            raise InvalidTransactionError(
                "Creator address not the same as txn.OriginatorID")

    def apply(self, store, txn):
        del store[self._object_id]


class UpdateDescription(market_place_object_update.UpdateDescription):
    UpdateType = 'UpdateAssetDescription'
    ObjectType = AssetObject
    CreatorType = participant_update.ParticipantObject


class UpdateName(market_place_object_update.UpdateName):
    UpdateType = 'UpdateAssetName'
    ObjectType = AssetObject
    CreatorType = participant_update.ParticipantObject

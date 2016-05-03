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

    def __init__(self, objectid=None, minfo={}):
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


class Register(market_place_object_update.Register):
    UpdateType = '/mktplace.transactions.AssetUpdate/Register'
    ObjectType = AssetObject
    CreatorType = participant_update.ParticipantObject

    def __init__(self, transaction=None, minfo={}):
        super(Register, self).__init__(transaction, minfo)

        self.CreatorID = minfo.get('CreatorID', '**UNKNOWN**')
        self.AssetTypeID = minfo.get('AssetTypeID', '**UNKNOWN**')
        self.Consumable = bool(minfo.get('Consumable', True))
        self.Restricted = bool(minfo.get('Restricted', True))
        self.Divisible = bool(minfo.get('Divisible', False))
        self.Description = minfo.get('Description', '')
        self.Name = minfo.get('Name', '')

    @property
    def References(self):
        return [self.CreatorID, self.AssetTypeID]

    def is_valid(self, store):
        if not super(Register, self).is_valid(store):
            return False

        if not self.is_permitted(store):
            return False

        assettype = asset_type_update.AssetTypeObject.load_from_store(
            store, self.AssetTypeID)
        if not assettype:
            logger.debug('missing asset type %s', self.AssetTypeID)
            return False

        # if the asset type is restricted then the creator of the asset type
        # is the only one who can create assets of that type
        if assettype.Restricted and assettype.CreatorID != self.CreatorID:
            logger.debug('no permission to create an asset of type %s',
                         self.AssetTypeID)
            return False

        return True

    def apply(self, store):
        pobj = self.ObjectType(self.ObjectID)

        pobj.CreatorID = self.CreatorID
        pobj.AssetTypeID = self.AssetTypeID
        pobj.Restricted = self.Restricted
        pobj.Consumable = self.Consumable
        pobj.Divisible = self.Divisible
        pobj.Description = self.Description
        pobj.Name = self.Name

        store[self.ObjectID] = pobj.dump()

    def dump(self):
        result = super(Register, self).dump()

        result['CreatorID'] = self.CreatorID
        result['AssetTypeID'] = self.AssetTypeID
        result['Restricted'] = self.Restricted
        result['Consumable'] = self.Consumable
        result['Divisible'] = self.Divisible
        result['Description'] = self.Description
        result['Name'] = self.Name

        return result


class Unregister(market_place_object_update.Unregister):
    UpdateType = '/mktplace.transactions.AssetUpdate/Unregister'
    ObjectType = AssetObject
    CreatorType = participant_update.ParticipantObject

    def __init__(self, transaction=None, minfo={}):
        super(Unregister, self).__init__(transaction, minfo)

    def is_valid(self, store):
        if not super(Unregister, self).is_valid(store):
            return False

        if not self.is_permitted(store):
            return False

        return True


class UpdateDescription(market_place_object_update.UpdateDescription):
    UpdateType = '/mktplace.transactions.AssetUpdate/UpdateDescription'
    ObjectType = AssetObject
    CreatorType = participant_update.ParticipantObject


class UpdateName(market_place_object_update.UpdateName):
    UpdateType = '/mktplace.transactions.AssetUpdate/UpdateName'
    ObjectType = AssetObject
    CreatorType = participant_update.ParticipantObject

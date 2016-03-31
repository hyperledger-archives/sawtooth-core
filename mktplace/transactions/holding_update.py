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

    def __init__(self, objectid=None, minfo={}):
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


class Register(market_place_object_update.Register):
    UpdateType = '/' + __name__ + '/Register'
    ObjectType = HoldingObject
    CreatorType = participant_update.ParticipantObject

    def __init__(self, transaction=None, minfo={}):
        super(Register, self).__init__(transaction, minfo)

        self.CreatorID = minfo.get('CreatorID', '**UNKNOWN**')
        self.AccountID = minfo.get('AccountID', '**UNKNOWN**')
        self.AssetID = minfo.get('AssetID', '**UNKNOWN**')
        self.Count = int(minfo.get('Count', 0))
        self.Description = minfo.get('Description', '')
        self.Name = minfo.get('Name', '')

    def is_valid(self, store):
        if not super(Register, self).is_valid(store):
            return False

        if not self.is_permitted(store):
            return False

        if not account_update.AccountObject.is_valid_object(store,
                                                            self.AccountID):
            return False

        if self.Count < 0:
            return False

        # make sure we have a valid asset
        asset = asset_update.AssetObject.load_from_store(store, self.AssetID)
        if not asset:
            logger.debug('invalid asset %s in holding', self.AssetID)
            return False

        # if the asset is restricted, then only the creator of the asset can
        # create holdings with a count greater than 0
        if asset.Restricted:
            if self.CreatorID != asset.CreatorID and 0 < self.Count:
                logger.debug(
                    'instances of a restricted asset %s can only be created '
                    'by the owner',
                    self.AssetID)
                return False

        # if the asset is not consumable then counts dont matter, the only
        # valid counts are 0 or 1
        if not asset.Consumable:
            if 1 < self.Count:
                logger.debug(
                    'non consumable assets of type %s are retricted to '
                    'a single instance',
                    self.AssetID)
                return False

        return True

    def apply(self, store):
        pobj = self.ObjectType(self.ObjectID)

        pobj.CreatorID = self.CreatorID
        pobj.AccountID = self.AccountID
        pobj.AssetID = self.AssetID
        pobj.Count = self.Count
        pobj.Description = self.Description
        pobj.Name = self.Name

        store[self.ObjectID] = pobj.dump()

    def dump(self):
        result = super(Register, self).dump()

        result['CreatorID'] = self.CreatorID
        result['AccountID'] = self.AccountID
        result['AssetID'] = self.AssetID
        result['Count'] = int(self.Count)
        result['Description'] = self.Description
        result['Name'] = self.Name

        return result


class Unregister(market_place_object_update.Unregister):
    UpdateType = '/' + __name__ + '/Unregister'
    ObjectType = HoldingObject
    CreatorType = participant_update.ParticipantObject

    def __init__(self, transaction=None, minfo={}):
        super(Unregister, self).__init__(transaction, minfo)

    def is_valid(self, store):
        if not super(Unregister, self).is_valid(store):
            return False

        if not self.is_permitted(store):
            return False

        return True

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


class Register(market_place_object_update.Register):
    UpdateType = '/mktplace.transactions.LiabilityUpdate/Register'
    ObjectType = LiabilityObject
    CreatorType = participant_update.ParticipantObject

    def __init__(self, transaction=None, minfo=None):
        if minfo is None:
            minfo = {}
        super(Register, self).__init__(transaction, minfo)

        self.CreatorID = minfo.get('CreatorID', '**UNKNOWN**')
        self.AccountID = minfo.get('AccountID', '**UNKNOWN**')
        self.AssetTypeID = minfo.get('AssetTypeID', '**UNKNOWN**')
        self.GuarantorID = minfo.get('GuarantorID', '**UNKNOWN**')
        self.Count = int(minfo.get('Count', 0))
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

        if not account_update.AccountObject.is_valid_object(store,
                                                            self.AccountID):
            return False

        if not asset_type_update.AssetTypeObject.is_valid_object(
                store, self.AssetTypeID):
            return False

        if not participant_update.ParticipantObject.is_valid_object(
                store, self.GuarantorID):
            return False

        if self.Count < 0:
            return False

        return True

    def apply(self, store):
        super(Register, self).apply(store)
        pobj = self.ObjectType(self.ObjectID)

        pobj.CreatorID = self.CreatorID
        pobj.AccountID = self.AccountID
        pobj.AssetTypeID = self.AssetTypeID
        pobj.GuarantorID = self.GuarantorID
        pobj.Count = self.Count
        pobj.Description = self.Description
        pobj.Name = self.Name

        store[self.ObjectID] = pobj.dump()

    def dump(self):
        result = super(Register, self).dump()

        result['CreatorID'] = self.CreatorID
        result['AccountID'] = self.AccountID
        result['AssetTypeID'] = self.AssetTypeID
        result['GuarantorID'] = self.GuarantorID
        result['Count'] = int(self.Count)
        result['Description'] = self.Description
        result['Name'] = self.Name

        return result


class Unregister(market_place_object_update.Unregister):
    UpdateType = '/mktplace.transactions.LiabilityUpdate/Unregister'
    ObjectType = LiabilityObject
    CreatorType = participant_update.ParticipantObject

    def __init__(self, transaction=None, minfo=None):
        if minfo is None:
            minfo = {}
        super(Unregister, self).__init__(transaction, minfo)

    def is_valid(self, store):
        if not super(Unregister, self).is_valid(store):
            return False

        if not self.is_permitted(store):
            return False

        return True


class UpdateDescription(market_place_object_update.UpdateDescription):
    UpdateType = '/mktplace.transactions.LiabilityUpdate/UpdateDescription'
    ObjectType = LiabilityObject
    CreatorType = participant_update.ParticipantObject


class UpdateName(market_place_object_update.UpdateName):
    UpdateType = '/mktplace.transactions.LiabilityUpdate/UpdateName'
    ObjectType = LiabilityObject
    CreatorType = participant_update.ParticipantObject

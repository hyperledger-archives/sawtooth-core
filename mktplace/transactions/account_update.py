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

    def __init__(self, objectid=None, minfo={}):
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


class Register(market_place_object_update.Register):
    UpdateType = '/' + __name__ + '/Register'
    ObjectType = AccountObject
    CreatorType = participant_update.ParticipantObject

    def __init__(self, transaction=None, minfo={}):
        super(Register, self).__init__(transaction, minfo)

        self.CreatorID = minfo.get('CreatorID', '**UNKNOWN**')
        self.Description = minfo.get('Description', '')
        self.Name = minfo.get('Name', '')

    def is_valid(self, store):
        if not super(Register, self).is_valid(store):
            return False

        if not self.is_permitted(store):
            return False

        return True

    def apply(self, store):
        pobj = self.ObjectType(self.ObjectID)

        pobj.CreatorID = self.CreatorID
        pobj.Description = self.Description
        pobj.Name = self.Name

        store[self.ObjectID] = pobj.dump()

    def dump(self):
        result = super(Register, self).dump()

        result['CreatorID'] = self.CreatorID
        result['Description'] = self.Description
        result['Name'] = self.Name

        return result


class Unregister(market_place_object_update.Unregister):
    UpdateType = '/' + __name__ + '/Unregister'
    ObjectType = AccountObject
    CreatorType = participant_update.ParticipantObject

    def __init__(self, transaction=None, minfo={}):
        super(Unregister, self).__init__(transaction, minfo)

    def is_valid(self, store):
        if not super(Unregister, self).is_valid(store):
            return False

        if not self.is_permitted(store):
            return False

        return True

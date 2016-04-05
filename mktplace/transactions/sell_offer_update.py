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
import sys

from mktplace.transactions import holding_update
from mktplace.transactions import liability_update
from mktplace.transactions import market_place_object_update
from mktplace.transactions import participant_update

logger = logging.getLogger(__name__)


class SellOfferObject(market_place_object_update.MarketPlaceObject):
    ObjectTypeName = 'SellOffer'
    ExecutionStyle = ['Any', 'ExecuteOnce', 'ExecuteOncePerParticipant']

    @classmethod
    def is_valid_object(cls, store, objectid):
        obj = cls.get_valid_object(store, objectid)
        if not obj:
            return False

        if not participant_update.ParticipantObject.is_valid_object(
                store, obj.get('creator')):
            return False

        if not liability_update.LiabilityObject.is_valid_object(
                store, obj.get('input')):
            return False

        if not holding_update.HoldingObject.is_valid_object(store,
                                                            obj.get('output')):
            return False

        if float(obj.get('ratio', 0)) <= 0:
            return False

        if obj.get('minimum') < 0 or obj.get('maximum') < 0:
            return False

        if obj.get('maximum') < obj.get('minimum'):
            return False

        if obj.get('execution') not in cls.ExecutionStyle:
            return False

        return True

    def __init__(self, objectid=None, minfo={}):
        super(SellOfferObject, self).__init__(objectid, minfo)

        self.CreatorID = minfo.get('creator', '**UNKNOWN**')
        self.InputID = minfo.get('input', '**UNKNOWN**')
        self.OutputID = minfo.get('output', '**UNKNOWN**')
        self.Ratio = float(minfo.get('ratio', 0))
        self.Description = minfo.get('description', '')
        self.Name = minfo.get('name', '')
        self.Minimum = int(minfo.get('minimum', 0))
        self.Maximum = int(minfo.get('maximum', sys.maxint))
        self.Execution = minfo.get('execution', 'Any')
        self.ExecutionState = {'ParticipantList': []}

    def dump(self):
        result = super(SellOfferObject, self).dump()

        result['creator'] = self.CreatorID
        result['input'] = self.InputID
        result['output'] = self.OutputID
        result['ratio'] = float(self.Ratio)
        result['description'] = self.Description
        result['name'] = self.Name
        result['minimum'] = int(self.Minimum)
        result['maximum'] = int(self.Maximum)
        result['execution'] = self.Execution
        result['execution-state'] = self.ExecutionState

        return result


class Register(market_place_object_update.Register):
    UpdateType = '/mktplace.transactions.SellOfferUpdate/Register'
    ObjectType = SellOfferObject
    CreatorType = participant_update.ParticipantObject

    def __init__(self, transaction=None, minfo={}):
        super(Register, self).__init__(transaction, minfo)

        self.CreatorID = minfo.get('CreatorID', '**UNKNOWN**')
        self.InputID = minfo.get('InputID')
        self.OutputID = minfo.get('OutputID')
        self.Ratio = float(minfo.get('Ratio', 1))
        self.Description = minfo.get('Description', '')
        self.Name = minfo.get('Name', '')
        self.Minimum = int(minfo.get('Minimum', 0))
        self.Maximum = int(minfo.get('Maximum', sys.maxint))
        self.Execution = minfo.get('Execution', 'Any')

    def is_valid(self, store):
        if not super(Register, self).is_valid(store):
            return False

        if not self.is_permitted(store):
            return False

        if not liability_update.LiabilityObject.is_valid_object(store,
                                                                self.InputID):
            return False

        obj = liability_update.LiabilityObject.get_valid_object(store,
                                                                self.InputID)
        if not self.CreatorType.is_valid_creator(store, obj.get('creator'),
                                                 self.OriginatorID):
            logger.info('%s does not have permission to modify liability %s',
                        self.OriginatorID, self.InputID)
            return False

        if not holding_update.HoldingObject.is_valid_object(store,
                                                            self.OutputID):
            return False

        obj = holding_update.HoldingObject.get_valid_object(
            store, self.OutputID)
        if not self.CreatorType.is_valid_creator(store, obj.get('creator'),
                                                 self.OriginatorID):
            logger.info('%s does not have permission to modify liability %s',
                        self.OriginatorID, self.OutputID)
            return False

        if self.Ratio <= 0:
            logger.debug('invalid ratio %s in offer %s', self.Ratio,
                         self.ObjectID)
            return False

        if self.Minimum < 0 or self.Maximum < 0 or self.Maximum < self.Minimum:
            logger.debug('inconsistent range %s < %s in offer %s',
                         self.Minimum, self.Maximum, self.ObjectID)
            return False

        if self.Execution not in SellOfferObject.ExecutionStyle:
            logger.debug('invalid execution style %s in offer %s',
                         self.Execution, self.ObjectID)
            return False

        return True

    def apply(self, store):
        pobj = self.ObjectType(self.ObjectID)

        pobj.CreatorID = self.CreatorID
        pobj.InputID = self.InputID
        pobj.OutputID = self.OutputID
        pobj.Ratio = float(self.Ratio)
        pobj.Description = self.Description
        pobj.Name = self.Name
        pobj.Minimum = self.Minimum
        pobj.Maximum = self.Maximum
        pobj.Execution = self.Execution

        store[self.ObjectID] = pobj.dump()

    def dump(self):
        result = super(Register, self).dump()

        result['CreatorID'] = self.CreatorID
        result['InputID'] = self.InputID
        result['OutputID'] = self.OutputID
        result['Ratio'] = float(self.Ratio)
        result['Description'] = self.Description
        result['Name'] = self.Name
        result['Minimum'] = int(self.Minimum)
        result['Maximum'] = int(self.Maximum)
        result['Execution'] = self.Execution

        return result


class Unregister(market_place_object_update.Unregister):
    UpdateType = '/mktplace.transactions.SellOfferUpdate/Unregister'
    ObjectType = SellOfferObject
    CreatorType = participant_update.ParticipantObject

    def __init__(self, transaction=None, minfo={}):
        super(Unregister, self).__init__(transaction, minfo)

    def is_valid(self, store):
        if not super(Unregister, self).is_valid(store):
            return False

        if not self.is_permitted(store):
            return False

        return True

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

from mktplace.transactions import liability_update
from mktplace.transactions import market_place_object_update
from mktplace.transactions import participant_update
from mktplace.transactions import sell_offer_update
from gossip.common import dict2json

logger = logging.getLogger(__name__)


class ExchangeOfferObject(market_place_object_update.MarketPlaceObject):
    ObjectTypeName = 'ExchangeOffer'
    ExecutionStyle = ['Any', 'ExecuteOnce', 'ExecuteOncePerParticipant']

    @classmethod
    def get_valid_object(cls, store, objectid, objecttypes=None):
        types = [cls.ObjectTypeName,
                 sell_offer_update.SellOfferObject.ObjectTypeName]
        return super(cls, cls).get_valid_object(store, objectid, types)

    @classmethod
    def is_valid_object(cls, store, objectid):
        obj = cls.get_valid_object(store, objectid)
        if not obj:
            return False

        # SellOffer is really just a subclass of ExchangeOffer
        if obj.get('object-type') == \
                sell_offer_update.SellOfferObject.ObjectTypeName:
            return sell_offer_update.SellOfferObject.is_valid_object(store,
                                                                     objectid)

        if not participant_update.ParticipantObject.is_valid_object(
                store, obj.get('creator')):
            return False

        if not liability_update.LiabilityObject.is_valid_object(
                store, obj.get('input')):
            return False

        if not liability_update.LiabilityObject.is_valid_object(
                store, obj.get('output')):
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
        super(ExchangeOfferObject, self).__init__(objectid, minfo)

        self.CreatorID = minfo.get('creator', '**UNKNOWN**')
        self.InputID = minfo.get('input', '**UNKNOWN**')
        self.OutputID = minfo.get('output', '**UNKNOWN**')
        self.Ratio = float(minfo.get('ratio', 0))
        self.Description = minfo.get('description', '')
        self.Name = minfo.get('name', '')
        self.Minimum = int(minfo.get('minimum', 1))
        self.Maximum = int(minfo.get('maximum', sys.maxint))
        self.Execution = minfo.get('execution', 'Any')
        self.ExecutionState = {'ParticipantList': []}

        # the minimum must be high enough so that at least 1 asset
        # is transferred out of the holding as a result of executing the offer
        if self.Ratio < 0:
            self.Minimum = max(self.Minimum, int(1.0 / self.Ratio))
            if self.Minimum * self.Ratio < 1.0:
                self.Minimum += 1

    def dump(self):
        result = super(ExchangeOfferObject, self).dump()

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
    UpdateType = '/mktplace.transactions.ExchangeOfferUpdate/Register'
    ObjectType = ExchangeOfferObject
    CreatorType = participant_update.ParticipantObject

    def __init__(self, transaction=None, minfo={}):
        super(Register, self).__init__(transaction, minfo)

        self.CreatorID = minfo.get('CreatorID', '**UNKNOWN**')
        self.InputID = minfo.get('InputID', '**UNKNOWN**')
        self.OutputID = minfo.get('OutputID', '**UNKNOWN**')
        self.Ratio = float(minfo.get('Ratio', 1.0))
        self.Description = minfo.get('Description', '')
        self.Name = minfo.get('Name', '')
        self.Minimum = int(minfo.get('Minimum', 0))
        self.Maximum = int(minfo.get('Maximum', sys.maxint))
        self.Execution = minfo.get('Execution', 'Any')

    @property
    def References(self):
        return [self.CreatorID, self.InputID, self.OutputID]

    def is_valid(self, store):
        if not super(Register, self).is_valid(store):
            logger.debug('something weird happened; %s',
                         dict2json(self.dump()))
            return False

        if not self.is_permitted(store):
            logger.debug('failed permission check on offer %s', self.ObjectID)
            return False

        if not liability_update.LiabilityObject.is_valid_object(store,
                                                                self.InputID):
            logger.debug('input liability %s is not valid in offer %s ',
                         self.InputID, self.ObjectID)
            return False

        obj = liability_update.LiabilityObject.get_valid_object(store,
                                                                self.InputID)
        if not self.CreatorType.is_valid_creator(store, obj.get('creator'),
                                                 self.OriginatorID):
            logger.info('%s does not have permission to modify liability %s',
                        self.OriginatorID, self.InputID)
            return False

        if not liability_update.LiabilityObject.is_valid_object(store,
                                                                self.OutputID):
            logger.debug('output liability %s is not valid in offer %s ',
                         self.OutputID, self.ObjectID)
            return False

        obj = liability_update.LiabilityObject.get_valid_object(store,
                                                                self.OutputID)
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

        if self.Execution not in ExchangeOfferObject.ExecutionStyle:
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
    UpdateType = '/mktplace.transactions.ExchangeOfferUpdate/Unregister'
    ObjectType = ExchangeOfferObject
    CreatorType = participant_update.ParticipantObject

    def __init__(self, transaction=None, minfo={}):
        super(Unregister, self).__init__(transaction, minfo)

    def is_valid(self, store):
        if not super(Unregister, self).is_valid(store):
            return False

        if not self.is_permitted(store):
            return False

        return True

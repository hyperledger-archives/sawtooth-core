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

from journal import transaction
from sawtooth.exceptions import InvalidTransactionError

from mktplace.transactions import liability_update
from mktplace.transactions import market_place_object_update
from mktplace.transactions import participant_update
from mktplace.transactions import sell_offer_update


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

    def __init__(self, objectid=None, minfo=None):
        if minfo is None:
            minfo = {}
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


class Register(transaction.Update):
    UpdateType = 'RegisterExchangeOffer'
    ObjectType = ExchangeOfferObject
    CreatorType = participant_update.ParticipantObject

    def __init__(self,
                 update_type,
                 creator_id=None,
                 input_id=None,
                 output_id=None,
                 ratio=1.0,
                 description=None,
                 name=None,
                 minimum=1,
                 maximum=None,
                 execution=None):
        super(Register, self).__init__(update_type)

        self._creator_id = creator_id or '**UNKNOWN**'
        self._input_id = input_id or '**UNKNOWN**'
        self._output_id = output_id or '**UNKNOWN**'
        self._ratio = ratio
        self._description = description or ''
        self._name = name or ''
        self._minimum = minimum
        self._maximum = maximum or sys.maxint
        self._execution = execution or 'Any'

    @property
    def References(self):
        return [self._creator_id, self._input_id, self._output_id]

    def check_valid(self, store, txn):
        if txn.Identifier in store:
            raise InvalidTransactionError(
                "ObjectId already in store")

        if not market_place_object_update.global_is_valid_name(
                store, self._name, self.ObjectType, self._creator_id):
            raise InvalidTransactionError(
                "Name isn't valid")

        if not market_place_object_update.global_is_permitted(
                store,
                txn,
                self._creator_id,
                self.CreatorType):
            logger.debug('failed permission check on offer %s',
                         txn.Identifier)
            raise InvalidTransactionError(
                "Creator address not the same as txn.OriginatorID")

        if not liability_update.LiabilityObject.is_valid_object(
                store, self._input_id):
            logger.debug('input liability %s is not valid in offer %s ',
                         self._input_id, txn.Identifier)
            raise InvalidTransactionError(
                "InputId, {}, is not a liability".format(str(self._input_id)))

        obj = liability_update.LiabilityObject.get_valid_object(
            store, self._input_id)
        if not self.CreatorType.is_valid_creator(store, obj.get('creator'),
                                                 txn.OriginatorID):
            logger.info('%s does not have permission to modify liability %s',
                        txn.OriginatorID, self._input_id)
            raise InvalidTransactionError(
                "txn.OriginatorID is not liability creator")

        if not liability_update.LiabilityObject.is_valid_object(
                store, self._output_id):
            logger.debug('output liability %s is not valid in offer %s ',
                         self._output_id, txn.Identifier)
            raise InvalidTransactionError(
                "OutputID is not a valid liability")

        obj = liability_update.LiabilityObject.get_valid_object(
            store, self._output_id)
        if not self.CreatorType.is_valid_creator(store, obj.get('creator'),
                                                 txn.OriginatorID):
            logger.info('%s does not have permission to modify liability %s',
                        txn.OriginatorID, self._output_id)
            raise InvalidTransactionError(
                "Output Liability creator is not the same as "
                "txn.OriginatorID")

        if self._ratio <= 0:
            logger.debug('invalid ratio %s in offer %s', self._ratio,
                         txn.Identifier)
            raise InvalidTransactionError(
                "Ratio is less than or equal to 0")

        if self._minimum < 0 or self._maximum < 0 or \
                self._maximum < self._minimum:
            logger.debug('inconsistent range %s < %s in offer %s',
                         self._minimum, self._maximum, txn.Identifier)
            raise InvalidTransactionError(
                "Minimum and Maximum are inconsistent")

        if self._execution not in ExchangeOfferObject.ExecutionStyle:
            logger.debug('invalid execution style %s in offer %s',
                         self._execution, txn.Identifier)
            raise InvalidTransactionError(
                "Execution not a valid ExecutionStyle")

    def apply(self, store, txn):
        pobj = self.ObjectType(txn.Identifier)

        pobj.CreatorID = self._creator_id
        pobj.InputID = self._input_id
        pobj.OutputID = self._output_id
        pobj.Ratio = float(self._ratio)
        pobj.Description = self._description
        pobj.Name = self._name
        pobj.Minimum = self._minimum
        pobj.Maximum = self._maximum
        pobj.Execution = self._execution

        store[txn.Identifier] = pobj.dump()


class Unregister(transaction.Update):
    UpdateType = 'UnregisterExchangeOffer'
    ObjectType = ExchangeOfferObject
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
        assert self._object_id
        assert self._creator_id

        if not self.ObjectType.is_valid_object(store, self._object_id):
            raise InvalidTransactionError(
                "ObjectId does not reference an ExchangeOffer")

        if not self.CreatorType.is_valid_creator(store, self._creator_id,
                                                 txn.OriginatorID):
            raise InvalidTransactionError(
                "CreatorId address is not the same as txn.OriginatorID")

    def apply(self, store, txn):
        del store[self._object_id]


class UpdateDescription(market_place_object_update.UpdateDescription):
    UpdateType = 'UpdateExchangeOfferDescription'
    ObjectType = ExchangeOfferObject
    CreatorType = participant_update.ParticipantObject


class UpdateName(market_place_object_update.UpdateName):
    UpdateType = 'UpdateExchangeOfferName'
    ObjectType = ExchangeOfferObject
    CreatorType = participant_update.ParticipantObject

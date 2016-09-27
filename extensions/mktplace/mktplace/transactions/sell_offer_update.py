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

    def __init__(self, objectid=None, minfo=None):
        if minfo is None:
            minfo = {}
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


class Register(transaction.Update):
    UpdateType = 'RegisterSellOffer'
    ObjectType = SellOfferObject
    CreatorType = participant_update.ParticipantObject

    def __init__(self,
                 update_type,
                 input_id,
                 output_id,
                 creator_id=None,
                 ratio=1,
                 description=None,
                 name=None,
                 minimum=0,
                 maximum=None,
                 execution=None):
        super(Register, self).__init__(update_type)

        self._creator_id = creator_id or '**UNKNOWN**'
        self._input_id = input_id
        self._output_id = output_id
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
            raise InvalidTransactionError("ObjectId already in store")

        if not market_place_object_update.global_is_permitted(
                store, txn, self._creator_id, self.CreatorType):
            raise InvalidTransactionError(
                "Creator address is different from txn.OriginatorID")

        if not market_place_object_update.global_is_valid_name(
                store, self._name, self.ObjectType, self._creator_id):
            raise InvalidTransactionError(
                "Name, {}, is not valid".format(self._name))

        if not liability_update.LiabilityObject.is_valid_object(
                store, self._input_id):
            raise InvalidTransactionError(
                "{} is not a Liability".format(self._input_id))

        obj = liability_update.LiabilityObject.get_valid_object(store,
                                                                self._input_id)
        if not self.CreatorType.is_valid_creator(store, obj.get('creator'),
                                                 txn.OriginatorID):
            logger.info('%s does not have permission to modify liability %s',
                        txn.OriginatorID, self._input_id)
            raise InvalidTransactionError(
                "Txn.OriginatorID not allowed to modify liability")

        if not holding_update.HoldingObject.is_valid_object(store,
                                                            self._output_id):
            raise InvalidTransactionError(
                "OutputId is not a valid Holding")

        obj = holding_update.HoldingObject.get_valid_object(
            store, self._output_id)
        if not self.CreatorType.is_valid_creator(store, obj.get('creator'),
                                                 txn.OriginatorID):
            logger.info('%s does not have permission to modify liability %s',
                        txn.OriginatorID, self._output_id)
            raise InvalidTransactionError(
                "Txn.OriginatorID does not have permission to modify "
                "liability")

        if self._ratio <= 0:
            logger.debug('invalid ratio %s in offer %s', self._ratio,
                         txn.Identifier)
            raise InvalidTransactionError(
                "Ratio < 0")

        if self._minimum < 0 or self._maximum < 0 or \
                self._maximum < self._minimum:
            logger.debug('inconsistent range %s < %s in offer %s',
                         self._minimum, self._maximum, txn.Identifier)
            raise InvalidTransactionError(
                "Minimum and Maximum are inconsistent")
        if self._execution not in SellOfferObject.ExecutionStyle:
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
    UpdateType = 'UnregisterSellOffer'
    ObjectType = SellOfferObject
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
        if not market_place_object_update.global_is_permitted(
                store,
                txn,
                self._creator_id,
                self.CreatorType):
            raise InvalidTransactionError(
                "Creator Address not the same as txn.OriginatorID"
            )

    def apply(self, store, txn):
        del store[self._object_id]


class UpdateDescription(market_place_object_update.UpdateDescription):
    UpdateType = 'UpdateSellOfferDescription'
    ObjectType = SellOfferObject
    CreatorType = participant_update.ParticipantObject


class UpdateName(market_place_object_update.UpdateName):
    UpdateType = 'UpdateSellOfferName'
    ObjectType = SellOfferObject
    CreatorType = participant_update.ParticipantObject

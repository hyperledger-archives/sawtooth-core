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

from mktplace.transactions import holding_update, participant_update
from journal import transaction

logger = logging.getLogger(__name__)


class Payment(object):
    PaymentType = '/mktplace.transactions.Payment/Payment'
    CreatorType = participant_update.ParticipantObject

    def __init__(self, transaction=None, minfo={}):
        self.Transaction = transaction

    def __str__(self):
        return "({0}, {1}, {2})".format(self.PaymentType, self.OriginatorID,
                                        self.ObjectID)

    @property
    def OriginatorID(self):
        assert self.Transaction
        return self.Transaction.OriginatorID

    @property
    def ObjectID(self):
        assert self.Transaction
        return self.Transaction.Identifier

    def is_valid(self, store):
        return True

    def is_permitted(self, store):
        """
        Global permission check, for now only verifies that the creator id
        corresponds to the originator of the transaction.
        """
        if not self.CreatorType.is_valid_creator(store, self.CreatorID,
                                                 self.OriginatorID):
            return False

        return True

    def apply(self, store):
        pass

    def dump(self):
        result = {'PaymentType': self.PaymentType}
        return result


class PayFromHolding(Payment):
    PaymentType = '/mktplace.transactions.Payment/PayFromHolding'
    ValidationTokenAssetID = None

    def __init__(self, transaction=None, minfo={}):
        super(PayFromHolding, self).__init__(transaction, minfo)

        self.CreatorID = None
        self.HoldingID = None
        self.Count = 0

        if minfo:
            self._unpack(minfo)

    def _unpack(self, minfo):
        try:
            self.CreatorID = minfo['CreatorID']
            self.HoldingID = minfo['HoldingID']
            self.Count = int(minfo['Count'])

        except KeyError as ke:
            logger.warn('missing required payment field %s', ke)
            raise transaction.SerializationError(
                self.PaymentType,
                'missing required payment field {0}'.format(ke))

    def is_valid(self, store):
        if not super(PayFromHolding, self).is_valid(store):
            return False

        # make sure the creator listed in the payment is actualy the same as
        # the one sending the transaction
        if not self.is_permitted(store):
            logger.debug('operation not permitted')
            return False

        # make sure the holding is really a holding
        if not holding_update.HoldingObject.is_valid_object(store,
                                                            self.HoldingID):
            logger.debug('invalid holding')
            return False

        # make sure that this creator has permission to modify the holding
        obj = holding_update.HoldingObject.get_valid_object(store,
                                                            self.HoldingID)
        if not self.CreatorType.is_valid_creator(store, obj.get('creator'),
                                                 self.OriginatorID):
            logger.info('%s does not have permission to modify holding %s',
                        self.OriginatorID, self.OutputID)
            return False

        if not PayFromHolding.ValidationTokenAssetID:
            PayFromHolding.ValidationTokenAssetID = store.n2i(
                '//marketplace/asset/validation-token')
            assert PayFromHolding.ValidationTokenAssetID

        if obj['asset'] != PayFromHolding.ValidationTokenAssetID:
            logger.info('holding %s does not contain validation tokens',
                        self.HoldingID)
            return False

        # make sure that there are enough validation tokens to cover the
        # requested amount
        if obj['count'] <= self.Count:
            logger.info('insufficient validation tokens in holding %s; %s',
                        self.HoldingID, obj['count'])
            return False

        return True

    def apply(self, store):
        obj = holding_update.HoldingObject.get_valid_object(store,
                                                            self.HoldingID)

        obj['count'] = int(obj['count']) - int(self.Count)
        assert 0 <= obj['count']

        store[self.HoldingID] = obj

    def dump(self):
        result = super(PayFromHolding, self).dump()

        result['CreatorID'] = self.CreatorID
        result['HoldingID'] = self.HoldingID
        result['Count'] = int(self.Count)

        return result

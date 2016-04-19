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


class IncentiveUpdate(object):
    UpdateType = '/mktplace.transactions.IncentiveUpdate/IncentiveUpdate'
    CreatorType = participant_update.ParticipantObject
    ValidationTokenAssetID = None

    def __init__(self, transaction=None, minfo={}):

        self.Transaction = transaction

        self.HoldingID = None
        self.Count = 0

        if minfo:
            self._unpack(minfo)

    def _unpack(self, minfo):
        try:
            self.HoldingID = minfo['HoldingID']
            self.Count = int(minfo['Count'])

        except KeyError as ke:
            logger.warn('missing incentive field %s', ke)
            raise transaction.SerializationError(
                self.PaymentType,
                'missing required incentive field {0}'.format(ke))

    @property
    def OriginatorID(self):
        assert self.Transaction
        return self.Transaction.OriginatorID

    @property
    def ObjectID(self):
        assert self.Transaction
        return self.Transaction.Identifier

    @property
    def References(self):
        return [self.CreatorID, self.AccountID, self.AssetTypeID,
                self.GuarantorID]

    def is_valid(self, store):
        # make sure the holding is really a holding
        if not holding_update.HoldingObject.is_valid_object(store,
                                                            self.HoldingID):
            return False

        # We don't need to check for any permissions since we are adding
        # tokens to a holding

        # Make sure the holding contains validation token assets, this will
        # require getting access to the token type, probably by name (ugghhh)
        if not IncentiveUpdate.ValidationTokenAssetID:
            IncentiveUpdate.ValidationTokenAssetID = store.n2i(
                '//marketplace/asset/validation-token')
            assert IncentiveUpdate.ValidationTokenAssetID

        obj = holding_update.HoldingObject.get_valid_object(store,
                                                            self.HoldingID)
        if obj.get('asset') != IncentiveUpdate.ValidationTokenAssetID:
            logger.info('holding %s does not contain validation tokens',
                        self.HoldingID)
            return False

        return True

    def apply(self, store):
        obj = holding_update.HoldingObject.get_valid_object(store,
                                                            self.HoldingID)
        obj['count'] = int(obj['count']) + int(self.Count)

        store[self.HoldingID] = obj

    def dump(self):
        result = {
            'UpdateType': self.UpdateType,
            'HoldingID': self.HoldingID,
            'Count': int(self.Count)
        }
        return result

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

from sawtooth.exceptions import InvalidTransactionError
from mktplace.transactions import holding_update, participant_update
from journal import transaction

logger = logging.getLogger(__name__)


class IncentiveUpdate(transaction.Update):
    UpdateType = 'IncentiveUpdate'
    CreatorType = participant_update.ParticipantObject
    ValidationTokenAssetID = None

    def __init__(self,
                 update_type,
                 holding_id,
                 count,
                 account_id,
                 asset_type_id,
                 guarantor_id,
                 creator_id):
        super(IncentiveUpdate, self).__init__(update_type)
        self._holding_id = holding_id
        self._count = count
        self._account_id = account_id
        self._asset_type_id = asset_type_id
        self._guarantor_id = guarantor_id
        self._creator_id = creator_id

    @property
    def References(self):
        return [self._creator_id, self._account_id, self._asset_type_id,
                self._guarantor_id]

    def check_valid(self, store, txn):
        # make sure the holding is really a holding
        if not holding_update.HoldingObject.is_valid_object(store,
                                                            self._holding_id):
            raise InvalidTransactionError(
                "HoldingId does not reference a holding")

        # We don't need to check for any permissions since we are adding
        # tokens to a holding

        # Make sure the holding contains validation token assets, this will
        # require getting access to the token type, probably by name (ugghhh)
        if not IncentiveUpdate.ValidationTokenAssetID:
            IncentiveUpdate.ValidationTokenAssetID = store.n2i(
                '//marketplace/asset/validation-token', 'Asset')
            assert IncentiveUpdate.ValidationTokenAssetID

        obj = holding_update.HoldingObject.get_valid_object(store,
                                                            self._holding_id)
        if obj.get('asset') != IncentiveUpdate.ValidationTokenAssetID:
            logger.info('holding %s does not contain validation tokens',
                        self._holding_id)
            raise InvalidTransactionError(
                "Holding {} does not contain validation "
                "tokens".format(self._holding_id))

    def apply(self, store, txn):
        obj = holding_update.HoldingObject.get_valid_object(store,
                                                            self._holding_id)
        obj['count'] = int(obj['count']) + int(self._count)

        store[self._holding_id] = obj

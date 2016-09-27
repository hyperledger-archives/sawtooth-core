# Copyright 2016 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ------------------------------------------------------------------------------

import unittest

from mktplace.transactions import participant_update
from mktplace.transactions import holding_update
from mktplace.transactions.market_place import MarketPlaceGlobalStore
from mktplace.transactions import market_place_object_update


class TestHoldingUpdate(unittest.TestCase):
    def test_duplicate_name(self):
        # Create a mock store and put a participant in it
        participant = participant_update.ParticipantObject(
            participantid='0000000000000000',
            minfo={
                'name': 'participant',
            })
        store = MarketPlaceGlobalStore()
        store[participant.ObjectID] = participant.dump()

        # Because we have not "registered" any holdings, the name
        # should not be a duplicate
        update = holding_update.Register(
            update_type=holding_update.Register.UpdateType,
            creator_id=participant.ObjectID,
            name='/holding'
        )
        self.assertTrue(market_place_object_update.global_is_valid_name(
            store,
            name='/holding',
            object_type=update.ObjectType,
            creator_id=participant.ObjectID,
        ))

        # Add a holding to the store with the creator being the participant
        # we inserted initially
        holding = holding_update.HoldingObject(
            objectid='0000000000000001',
            minfo={
                'name': '//participant/holding',
                'creator': participant.ObjectID
            })
        store[holding.ObjectID] = holding.dump()

        # Because the holding name is in the store, trying to register using
        # a relative name based upon creator and a fully-qualified name should
        # not be a valid name as it is a duplicate
        update = holding_update.Register(
            update_type=holding_update.Register.UpdateType,
            creator_id=participant.ObjectID,
            name='/holding'
        )
        self.assertFalse(market_place_object_update.global_is_valid_name(
            store,
            name='/holding',
            object_type=update.ObjectType,
            creator_id=participant.ObjectID
        ))
        update = holding_update.Register(
            update_type=holding_update.Register.UpdateType,
            creator_id=participant.ObjectID,
            name='//participant/holding'
        )
        self.assertFalse(market_place_object_update.global_is_valid_name(
            store,
            name='//participant/holding',
            object_type=update.ObjectType,
            creator_id=participant.ObjectID
        ))


class TestHoldingUpdateName(unittest.TestCase):
    def test_duplicate_name(self):
        # Create a mock store and put a participant in it
        participant = participant_update.ParticipantObject(
            participantid='0000000000000000',
            minfo={
                'name': 'participant',
            })
        store = MarketPlaceGlobalStore()
        store[participant.ObjectID] = participant.dump()

        # Because we have not "registered" any holdings, the name
        # should not be a duplicate
        update = holding_update.UpdateName(
            update_type=holding_update.UpdateName.UpdateType,
            object_id='0000000000000001',
            creator_id=participant.ObjectID,
            name='/holding'
        )
        self.assertTrue(update.is_valid_name(store))

        # Add a holding to the store with the creator being the participant
        # we inserted initially
        holding = holding_update.HoldingObject(
            objectid='0000000000000001',
            minfo={
                'name': '//participant/holding',
                'creator': participant.ObjectID
            })
        store[holding.ObjectID] = holding.dump()

        # Because the holding name is in the store, trying to update the name
        # using a relative name based upon creator and a fully-qualified name
        # should not be a valid name as it is a duplicate
        update = holding_update.UpdateName(
            update_type=holding_update.UpdateName.UpdateType,
            object_id=holding.ObjectID,
            creator_id=participant.ObjectID,
            name='/holding'
        )
        self.assertFalse(update.is_valid_name(store))
        update = holding_update.UpdateName(
            update_type=holding_update.UpdateName.UpdateType,
            object_id=holding.ObjectID,
            creator_id=participant.ObjectID,
            name='//participant/holding'
        )
        self.assertFalse(update.is_valid_name(store))

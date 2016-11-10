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
from mktplace.transactions import liability_update
from mktplace.transactions.market_place import MarketPlaceGlobalStore
from mktplace.transactions.market_place_object_update import \
    global_is_valid_name


class TestLiabilityUpdate(unittest.TestCase):
    def test_duplicate_name(self):
        # Create a mock store and put a participant in it
        participant = participant_update.ParticipantObject(
            participantid='0000000000000000',
            minfo={
                'name': 'participant',
            })
        store = MarketPlaceGlobalStore()
        store[participant.ObjectID] = participant.dump()

        # Because we have not "registered" any liabilities, the name
        # should not be a duplicate
        update = liability_update.Register(
            update_type=liability_update.Register.UpdateType,
            creator_id=participant.ObjectID,
            name='/liability'
        )
        self.assertTrue(global_is_valid_name(
            store, '/liability',
            liability_update.Register.ObjectType,
            participant.ObjectID))

        # Add a liability to the store with the creator being the participant
        # we inserted initially
        liability = liability_update.LiabilityObject(
            objectid='0000000000000001',
            minfo={
                'name': '//participant/liability',
                'creator': participant.ObjectID
            })
        store[liability.ObjectID] = liability.dump()

        # Because the liability name is in the store, trying to register using
        # a relative name based upon creator and a fully-qualified name should
        # not be a valid name as it is a duplicate
        update = liability_update.Register(
            update_type=liability_update.Register.UpdateType,
            creator_id=participant.ObjectID,
            name='/liability'
        )
        self.assertFalse(global_is_valid_name(
            store, '/liability',
            liability_update.Register.ObjectType,
            participant.ObjectID))

        update = liability_update.Register(
            update_type=liability_update.Register.UpdateType,
            creator_id=participant.ObjectID,
            name='//participant/liability'
        )
        self.assertFalse(global_is_valid_name(
            store, '//participant/liability',
            liability_update.Register.ObjectType,
            participant.ObjectID))


class TestLiabilityUpdateName(unittest.TestCase):
    def test_duplicate_name(self):
        # Create a mock store and put a participant in it
        participant = participant_update.ParticipantObject(
            participantid='0000000000000000',
            minfo={
                'name': 'participant',
            })
        store = MarketPlaceGlobalStore()
        store[participant.ObjectID] = participant.dump()

        # Because we have not "registered" any liabilities, the name
        # should not be a duplicate
        update = liability_update.UpdateName(
            update_type=liability_update.UpdateName.UpdateType,
            object_id='0000000000000001',
            creator_id=participant.ObjectID,
            name='/liability'
        )
        self.assertTrue(update.is_valid_name(store))

        # Add a liability to the store with the creator being the participant
        # we inserted initially
        liability = liability_update.LiabilityObject(
            objectid='0000000000000001',
            minfo={
                'name': '//participant/liability',
                'creator': participant.ObjectID
            })
        store[liability.ObjectID] = liability.dump()

        # Because the liability name is in the store, trying to update the name
        # using a relative name based upon creator and a fully-qualified name
        # should not be a valid name as it is a duplicate
        update = liability_update.UpdateName(
            update_type=liability_update.UpdateName.UpdateType,
            object_id=liability.ObjectID,
            creator_id=participant.ObjectID,
            name='/liability'
        )
        self.assertFalse(update.is_valid_name(store))
        update = liability_update.UpdateName(
            update_type=liability_update.UpdateName.UpdateType,
            object_id=liability.ObjectID,
            creator_id=participant.ObjectID,
            name='//participant/liability'
        )
        self.assertFalse(update.is_valid_name(store))

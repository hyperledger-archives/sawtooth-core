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
from mktplace.transactions import sell_offer_update
from mktplace.transactions.market_place import MarketPlaceGlobalStore
from mktplace.transactions import market_place_object_update


class TestSellOfferUpdate(unittest.TestCase):
    def test_duplicate_name(self):
        # Create a mock store and put a participant in it
        participant = participant_update.ParticipantObject(
            participantid='0000000000000000',
            minfo={
                'name': 'participant',
            })
        store = MarketPlaceGlobalStore()
        store[participant.ObjectID] = participant.dump()

        # Because we have not "registered" any sell offers, the name
        # should not be a duplicate
        update = sell_offer_update.Register(
            input_id='**FAKE**',
            output_id='**FAKE**',
            update_type=sell_offer_update.Register.UpdateType,
            creator_id=participant.ObjectID,
            name='/selloffer'
        )
        self.assertTrue(market_place_object_update.global_is_valid_name(
            store, '/selloffer', sell_offer_update.Register.ObjectType,
            participant.ObjectID))

        # Add a sell offer to the store with the creator being the participant
        # we inserted initially
        sell_offer = sell_offer_update.SellOfferObject(
            objectid='0000000000000001',
            minfo={
                'name': '//participant/selloffer',
                'creator': participant.ObjectID
            })
        store[sell_offer.ObjectID] = sell_offer.dump()

        # Because the sell offer name is in the store, trying to register
        # using a relative name based upon creator and a fully-qualified name
        # should not be a valid name as it is a duplicate
        update = sell_offer_update.Register(
            input_id='**FAKE**',
            output_id='**FAKE**',
            update_type=sell_offer_update.Register,
            creator_id=participant.ObjectID,
            name='/selloffer'
        )
        self.assertFalse(market_place_object_update.global_is_valid_name(
            store, '/selloffer', sell_offer_update.Register.ObjectType,
            participant.ObjectID))
        update = sell_offer_update.Register(
            update_type=sell_offer_update.Register.UpdateType,
            input_id='**FAKE**',
            output_id='**FAKE**',
            creator_id=participant.ObjectID,
            name='//participant/selloffer'
        )
        self.assertFalse(market_place_object_update.global_is_valid_name(
            store, '//participant/selloffer',
            sell_offer_update.Register.ObjectType,
            participant.ObjectID))


class TestSellOfferUpdateName(unittest.TestCase):
    def test_duplicate_name(self):
        # Create a mock store and put a participant in it
        participant = participant_update.ParticipantObject(
            participantid='0000000000000000',
            minfo={
                'name': 'participant',
            })
        store = MarketPlaceGlobalStore()
        store[participant.ObjectID] = participant.dump()

        # Because we have not "registered" any sell offers, the name
        # should not be a duplicate
        update = sell_offer_update.UpdateName(
            update_type=sell_offer_update.UpdateName.UpdateType,
            object_id='0000000000000001',
            creator_id=participant.ObjectID,
            name='/selloffer'
        )
        self.assertTrue(update.is_valid_name(store))

        # Add a sell offer to the store with the creator being the participant
        # we inserted initially
        sell_offer = sell_offer_update.SellOfferObject(
            objectid='0000000000000001',
            minfo={
                'name': '//participant/selloffer',
                'creator': participant.ObjectID
            })
        store[sell_offer.ObjectID] = sell_offer.dump()

        # Because the sell offer name is in the store, trying to update the
        # name using a relative name based upon creator and a fully-qualified
        # name should not be a valid name as it is a duplicate
        update = sell_offer_update.UpdateName(
            update_type=sell_offer_update.UpdateName.UpdateType,
            object_id=sell_offer.ObjectID,
            creator_id=participant.ObjectID,
            name='/selloffer'
        )
        self.assertFalse(update.is_valid_name(store))
        update = sell_offer_update.UpdateName(
            update_type=sell_offer_update.UpdateName.UpdateType,
            object_id=sell_offer.ObjectID,
            creator_id=participant.ObjectID,
            name='//participant/selloffer'
        )
        self.assertFalse(update.is_valid_name(store))

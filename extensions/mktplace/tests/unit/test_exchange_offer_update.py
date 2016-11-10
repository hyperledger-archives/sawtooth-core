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
from mktplace.transactions import exchange_offer_update
from mktplace.transactions.market_place import MarketPlaceGlobalStore
from mktplace.transactions import market_place_object_update


class TestExchangeOfferUpdate(unittest.TestCase):
    def test_duplicate_name(self):
        # Create a mock store and put a participant in it
        participant = participant_update.ParticipantObject(
            participantid='0000000000000000',
            minfo={
                'name': 'participant',
            })
        store = MarketPlaceGlobalStore()
        store[participant.ObjectID] = participant.dump()

        # Because we have not "registered" any accounts, the name
        # should not be a duplicate
        update = exchange_offer_update.Register(
            update_type=exchange_offer_update.Register.UpdateType,
            creator_id=participant.ObjectID,
            name='/exchangeoffer')
        self.assertTrue(market_place_object_update.global_is_valid_name(
            store,
            name='/exchangeoffer',
            object_type=update.ObjectType,
            creator_id=participant.ObjectID))

        # Add an exchange offer to the store with the creator being the
        # participant we inserted initially
        exchange_offer = exchange_offer_update.ExchangeOfferObject(
            objectid='0000000000000001',
            minfo={
                'name': '//participant/exchangeoffer',
                'creator': participant.ObjectID
            })
        store[exchange_offer.ObjectID] = exchange_offer.dump()

        # Because the account name is in the store, trying to register using
        # a relative name based upon creator and a fully-qualified name should
        # not be a valid name as it is a duplicate
        update = exchange_offer_update.Register(
            update_type=exchange_offer_update.Register.UpdateType,
            creator_id=participant.ObjectID,
            name='/exchangeoffer'
        )
        self.assertFalse(market_place_object_update.global_is_valid_name(
            store,
            name='/exchangeoffer',
            object_type=update.ObjectType,
            creator_id=participant.ObjectID))

        update = exchange_offer_update.Register(
            update_type=exchange_offer_update.Register.UpdateType,
            creator_id=participant.ObjectID,
            name='//participant/exchangeoffer'
        )
        self.assertFalse(market_place_object_update.global_is_valid_name(
            store,
            name='//participant/exchangeoffer',
            object_type=update.ObjectType,
            creator_id=participant.ObjectID))


class TestExchangeOfferUpdateName(unittest.TestCase):
    def test_duplicate_name(self):
        # Create a mock store and put a participant in it
        participant = participant_update.ParticipantObject(
            participantid='0000000000000000',
            minfo={
                'name': 'participant',
            })
        store = MarketPlaceGlobalStore()
        store[participant.ObjectID] = participant.dump()

        # Because we have not "registered" any exchange offers, the name
        # should not be a duplicate
        update = exchange_offer_update.UpdateName(
            update_type=exchange_offer_update.UpdateName.UpdateType,
            object_id='0000000000000001',
            creator_id=participant.ObjectID,
            name='/exchangeoffer'
        )
        self.assertTrue(update.is_valid_name(store))

        # Add an exchange offer to the store with the creator being the
        # participant we inserted initially
        exchange_offer = exchange_offer_update.ExchangeOfferObject(
            objectid='0000000000000001',
            minfo={
                'name': '//participant/exchangeoffer',
                'creator': participant.ObjectID
            })
        store[exchange_offer.ObjectID] = exchange_offer.dump()

        # Because the exchange offer name is in the store, trying to update
        # the name using a relative name based upon creator and a fully-
        # qualified name should not be a valid name as it is a duplicate
        update = exchange_offer_update.UpdateName(
            update_type=exchange_offer_update.UpdateName.UpdateType,
            object_id=exchange_offer.ObjectID,
            creator_id=participant.ObjectID,
            name='/exchangeoffer'
        )
        self.assertFalse(update.is_valid_name(store))
        update = exchange_offer_update.UpdateName(
            update_type=exchange_offer_update.UpdateName.UpdateType,
            object_id=exchange_offer.ObjectID,
            creator_id=participant.ObjectID,
            name='//participant/exchangeoffer'
        )
        self.assertFalse(update.is_valid_name(store))

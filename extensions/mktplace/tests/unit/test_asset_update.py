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
from mktplace.transactions import asset_update
from mktplace.transactions.market_place import MarketPlaceGlobalStore
from mktplace.transactions.market_place_object_update import \
    global_is_valid_name


class TestAssetUpdate(unittest.TestCase):
    def test_duplicate_name(self):
        # Create a mock store and put a participant in it
        participant = participant_update.ParticipantObject(
            participantid='0000000000000000',
            minfo={
                'name': 'participant',
            })
        store = MarketPlaceGlobalStore()
        store[participant.ObjectID] = participant.dump()

        # Because we have not "registered" any assets, the name
        # should not be a duplicate
        update = asset_update.Register(
            update_type=asset_update.Register.UpdateType,
            creator_id=participant.ObjectID,
            name='/asset'
        )
        self.assertTrue(global_is_valid_name(
            store, '/asset',
            asset_update.Register.ObjectType,
            participant.ObjectID))

        # Add an asset to the store with the creator being the participant
        # we inserted initially
        asset = asset_update.AssetObject(
            objectid='0000000000000001',
            minfo={
                'name': '//participant/asset',
                'creator': participant.ObjectID
            })
        store[asset.ObjectID] = asset.dump()

        # Because the asset name is in the store, trying to register using
        # a relative name based upon creator and a fully-qualified name should
        # not be a valid name as it is a duplicate
        update = asset_update.Register(
            update_type=asset_update.Register.UpdateType,
            creator_id=participant.ObjectID,
            name='/asset'
        )
        self.assertFalse(global_is_valid_name(
            store, '/asset',
            asset_update.Register.ObjectType,
            participant.ObjectID))

        update = asset_update.Register(
            update_type=asset_update.Register.UpdateType,
            creator_id=participant.ObjectID,
            name='//participant/asset'
        )
        self.assertFalse(global_is_valid_name(
            store, '//participant/asset',
            asset_update.Register.ObjectType,
            participant.ObjectID))


class TestAssetUpdateName(unittest.TestCase):
    def test_duplicate_name(self):
        # Create a mock store and put a participant in it
        participant = participant_update.ParticipantObject(
            participantid='0000000000000000',
            minfo={
                'name': 'participant',
            })
        store = MarketPlaceGlobalStore()
        store[participant.ObjectID] = participant.dump()

        # Because we have not "registered" any asset2, the name
        # should not be a duplicate
        update = asset_update.UpdateName(
            update_type=asset_update.UpdateName.UpdateType,
            object_id='0000000000000001',
            creator_id=participant.ObjectID,
            name='/asset'
        )
        self.assertTrue(update.is_valid_name(store))

        # Add an asset to the store with the creator being the participant
        # we inserted initially
        asset = asset_update.AssetObject(
            objectid='0000000000000001',
            minfo={
                'name': '//participant/asset',
                'creator': participant.ObjectID
            })
        store[asset.ObjectID] = asset.dump()

        # Because the asset name is in the store, trying to update the name
        # using a relative name based upon creator and a fully-qualified name
        # should not be a valid name as it is a duplicate
        update = asset_update.UpdateName(
            update_type=asset_update.UpdateName.UpdateType,
            object_id=asset.ObjectID,
            creator_id=participant.ObjectID,
            name='/asset'
        )
        self.assertFalse(update.is_valid_name(store))
        update = asset_update.UpdateName(
            update_type=asset_update.UpdateName.UpdateType,
            object_id=asset.ObjectID,
            creator_id=participant.ObjectID,
            name='//participant/asset'
        )
        self.assertFalse(update.is_valid_name(store))

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
from unit.mock_market_place_global_store import MockMarketPlaceGlobalStore


class TestParticipantUpdate(unittest.TestCase):
    def test_duplicate_name(self):
        # Create a mock store
        store = MockMarketPlaceGlobalStore()

        # Because we have not "registered" any participants, the name
        # should not be a duplicate
        update = participant_update.Register(
            minfo={
                'Name': 'participant'
            })
        self.assertTrue(update.is_valid_name(store))

        #  Put a participant in the store
        participant = participant_update.ParticipantObject(
            participantid='0000000000000000',
            minfo={
                'name': 'participant',
            })
        store[participant.ObjectID] = participant.dump()
        store.bind(store.i2n(participant.ObjectID), participant.ObjectID)

        # Because the participant name is in the store, the name should
        # not be a valid name as it is a duplicate
        update = participant_update.Register(
            minfo={
                'Name': 'participant'
            })
        self.assertFalse(update.is_valid_name(store))


class TestParticipantUpdateName(unittest.TestCase):
    def test_duplicate_name(self):
        # Create a mock store
        store = MockMarketPlaceGlobalStore()

        # Because we have not "registered" any participants, the name
        # should not be a duplicate
        update = participant_update.UpdateName(
            minfo={
                'ObjectID': '0000000000000000',
                'CreatorID': '0000000000000000',
                'Name': 'participant'
            })
        self.assertTrue(update.is_valid_name(store))

        # Put a participant in the store
        participant = participant_update.ParticipantObject(
            participantid='0000000000000000',
            minfo={
                'name': 'participant',
            })
        store = MockMarketPlaceGlobalStore()
        store[participant.ObjectID] = participant.dump()
        store.bind(store.i2n(participant.ObjectID), participant.ObjectID)

        # Because the participant name is in the store, trying to update the
        # name a valid name as it is a duplicate
        update = participant_update.UpdateName(
            minfo={
                'ObjectID': participant.ObjectID,
                'CreatorID': participant.ObjectID,
                'Name': 'participant'
            })
        self.assertFalse(update.is_valid_name(store))

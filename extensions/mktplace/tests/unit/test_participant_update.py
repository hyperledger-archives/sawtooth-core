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
from mktplace.transactions.market_place import MarketPlaceGlobalStore


class TestParticipantUpdate(unittest.TestCase):
    def test_duplicate_name(self):
        # Create a mock store
        store = MarketPlaceGlobalStore()

        # Because we have not "registered" any participants, the name
        # should not be a duplicate
        update = participant_update.Register(
            update_type=participant_update.Register.UpdateType,
            name='participant'
        )
        self.assertTrue(update.is_valid_name(store))

        #  Put a participant in the store
        participant = participant_update.ParticipantObject(
            participantid='0000000000000000',
            minfo={
                'name': 'participant',
            })
        store[participant.ObjectID] = participant.dump()

        # Because the participant name is in the store, the name should
        # not be a valid name as it is a duplicate
        update = participant_update.Register(
            update_type=participant_update.Register.UpdateType,
            name='participant'
        )
        self.assertFalse(update.is_valid_name(store))


class TestParticipantUpdateName(unittest.TestCase):
    def test_duplicate_name(self):
        # Create a mock store
        store = MarketPlaceGlobalStore()

        # Because we have not "registered" any participants, the name
        # should not be a duplicate
        update = participant_update.UpdateName(
            update_type=participant_update.UpdateName.UpdateType,
            object_id='0000000000000000',
            creator_id='0000000000000000',
            name='participant'
        )
        self.assertTrue(update.is_valid_name(store))

        # Put a participant in the store
        participant = participant_update.ParticipantObject(
            participantid='0000000000000000',
            minfo={
                'name': 'participant',
            })
        store = MarketPlaceGlobalStore()
        store[participant.ObjectID] = participant.dump()

        # Because the participant name is in the store, trying to update the
        # name a valid name as it is a duplicate
        update = participant_update.UpdateName(
            update_type=participant_update.UpdateName.UpdateType,
            object_id=participant.ObjectID,
            creator_id=participant.ObjectID,
            name='participant'
        )
        self.assertFalse(update.is_valid_name(store))

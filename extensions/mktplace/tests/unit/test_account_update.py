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
from mktplace.transactions import account_update
from mktplace.transactions.market_place import MarketPlaceGlobalStore


class TestAccountUpdate(unittest.TestCase):
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
        update = account_update.Register(
            minfo={
                'CreatorID': participant.ObjectID,
                'Name': '/account'
            })
        self.assertTrue(update.is_valid_name(store))

        # Add an account to the store with the creator being the participant
        # we inserted initially
        account = account_update.AccountObject(
            objectid='0000000000000001',
            minfo={
                'name': '//participant/account',
                'creator': participant.ObjectID
            })
        store[account.ObjectID] = account.dump()

        # Because the account name is in the store, trying to register using
        # a relative name based upon creator and a fully-qualified name should
        # not be a valid name as it is a duplicate
        update = account_update.Register(
            minfo={
                'CreatorID': participant.ObjectID,
                'Name': '/account'
            })
        self.assertFalse(update.is_valid_name(store))
        update = account_update.Register(
            minfo={
                'CreatorID': participant.ObjectID,
                'Name': '//participant/account'
            })
        self.assertFalse(update.is_valid_name(store))


class TestAccountUpdateName(unittest.TestCase):
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
        update = account_update.UpdateName(
            minfo={
                'ObjectID': '0000000000000001',
                'CreatorID': participant.ObjectID,
                'Name': '/account'
            })
        self.assertTrue(update.is_valid_name(store))

        # Add an account to the store with the creator being the participant
        # we inserted initially
        account = account_update.AccountObject(
            objectid='0000000000000001',
            minfo={
                'name': '//participant/account',
                'creator': participant.ObjectID
            })
        store[account.ObjectID] = account.dump()

        # Because the account name is in the store, trying to update the name
        # using a relative name based upon creator and a fully-qualified name
        # should not be a valid name as it is a duplicate
        update = account_update.UpdateName(
            minfo={
                'ObjectID': account.ObjectID,
                'CreatorID': participant.ObjectID,
                'Name': '/account'
            })
        self.assertFalse(update.is_valid_name(store))
        update = account_update.UpdateName(
            minfo={
                'ObjectID': account.ObjectID,
                'CreatorID': participant.ObjectID,
                'Name': '//participant/account'
            })
        self.assertFalse(update.is_valid_name(store))

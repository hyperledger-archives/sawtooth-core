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

import unittest
import time

from gossip import signed_object
from journal.object_store import ObjectStore
from sawtooth_bond.txn_family import BondTransaction
from sawtooth_bond.updates.identity import CreateParticipantUpdate
from sawtooth.exceptions import InvalidTransactionError


class TestCreateQuoteUpdate(unittest.TestCase):

    def setUp(self):
        self.key = signed_object.generate_signing_key()
        participant = CreateParticipantUpdate("CreateParticipant", "testuser")
        object_id = participant._object_id
        transaction = BondTransaction({})
        transaction._updates = [participant]
        self.store = ObjectStore()
        transaction.sign_object(self.key)
        transaction.check_valid(self.store)
        transaction.apply(self.store)
        sub = self.store.lookup("participant:username",
                                "testuser")["object-id"]

        transaction = BondTransaction({
            'Updates': [{
                'UpdateType': 'Clock',
                'Blocknum': 0,
                'PreviousBlockId': 0,
                'Timestamp': time.time()
            }]
        })
        transaction.sign_object(self.key)
        transaction.check_valid(self.store)
        transaction.apply(self.store)

        transaction = BondTransaction({
            "UpdateType": "CreateOrganization",
            'Updates': [{"UpdateType": "CreateOrganization",
                         "name": "Test Bank",
                         "ticker": "T",
                         "pricing_source": "ABCD",
                         "industry": "Test",
                         "authorization": [{"ParticipantId": sub,
                                            "Role": "marketmaker"}]
                         }]
        })
        transaction.sign_object(self.key)
        transaction.check_valid(self.store)
        transaction.apply(self.store)

        transaction = BondTransaction({
            "UpdateType": "CreateBond",
            'Updates': [{
                "UpdateType": "CreateBond",
                "amount_outstanding": 42671000000,
                'corporate_debt_ratings': {
                    "Fitch": "AAA",
                    "Moodys": "AAA",
                    "S&P": "AA+"},
                "coupon_rate": 1.375,
                "coupon_type": "Fixed",
                "coupon_frequency": "Quarterly",
                "cusip": "912828R77",
                "face_value": 1000,
                "isin": "US912828R770",
                "first_settlement_date": "01/11/2012",
                "first_coupon_date": "03/01/2012",
                "maturity_date": "01/11/2022",
                "issuer": "T"
            }]
        })
        transaction.sign_object(self.key)
        transaction.check_valid(self.store)
        transaction.apply(self.store)

    def test_create_quote_valid(self):
        transaction = BondTransaction({
            "UpdateType": "CreateQuote",
            'Updates': [{
                "UpdateType": "CreateQuote",
                "Firm": "ABCD",
                "Isin": "US912828R770",
                "BidPrice": "98-05.875",
                "BidQty": 25000,
                "AskPrice": "98-06.875",
                "AskQty": 25000
            }]
        })
        try:
            transaction.sign_object(self.key)
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should be valid")

        transaction = BondTransaction({
            "UpdateType": "CreateQuote",
            'Updates': [{
                "UpdateType": "CreateQuote",
                "Firm": "ABCD",
                "Cusip": "912828R77",
                "BidPrice": "98-05.875",
                "BidQty": 24000,
                "AskPrice": "98-06.875",
                "AskQty": 24000
            }]
        })
        try:
            transaction.sign_object(self.key)
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should be valid")

        transaction = BondTransaction({
            "UpdateType": "CreateQuote",
            'Updates': [{
                "UpdateType": "CreateQuote",
                "Firm": "ABCD",
                "Cusip": "912828R77",
                "Isin": "US912828R770",
                "BidPrice": "98-05.875",
                "BidQty": 23000,
                "AskPrice": "98-06.875",
                "AskQty": 23000
            }]
        })
        try:
            transaction.sign_object(self.key)
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should be valid")

    def test_create_quote_object_id(self):
        org = self.store.lookup("organization:name", "Test Bank")
        transaction = BondTransaction({
            "UpdateType": "CreateQuote",
            'Updates': [{
                "UpdateType": "CreateQuote",
                "Firm": "ABCD",
                "Isin": "US912828R770",
                "BidPrice": "98-05.875",
                "BidQty": 25000,
                "AskPrice": "98-06.875",
                "AskQty": 25000,
                "ObjectId": org["object-id"]

            }]
        })
        transaction.sign_object(self.key)

        try:
            transaction.check_valid(self.store)
            self.fail("Object id already exists")
        except InvalidTransactionError:
            pass

    def test_create_quote_bond(self):
        transaction = BondTransaction({
            "UpdateType": "CreateQuote",
            'Updates': [{
                "UpdateType": "CreateQuote",
                "Firm": "ABCD",
                "BidPrice": "98-05.875",
                "BidQty": 25000,
                "AskPrice": "98-06.875",
                "AskQty": 25000
            }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            self.fail("No Bond ")
        except InvalidTransactionError:
            pass

    def test_create_quote_diff_bond(self):
        transaction = BondTransaction({
            "UpdateType": "CreateQuote",
            'Updates': [{
                "UpdateType": "CreateQuote",
                "Firm": "ABCD",
                "Isin": "US912828R770",
                "Cusip": "912828R7",
                "BidPrice": "98-05.875",
                "BidQty": 25000,
                "AskPrice": "98-06.875",
                "AskQty": 25000
            }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            self.fail("No Cusip given does not point to correct bond ")
        except InvalidTransactionError:
            pass

    def test_create_quote_bad_firm(self):
        transaction = BondTransaction({
            "UpdateType": "CreateQuote",
            'Updates': [{
                "UpdateType": "CreateQuote",
                "Firm": "ABD",
                "Isin": "US912828R770",
                "BidPrice": "98-05.875",
                "BidQty": 25000,
                "AskPrice": "98-06.875",
                "AskQty": 25000
            }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            self.fail("Incorrect Organization")
        except InvalidTransactionError:
            pass

    def test_create_quote_diff_submitted(self):
        key = signed_object.generate_signing_key()
        transaction = BondTransaction({
            "UpdateType": "CreateQuote",
            'Updates': [{
                "UpdateType": "CreateQuote",
                "Firm": "ABCD",
                "Isin": "US912828R770",
                "BidPrice": "98-05.875",
                "BidQty": 25000,
                "AskPrice": "98-06.875",
                "AskQty": 25000
            }]
        })
        transaction.sign_object(key)
        try:
            transaction.check_valid(self.store)
            self.fail("Signed by an unauthorized participant")
        except InvalidTransactionError:
            pass

        transaction = BondTransaction({
            "UpdateType": "CreateOrganization",
            'Updates': [{"UpdateType": "CreateOrganization",
                         "name": "NewBank",
                         "ticker": "F",
                         "pricing_source": "EFGH",
                         "industry": "Test",
                         "authorization": []
                         }]
        })
        transaction.sign_object(self.key)
        transaction.check_valid(self.store)
        transaction.apply(self.store)

        key = signed_object.generate_signing_key()
        transaction = BondTransaction({
            "UpdateType": "CreateQuote",
            'Updates': [{
                "UpdateType": "CreateQuote",
                "Firm": "EFGH",
                "Isin": "US912828R770",
                "BidPrice": "98-05.875",
                "BidQty": 25000,
                "AskPrice": "98-06.875",
                "AskQty": 25000
            }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            self.fail("Signed by an unauthorized participant")
        except InvalidTransactionError:
            pass

    def test_create_quote_ref_count(self):
        transaction = BondTransaction({
            "UpdateType": "CreateQuote",
            'Updates': [{
                "UpdateType": "CreateQuote",
                "Firm": "ABCD",
                "Cusip": "912828R77",
                "BidPrice": "98-05.875",
                "BidQty": 24000,
                "AskPrice": "98-06.875",
                "AskQty": 24000
            }]
        })
        try:
            transaction.sign_object(self.key)
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should be valid")

        firm = self.store.lookup("organization:pricing-source", "ABCD")
        self.assertEquals(firm["ref-count"], 2)


class TestDeleteQuoteUpdate(unittest.TestCase):

    def setUp(self):
        self.key = signed_object.generate_signing_key()
        participant = CreateParticipantUpdate("CreateParticipant", "testuser")
        object_id = participant._object_id
        transaction = BondTransaction({})
        transaction._updates = [participant]
        self.store = ObjectStore()
        transaction.sign_object(self.key)
        transaction.check_valid(self.store)
        transaction.apply(self.store)
        sub = self.store.lookup("participant:username",
                                "testuser")["object-id"]

        transaction = BondTransaction({
            'Updates': [{
                'UpdateType': 'Clock',
                'Blocknum': 0,
                'PreviousBlockId': 0,
                'Timestamp': time.time()
            }]
        })
        transaction.sign_object(self.key)
        transaction.check_valid(self.store)
        transaction.apply(self.store)

        transaction = BondTransaction({
            "UpdateType": "CreateOrganization",
            'Updates': [{"UpdateType": "CreateOrganization",
                         "name": "Test Bank",
                         "ticker": "T",
                         "pricing_source": "ABCD",
                         "industry": "Test",
                         "authorization": [{"ParticipantId": sub,
                                            "Role": "marketmaker"}]
                         }]
        })
        transaction.sign_object(self.key)
        transaction.check_valid(self.store)
        transaction.apply(self.store)

        transaction = BondTransaction({
            "UpdateType": "CreateBond",
            'Updates': [{
                "UpdateType": "CreateBond",
                "amount_outstanding": 42671000000,
                'corporate_debt_ratings': {
                    "Fitch": "AAA",
                    "Moodys": "AAA",
                    "S&P": "AA+"},
                "coupon_rate": 1.375,
                "coupon_type": "Fixed",
                "coupon_frequency": "Quarterly",
                "cusip": "912828R77",
                "face_value": 1000,
                "isin": "US912828R770",
                "first_settlement_date": "01/11/2012",
                "first_coupon_date": "03/01/2012",
                "maturity_date": "01/11/2022",
                "issuer": "T"
            }]
        })
        transaction.sign_object(self.key)
        transaction.check_valid(self.store)
        transaction.apply(self.store)

        transaction = BondTransaction({
            "UpdateType": "CreateQuote",
            'Updates': [{
                "UpdateType": "CreateQuote",
                "Firm": "ABCD",
                "Isin": "US912828R770",
                "BidPrice": "98-05.875",
                "BidQty": 25000,
                "AskPrice": "98-06.875",
                "AskQty": 25000,
                "ObjectId": "3932250c4877136ee99bf76e5ffbb50b7f"
                "bd46d6788340d29422abcdabcdabcd"
            }]
        })
        try:
            transaction.sign_object(self.key)
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should be valid")

    def test_delete_quote(self):
        transaction = BondTransaction({
            "UpdateType": "DeleteQuote",
            'Updates': [{
                "UpdateType": "DeleteQuote",
                "ObjectId": "3932250c4877136ee99bf76e5ffbb50b7f"
                "bd46d6788340d29422abcdabcdabcd"
            }]
        })
        try:
            transaction.sign_object(self.key)
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should be valid")

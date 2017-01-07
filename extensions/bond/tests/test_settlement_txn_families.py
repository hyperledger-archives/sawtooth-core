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


class TestCreateHoldingUpdate(unittest.TestCase):

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

    def test_create_holding_valid(self):
        org = self.store.lookup("organization:name", "Test Bank")
        transaction = BondTransaction({
            "UpdateType": "CreateHolding",
            'Updates': [{
                "UpdateType": "CreateHolding",
                "owner_id": org["object-id"],
                "asset_type": "Currency",
                "asset_id": "USD",
                "amount": 10000,
                "object_id": "34d813716009ca1786222a44347ccff258a4ab6029" +
                              "d936664fde0d13f23992b6"
            }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should be valid")

        bond = self.store.lookup("bond:cusip", "912828R77")
        transaction = BondTransaction({
            "UpdateType": "CreateHolding",
            'Updates': [{
                "UpdateType": "CreateHolding",
                "owner_id": org["object-id"],
                "asset_type": "Bond",
                "asset_id": bond["object-id"],
                "amount": 10000,
                "object_id": "34d813716009ca1786222a44347ccff258a4ab6029" +
                              "d936664fde0d13f23992b7"
            }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should be valid")

    def test_create_holding_owner_id(self):
        transaction = BondTransaction({
            "UpdateType": "CreateHolding",
            'Updates': [{
                "UpdateType": "CreateHolding",
                "owner_id": "BadOrganization",
                "asset_type": "Currency",
                "asset_id": "USD",
                "amount": 10000,
                "object_id": "34d813716009ca1786222a44347ccff258a4ab6029" +
                              "d936664fde0d13f23992b6"
            }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            self.fail("Bad Organization")
        except InvalidTransactionError:
            pass

    def test_create_holding_currency(self):
        org = self.store.lookup("organization:name", "Test Bank")
        transaction = BondTransaction({
            "UpdateType": "CreateHolding",
            'Updates': [{
                "UpdateType": "CreateHolding",
                "owner_id": org["object-id"],
                "asset_type": "Currency",
                "asset_id": "Euro",
                "amount": 10000,
                "object_id": "34d813716009ca1786222a44347ccff258a4ab6029" +
                              "d936664fde0d13f23992b6"
            }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            self.fail("Not USD")
        except InvalidTransactionError:
            pass

    def test_create_holding_bond(self):
        org = self.store.lookup("organization:name", "Test Bank")
        transaction = BondTransaction({
            "UpdateType": "CreateHolding",
            'Updates': [{
                "UpdateType": "CreateHolding",
                "owner_id": org["object-id"],
                "asset_type": "Bond",
                "asset_id": "BadBond",
                "amount": 10000,
                "object_id": "34d813716009ca1786222a44347ccff258a4ab6029" +
                              "d936664fde0d13f23992b7"
            }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            self.fail("No such bond")
        except InvalidTransactionError:
            pass

    def test_create_holding_asset_other(self):
        org = self.store.lookup("organization:name", "Test Bank")
        transaction = BondTransaction({
            "UpdateType": "CreateHolding",
            'Updates': [{
                "UpdateType": "CreateHolding",
                "owner_id": org["object-id"],
                "asset_type": "Cookies",
                "asset_id": "Coco Chip",
                "amount": 10000,
                "object_id": "34d813716009ca1786222a44347ccff258a4ab6029" +
                              "d936664fde0d13f23992b6"
            }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            self.fail("Unknown asset-type")
        except InvalidTransactionError:
            pass

    def test_create_holding_duplicate(self):
        org = self.store.lookup("organization:name", "Test Bank")
        transaction = BondTransaction({
            "UpdateType": "CreateHolding",
            'Updates': [{
                "UpdateType": "CreateHolding",
                "owner_id": org["object-id"],
                "asset_type": "Currency",
                "asset_id": "USD",
                "amount": 10000
            }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should be valid")

        org = self.store.lookup("organization:name", "Test Bank")
        transaction = BondTransaction({
            "UpdateType": "CreateHolding",
            'Updates': [{
                "UpdateType": "CreateHolding",
                "owner_id": org["object-id"],
                "asset_type": "Currency",
                "asset_id": "USD",
                "amount": 10000
            }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            self.fail("Same Holding")
        except InvalidTransactionError:
            pass

        org = self.store.lookup("organization:name", "Test Bank")
        transaction = BondTransaction({
            "UpdateType": "CreateHolding",
            'Updates': [{
                "UpdateType": "CreateHolding",
                "owner_id": org["object-id"],
                "asset_type": "Currency",
                "asset_id": "USD",
                "amount": 100
            }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            self.fail("Same Asset Type")
        except InvalidTransactionError:
            pass

        bond = self.store.lookup("bond:cusip", "912828R77")
        transaction = BondTransaction({
            "UpdateType": "CreateHolding",
            'Updates': [{
                "UpdateType": "CreateHolding",
                "owner_id": org["object-id"],
                "asset_type": "Bond",
                "asset_id": bond["object-id"],
                "amount": 10000
            }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should be valid")

        bond = self.store.lookup("bond:cusip", "912828R77")
        transaction = BondTransaction({
            "UpdateType": "CreateHolding",
            'Updates': [{
                "UpdateType": "CreateHolding",
                "owner_id": org["object-id"],
                "asset_type": "Bond",
                "asset_id": bond["object-id"],
                "amount": 10000
            }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            self.fail("Same Holding")
        except InvalidTransactionError:
            pass

        bond = self.store.lookup("bond:cusip", "912828R77")
        transaction = BondTransaction({
            "UpdateType": "CreateHolding",
            'Updates': [{
                "UpdateType": "CreateHolding",
                "owner_id": org["object-id"],
                "asset_type": "Bond",
                "asset_id": bond["object-id"],
                "amount": 1000
            }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            self.fail("Same asset-id")
        except InvalidTransactionError:
            pass

    def test_create_holding_refcounts(self):
        org = self.store.lookup("organization:name", "Test Bank")
        bond = self.store.lookup("bond:cusip", "912828R77")
        org_refcount_before = org["ref-count"]
        bond_refcount_before = bond["ref-count"]

        transaction = BondTransaction({
            "UpdateType": "CreateHolding",
            'Updates': [{
                "UpdateType": "CreateHolding",
                "owner_id": org["object-id"],
                "asset_type": "Bond",
                "asset_id": bond["object-id"],
                "amount": 10000
            }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should be valid")

        org = self.store.lookup("organization:name", "Test Bank")
        bond = self.store.lookup("bond:cusip", "912828R77")

        self.assertEquals(org_refcount_before + 1, org["ref-count"])
        self.assertEquals(bond_refcount_before + 1, bond["ref-count"])


class TestCreateSettlementUpdate(unittest.TestCase):

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

        # add another organization
        transaction = BondTransaction({
            "UpdateType": "CreateOrganization",
            'Updates': [{"UpdateType": "CreateOrganization",
                         "name": "First Bank",
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
            "UpdateType": "CreateOrganization",
            'Updates': [{"UpdateType": "CreateOrganization",
                         "name": "Second Bank",
                         "ticker": "I",
                         "pricing_source": "EFGH",
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

        org = self.store.lookup("organization:name", "First Bank")
        # add holding?
        transaction = BondTransaction({
            "UpdateType": "CreateHolding",
            'Updates': [{
                "UpdateType": "CreateHolding",
                "owner_id": org["object-id"],
                "asset_type": "Currency",
                "asset_id": "USD",
                "amount": 0,
                "object_id": "34d813716009ca1786222a44347ccff258a4ab6029" +
                              "d936664fde0d13f23992b5"
            }]
        })
        transaction.sign_object(self.key)
        transaction.check_valid(self.store)
        try:
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should be valid")

        bond = self.store.lookup("bond:cusip", "912828R77")
        transaction = BondTransaction({
            "UpdateType": "CreateHolding",
            'Updates': [{
                "UpdateType": "CreateHolding",
                "owner_id": org["object-id"],
                "asset_type": "Bond",
                "asset_id": bond["object-id"],
                "amount": 2500000,
                "object_id": "34d813716009ca1786222a44347ccff258a4ab6029" +
                              "d936664fde0d13f23992b7"
            }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should be valid")

        org2 = self.store.lookup("organization:name", "Second Bank")
        transaction = BondTransaction({
            "UpdateType": "CreateHolding",
            'Updates': [{
                "UpdateType": "CreateHolding",
                "owner_id": org2["object-id"],
                "asset_type": "Currency",
                "asset_id": "USD",
                "amount": 2500000,
                "object_id": "34d813716009ca1786222a44347ccff258a4ab6029" +
                              "d936664fde0d13f23992b6"
            }]
        })
        transaction.sign_object(self.key)
        transaction.check_valid(self.store)
        try:
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should be valid")

        transaction = BondTransaction({
            "UpdateType": "CreateHolding",
            'Updates': [{
                "UpdateType": "CreateHolding",
                "owner_id": org2["object-id"],
                "asset_type": "Bond",
                "asset_id": bond["object-id"],
                "amount": 0,
                "object_id": "34d813716009ca1786222a44347ccff258a4ab6029" +
                              "d936664fde0d13f23992b8"
            }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should be valid")

        transaction = BondTransaction({
            "UpdateType": "CreateQuote",
            'Updates': [{
                "UpdateType": "CreateQuote",
                "Firm": "ABCD",
                "Isin": "US912828R770",
                "BidPrice": "101",
                "BidQty": 250000,
                "AskPrice": "101",
                "AskQty": 250000,
                "object_id": "555553716009ca1786222a44347ccff258a4ab6029" +
                              "d936664fde0d13f23992b7"
            }]
        })
        try:
            transaction.sign_object(self.key)
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should be valid")

        org2 = self.store.lookup("organization:name", "Second Bank")
        transaction = BondTransaction({
            "UpdateType": "CreateOrder",
            'Updates': [{
                "UpdateType": "CreateOrder",
                "Action": "Buy",
                "OrderType": "Limit",
                "FirmId": org2["object-id"],
                "Isin": bond["isin"],
                "Quantity": 100000,
                "LimitPrice": "98-05.875",
                "LimitYield": 0.015,
                "QuoteId":"555553716009ca1786222a44347ccff258a4ab6029" +
                              "d936664fde0d13f23992b7",
                "object_id": "123453716009ca1786222a44347ccff258a4ab6029" +
                              "d936664fde0d13f23992b7"
            }]
        })
        # quote-id
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should be valid")

    def test_create_settlement_valid_buy_and_sell(self):
        transaction = BondTransaction({
            "UpdateType": "CreateSettlement",
            'Updates': [{
                "UpdateType": "CreateSettlement",
                "order_id": "123453716009ca1786222a44347ccff258a4ab6029" +
                              "d936664fde0d13f23992b7"
            }]
        })

        transaction.sign_object(self.key)
        transaction.check_valid(self.store)
        try:
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should be valid")

        bonds_first_bank = self.store['34d813716009ca1786222a44347cc'
                                      'ff258a4ab6029d936664fde0d13f23'
                                      '992b7']["amount"]
        bonds_second_bank = self.store['34d813716009ca1786222a44347ccff258a4'
                                       'ab6029d936664fde0d13f23'
                                       '992b8']["amount"]
        currency_first_bank = self.store['34d813716009ca1786222a44347ccff258a'
                                         '4ab6029d936664fde0d13f23'
                                         '992b5']["amount"]
        currency_second_bank = self.store["34d813716009ca1786222a44347ccff258"
                                          "a4ab6029d936664fde0d13f2"
                                          "3992b6"]["amount"]
        self.assertEquals(bonds_first_bank, 2400000)
        self.assertEquals(bonds_second_bank, 100000)
        self.assertEquals(currency_first_bank, 101000)
        self.assertEquals(currency_second_bank, 2500000 - 101000)

        org2 = self.store.lookup("organization:name", "Second Bank")
        transaction = BondTransaction({
            "UpdateType": "CreateOrder",
            'Updates': [{
                "UpdateType": "CreateOrder",
                "Action": "Sell",
                "OrderType": "Limit",
                "FirmId": org2["object-id"],
                "Isin": "US912828R770",
                "Quantity": 100000,
                "LimitPrice": "98-05.875",
                "LimitYield": 0.015,
                "QuoteId":"555553716009ca1786222a44347ccff258a4ab6029" +
                              "d936664fde0d13f23992b7",
                "object_id": "123453716009ca1786222a44347ccff258a4ab6029" +
                              "d936664fde0d13f23sell"
            }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should be valid")

        transaction = BondTransaction({
            "UpdateType": "CreateSettlement",
            'Updates': [{
                "UpdateType": "CreateSettlement",
                "order_id": "123453716009ca1786222a44347ccff258a4ab6029" +
                              "d936664fde0d13f23sell"
            }]
        })

        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should be valid")

        bonds_first_bank = self.store['34d813716009ca1786222a44347cc'
                                      'ff258a4ab6029d936664fde0d13f23'
                                      '992b7']["amount"]
        bonds_second_bank = self.store['34d813716009ca1786222a44347ccff258a4'
                                       'ab6029d936664fde0d13f23'
                                       '992b8']["amount"]
        currency_first_bank = self.store['34d813716009ca1786222a44347ccff258a'
                                         '4ab6029d936664fde0d13f23'
                                         '992b5']["amount"]
        currency_second_bank = self.store["34d813716009ca1786222a44347ccff258"
                                          "a4ab6029d936664fde0d13f2"
                                          "3992b6"]["amount"]
        self.assertEquals(bonds_first_bank, 2500000)
        self.assertEquals(bonds_second_bank, 0)
        self.assertEquals(currency_first_bank, 0)
        self.assertEquals(currency_second_bank, 2500000)

    def test_create_settlement_order_id(self):
        transaction = BondTransaction({
            "UpdateType": "CreateSettlement",
            'Updates': [{
                "UpdateType": "CreateSettlement",
                "order_id": "bad Id"
            }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            self.fail("No Order found")
        except InvalidTransactionError:
            pass

    def test_create_settlement_holding_order_firm(self):
        transaction = BondTransaction({
            "UpdateType": "CreateQuote",
            'Updates': [{
                "UpdateType": "CreateQuote",
                "Firm": "ABCD",
                "Isin": "US912828R770",
                "BidPrice": "103",
                "BidQty": 250000,
                "AskPrice": "102",
                "AskQty": 250000,
                "object_id": "666663716009ca1786222a44347ccff258a4ab6029" +
                              "d936664fde0d13f23992b7"
            }]
        })
        try:
            transaction.sign_object(self.key)
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should be valid")

        org2 = self.store.lookup("organization:name", "Second Bank")
        transaction = BondTransaction({
            "UpdateType": "CreateOrder",
            'Updates': [{
                "UpdateType": "CreateOrder",
                "Action": "Buy",
                "OrderType": "Limit",
                "FirmId": org2["object-id"],
                "Isin": "US912828R770",
                "Quantity": 100000000,
                "LimitPrice": "98-05.875",
                "LimitYield": 0.015,
                "QuoteId":"666663716009ca1786222a44347ccff258a4ab6029" +
                              "d936664fde0d13f23992b7",
                "object_id": "765432116009ca1786222a44347ccff258a4ab6029" +
                              "d936664fde0d13f23992b7"
            }]
        })
        # quote-id
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should be valid")

        transaction = BondTransaction({
            "UpdateType": "CreateSettlement",
            'Updates': [{
                "UpdateType": "CreateSettlement",
                "order_id": "765432116009ca1786222a44347ccff258a4ab6029" +
                              "d936664fde0d13f23992b7"
            }]
        })

        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            self.fail("Ordering firm does not have enough currency")
        except:
            pass

    def test_create_settlement_holding_bond_id(self):
        transaction = BondTransaction({
            "UpdateType": "CreateQuote",
            'Updates': [{
                "UpdateType": "CreateQuote",
                "Firm": "ABCD",
                "Isin": "US912828R770",
                "BidPrice": "103",
                "BidQty": 250000,
                "AskPrice": "2",
                "AskQty": 250000,
                "object_id": "666663716009ca1786222a44347ccff258a4ab6029" +
                              "d936664fde0d13f23992b7"
            }]
        })
        try:
            transaction.sign_object(self.key)
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should be valid")

        org2 = self.store.lookup("organization:name", "Second Bank")
        transaction = BondTransaction({
            "UpdateType": "CreateOrder",
            'Updates': [{
                "UpdateType": "CreateOrder",
                "Action": "Buy",
                "OrderType": "Limit",
                "FirmId": org2["object-id"],
                "Isin": "US912828R770",
                "Quantity": 100000000,
                "LimitPrice": "98-05.875",
                "LimitYield": 0.015,
                "QuoteId":"666663716009ca1786222a44347ccff258a4ab6029" +
                              "d936664fde0d13f23992b7",
                "object_id": "765432116009ca1786222a44347ccff258a4ab6029" +
                              "d936664fde0d13f23992b7"
            }]
        })
        # quote-id
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should be valid")

        transaction = BondTransaction({
            "UpdateType": "CreateSettlement",
            'Updates': [{
                "UpdateType": "CreateSettlement",
                "order_id": "765432116009ca1786222a44347ccff258a4ab6029" +
                              "d936664fde0d13f23992b7"
            }]
        })

        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            self.fail("Quoting firm does not have enough bonds")
        except:
            pass

    def test_create_settlement_status(self):
        org2 = self.store.lookup("organization:name", "Second Bank")
        transaction = BondTransaction({
            "UpdateType": "CreateOrder",
            'Updates': [{
                "UpdateType": "CreateOrder",
                "Action": "Buy",
                "OrderType": "Limit",
                "FirmId": org2["object-id"],
                "Isin": "US912828R770",
                "Quantity": 100000,
                "LimitPrice": "98-05.875",
                "LimitYield": 0.015,
                "object_id": "765432116009ca1786222a44347ccff258a4ab6029" +
                              "d936664fde0d13f23992b7"
            }]
        })
        # quote-id
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should be valid")

        transaction = BondTransaction({
            "UpdateType": "CreateSettlement",
            'Updates': [{
                "UpdateType": "CreateSettlement",
                "order_id": "765432116009ca1786222a44347ccff258a4ab6029" +
                              "d936664fde0d13f23992b7"
            }]
        })

        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            self.fail("Order is not matched")
        except:
            pass

    def test_create_settlement_ref_count(self):
        org = self.store.lookup("organization:name", "First Bank")["ref-count"]
        org2 = self.store.lookup("organization:name",
                                 "Second Bank")["ref-count"]
        transaction = BondTransaction({
            "UpdateType": "CreateSettlement",
            'Updates': [{
                "UpdateType": "CreateSettlement",
                "order_id": "123453716009ca1786222a44347ccff258a4ab6029" +
                              "d936664fde0d13f23992b7"
            }]
        })

        transaction.sign_object(self.key)
        transaction.check_valid(self.store)
        try:
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should be valid")

        new_org = self.store.lookup("organization:name",
                                    "First Bank")["ref-count"]
        new_org2 = self.store.lookup("organization:name",
                                     "Second Bank")["ref-count"]

        self.assertEquals(org + 1, new_org)
        self.assertEquals(org2 + 1, new_org)

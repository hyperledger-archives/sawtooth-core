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
import tempfile
import datetime

from sawtooth_validator.consensus.dev_mode.dev_mode_consensus \
    import DevModeConsensus

from gossip import signed_object
from gossip.node import Node
from gossip.gossip_core import Gossip
from journal.journal_core import Journal
from journal.object_store import ObjectStore
from sawtooth_bond.txn_family import BondTransaction
import sawtooth_bond.txn_family as Family
from sawtooth_bond.updates.identity import CreateParticipantUpdate
from sawtooth.exceptions import InvalidTransactionError


class TestReceipts(unittest.TestCase):

    def _set_clock(self, year, month, day, num):
        date = time.mktime(datetime.date(year, month, day).timetuple())
        transaction = BondTransaction({
            'Updates': [{
                'UpdateType': 'Clock',
                'Blocknum': num,
                'PreviousBlockId': 0,
                'Timestamp': date
            }]
        })
        transaction.sign_object(self.key)
        transaction.check_valid(self.store)
        transaction.apply(self.store)

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

        self._set_clock(1994, 10, 4, 0)

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
                "coupon_rate": 1,
                "coupon_type": "Fixed",
                "coupon_frequency": "Quarterly",
                "cusip": "912828R77",
                "face_value": 1000,
                "isin": "US912828R770",
                "first_settlement_date": "01/11/2012",
                "first_coupon_date": "03/01/2012",
                "maturity_date": "01/01/2016",
                "issuer": "T"
            }]
        })
        transaction.sign_object(self.key)
        transaction.check_valid(self.store)
        transaction.apply(self.store)

        org = self.store.lookup("organization:name", "Second Bank")
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
                "amount": 100000,
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

        org1 = self.store.lookup("organization:name", "First Bank")
        transaction = BondTransaction({
            "UpdateType": "CreateHolding",
            'Updates': [{
                "UpdateType": "CreateHolding",
                "owner_id": org1["object-id"],
                "asset_type": "Currency",
                "asset_id": "USD",
                "amount": 100000000,
                "object_id": "34d813716009ca1786222a44347ccff258a4ab6029" +
                              "d936664fde0d13f23org1"
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
                "owner_id": org1["object-id"],
                "asset_type": "Bond",
                "asset_id": bond["object-id"],
                "amount": 100000,
                "object_id": "34d813716009ca1786222a44347ccff258a4ab6029" +
                              "d936664fde0d13f239org1"
            }]
        })
        transaction.sign_object(self.key)
        transaction.check_valid(self.store)
        try:
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should be valid")

    def test_is_coupon_date(self):
        # Test Quarterly
        date = datetime.datetime(1994, 10, 1)
        bond = {'maturity-date': "10/05/1994", "coupon-frequency": "Quarterly"}
        self.assertTrue(Family._is_coupon_date(bond, date))
        date = datetime.datetime(1994, 10, 4)
        self.assertFalse(Family._is_coupon_date(bond, date))
        date = datetime.datetime(1994, 9, 1)
        self.assertFalse(Family._is_coupon_date(bond, date))

        # Test Monthly
        date = datetime.datetime(1994, 10, 1)
        bond = {'maturity-date': "10/05/1994", "coupon-frequency": "Monthly"}
        self.assertTrue(Family._is_coupon_date(bond, date))
        date = datetime.datetime(1994, 10, 4)
        self.assertFalse(Family._is_coupon_date(bond, date))

        # Test Daily
        date = datetime.datetime(1994, 10, 1)
        bond = {'maturity-date': "10/05/1994", "coupon-frequency": "Daily"}
        self.assertTrue(Family._is_coupon_date(bond, date))
        date = datetime.datetime(1994, 10, 4)
        self.assertTrue(Family._is_coupon_date(bond, date))
        date = datetime.datetime(1994, 9, 1)
        self.assertTrue(Family._is_coupon_date(bond, date))

    def test_is_mature(self):
        date = datetime.datetime(1994, 10, 4)
        bond = {'maturity-date': "10/05/1994"}
        self.assertFalse(Family._is_mature(bond, date))

        date = datetime.datetime(1994, 10, 7)
        self.assertTrue(Family._is_mature(bond, date))

    def test_has_holding(self):
        org = self.store.lookup("organization:name", "Second Bank")
        bond = self.store.lookup("bond:cusip", "912828R77")
        self.assertTrue(Family._has_holding(self.store, org, bond))

        org = self.store.lookup("organization:name", "First Bank")
        org["holdings"] = ["34d813716009ca1786222a44347ccff258a4ab6029" +
                           "d936664fde0d13f23992b5"]
        # a holding that doesn't point to the the correct bond
        self.assertFalse(Family._has_holding(self.store, org, bond))

    def test_coupon_exists(self):
        org = self.store.lookup("organization:name", "Second Bank")
        bond = self.store.lookup("bond:cusip", "912828R77")
        date = datetime.datetime(2015, 4, 1)
        self._set_clock(2015, 4, 1, 1)
        self.assertFalse(Family._coupon_exists(self.store, bond, org, date))

        transaction = BondTransaction({
            'Updates': [{
                'UpdateType': 'CreateReceipt',
                'PaymentType': 'Coupon',
                'BondID': bond['object-id'],
                'PayeeID': org['object-id'],
                'CouponDate': "04/01/2015"
            }]
        })
        transaction.sign_object(self.key)
        transaction.check_valid(self.store)
        try:
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should be valid")

        org = self.store.lookup("organization:name", "Second Bank")
        bond = self.store.lookup("bond:cusip", "912828R77")
        self.assertTrue(Family._coupon_exists(self.store, bond, org, date))

    def test_create_coupon(self):
        date = datetime.datetime(2015, 4, 1)
        self._set_clock(2015, 4, 1, 1)
        org = self.store.lookup("organization:name", "Second Bank")
        bond = self.store.lookup("bond:cusip", "912828R77")
        coupon = Family._create_coupon(self.store, bond, org, date)
        self.assertIsNotNone(coupon)
        transaction = BondTransaction(coupon)
        transaction.sign_object(self.key)
        transaction.check_valid(self.store)
        transaction.apply(self.store)

        org_usd_holding = self.store["34d813716009ca1786222a44347ccff"
                                     "258a4ab6029d936664fde0d13f23992b5"]
        self.assertEquals(org_usd_holding["amount"], 25000.0)

        date = datetime.datetime(2015, 7, 1)
        self._set_clock(2015, 7, 1, 2)
        coupon = Family._create_coupon(self.store, bond, org, date)
        self.assertIsNotNone(coupon)
        transaction = BondTransaction(coupon)
        transaction.sign_object(self.key)
        transaction.check_valid(self.store)
        transaction.apply(self.store)

        org_usd_holding = self.store["34d813716009ca1786222a44347ccff"
                                     "258a4ab6029d936664fde0d13f23992b5"]
        self.assertEquals(org_usd_holding["amount"], 50000.0)

    def test_create_redemption(self):
        self._set_clock(2016, 4, 1, 1)
        org = self.store.lookup("organization:name", "Second Bank")
        bond = self.store.lookup("bond:cusip", "912828R77")
        coupon = Family._create_redemption(self.store, bond, org)
        self.assertIsNotNone(coupon)
        transaction = BondTransaction(coupon)
        transaction.sign_object(self.key)
        transaction.check_valid(self.store)
        transaction.apply(self.store)

        first_bond = self.store["34d813716009ca1786222a44347ccff258a4ab6029" +
                                "d936664fde0d13f239org1"]["amount"]
        second_bond = self.store["34d813716009ca1786222a44347ccff258a4ab6029" +
                                 "d936664fde0d13f23992b7"]["amount"]
        first_usd = self.store["34d813716009ca1786222a44347ccff258a4ab6029" +
                               "d936664fde0d13f23992b5"]["amount"]
        second_usd = self.store["34d813716009ca1786222a44347ccff258a4ab6029" +
                                "d936664fde0d13f23org1"]["amount"]
        self.assertEquals(first_bond, 200000)
        self.assertEquals(second_bond, 0)
        self.assertEquals(first_usd, 100000)
        self.assertEquals(second_usd, 100000000 - 100000)

    def test_generate_coupons_redemption(self):
        self._set_clock(2016, 4, 1, 1)
        signingkey = signed_object.generate_signing_key()
        ident = signed_object.generate_identifier(signingkey)
        node = Node(identifier=ident, signingkey=signingkey,
                    address=("localhost", 10020))
        node.is_peer = True
        path = tempfile.mkdtemp()
        gossip = Gossip(node)
        journal = Journal(node,
                          gossip,
                          gossip.dispatcher,
                          consensus=DevModeConsensus(),
                          data_directory=path)
        journal.global_store.TransactionStores['/BondTransaction'] = \
            self.store
        # creates a redemption
        updates = Family._generate_coupons(journal)
        self.assertNotEquals(updates, [])

        transaction = BondTransaction(updates[0])
        transaction.sign_object(self.key)
        transaction.check_valid(self.store)
        transaction.apply(self.store)
        first_bond = self.store["34d813716009ca1786222a44347ccff258a4ab6029" +
                                "d936664fde0d13f239org1"]["amount"]
        second_bond = self.store["34d813716009ca1786222a44347ccff258a4ab6029" +
                                 "d936664fde0d13f23992b7"]["amount"]
        first_usd = self.store["34d813716009ca1786222a44347ccff258a4ab6029" +
                               "d936664fde0d13f23992b5"]["amount"]
        second_usd = self.store["34d813716009ca1786222a44347ccff258a4ab6029" +
                                "d936664fde0d13f23org1"]["amount"]
        self.assertEquals(first_bond, 200000)
        self.assertEquals(second_bond, 0)
        self.assertEquals(first_usd, 100000)
        self.assertEquals(second_usd, 100000000 - 100000)

    def test_generate_coupons_coupon(self):
        self._set_clock(2015, 4, 1, 1)
        signingkey = signed_object.generate_signing_key()
        ident = signed_object.generate_identifier(signingkey)
        node = Node(identifier=ident, signingkey=signingkey,
                    address=("localhost", 10021))
        node.is_peer = True
        path = tempfile.mkdtemp()
        gossip = Gossip(node)
        journal = Journal(node,
                          gossip,
                          gossip.dispatcher,
                          consensus=DevModeConsensus(),
                          data_directory=path)
        journal.global_store.TransactionStores['/BondTransaction'] = \
            self.store
        # creates a redemption
        updates = Family._generate_coupons(journal)

        self.assertNotEquals(updates, [])

        transaction = BondTransaction(updates[0])
        transaction.sign_object(self.key)
        transaction.check_valid(self.store)
        transaction.apply(self.store)

        org_usd_holding = self.store["34d813716009ca1786222a44347ccff"
                                     "258a4ab6029d936664fde0d13f23992b5"]
        self.assertEquals(org_usd_holding["amount"], 25000.0)

    def test_create_receipt_update_valid(self):
        self._set_clock(2015, 4, 1, 1)
        org = self.store.lookup("organization:name", "Second Bank")
        bond = self.store.lookup("bond:isin", "US912828R770")
        transaction = BondTransaction({
            'Updates': [{
                'UpdateType': 'CreateReceipt',
                'PaymentType': 'Coupon',
                'BondID': bond['object-id'],
                'PayeeID': org['object-id'],
                'CouponDate': "04/01/2015"
            }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should be valid")

        self._set_clock(2016, 1, 2, 2)
        org = self.store.lookup("organization:name", "Second Bank")
        bond = self.store.lookup("bond:isin", "US912828R770")
        transaction = BondTransaction({
            'Updates': [{
                'UpdateType': 'CreateReceipt',
                'PaymentType': 'Redemption',
                'BondID': bond['object-id'],
                'PayeeID': org['object-id']
            }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should be valid")

    def test_create_receipt_update_bad_type(self):
        org = self.store.lookup("organization:name", "Second Bank")
        bond = self.store.lookup("bond:isin", "US912828R770")
        transaction = BondTransaction({
            'Updates': [{
                'UpdateType': 'CreateReceipt',
                'PaymentType': 'PayOut',
                'BondID': bond['object-id'],
                'PayeeID': org['object-id']
            }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            self.fail("PaymentType is not Coupon or Redemption")
        except InvalidTransactionError:
            pass

    def test_create_receipt_update_bad_bond(self):
        org = self.store.lookup("organization:name", "Second Bank")
        transaction = BondTransaction({
            'Updates': [{
                'UpdateType': 'CreateReceipt',
                'PaymentType': 'Redemption',
                'BondID': "BondId",
                'PayeeID': org['object-id']
            }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            self.fail("No such bond")
        except InvalidTransactionError:
            pass

        transaction = BondTransaction({
            'Updates': [{
                'UpdateType': 'CreateReceipt',
                'PaymentType': 'Redemption',
                'BondID': org['object-id'],
                'PayeeID': org['object-id']
            }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            self.fail("Not a Bond")
        except InvalidTransactionError:
            pass

    def test_create_receipt_update_bad_organization(self):
        bond = self.store.lookup("bond:isin", "US912828R770")
        transaction = BondTransaction({
            'Updates': [{
                'UpdateType': 'CreateReceipt',
                'PaymentType': 'Redemption',
                'BondID': bond['object-id'],
                'PayeeID': "PayeeID"
            }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            self.fail("No organization")
        except InvalidTransactionError:
            pass

        bond = self.store.lookup("bond:isin", "US912828R770")
        transaction = BondTransaction({
            'Updates': [{
                'UpdateType': 'CreateReceipt',
                'PaymentType': 'Redemption',
                'BondID': bond['object-id'],
                'PayeeID': bond['object-id']
            }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            self.fail("Not an organization")
        except InvalidTransactionError:
            pass

    def test_create_receipt_update_bad_quantity_payee(self):
        self._set_clock(2015, 4, 1, 1)
        org = self.store.lookup("organization:name", "Second Bank")
        bond = self.store.lookup("bond:isin", "US912828R770")
        self.store["34d813716009ca1786222a44347ccff258a4ab6029" +
                   "d936664fde0d13f23992b5"] = \
            {"object-type": "holding",
             "asset-id": "None",
             "asset-type": "None"}

        transaction = BondTransaction({
            'Updates': [{
                'UpdateType': 'CreateReceipt',
                'PaymentType': 'Coupon',
                'BondID': bond['object-id'],
                'PayeeID': org['object-id'],
                'CouponDate': "04/01/2015"
            }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            self.fail("No USD holding")
        except InvalidTransactionError:
            pass

        holding = self.store["34d813716009ca1786222a44347ccff258a4ab6029" +
                             "d936664fde0d13f23992b7"]
        holding["amount"] = 0
        self.store["34d813716009ca1786222a44347ccff258a4ab6029" +
                   "d936664fde0d13f23992b7"] = holding

        transaction = BondTransaction({
            'Updates': [{
                'UpdateType': 'CreateReceipt',
                'PaymentType': 'Coupon',
                'BondID': bond['object-id'],
                'PayeeID': org['object-id'],
                'CouponDate': "04/01/2015"
            }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            self.fail("Zero holding")
        except InvalidTransactionError:
            pass

        self.store["34d813716009ca1786222a44347ccff258a4ab6029" +
                   "d936664fde0d13f23992b7"] = \
            {"object-type": "holding",
             "asset-id": "None",
             "asset-type": "None"}

        transaction = BondTransaction({
            'Updates': [{
                'UpdateType': 'CreateReceipt',
                'PaymentType': 'Coupon',
                'BondID': bond['object-id'],
                'PayeeID': org['object-id'],
                'CouponDate': "04/01/2015"
            }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            self.fail("Payee does not have a holding in bond")
        except InvalidTransactionError:
            pass

    def test_create_receipt_update_bad_quantity_payer(self):
        self._set_clock(2015, 4, 1, 1)
        org = self.store.lookup("organization:name", "Second Bank")
        bond = self.store.lookup("bond:isin", "US912828R770")

        holding = self.store["34d813716009ca1786222a44347ccff258a4ab6029" +
                             "d936664fde0d13f23org1"]
        holding["amount"] = 0
        self.store["34d813716009ca1786222a44347ccff258a4ab6029" +
                   "d936664fde0d13f23org1"] = holding

        transaction = BondTransaction({
            'Updates': [{
                'UpdateType': 'CreateReceipt',
                'PaymentType': 'Coupon',
                'BondID': bond['object-id'],
                'PayeeID': org['object-id'],
                'CouponDate': "04/01/2015"
            }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            self.fail("Not enough usd")
        except InvalidTransactionError:
            pass

        self.store["34d813716009ca1786222a44347ccff258a4ab6029" +
                   "d936664fde0d13f23org1"] = \
            {"object-type": "holding",
             "asset-id": "None",
             "asset-type": "None"}

        transaction = BondTransaction({
            'Updates': [{
                'UpdateType': 'CreateReceipt',
                'PaymentType': 'Redemption',
                'BondID': bond['object-id'],
                'PayeeID': org['object-id'],
            }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            self.fail("No usd holding")
        except InvalidTransactionError:
            pass

        holding = self.store["34d813716009ca1786222a44347ccff258a4ab6029" +
                             "d936664fde0d13f239org1"]
        self.store["34d813716009ca1786222a44347ccff258a4ab6029" +
                   "d936664fde0d13f239org1"] = \
            {"object-type": "holding",
             "asset-id": "None",
             "asset-type": "None"}

        transaction = BondTransaction({
            'Updates': [{
                'UpdateType': 'CreateReceipt',
                'PaymentType': 'Redemption',
                'BondID': bond['object-id'],
                'PayeeID': org['object-id'],
            }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            self.fail("Zero holidng for bond")
        except InvalidTransactionError:
            pass

    def test_create_receipt_update_bad_libor(self):
        self._set_clock(2015, 4, 1, 1)
        bond = self.store.lookup("bond:isin", "US912828R770")
        org = self.store.lookup("organization:name", "Second Bank")
        bond["coupon-type"] = "Floating"
        self.store[bond["object-id"]] = bond
        transaction = BondTransaction({
            'Updates': [{
                'UpdateType': 'CreateReceipt',
                'PaymentType': 'Coupon',
                'BondID': bond['object-id'],
                'PayeeID': org['object-id'],
                'CouponDate': "04/01/2015"
            }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            self.fail("No libor data available")
        except InvalidTransactionError:
            pass

        info = {
            'object-id': 'current_libor',
            'object-type': 'libor',
            'date': "2015-04-01",
            'rates': {
                'Overnight': 0.1,
                'OneWeek': 0.1,
                'OneMonth': 0.1,
                'TwoMonth': 0.1,
                'ThreeMonth': 0.1,
                'SixMonth': 0.1,
                'OneYear': 0.1
            },
            'signature': "Test"
        }
        self.store['current_libor'] = info

        bond["coupon-benchmark"] = "NoLibor"
        self.store[bond["object-id"]] = bond

        transaction = BondTransaction({
            'Updates': [{
                'UpdateType': 'CreateReceipt',
                'PaymentType': 'Coupon',
                'BondID': bond['object-id'],
                'PayeeID': org['object-id'],
                'CouponDate': "04/01/2015"
            }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            self.fail("Bad Benchmark")
        except InvalidTransactionError:
            pass

        bond["coupon-benchmark"] = "Overnight"
        self.store[bond["object-id"]] = bond

        transaction = BondTransaction({
            'Updates': [{
                'UpdateType': 'CreateReceipt',
                'PaymentType': 'Coupon',
                'BondID': bond['object-id'],
                'PayeeID': org['object-id'],
                'CouponDate': "04/01/2015"
            }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should be valid")

        org_usd_holding = self.store["34d813716009ca1786222a44347ccff"
                                     "258a4ab6029d936664fde0d13f23992b5"]
        self.assertEquals(org_usd_holding["amount"], 27500.0)

    def test_create_receipt_update_coupon_date(self):
        self._set_clock(2015, 4, 1, 1)
        bond = self.store.lookup("bond:isin", "US912828R770")
        org = self.store.lookup("organization:name", "Second Bank")
        transaction = BondTransaction({
            'Updates': [{
                'UpdateType': 'CreateReceipt',
                'PaymentType': 'Coupon',
                'BondID': bond['object-id'],
                'PayeeID': org['object-id'],
                'CouponDate': "04-02-2015"
            }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            self.fail("Coupon date is in the wrong format")
        except InvalidTransactionError:
            pass

        transaction = BondTransaction({
            'Updates': [{
                'UpdateType': 'CreateReceipt',
                'PaymentType': 'Coupon',
                'BondID': bond['object-id'],
                'PayeeID': org['object-id'],
                'CouponDate': "04/02/2015"
            }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            self.fail("Current date is not the coupon redemption date")
        except InvalidTransactionError:
            pass

        self._set_clock(2015, 4, 2, 2)
        transaction = BondTransaction({
            'Updates': [{
                'UpdateType': 'CreateReceipt',
                'PaymentType': 'Coupon',
                'BondID': bond['object-id'],
                'PayeeID': org['object-id'],
                'CouponDate': "04/02/2015"
            }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            self.fail("Does not Fall on start of quarter")
        except InvalidTransactionError:
            pass

        bond = self.store.lookup("bond:isin", "US912828R770")
        bond["coupon-frequency"] = "Monthly"
        self.store[bond["object-id"]] = bond

        transaction = BondTransaction({
            'Updates': [{
                'UpdateType': 'CreateReceipt',
                'PaymentType': 'Coupon',
                'BondID': bond['object-id'],
                'PayeeID': org['object-id'],
                'CouponDate': "04/02/2015"
            }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            self.fail("Does not Fall on start of Month")
        except InvalidTransactionError:
            pass

    def test_create_receipt_update_double_receipts(self):
        self._set_clock(2015, 4, 1, 1)
        org = self.store.lookup("organization:name", "Second Bank")
        bond = self.store.lookup("bond:isin", "US912828R770")
        transaction = BondTransaction({
            'Updates': [{
                'UpdateType': 'CreateReceipt',
                'PaymentType': 'Coupon',
                'BondID': bond['object-id'],
                'PayeeID': org['object-id'],
                'CouponDate': "04/01/2015"
            }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should be valid")

        transaction = BondTransaction({
            'Updates': [{
                'UpdateType': 'CreateReceipt',
                'PaymentType': 'Coupon',
                'BondID': bond['object-id'],
                'PayeeID': org['object-id'],
                'CouponDate': "04/01/2015"
            }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            self.fail("Same object Id")
        except InvalidTransactionError:
            pass

        org = self.store.lookup("organization:name", "Second Bank")
        bond = self.store.lookup("bond:isin", "US912828R770")
        transaction = BondTransaction({
            'Updates': [{
                'UpdateType': 'CreateReceipt',
                'PaymentType': 'Coupon',
                'BondID': bond['object-id'],
                'PayeeID': org['object-id'],
                'CouponDate': "04/01/2015",
                'ObjectId': "b7d0717678424ac017a3ba414e547f3691beeb"
                "7d343141225afe05c5d663fnew"
            }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            self.fail("Double coupon for period")
        except InvalidTransactionError:
            pass

    def test_create_receipt_update_early_redemption(self):
        self._set_clock(2015, 4, 1, 1)
        org = self.store.lookup("organization:name", "Second Bank")
        bond = self.store.lookup("bond:isin", "US912828R770")
        transaction = BondTransaction({
            'Updates': [{
                'UpdateType': 'CreateReceipt',
                'PaymentType': 'Redemption',
                'BondID': bond['object-id'],
                'PayeeID': org['object-id']
            }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            self.fail("Early Redemption")
        except InvalidTransactionError:
            pass

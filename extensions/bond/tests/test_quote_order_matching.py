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

from sawtooth_validator.consensus.dev_mode.dev_mode_consensus \
    import DevModeConsensus

from gossip import signed_object
from gossip.node import Node
from gossip.gossip_core import Gossip
from journal.journal_core import Journal
from journal.object_store import ObjectStore
from sawtooth_bond.txn_family import BondTransaction
from sawtooth_bond.txn_family import _generate_match_orders
from sawtooth_bond.updates.identity import CreateParticipantUpdate
from sawtooth.exceptions import InvalidTransactionError


class TestMatchingUpdate(unittest.TestCase):

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

    def test_matching_limit_valid(self):
        signingkey = signed_object.generate_signing_key()
        ident = signed_object.generate_identifier(signingkey)
        node = Node(identifier=ident, signingkey=signingkey,
                    address=("localhost", 10000))
        node.is_peer = True
        path = tempfile.mkdtemp()
        gossip = Gossip(node)
        journal = Journal(node,
                          gossip,
                          gossip.dispatcher,
                          consensus=DevModeConsensus(),
                          data_directory=path)

        org2 = self.store.lookup("organization:name", "Second Bank")
        bond = self.store.lookup("bond:cusip", "912828R77")
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
                "LimitPrice": "105",
                "LimitYield": 0.015,
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

        journal.global_store.TransactionStores['/BondTransaction'] = \
            self.store
        matched_orders = _generate_match_orders(journal)

        self.assertEquals(matched_orders[0]["Updates"][0]["ObjectId"],
                          "123453716009ca1786222a44347ccff258a4ab6029"
                          "d936664fde0d13f23992b7")
        transaction = BondTransaction(matched_orders[0])
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should be valid")

        matched_orders = _generate_match_orders(journal)
        self.assertEquals(matched_orders, [])

        self.assertEqual(self.store["123453716009ca1786222a44347ccff258a4ab60"
                                    "29d936664fde0d13f23992b7"]["status"],
                         "Matched")

    def test_matching_market(self):
        signingkey = signed_object.generate_signing_key()
        ident = signed_object.generate_identifier(signingkey)
        node = Node(identifier=ident, signingkey=signingkey,
                    address=("localhost", 10001))
        node.is_peer = True
        path = tempfile.mkdtemp()
        gossip = Gossip(node)
        journal = Journal(node,
                          gossip,
                          gossip.dispatcher,
                          consensus=DevModeConsensus(),
                          data_directory=path)
        org2 = self.store.lookup("organization:name", "Second Bank")
        bond = self.store.lookup("bond:cusip", "912828R77")
        transaction = BondTransaction({
            "UpdateType": "CreateQuote",
            'Updates': [{
                "UpdateType": "CreateQuote",
                "Firm": "ABCD",
                "Isin": "US912828R770",
                "BidPrice": "101",
                "BidQty": 190000,
                "AskPrice": "101",
                "AskQty": 190000,
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
                "OrderType": "Market",
                "FirmId": org2["object-id"],
                "Isin": bond["isin"],
                "Quantity": 100000,
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

        journal.global_store.TransactionStores['/BondTransaction'] = \
            self.store
        matched_orders = _generate_match_orders(journal)
        self.assertEquals(matched_orders[0]["Updates"][0]["ObjectId"],
                          "123453716009ca1786222a44347ccff258a4ab6029"
                          "d936664fde0d13f23992b7")

        transaction = BondTransaction(matched_orders[0])
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should be valid")

        matched_orders = _generate_match_orders(journal)
        # Everything already matched
        self.assertEquals(matched_orders, [])
        # 90000 < 100000 so quotes should be closed
        self.assertEquals(self.store["555553716009ca1786222a44347ccff258a4ab60"
                                     "29d936664fde0d13f23992b7"]["status"],
                          "Closed")

    def test_matching_nothing_to_match(self):
        signingkey = signed_object.generate_signing_key()
        ident = signed_object.generate_identifier(signingkey)
        node = Node(identifier=ident, signingkey=signingkey,
                    address=("localhost", 10002))
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
        matched_orders = _generate_match_orders(journal)
        self.assertEquals(matched_orders, [])

    def test_matching_no_quotes(self):
        signingkey = signed_object.generate_signing_key()
        ident = signed_object.generate_identifier(signingkey)
        node = Node(identifier=ident, signingkey=signingkey,
                    address=("localhost", 10003))
        node.is_peer = True
        path = tempfile.mkdtemp()
        gossip = Gossip(node)
        journal = Journal(node,
                          gossip,
                          gossip.dispatcher,
                          consensus=DevModeConsensus(),
                          data_directory=path)

        org2 = self.store.lookup("organization:name", "Second Bank")
        bond = self.store.lookup("bond:cusip", "912828R77")
        transaction = BondTransaction({
            "UpdateType": "CreateOrder",
            'Updates': [{
                "UpdateType": "CreateOrder",
                "Action": "Buy",
                "OrderType": "Market",
                "FirmId": org2["object-id"],
                "Isin": bond["isin"],
                "Quantity": 100000,
                "object_id": "123453716009ca1786222a44347ccff258a4ab6029" +
                "d936664fde0d13f23992b7"
            }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should be valid")

        journal.global_store.TransactionStores['/BondTransaction'] = \
            self.store
        matched_orders = _generate_match_orders(journal)
        self.assertEquals(matched_orders, [])

    def test_matching_no_order(self):
        signingkey = signed_object.generate_signing_key()
        ident = signed_object.generate_identifier(signingkey)
        node = Node(identifier=ident, signingkey=signingkey,
                    address=("localhost", 10004))
        node.is_peer = True
        path = tempfile.mkdtemp()
        gossip = Gossip(node)
        journal = Journal(node,
                          gossip,
                          gossip.dispatcher,
                          consensus=DevModeConsensus(),
                          data_directory=path)
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
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should be valid")

        journal.global_store.TransactionStores['/BondTransaction'] = \
            self.store
        matched_orders = _generate_match_orders(journal)
        self.assertEquals(matched_orders, [])

    def test_matching_incorrect_quantities(self):
        signingkey = signed_object.generate_signing_key()
        ident = signed_object.generate_identifier(signingkey)
        node = Node(identifier=ident, signingkey=signingkey,
                    address=("localhost", 10005))
        node.is_peer = True
        path = tempfile.mkdtemp()
        gossip = Gossip(node)
        journal = Journal(node,
                          gossip,
                          gossip.dispatcher,
                          consensus=DevModeConsensus(),
                          data_directory=path)
        org2 = self.store.lookup("organization:name", "Second Bank")
        bond = self.store.lookup("bond:cusip", "912828R77")
        transaction = BondTransaction({
            "UpdateType": "CreateQuote",
            'Updates': [{
                "UpdateType": "CreateQuote",
                "Firm": "ABCD",
                "Isin": "US912828R770",
                "BidPrice": "101",
                "BidQty": 25000,
                "AskPrice": "101",
                "AskQty": 25000,
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
                "OrderType": "Market",
                "FirmId": org2["object-id"],
                "Isin": bond["isin"],
                "Quantity": 100000,
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

        journal.global_store.TransactionStores['/BondTransaction'] = \
            self.store
        matched_orders = _generate_match_orders(journal)
        # Quote should not have enough quantity (market)
        self.assertEquals(matched_orders, [])

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
                "LimitPrice": "105",
                "LimitYield": 0.015,
                "object_id": "123453716009ca1786222a44347ccff258a4ab6029" +
                              "d936664fde0d13f2399000"
            }]
        })
        # quote-id
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should be valid")

        journal.global_store.TransactionStores['/BondTransaction'] = \
            self.store
        matched_orders = _generate_match_orders(journal)
        # Quote should not have enough quantity (limit)
        self.assertEquals(matched_orders, [])

    def test_matching_multiple(self):
        signingkey = signed_object.generate_signing_key()
        ident = signed_object.generate_identifier(signingkey)
        node = Node(identifier=ident, signingkey=signingkey,
                    address=("localhost", 10007))
        node.is_peer = True
        path = tempfile.mkdtemp()
        gossip = Gossip(node)
        journal = Journal(node,
                          gossip,
                          gossip.dispatcher,
                          consensus=DevModeConsensus(),
                          data_directory=path)

        org2 = self.store.lookup("organization:name", "Second Bank")
        bond = self.store.lookup("bond:cusip", "912828R77")
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
                "LimitPrice": "105",
                "LimitYield": 0.015,
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

        org2 = self.store.lookup("organization:name", "Second Bank")
        transaction = BondTransaction({
            "UpdateType": "CreateOrder",
            'Updates': [{
                "UpdateType": "CreateOrder",
                "Action": "Buy",
                "OrderType": "Market",
                "FirmId": org2["object-id"],
                "Isin": bond["isin"],
                "Quantity": 100000,
                "object_id": "123453716009ca1786222a44347ccff258a4ab6029" +
                "d936664fde0d13f2399000"
            }]
        })
        # quote-id
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should be valid")

        journal.global_store.TransactionStores['/BondTransaction'] = \
            self.store
        matched_orders = _generate_match_orders(journal)
        self.assertEqual(len(matched_orders), 2)

        transaction = BondTransaction(matched_orders[0])
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should be valid")

        transaction = BondTransaction(matched_orders[1])
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should be valid")

        matched_orders = _generate_match_orders(journal)
        self.assertEqual(matched_orders, [])

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

from gossip import signed_object
from journal.object_store import ObjectStore
from sawtooth_bond.txn_family import BondTransaction
from sawtooth_bond.updates.identity import CreateParticipantUpdate
from sawtooth.exceptions import InvalidTransactionError


class TestCreateBondUpdate(unittest.TestCase):

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

    def test_create_bond_valid(self):
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
        try:
            transaction.check_valid(self.store)
            transaction.apply(self.store)
        except InvalidTransactionError:
            self.fail("This should be valid")

    def test_create_bond_ticker(self):
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
                "issuer": "AB"
            }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            self.fail("Ticker doesnt exist")
        except InvalidTransactionError:
            pass

    def test_create_bond_isin_cusip(self):
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
                "face_value": 1000,
                "first_settlement_date": "01/11/2012",
                "first_coupon_date": "03/01/2012",
                "maturity_date": "01/11/2022",
                "issuer": "T"
            }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            self.fail("Need either Isin and Cusip")
        except InvalidTransactionError:
            pass

    def test_create_bond_isin(self):
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
                "isin": "US912828R770",
                "face_value": 1000,
                "first_settlement_date": "01/11/2012",
                "first_coupon_date": "03/01/2012",
                "maturity_date": "01/11/2022",
                "issuer": "T"
            }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
        except InvalidTransactionError:
            self.fail("This should be valid")

    def test_create_bond_cusp(self):
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
                "first_settlement_date": "01/11/2012",
                "first_coupon_date": "03/01/2012",
                "maturity_date": "01/11/2022",
                "issuer": "T"
            }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
        except InvalidTransactionError:
            self.fail("This should be valid")

    def test_create_bond_libor(self):
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
                "coupon_type": "Floating",
                "coupon_benchmark": 'Overnight',
                "coupon_frequency": "Quarterly",
                "cusip": "912828R77",
                "face_value": 1000,
                "first_settlement_date": "01/11/2012",
                "first_coupon_date": "03/01/2012",
                "maturity_date": "01/11/2022",
                "issuer": "T"
            }]
        })
        transaction.sign_object(self.key)
        transaction.check_valid(self.store)
        try:
            transaction.check_valid(self.store)
        except InvalidTransactionError:
            self.fail("This should be valid")

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
                "coupon_type": "Floating",
                "coupon_frequency": "Quarterly",
                "cusip": "912828R77",
                "face_value": 1000,
                "first_settlement_date": "01/11/2012",
                "first_coupon_date": "03/01/2012",
                "maturity_date": "01/11/2022",
                "issuer": "T"
            }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            self.fail("No Coupon Benchmark")
        except InvalidTransactionError:
            pass

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
                "coupon_type": "Floating",
                "coupon_benchmark": "OneMinute",
                "coupon_frequency": "Quarterly",
                "cusip": "912828R77",
                "face_value": 1000,
                "first_settlement_date": "01/11/2012",
                "first_coupon_date": "03/01/2012",
                "maturity_date": "01/11/2022",
                "issuer": "T"
            }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            self.fail("Incorrect Coupon Benchmark")
        except InvalidTransactionError:
            pass

    def test_create_bond_maturity_date(self):
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
                "maturity_date": "01112022",
                "issuer": "T"
            }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            self.fail("Inncorect Maturity date format")
        except InvalidTransactionError:
            pass

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
                "maturity_date": "20221101",
                "issuer": "T"
            }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            self.fail("Inncorect Maturity date format")
        except InvalidTransactionError:
            pass

    def test_create_bond_creator(self):
        key = signed_object.generate_signing_key()
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
        transaction.sign_object(key)
        try:
            transaction.check_valid(self.store)
            self.fail("Bad creator")
        except InvalidTransactionError:
            pass

    def test_create_bond_coupon_type(self):
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
                "coupon_type": "Free",
                "coupon_frequency": "Quarterly",
                "cusip": "912828R77",
                "face_value": 1000,
                "first_settlement_date": "01/11/2012",
                "first_coupon_date": "03/01/2012",
                "maturity_date": "01/11/2022",
                "issuer": "T"
            }]
        })
        transaction.sign_object(self.key)
        try:
            transaction.check_valid(self.store)
            self.fail("Incorrect Coupon type")
        except InvalidTransactionError:
            pass

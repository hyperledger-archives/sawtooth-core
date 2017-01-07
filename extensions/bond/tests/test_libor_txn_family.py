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
from sawtooth_bond.updates.libor import CreateLIBORUpdate
from sawtooth.exceptions import InvalidTransactionError
from sawtooth_signing import pbct_nativerecover as signing


class TestCreateLIBORUpdate(unittest.TestCase):

    libor_key = None

    @classmethod
    def setUpClass(cls):
        TestCreateLIBORUpdate.libor_key = \
            signed_object.generate_signing_key()

    def test_libor_update_not_signed(self):
        key = signed_object.generate_signing_key()
        store = ObjectStore()
        update = \
            CreateLIBORUpdate(
                update_type='CreateLIBOR',
                date='2016-05-24',
                rates={
                    'Overnight': '0.1',
                    'OneWeek': '0.1',
                    'OneMonth': '0.1',
                    'TwoMonth': '0.1',
                    'ThreeMonth': '0.1',
                    'SixMonth': '0.1',
                    'OneYear': '0.1'
                },
                signature=None)

        transaction = BondTransaction()
        transaction._updates = [update]
        transaction.sign_object(key)

        try:
            transaction.check_valid(store)
            self.fail('This transaction should be invalid')
        except InvalidTransactionError:
            pass

    def test_libor_update_signature_does_not_match(self):
        key = signed_object.generate_signing_key()
        store = ObjectStore()
        libor_key = TestCreateLIBORUpdate.libor_key
        libor_invalid_public_key = signing.generate_pubkey(key)
        update = \
            CreateLIBORUpdate(
                update_type='CreateLIBOR',
                date='2016-05-24',
                rates={
                    'Overnight': '0.1',
                    'OneWeek': '0.1',
                    'OneMonth': '0.1',
                    'TwoMonth': '0.1',
                    'ThreeMonth': '0.1',
                    'SixMonth': '0.1',
                    'OneYear': '0.1',
                },
                libor_public_key=libor_invalid_public_key)
        update.sign_update_object(libor_key)

        transaction = BondTransaction()
        transaction._updates = [update]
        transaction.sign_object(key)

        try:
            transaction.check_valid(store)
            self.fail('This transaction should be invalid')
        except InvalidTransactionError:
            pass

    def test_libor_update_missing_date(self):
        key = signed_object.generate_signing_key()
        store = ObjectStore()
        libor_key = TestCreateLIBORUpdate.libor_key
        libor_public_key = signing.generate_pubkey(libor_key)
        update = \
            CreateLIBORUpdate(
                update_type='CreateLIBOR',
                date=None,
                rates={
                    'Overnight': 0.1,
                    'OneWeek': 0.1,
                    'OneMonth': 0.1,
                    'TwoMonth': 0.1,
                    'ThreeMonth': 0.1,
                    'SixMonth': 0.1,
                    'OneYear': 0.1
                },
                libor_public_key=libor_public_key)
        update.sign_update_object(libor_key)
        transaction = BondTransaction()
        transaction._updates = [update]
        transaction.sign_object(key)

        try:
            transaction.check_valid(store)
            self.fail('This transaction should be invalid')
        except InvalidTransactionError:
            pass

    def test_libor_update_missing_overnight(self):
        key = signed_object.generate_signing_key()
        store = ObjectStore()
        libor_key = TestCreateLIBORUpdate.libor_key
        libor_public_key = signing.generate_pubkey(libor_key)
        update = \
            CreateLIBORUpdate(
                update_type='CreateLIBOR',
                date='2016-05-24',
                rates={
                    'OneWeek': 0.1,
                    'OneMonth': 0.1,
                    'TwoMonth': 0.1,
                    'ThreeMonth': 0.1,
                    'SixMonth': 0.1,
                    'OneYear': 0.1
                },
                libor_public_key=libor_public_key)
        update.sign_update_object(libor_key)
        transaction = BondTransaction()
        transaction._updates = [update]
        transaction.sign_object(key)

        try:
            transaction.check_valid(store)
            self.fail('This transaction should be invalid')
        except InvalidTransactionError:
            pass

    def test_libor_update_missing_one_week(self):
        key = signed_object.generate_signing_key()
        store = ObjectStore()
        libor_key = TestCreateLIBORUpdate.libor_key
        libor_public_key = signing.generate_pubkey(libor_key)
        update = \
            CreateLIBORUpdate(
                update_type='CreateLIBOR',
                date='2016-05-24',
                rates={
                    'Overnight': 0.1,
                    'OneMonth': 0.1,
                    'TwoMonth': 0.1,
                    'ThreeMonth': 0.1,
                    'SixMonth': 0.1,
                    'OneYear': 0.1
                },
                libor_public_key=libor_public_key)
        update.sign_update_object(libor_key)
        transaction = BondTransaction()
        transaction._updates = [update]
        transaction.sign_object(key)

        try:
            transaction.check_valid(store)
            self.fail('This transaction should be invalid')
        except InvalidTransactionError:
            pass

    def test_libor_update_missing_one_month(self):
        key = signed_object.generate_signing_key()
        store = ObjectStore()
        libor_key = TestCreateLIBORUpdate.libor_key
        libor_public_key = signing.generate_pubkey(libor_key)
        update = \
            CreateLIBORUpdate(
                update_type='CreateLIBOR',
                date='2016-05-24',
                rates={
                    'Overnight': 0.1,
                    'OneWeek': 0.1,
                    'TwoMonth': 0.1,
                    'ThreeMonth': 0.1,
                    'SixMonth': 0.1,
                    'OneYear': 0.1
                },
                libor_public_key=libor_public_key)
        update.sign_update_object(libor_key)

        transaction = BondTransaction()
        transaction._updates = [update]
        transaction.sign_object(key)

        try:
            transaction.check_valid(store)
            self.fail('This transaction should be invalid')
        except InvalidTransactionError:
            pass

    def test_libor_update_missing_two_month(self):
        key = signed_object.generate_signing_key()
        store = ObjectStore()
        libor_key = TestCreateLIBORUpdate.libor_key
        libor_public_key = signing.generate_pubkey(libor_key)
        update = \
            CreateLIBORUpdate(
                update_type='CreateLIBOR',
                date='2016-05-24',
                rates={
                    'Overnight': 0.1,
                    'OneWeek': 0.1,
                    'OneMonth': 0.1,
                    'ThreeMonth': 0.1,
                    'SixMonth': 0.1,
                    'OneYear': 0.1
                },
                libor_public_key=libor_public_key)
        update.sign_update_object(libor_key)

        transaction = BondTransaction()
        transaction._updates = [update]
        transaction.sign_object(key)

        try:
            transaction.check_valid(store)
            self.fail('This transaction should be invalid')
        except InvalidTransactionError:
            pass

    def test_libor_update_missing_three_month(self):
        key = signed_object.generate_signing_key()
        store = ObjectStore()
        libor_key = TestCreateLIBORUpdate.libor_key
        libor_public_key = signing.generate_pubkey(libor_key)
        update = \
            CreateLIBORUpdate(
                update_type='CreateLIBOR',
                date='2016-05-24',
                rates={
                    'Overnight': 0.1,
                    'OneWeek': 0.1,
                    'OneMonth': 0.1,
                    'TwoMonth': 0.1,
                    'SixMonth': 0.1,
                    'OneYear': 0.1
                },
                libor_public_key=libor_public_key)
        update.sign_update_object(libor_key)

        transaction = BondTransaction()
        transaction._updates = [update]
        transaction.sign_object(key)

        try:
            transaction.check_valid(store)
            self.fail('This transaction should be invalid')
        except InvalidTransactionError:
            pass

    def test_libor_update_missing_six_month(self):
        key = signed_object.generate_signing_key()
        store = ObjectStore()
        libor_key = TestCreateLIBORUpdate.libor_key
        libor_public_key = signing.generate_pubkey(libor_key)
        update = \
            CreateLIBORUpdate(
                update_type='CreateLIBOR',
                date='2016-05-24',
                rates={
                    'Overnight': 0.1,
                    'OneWeek': 0.1,
                    'OneMonth': 0.1,
                    'TwoMonth': 0.1,
                    'ThreeMonth': 0.1,
                    'OneYear': 0.1
                },
                libor_public_key=libor_public_key)
        update.sign_update_object(libor_key)

        transaction = BondTransaction()
        transaction._updates = [update]
        transaction.sign_object(key)

        try:
            transaction.check_valid(store)
            self.fail('This transaction should be invalid')
        except InvalidTransactionError:
            pass

    def test_libor_update_missing_one_year(self):
        key = signed_object.generate_signing_key()
        store = ObjectStore()
        libor_key = TestCreateLIBORUpdate.libor_key
        libor_public_key = signing.generate_pubkey(libor_key)
        update = \
            CreateLIBORUpdate(
                update_type='CreateLIBOR',
                date='2016-05-24',
                rates={
                    'Overnight': 0.1,
                    'OneWeek': 0.1,
                    'OneMonth': 0.1,
                    'TwoMonth': 0.1,
                    'ThreeMonth': 0.1,
                    'SixMonth': 0.1
                },
                libor_public_key=libor_public_key)
        update.sign_update_object(libor_key)

        transaction = BondTransaction()
        transaction._updates = [update]
        transaction.sign_object(key)

        try:
            transaction.check_valid(store)
            self.fail('This transaction should be invalid')
        except InvalidTransactionError:
            pass

    def test_libor_update_date_in_the_future(self):
        key = signed_object.generate_signing_key()
        store = ObjectStore()
        libor_key = TestCreateLIBORUpdate.libor_key
        libor_public_key = signing.generate_pubkey(libor_key)
        update = \
            CreateLIBORUpdate(
                update_type='CreateLIBOR',
                date='2100-01-01',
                rates={
                    'Overnight': 0.1,
                    'OneWeek': 0.1,
                    'OneMonth': 0.1,
                    'TwoMonth': 0.1,
                    'ThreeMonth': 0.1,
                    'SixMonth': 0.1,
                    'OneYear': 0.1
                },
                libor_public_key=libor_public_key)
        update.sign_update_object(libor_key)

        transaction = BondTransaction()
        transaction._updates = [update]
        transaction.sign_object(key)

        try:
            transaction.check_valid(store)
            self.fail('This transaction should be invalid')
        except InvalidTransactionError:
            pass

    def test_libor_update_invalid_date_format(self):
        key = signed_object.generate_signing_key()
        store = ObjectStore()
        libor_key = TestCreateLIBORUpdate.libor_key
        libor_public_key = signing.generate_pubkey(libor_key)
        update = \
            CreateLIBORUpdate(
                update_type='CreateLIBOR',
                date='05/24/2016',
                rates={
                    'Overnight': 0.1,
                    'OneWeek': 0.1,
                    'OneMonth': 0.1,
                    'TwoMonth': 0.1,
                    'ThreeMonth': 0.1,
                    'SixMonth': 0.1,
                    'OneYear': 0.1
                },
                libor_public_key=libor_public_key)
        update.sign_update_object(libor_key)

        transaction = BondTransaction()
        transaction._updates = [update]
        transaction.sign_object(key)

        try:
            transaction.check_valid(store)
            self.fail('This transaction should be invalid')
        except InvalidTransactionError:
            pass

        update = \
            CreateLIBORUpdate(
                update_type='CreateLIBOR',
                date='05-24-2016',
                rates={
                    'Overnight': 0.1,
                    'OneWeek': 0.1,
                    'OneMonth': 0.1,
                    'TwoMonth': 0.1,
                    'ThreeMonth': 0.1,
                    'SixMonth': 0.1,
                    'OneYear': 0.1
                },
                signature='G7OL7YDOVHzOevEaGgg1PvnpxiRhws7vdut3F1RUdMXDNH6gH'
                          'sY9nk/Zt+WwQYo/4QhZOY6CO0Inv5HUi8MyrPo=')

        transaction._updates = [update]
        transaction.sign_object(key)

        try:
            transaction.check_valid(store)
            self.fail('This transaction should be invalid')
        except InvalidTransactionError:
            pass

        update = \
            CreateLIBORUpdate(
                update_type='CreateLIBOR',
                date='May 24, 2016',
                rates={
                    'OneWeek': 0.1,
                    'Overnight': 0.1,
                    'OneMonth': 0.1,
                    'TwoMonth': 0.1,
                    'ThreeMonth': 0.1,
                    'SixMonth': 0.1,
                    'OneYear': 0.1
                },
                libor_public_key=libor_public_key)
        update.sign_update_object(libor_key)

        transaction._updates = [update]
        transaction.sign_object(key)

        try:
            transaction.check_valid(store)
            self.fail('This transaction should be invalid')
        except InvalidTransactionError:
            pass

        update = \
            CreateLIBORUpdate(
                update_type='CreateLIBOR',
                date='24-May-2016',
                rates={
                    'OneWeek': 0.1,
                    'Overnight': 0.1,
                    'OneMonth': 0.1,
                    'TwoMonth': 0.1,
                    'ThreeMonth': 0.1,
                    'SixMonth': 0.1,
                    'OneYear': 0.1
                },
                libor_public_key=libor_public_key)
        update.sign_update_object(libor_key)

        transaction._updates = [update]
        transaction.sign_object(key)

        try:
            transaction.check_valid(store)
            self.fail('This transaction should be invalid')
        except InvalidTransactionError:
            pass

        update = \
            CreateLIBORUpdate(
                update_type='CreateLIBOR',
                date='May 24 2016',
                rates={
                    'Overnight': 0.1,
                    'OneWeek': 0.1,
                    'OneMonth': 0.1,
                    'TwoMonth': 0.1,
                    'ThreeMonth': 0.1,
                    'SixMonth': 0.1,
                    'OneYear': 0.1
                },
                libor_public_key=libor_public_key)
        update.sign_update_object(libor_key)

        transaction._updates = [update]
        transaction.sign_object(key)

        try:
            transaction.check_valid(store)
            self.fail('This transaction should be invalid')
        except InvalidTransactionError:
            pass

        update = \
            CreateLIBORUpdate(
                update_type='CreateLIBOR',
                date='24 May 2016',
                rates={
                    'Overnight': 0.1,
                    'OneWeek': 0.1,
                    'OneMonth': 0.1,
                    'TwoMonth': 0.1,
                    'ThreeMonth': 0.1,
                    'SixMonth': 0.1,
                    'OneYear': 0.1
                },
                libor_public_key=libor_public_key)
        update.sign_update_object(libor_key)

        transaction._updates = [update]
        transaction.sign_object(key)

        try:
            transaction.check_valid(store)
            self.fail('This transaction should be invalid')
        except InvalidTransactionError:
            pass

        update = \
            CreateLIBORUpdate(
                update_type='CreateLIBOR',
                date='',
                rates={
                    'Overnight': 0.1,
                    'OneWeek': 0.1,
                    'OneMonth': 0.1,
                    'TwoMonth': 0.1,
                    'ThreeMonth': 0.1,
                    'SixMonth': 0.1,
                    'OneYear': 0.1,
                },
                libor_public_key=libor_public_key)
        update.sign_update_object(libor_key)

        transaction._updates = [update]
        transaction.sign_object(key)

        try:
            transaction.check_valid(store)
            self.fail('This transaction should be invalid')
        except InvalidTransactionError:
            pass

    def test_libor_update_invalid_date(self):
        key = signed_object.generate_signing_key()
        store = ObjectStore()
        libor_key = TestCreateLIBORUpdate.libor_key
        libor_public_key = signing.generate_pubkey(libor_key)
        update = \
            CreateLIBORUpdate(
                update_type='CreateLIBOR',
                date='2016-01-32',
                rates={
                    'Overnight': 0.1,
                    'OneWeek': 0.1,
                    'OneMonth': 0.1,
                    'TwoMonth': 0.1,
                    'ThreeMonth': 0.1,
                    'SixMonth': 0.1,
                    'OneYear': 0.1
                },
                libor_public_key=libor_public_key)
        update.sign_update_object(libor_key)
        transaction = BondTransaction()
        transaction._updates = [update]
        transaction.sign_object(key)

        try:
            transaction.check_valid(store)
            self.fail('This transaction should be invalid')
        except InvalidTransactionError:
            pass

        update = \
            CreateLIBORUpdate(
                update_type='CreateLIBOR',
                date='2016-12-32',
                rates={
                    'Overnight': 0.1,
                    'OneWeek': 0.1,
                    'OneMonth': 0.1,
                    'TwoMonth': 0.1,
                    'ThreeMonth': 0.1,
                    'SixMonth': 0.1,
                    'OneYear': 0.1
                },
                signature='HG/+Byml9CU13jdMD9TvOtlNlLvAO5jzBGUqoJGSng2ksojoh8'
                          'mUxYKJ4rTE5pZ4Q1S+lHRLuQLVgprhQkY25eQ=')

        transaction._updates = [update]
        transaction.sign_object(key)

        try:
            transaction.check_valid(store)
            self.fail('This transaction should be invalid')
        except InvalidTransactionError:
            pass

        update = \
            CreateLIBORUpdate(
                update_type='CreateLIBOR',
                date='2015-02-29',
                rates={
                    'Overnight': 0.1,
                    'OneWeek': 0.1,
                    'OneMonth': 0.1,
                    'TwoMonth': 0.1,
                    'ThreeMonth': 0.1,
                    'SixMonth': 0.1,
                    'OneYear': 0.1
                },
                libor_public_key=libor_public_key)
        update.sign_update_object(libor_key)

        transaction._updates = [update]
        transaction.sign_object(key)

        try:
            transaction.check_valid(store)
            self.fail('This transaction should be invalid')
        except InvalidTransactionError:
            pass

        update = \
            CreateLIBORUpdate(
                update_type='CreateLIBOR',
                date='2016-02-30',
                rates={
                    'Overnight': 0.1,
                    'OneWeek': 0.1,
                    'OneMonth': 0.1,
                    'TwoMonth': 0.1,
                    'ThreeMonth': 0.1,
                    'SixMonth': 0.1,
                    'OneYear': 0.1
                },
                libor_public_key=libor_public_key)
        update.sign_update_object(libor_key)

        transaction._updates = [update]
        transaction.sign_object(key)

        try:
            transaction.check_valid(store)
            self.fail('This transaction should be invalid')
        except InvalidTransactionError:
            pass

        update = \
            CreateLIBORUpdate(
                update_type='CreateLIBOR',
                date='2016-13-30',
                rates={
                    'Overnight': 0.1,
                    'OneWeek': 0.1,
                    'OneMonth': 0.1,
                    'TwoMonth': 0.1,
                    'ThreeMonth': 0.1,
                    'SixMonth': 0.1,
                    'OneYear': 0.1
                },
                signature='G4JyMWYLEWwwSQlOLHWDclAKB2kXersC/cuc3VbzyRTJ92Nj'
                          'e2nGPgSIsQzQ4uR94r9pYi1S6E4z7zQrdwCCKlg=')

        transaction._updates = [update]
        transaction.sign_object(key)

        try:
            transaction.check_valid(store)
            self.fail('This transaction should be invalid')
        except InvalidTransactionError:
            pass

        update = \
            CreateLIBORUpdate(
                update_type='CreateLIBOR',
                date='2016-00-15',
                rates={
                    'Overnight': 0.1,
                    'OneWeek': 0.1,
                    'OneMonth': 0.1,
                    'TwoMonth': 0.1,
                    'ThreeMonth': 0.1,
                    'SixMonth': 0.1,
                    'OneYear': 0.1
                },
                libor_public_key=libor_public_key)
        update.sign_update_object(libor_key)

        transaction._updates = [update]
        transaction.sign_object(key)

        try:
            transaction.check_valid(store)
            self.fail('This transaction should be invalid')
        except InvalidTransactionError:
            pass

        update = \
            CreateLIBORUpdate(
                update_type='CreateLIBOR',
                date='2016-01-00',
                rates={
                    'Overnight': 0.1,
                    'OneWeek': 0.1,
                    'OneMonth': 0.1,
                    'TwoMonth': 0.1,
                    'ThreeMonth': 0.1,
                    'SixMonth': 0.1,
                    'OneYear': 0.1
                },
                libor_public_key=libor_public_key)
        update.sign_update_object(libor_key)

        transaction._updates = [update]
        transaction.sign_object(key)

        try:
            transaction.check_valid(store)
            self.fail('This transaction should be invalid')
        except InvalidTransactionError:
            pass

    def test_libor_update_duplicate_date(self):
        key = signed_object.generate_signing_key()
        store = ObjectStore()
        libor_key = TestCreateLIBORUpdate.libor_key
        libor_public_key = signing.generate_pubkey(libor_key)
        update = \
            CreateLIBORUpdate(
                update_type='CreateLIBOR',
                date='2016-05-24',
                rates={
                    'Overnight': 0.1,
                    'OneWeek': 0.1,
                    'OneMonth': 0.1,
                    'TwoMonth': 0.1,
                    'ThreeMonth': 0.1,
                    'SixMonth': 0.1,
                    'OneYear': 0.1
                },
                libor_public_key=libor_public_key)
        update.sign_update_object(libor_key)

        transaction = BondTransaction()
        transaction._updates = [update]
        transaction.sign_object(key)

        try:
            transaction.check_valid(store)
        except InvalidTransactionError:
            self.fail('This transaction should be valid')

        transaction.apply(store)

        try:
            transaction.check_valid(store)
            self.fail('This transaction should be invalid')
        except InvalidTransactionError:
            pass

    def test_libor_update_invalid_value_overnight(self):
        key = signed_object.generate_signing_key()
        store = ObjectStore()
        libor_key = TestCreateLIBORUpdate.libor_key
        libor_public_key = signing.generate_pubkey(libor_key)
        update = \
            CreateLIBORUpdate(
                update_type='CreateLIBOR',
                date='2016-05-24',
                rates={
                    'Overnight': 'invalid rate',
                    'OneWeek': 0.1,
                    'OneMonth': 0.1,
                    'TwoMonth': 0.1,
                    'ThreeMonth': 0.1,
                    'SixMonth': 0.1,
                    'OneYear': 0.1
                },
                libor_public_key=libor_public_key)
        update.sign_update_object(libor_key)

        transaction = BondTransaction()
        transaction._updates = [update]
        transaction.sign_object(key)

        try:
            transaction.check_valid(store)
            self.fail('This transaction should be invalid')
        except InvalidTransactionError:
            pass

    def test_libor_update_invalid_value_one_week(self):
        key = signed_object.generate_signing_key()
        store = ObjectStore()
        libor_key = TestCreateLIBORUpdate.libor_key
        libor_public_key = signing.generate_pubkey(libor_key)
        update = \
            CreateLIBORUpdate(
                update_type='CreateLIBOR',
                date='2016-05-24',
                rates={
                    'Overnight': 0.1,
                    'OneWeek': 'invalid rate',
                    'OneMonth': 0.1,
                    'TwoMonth': 0.1,
                    'ThreeMonth': 0.1,
                    'SixMonth': 0.1,
                    'OneYear': 0.1
                },
                libor_public_key=libor_public_key)
        update.sign_update_object(libor_key)

        transaction = BondTransaction()
        transaction._updates = [update]
        transaction.sign_object(key)

        try:
            transaction.check_valid(store)
            self.fail('This transaction should be invalid')
        except InvalidTransactionError:
            pass

    def test_libor_update_invalid_value_one_month(self):
        key = signed_object.generate_signing_key()
        store = ObjectStore()
        libor_key = TestCreateLIBORUpdate.libor_key
        libor_public_key = signing.generate_pubkey(libor_key)
        update = \
            CreateLIBORUpdate(
                update_type='CreateLIBOR',
                date='2016-05-24',
                rates={
                    'Overnight': 0.1,
                    'OneWeek': 0.1,
                    'OneMonth': 'invalid rate',
                    'TwoMonth': 0.1,
                    'ThreeMonth': 0.1,
                    'SixMonth': 0.1,
                    'OneYear': 0.1
                },
                libor_public_key=libor_public_key)
        update.sign_update_object(libor_key)

        transaction = BondTransaction()
        transaction._updates = [update]
        transaction.sign_object(key)

        try:
            transaction.check_valid(store)
            self.fail('This transaction should be invalid')
        except InvalidTransactionError:
            pass

    def test_libor_update_invalid_value_two_month(self):
        key = signed_object.generate_signing_key()
        store = ObjectStore()
        libor_key = TestCreateLIBORUpdate.libor_key
        libor_public_key = signing.generate_pubkey(libor_key)
        update = \
            CreateLIBORUpdate(
                update_type='CreateLIBOR',
                date='2016-05-24',
                rates={
                    'Overnight': 0.1,
                    'OneWeek': 0.1,
                    'OneMonth': 0.1,
                    'TwoMonth': 'invalid rate',
                    'ThreeMonth': 0.1,
                    'SixMonth': 0.1,
                    'OneYear': 0.1
                },
                libor_public_key=libor_public_key)
        update.sign_update_object(libor_key)

        transaction = BondTransaction()
        transaction._updates = [update]
        transaction.sign_object(key)

        try:
            transaction.check_valid(store)
            self.fail('This transaction should be invalid')
        except InvalidTransactionError:
            pass

    def test_libor_update_invalid_value_three_month(self):
        key = signed_object.generate_signing_key()
        store = ObjectStore()
        libor_key = TestCreateLIBORUpdate.libor_key
        libor_public_key = signing.generate_pubkey(libor_key)
        update = \
            CreateLIBORUpdate(
                update_type='CreateLIBOR',
                date='2016-05-24',
                rates={
                    'Overnight': 0.1,
                    'OneWeek': 0.1,
                    'OneMonth': 0.1,
                    'TwoMonth': 0.1,
                    'ThreeMonth': 'invalid rate',
                    'SixMonth': 0.1,
                    'OneYear': 0.1
                },
                libor_public_key=libor_public_key)
        update.sign_update_object(libor_key)

        transaction = BondTransaction()
        transaction._updates = [update]
        transaction.sign_object(key)

        try:
            transaction.check_valid(store)
            self.fail('This transaction should be invalid')
        except InvalidTransactionError:
            pass

    def test_libor_update_invalid_value_six_month(self):
        key = signed_object.generate_signing_key()
        store = ObjectStore()
        libor_key = TestCreateLIBORUpdate.libor_key
        libor_public_key = signing.generate_pubkey(libor_key)
        update = \
            CreateLIBORUpdate(
                update_type='CreateLIBOR',
                date='2016-05-24',
                rates={
                    'Overnight': 0.1,
                    'OneWeek': 0.1,
                    'OneMonth': 0.1,
                    'TwoMonth': 0.1,
                    'ThreeMonth': 0.1,
                    'SixMonth': 'invalid rate',
                    'OneYear': 0.1
                },
                libor_public_key=libor_public_key)
        update.sign_update_object(libor_key)

        transaction = BondTransaction()
        transaction._updates = [update]
        transaction.sign_object(key)

        try:
            transaction.check_valid(store)
            self.fail('This transaction should be invalid')
        except InvalidTransactionError:
            pass

    def test_libor_update_invalid_value_one_year(self):
        key = signed_object.generate_signing_key()
        store = ObjectStore()
        libor_key = TestCreateLIBORUpdate.libor_key
        libor_public_key = signing.generate_pubkey(libor_key)
        update = \
            CreateLIBORUpdate(
                update_type='CreateLIBOR',
                date='2016-05-24',
                rates={
                    'Overnight': 0.1,
                    'OneWeek': 0.1,
                    'OneMonth': 0.1,
                    'TwoMonth': 0.1,
                    'ThreeMonth': 0.1,
                    'SixMonth': 0.1,
                    'OneYear': 'invalid rate'
                },
                libor_public_key=libor_public_key)
        update.sign_update_object(libor_key)

        transaction = BondTransaction()
        transaction._updates = [update]
        transaction.sign_object(key)

        try:
            transaction.check_valid(store)
            self.fail('This transaction should be invalid')
        except InvalidTransactionError:
            pass

    def test_libor_update(self):
        key = signed_object.generate_signing_key()
        store = ObjectStore()
        libor_key = TestCreateLIBORUpdate.libor_key
        libor_public_key = signing.generate_pubkey(libor_key)
        update = \
            CreateLIBORUpdate(
                update_type='CreateLIBOR',
                date='2016-05-24',
                rates={
                    'Overnight': 0.1,
                    'OneWeek': 0.1,
                    'OneMonth': 0.1,
                    'TwoMonth': 0.1,
                    'ThreeMonth': 0.1,
                    'SixMonth': 0.1,
                    'OneYear': 0.1
                },
                libor_public_key=libor_public_key)
        update.sign_update_object(libor_key)
        transaction = BondTransaction()
        transaction._updates = [update]
        transaction.sign_object(key)

        try:
            transaction.check_valid(store)
        except InvalidTransactionError as e:
            self.fail('This transaction should be valid\n error:' + str(e))

        try:
            store.lookup('libor:date', '2016-05-24')
            self.fail('LIBOR data for 2016-05-24 should not be in store')
        except KeyError:
            pass

        transaction.apply(store)

        self.assertIsNotNone(store.lookup('libor:date', '2016-05-24'))

        update = \
            CreateLIBORUpdate(
                update_type='CreateLIBOR',
                date='2016-05-25',
                rates={
                    'Overnight': '0.1',
                    'OneWeek': '-0.1',
                    'OneMonth': '0',
                    'TwoMonth': 0.1,
                    'ThreeMonth': -0.1,
                    'SixMonth': 0,
                    'OneYear': 1
                },
                libor_public_key=libor_public_key)
        update.sign_update_object(libor_key)

        transaction._updates = [update]
        transaction.sign_object(key)

        try:
            transaction.check_valid(store)
        except InvalidTransactionError as e:
            self.fail('This transaction should be valid\n error: ' + str(e))

        try:
            store.lookup('libor:date', '2016-05-25')
            self.fail('LIBOR data for 2016-05-25 should not be in store')
        except KeyError:
            pass

        transaction.apply(store)

        self.assertIsNotNone(store.lookup('libor:date', '2016-05-25'))

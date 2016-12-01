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


class TestCreateLIBORUpdate(unittest.TestCase):
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
                signature='hjoq7knkzlxo4qubsjslfarl1ej/qso0ar4zsucd5xguniuvqjv'
                          'zj5lrqhayi5tqvniqxai0lkt31zqsztgojxw=')

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
                signature="G78QicusrNO9l8Yxt/qJGX0TxkVh0ftSiW9dYkQPL5qYctd"
                          "pb4Cq3GR15gT6DeHj0ujFcf4CK+Pu0Sqe77Zi92Y=")

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
                signature='HLwpLLCM0TdAOdyj/zpR4LUNp7QQosVTBBTqEq71zZkjKZ3a5yS'
                          'qRqFAC8Wgv9VQHyRbScLXJxFOG7xH83SxLYc=')
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
                signature="HBYQ8UxaSl6tTv2Ab3Hctki7kl+G8qBthr+4vVXRvJhMrppcEA"
                          "3CMtm3OitDoYsqmB6MC0WiFqqgSzOEiqJmPUg=")

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
                signature='G+eKJzXQBJCEgIj3ZZ46mfp73WqECskUBh4JPjFIMy9D2EAW02'
                          'ry7VN1NA6r4ZPf2dGtRY50yHSLrRwf/3Yn0gs=')

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
                signature='HCi5tDerqxHZ8han4SmTqMsbKN1JscETRCqYDU3gNQSofpt8fm2'
                          '5i5xyo7EwBXDlxpcOyU5em8DVQOGsdyx8jXk=')

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
                signature='HO+xNW91CfhWVrvBKyk2P0rak82TPG8ZSsBucI3QhSXT7SegQd'
                          'y/Sq0dTZC+31rGQgMVdylbXLSO++aIb9OP0y8=')

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
                signature='HHlwEyzhFYP53vg2tE44snVyAD4UUIzElBiaiNUPZLKrkGmO'
                          '5TLHHmRJ8RvTAkxL5elIicRiNwOKc7JI0Zjkn5o=')

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
                signature="HDRqSWSJN8wCPMGITZLx0pW/ccqsMDYnnG9mbRUL3x1O8bztf"
                          "GmgkD9n+6OQgb/glO52zuJdFIFV5ehCdr4L0Ug=")

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
                signature='G/gl8XhptfXUGih7X4g4s8EeXNXpX+qz7yEHd6ah1xXyrica2p'
                          'pdePFikWb9wbR5rOnvKC8FDAIg8CadhAaizt0=')

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
                signature='G9AKVsz3JlT/apjOieVwFc8PYkIXu787S0JkIYNY59GTI7h'
                          '0pLP5SVqxycXkXJg+xtR8lK5vT0JeNAoYxpg3bzI=')

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
                signature='HOV3d7ESaywjUB3c3qPcV4DBKKpZR0tokeILinSEVdapNi2y7m'
                          'NYrhAXjdgzbPzTGFmp0btjAPVFFUvzYKgOYvo=')

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
                signature='HEnC3vEdBhBcHAndjgouHj4T+ILyOX2PTCveiShIb8VK0woyM'
                          '4UheSM4f2ucv8Xj/ySMhAl16JQYaDk6mZ7fARI=')

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
                signature="G9tsTDOQG/dG1f1rrduq7/rBxYqmWujbM7iMUuJc94pe1Ue7kt"
                          "gbxlIqzND/+sxWR+PjtCKlzcN/AmW1MyBSAfs=")

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
                signature='HAjOWJgM9yP20fJ4pqD3x3dCrutwIYs0u3PepaWqNZXYC8L13'
                          'xbqaCJ3/6vNX6BZRi9BD03t9VXxkmKHI6m/SOM=')

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
                signature='HM6jsivVl3OUszzyh8cjo68fLHlPsIj3kyxJ0u0CiwVDzXyKF'
                          '0K8cpS3FvoYX9xOfG1i8jtxiMt0+EkAjJHxvP8=')

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
                signature="G+9NKjqnXnEtMbYWbuUeiQqk3dcCdEKi1lf0V3W5/XwTnp5UwA"
                          "eRcyeLALzsDhdnC3/qX2dBjewrA8vLFBOBNMw=")

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
                signature='G9+MiYwYtErSOAd7FsWhda3pP9/iuNt+XWmHWdHk8Qs0qzCC'
                          'ZxCjoM8onOalFwP9a0QtIQOnCOuhU8XpUOez6qk=')

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
                signature='G48nBn9dGbSDsN5NlEXVo30AE8AoAda5s9YzgSC1IO81GiB32'
                          'O9kSPts+z7PGsdAhAOnv5OvTzsUVIntPBQwJ44=')

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
                signature='HE6eRRqetDR2hFYxUf9dY/H9LmN13yWL5FKnx+g9ME1WF/oB52'
                          'OZlq0dIBwRemFA7tlN0jWgFgpBHrIG5E0avzk=')

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
                signature='HC29Ih92jlFIj/C5zD8ulPpvkEsNKXfXOk6I4FTqsdAyq+H8igh'
                          '76evTLbgpF5AQ956I7gGt4ACNUXdjMdH19QQ=')

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
                signature='G38pbExUmKqKzdC07QJS1OJSglnpLKGr+PMu4muigey37CdT2P'
                          '7d0PBQxmaWNjtsADdPxQAS5FhtHOQbtD41fkU=')

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
                signature='HLwpLLCM0TdAOdyj/zpR4LUNp7QQosVTBBTqEq71zZkjKZ3a5y'
                          'SqRqFAC8Wgv9VQHyRbScLXJxFOG7xH83SxLYc=')

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
                signature='HBYQ8UxaSl6tTv2Ab3Hctki7kl+G8qBthr+4vVXRvJhMrppcEA3'
                          'CMtm3OitDoYsqmB6MC0WiFqqgSzOEiqJmPUg=')

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
                signature='G+eKJzXQBJCEgIj3ZZ46mfp73WqECskUBh4JPjFIMy9D2EAW0'
                          '2ry7VN1NA6r4ZPf2dGtRY50yHSLrRwf/3Yn0gs=')

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
                signature='HCi5tDerqxHZ8han4SmTqMsbKN1JscETRCqYDU3gNQSofp'
                          't8fm25i5xyo7EwBXDlxpcOyU5em8DVQOGsdyx8jXk=')

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
                signature='HO+xNW91CfhWVrvBKyk2P0rak82TPG8ZSsBucI3QhSXT7SegQd'
                          'y/Sq0dTZC+31rGQgMVdylbXLSO++aIb9OP0y8=')

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
                signature='HHlwEyzhFYP53vg2tE44snVyAD4UUIzElBiaiNUPZLKrkGmO'
                          '5TLHHmRJ8RvTAkxL5elIicRiNwOKc7JI0Zjkn5o=')

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
                signature='HDRqSWSJN8wCPMGITZLx0pW/ccqsMDYnnG9mbRUL3x1O8bz'
                          'tfGmgkD9n+6OQgb/glO52zuJdFIFV5ehCdr4L0Ug=')

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
                signature='G38pbExUmKqKzdC07QJS1OJSglnpLKGr+PMu4muigey37CdT2P7'
                          'd0PBQxmaWNjtsADdPxQAS5FhtHOQbtD41fkU=')

        transaction = BondTransaction()
        transaction._updates = [update]
        transaction.sign_object(key)

        try:
            transaction.check_valid(store)
        except InvalidTransactionError:
            self.fail('This transaction should be valid')

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
                signature='GzcrWBTv180bCZcKkluVOSPcqNbNrcLCj3FocJH9uliKkl+3yNR'
                          'yhj5DAIsTWOY2ZwrcDVEMOp1P1jJpfctst6I=')
        transaction._updates = [update]
        transaction.sign_object(key)

        try:
            transaction.check_valid(store)
        except InvalidTransactionError:
            self.fail('This transaction should be valid')

        try:
            store.lookup('libor:date', '2016-05-25')
            self.fail('LIBOR data for 2016-05-25 should not be in store')
        except KeyError:
            pass

        transaction.apply(store)

        self.assertIsNotNone(store.lookup('libor:date', '2016-05-25'))

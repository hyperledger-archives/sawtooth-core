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

import datetime
from sawtooth.exceptions import InvalidTransactionError

from journal.transaction import Update


class CreateBondUpdate(Update):
    def __init__(self, update_type, issuer, corporate_debt_ratings,
                 maturity_date, amount_outstanding, coupon_type, coupon_rate,
                 coupon_frequency, first_coupon_date, face_value,
                 first_settlement_date=None, coupon_benchmark=None,
                 cusip=None, isin=None, object_id=None, nonce=None):
        super(CreateBondUpdate, self).__init__(update_type)
        self._issuer = issuer
        self._isin = isin
        self._cusip = cusip
        self._corporate_debt_ratings = corporate_debt_ratings
        self._first_settlement_date = first_settlement_date
        self._amount_outstanding = amount_outstanding
        self._maturity_date = maturity_date
        self._coupon_type = coupon_type
        self._coupon_rate = coupon_rate
        self._coupon_benchmark = coupon_benchmark
        self._coupon_frequency = coupon_frequency
        self._first_coupon_date = first_coupon_date
        self._face_value = face_value
        self._nonce = nonce

        if object_id is None:
            self._object_id = self.create_id()
        else:
            self._object_id = object_id

    def check_valid(self, store, txn):
        try:
            store.lookup('participant:key-id', txn.OriginatorID)
        except KeyError:
            raise InvalidTransactionError(
                "Creator was not found : {}".format(txn.OriginatorID))

        if self._object_id in store:
            raise InvalidTransactionError(
                "Object with id already exists: {}".format(self._object_id))

        try:
            store.lookup('organization:ticker', self._issuer)
        except KeyError:
            raise InvalidTransactionError(
                "No such ticker: {}".format(self._issuer))

        if self._isin is None and self._cusip is None:
            raise InvalidTransactionError(
                "A bond needs either Isin or Cusip")

        try:
            store.lookup("bond:isin", self._isin)
            raise InvalidTransactionError(
                "Object with isin already exists: {}".format(self._isin))
        except KeyError:
            pass

        try:
            store.lookup("bond:cusip", self._cusip)
            raise InvalidTransactionError(
                "Object with cusip already exists: {}".format(self._cusip))
        except KeyError:
            pass

        if self._coupon_type != "Floating" and self._coupon_type != "Fixed":
            raise InvalidTransactionError("Coupon type must be Floating "
                                          "or Fixed: {}".format(self._cusip))

        # keys mentioned in libor
        libor = ['Overnight', 'OneWeek', 'OneMonth', 'TwoMonth', 'ThreeMonth',
                 'SixMonth', 'OneYear']

        if self._coupon_benchmark is not None and  \
                self._coupon_benchmark not in libor:
            raise InvalidTransactionError("Coupon Benchmark must a Libor"
                                          " benchmark:"
                                          "{}".format(self._coupon_benchmark))

        if self._coupon_type == "Floating" and self._coupon_benchmark is None:
            raise InvalidTransactionError("Coupon Benchmark must be Libor:"
                                          " {}".format(self._coupon_benchmark))

        try:
            datetime.datetime.strptime(self._maturity_date, "%m/%d/%Y")
        except ValueError:
            raise InvalidTransactionError("Maturity Date is in the wrong "
                                          "format: "
                                          "{}".format(self._maturity_date))

        frequencies = ['Quarterly', 'Monthly', 'Daily']

        if (self._coupon_frequency is not None and
                self._coupon_frequency not in frequencies):
            raise InvalidTransactionError("Coupon Frequency must be "
                                          "one of: {}".format(frequencies))

        try:
            datetime.datetime.strptime(self._first_coupon_date, "%m/%d/%Y")
        except ValueError:
            raise InvalidTransactionError("First Coupon Date is in the wrong "
                                          "format: "
                                          "{}".format(self._first_coupon_date))

    def apply(self, store, txn):
        creator = store.lookup('participant:key-id', txn.OriginatorID)
        obj = {
            'object-id': self._object_id,
            'object-type': 'bond',
            'issuer': self._issuer,
            'corporate-debt-ratings': self._corporate_debt_ratings,
            'amount-outstanding': self._amount_outstanding,
            'maturity-date': self._maturity_date,
            'coupon-type': self._coupon_type,
            'coupon-rate': self._coupon_rate,
            'coupon-frequency': self._coupon_frequency,
            'first-coupon-date': self._first_coupon_date,
            'face-value': self._face_value,
            'ref-count': 0,
            'creator-id': creator["object-id"]
        }
        if self._isin is not None:
            obj['isin'] = self._isin
        if self._cusip is not None:
            obj['cusip'] = self._cusip
        if self._coupon_benchmark is not None:
            obj['coupon-benchmark'] = self._coupon_benchmark
        if self._first_settlement_date is not None:
            obj['first-settlement-date'] = self._first_settlement_date
        store[self._object_id] = obj

        if 'bonds' in store:
            bondlist_obj = store['bonds']
            bondlist_obj['bond-list'].append(self._object_id)
        else:
            bondlist_obj = {
                'object-id': 'bonds',
                'object-type': 'bond-list',
                'bond-list': [self._object_id]
            }
        store['bonds'] = bondlist_obj

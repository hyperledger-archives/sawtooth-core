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

import logging
from datetime import datetime

from sawtooth.exceptions import InvalidTransactionError

from journal.transaction import Update
from sawtooth_bond import bond_utils

LOGGER = logging.getLogger(__name__)


class CreateHoldingUpdate(Update):
    def __init__(self, update_type, owner_id, asset_type,
                 asset_id, amount, object_id=None, nonce=None):
        super(CreateHoldingUpdate, self).__init__(update_type)
        self._owner_id = owner_id
        self._asset_type = asset_type
        self._asset_id = asset_id
        self._amount = amount
        self._nonce = nonce

        if object_id is None:
            self._object_id = self.create_id()
        else:
            self._object_id = object_id

    def check_valid(self, store, txn):
        if self._object_id in store:
            raise InvalidTransactionError(
                "Object with id already exists: {}".format(self._object_id))

        # Verify that the transaction originator is registered
        # as a participant
        try:
            store.lookup('participant:key-id', txn.OriginatorID)
        except KeyError:
            raise InvalidTransactionError(
                "No participant associated with the transaction originator "
                "was found: {}".format(txn.OriginatorID))

        # Verify that owner_id exists in the store
        if self._owner_id not in store:
            raise InvalidTransactionError(
                "No such organization: {}".format(self._owner_id))

        owner = store[self._owner_id]

        # Verify that the object referenced by owner_id is an organization
        if ("object-type" not in owner or
                owner["object-type"] != "organization"):
            raise InvalidTransactionError(
                "Provided owner id does not "
                "reference an organization object: {}".format(self._owner_id))

        bond = None

        if self._asset_type == "Currency":
            if self._asset_id != "USD":
                raise InvalidTransactionError(
                    "Currency holdings must "
                    "be in USD: {}".format(self._object_id))
        elif self._asset_type == "Bond":
            # Verify that the asset_id exists in the store
            if self._asset_id not in store:
                raise InvalidTransactionError(
                    "No such bond: {}".format(self._asset_id))

            bond = store[self._asset_id]

            # Verify that the object referenced by asset_id is a bond
            if ("object-type" not in bond or
                    bond["object-type"] != "bond"):
                raise InvalidTransactionError(
                    "Provided asset id does not "
                    "reference a bond object: {}".format(self._asset_id))
        else:
            raise InvalidTransactionError(
                "Asset type must be 'Currency' "
                "or 'Bond': {}".format(self._object_id))

        # Verify that the organization does not already have a holding
        # with an identical asset id
        if "holdings" in owner:
            for owner_holding in owner["holdings"]:
                holding = store[owner_holding]
                if holding["asset-id"] == self._asset_id:
                    raise InvalidTransactionError(
                        "Provided owner id {} already has "
                        "a holding with asset id: {}".format(self._owner_id,
                                                             self._asset_id))

    def apply(self, store, txn):
        creator = store.lookup('participant:key-id', txn.OriginatorID)
        obj = {
            'object-id': self._object_id,
            'object-type': 'holding',
            'creator-id': creator["object-id"],
            'ref-count': 1,
            'owner-id': self._owner_id,
            'asset-type': self._asset_type,
            'asset-id': self._asset_id,
            'amount': self._amount
        }
        store[self._object_id] = obj

        owner_obj = store[self._owner_id]
        if "holdings" in owner_obj:
            owner_obj["holdings"].append(self._object_id)
        else:
            owner_obj["holdings"] = [self._object_id]
        owner_obj["ref-count"] += 1
        store[self._owner_id] = owner_obj

        if self._asset_type == "Bond":
            bond_obj = store[self._asset_id]
            bond_obj["ref-count"] += 1
            store[self._asset_id] = bond_obj


class CreateSettlementUpdate(Update):
    def __init__(self, update_type, order_id, object_id=None, nonce=None):
        super(CreateSettlementUpdate, self).__init__(update_type)
        self._order_id = order_id
        self._nonce = nonce

        if object_id is None:
            self._object_id = self.create_id()
        else:
            self._object_id = object_id

        self.__action__ = None
        self.__order__ = None
        self.__cost__ = None
        self.__quote__ = None
        self.__quoting_firm__ = None
        self.__ordering_firm__ = None
        self.__qfch__ = None
        self.__qfbh__ = None
        self.__ofch__ = None
        self.__ofbh__ = None

    def check_valid(self, store, txn):
        if self._object_id in store:
            raise InvalidTransactionError(
                "Object with id already exists: {}".format(self._object_id))

        # Verify that the transaction originator is registered
        # as a participant
        try:
            store.lookup('participant:key-id', txn.OriginatorID)
        except KeyError:
            raise InvalidTransactionError(
                "No participant associated with the transaction originator "
                "was found: {}".format(txn.OriginatorID))

        # Verify that order_id exists in the store
        if self._order_id not in store:
            raise InvalidTransactionError(
                "No such order: {}".format(self._order_id))

        order = store[self._order_id]

        # Verify that the object referenced by order_id is an order
        if ("object-type" not in order or
                order["object-type"] != "order"):
            raise InvalidTransactionError(
                "Provided order id does not "
                "reference an order object: {}".format(self._order_id))

        # Verify that the status on the order is "Matched"
        if ("status" not in order or
                order["status"] != "Matched"):
            raise InvalidTransactionError(
                "Provided order is not in "
                "matched status: {}".format(self._order_id))

        # Look up bond
        bond = None

        if "isin" in order:
            bond = store.lookup('bond:isin', order["isin"])
        elif "cusip" in order:
            bond = store.lookup('bond:cusip', order["cusip"])
        else:
            raise InvalidTransactionError(
                "Provided order does not "
                "reference a bond: {}".format(self._order_id))

        bond_obj_id = bond["object-id"]

        # Verify that the order references a quote-id
        if "quote-id" not in order:
            raise InvalidTransactionError(
                "Provided order is in matched status but "
                "does not reference a "
                "valid quote-id: {}".format(self._order_id))

        quote_id = store[self._order_id]["quote-id"]

        # Verify that the quote-id is in the store
        if quote_id not in store:
            raise InvalidTransactionError(
                "No such quote: {} referenced "
                "in order: {}".format(quote_id, self._order_id))

        quote = store[quote_id]

        # Verify that the object type referenced by quote-id is a quote
        if ("object-type" not in quote or
                quote["object-type"] != "quote"):
            raise InvalidTransactionError(
                "Provided quote id does not "
                "reference a quote object: {} "
                "referenced in order: {}".format(quote_id, self._order_id))

        # Verify that the quote contains a firm id (pricing source)
        if "firm" not in quote:
            raise InvalidTransactionError(
                "Provided quote id does not "
                "contain a firm identifier: {}".format(quote_id))

        # Look up the firm by pricing source
        try:
            quoting_firm = store.lookup('organization:pricing-source',
                                        quote["firm"])
        except KeyError:
            raise InvalidTransactionError(
                "No such pricing source: {}".format(quote["firm"]))

        quoting_firm_id = quoting_firm["object-id"]

        # Verify the quoting_firm has holdings
        if ("holdings" not in quoting_firm or
                len(quoting_firm["holdings"]) == 0):
            raise InvalidTransactionError(
                "Referenced quoting firm "
                "has no holdings: {}".format(quote["firm"]))

        quoting_firm_currency_holding = None
        quoting_firm_bond_holding = None

        # Iterate through the quoting_firm holdings and identify
        # the currency holding and the specific bond holding
        for holding_id in quoting_firm["holdings"]:
            if holding_id not in store:
                continue

            holding = store[holding_id]

            if ("object-type" not in holding or
                    holding["object-type"] != "holding"):
                continue

            if (holding["asset-type"] == "Currency" and
                    holding["asset-id"] == "USD"):
                quoting_firm_currency_holding = holding
                continue

            if (holding["asset-type"] == "Bond" and
                    holding["asset-id"] == bond_obj_id):
                quoting_firm_bond_holding = holding
                continue

        # We must identify both holdings, otherwise the settlement
        # is invalid
        if (quoting_firm_currency_holding is None or
                quoting_firm_bond_holding is None):
            raise InvalidTransactionError(
                "Referenced quoting firm "
                "does not have the correct holdings: {}".format(quote["firm"]))

        # Verify that order contains an ordering firm-id
        if "firm-id" not in order:
            raise InvalidTransactionError(
                "Provided order is in matched status but "
                "does not reference "
                "a valid firm-id: {}".format(self._order_id))

        ordering_firm_id = store[self._order_id]["firm-id"]

        # Verify that the ordering firm-id is in the store
        if ordering_firm_id not in store:
            raise InvalidTransactionError(
                "No such firm: {} referenced "
                "in order: {}".format(ordering_firm_id, self._order_id))

        ordering_firm = store[ordering_firm_id]

        # Verify that the ordering firm-id references an org object
        if ("object-type" not in ordering_firm or
                ordering_firm["object-type"] != "organization"):
            raise InvalidTransactionError(
                "Referenced firm object is not "
                "an organization: {} referenced in "
                "order: {}".format(ordering_firm_id, self._order_id))

        # Verify that the ordering firm references holdings
        if ("holdings" not in ordering_firm or
                len(ordering_firm["holdings"]) == 0):
            raise InvalidTransactionError(
                "Referenced ordering firm "
                "has no holdings: {}".format(ordering_firm_id))

        ordering_firm_currency_holding = None
        ordering_firm_bond_holding = None

        # Iterate through the quoting_firm holdings and identify
        # the currency holding and the specific bond holding
        for holding_id in ordering_firm["holdings"]:
            if holding_id not in store:
                pass

            holding = store[holding_id]

            if ("object-type" not in holding or
                    holding["object-type"] != "holding"):
                pass

            if (holding["asset-type"] == "Currency" and
                    holding["asset-id"] == "USD"):
                ordering_firm_currency_holding = holding

            if (holding["asset-type"] == "Bond" and
                    holding["asset-id"] == bond_obj_id):
                ordering_firm_bond_holding = holding

        # We must identify both holdings, otherwise the trade
        # cannot be settled
        if (ordering_firm_currency_holding is None or
                ordering_firm_bond_holding is None):
            raise InvalidTransactionError(
                "Referenced ordering firm does not "
                "have the correct holdings: {}".format(ordering_firm_id))

        # Determine the cost and whether the involved source holdings
        # have sufficient funds/bonds in them based on whether this
        # is a buy or sell order
        if order["action"] == "Buy":
            price = bond_utils.bondprice_to_float(quote["ask-price"]) / 100
            cost = order["quantity"] * price

            if ordering_firm_currency_holding["amount"] < cost:
                raise InvalidTransactionError(
                    "Ordering firm does not "
                    "have sufficient funds in "
                    "its currency holding: {}".format(ordering_firm_id))

            if quoting_firm_bond_holding["amount"] < order["quantity"]:
                raise InvalidTransactionError(
                    "Quoting firm does not "
                    "have a sufficient quantity "
                    "in its bond holding: {}".format(quoting_firm_id))
        else:
            price = bond_utils.bondprice_to_float(quote["bid-price"]) / 100
            cost = order["quantity"] * price

            if quoting_firm_currency_holding["amount"] < cost:
                raise InvalidTransactionError(
                    "Quoting firm does not "
                    "have sufficient funds in "
                    "its currency holding: {}".format(quoting_firm_id))

            if ordering_firm_bond_holding["amount"] < order["quantity"]:
                raise InvalidTransactionError(
                    "Ordering firm does not "
                    "have a sufficient quantity "
                    "in its bond holding: {}".format(ordering_firm_id))

        self.__action__ = order["action"]
        self.__order__ = order
        self.__cost__ = cost
        self.__quote__ = quote
        self.__quoting_firm__ = quoting_firm
        self.__ordering_firm__ = ordering_firm
        self.__qfch__ = quoting_firm_currency_holding
        self.__qfbh__ = quoting_firm_bond_holding
        self.__ofch__ = ordering_firm_currency_holding
        self.__ofbh__ = ordering_firm_bond_holding

    def apply(self, store, txn):
        creator = store.lookup('participant:key-id', txn.OriginatorID)
        obj = {
            'object-id': self._object_id,
            'object-type': 'settlement',
            'creator-id': creator["object-id"],
            'order-id': self._order_id,
            'ordering-firm-id': self.__ordering_firm__["object-id"],
            'quoting-firm-id': self.__quoting_firm__["object-id"],
            'order-bond-holding-id': self.__ofbh__["object-id"],
            'order-currency-holding-id': self.__ofch__["object-id"],
            'quote-bond-holding-id': self.__qfbh__["object-id"],
            'quote-currency-holding-id': self.__qfch__["object-id"],
            'action': self.__action__,
            'bond-quantity': self.__order__["quantity"],
            'currency-amount': self.__cost__,
        }
        store[self._object_id] = obj

        ofbh_obj = store[self.__ofbh__["object-id"]]
        ofch_obj = store[self.__ofch__["object-id"]]
        qfbh_obj = store[self.__qfbh__["object-id"]]
        qfch_obj = store[self.__qfch__["object-id"]]

        if self.__action__ == "Buy":
            ofbh_obj["amount"] += self.__order__["quantity"]
            qfbh_obj["amount"] -= self.__order__["quantity"]
            ofch_obj["amount"] -= self.__cost__
            qfch_obj["amount"] += self.__cost__
        else:
            ofbh_obj["amount"] -= self.__order__["quantity"]
            qfbh_obj["amount"] += self.__order__["quantity"]
            ofch_obj["amount"] += self.__cost__
            qfch_obj["amount"] -= self.__cost__

        ofbh_obj["ref-count"] += 1
        ofch_obj["ref-count"] += 1
        qfbh_obj["ref-count"] += 1
        qfch_obj["ref-count"] += 1

        store[ofbh_obj["object-id"]] = ofbh_obj
        store[ofch_obj["object-id"]] = ofch_obj
        store[qfbh_obj["object-id"]] = qfbh_obj
        store[qfch_obj["object-id"]] = qfch_obj

        ordering_firm_obj = store[self.__ordering_firm__["object-id"]]
        ordering_firm_obj["ref-count"] += 1
        store[ordering_firm_obj["object-id"]] = ordering_firm_obj

        quoting_firm_obj = store[self.__quoting_firm__["object-id"]]
        quoting_firm_obj["ref-count"] += 1
        store[quoting_firm_obj["object-id"]] = quoting_firm_obj

        order_obj = store[self._order_id]
        order_obj["ref-count"] += 1
        order_obj["status"] = "Settled"
        store[order_obj["object-id"]] = order_obj

        self.__quote__["ref-count"] += 1
        store[self.__quote__["object-id"]] = self.__quote__


class CreateReceiptUpdate(Update):
    def __init__(self, update_type, payment_type, bond_id, payee_id,
                 coupon_date=None, object_id=None, nonce=None):
        super(CreateReceiptUpdate, self).__init__(update_type)
        self._payment_type = payment_type
        self._bond_id = bond_id
        self._payee_id = payee_id
        self._coupon_date = coupon_date
        self._nonce = nonce

        if object_id is None:
            self._object_id = self.create_id()
        else:
            self._object_id = object_id

        self.__payee_bond_holding__ = None
        self.__payee_cash_holding__ = None
        self.__payer_bond_holding__ = None
        self.__payer_cash_holding__ = None
        self.__amount__ = None

    def check_valid(self, store, txn):
        if self._object_id in store:
            raise InvalidTransactionError(
                "Object with id already exists: {}".format(self._object_id))

        # Verify that payment type is Coupon or Redemption
        payment_types = ['Coupon', 'Redemption']

        if (self._payment_type is not None and
                self._payment_type not in payment_types):
            raise InvalidTransactionError("Payment Type must be "
                                          "one of: {}".format(payment_types))
        # Verify that bond exists
        if self._bond_id not in store:
            raise InvalidTransactionError(
                "No such bond: {}".format(self._bond_id))

        bond = store[self._bond_id]

        # Verify that the object referenced by bond_id is a bond
        if ("object-type" not in bond or
                bond["object-type"] != "bond"):
            raise InvalidTransactionError(
                "Provided bond id does not "
                "reference a bond object: {}".format(self._bond_id))

        # Verify that payee exists
        if self._payee_id not in store:
            raise InvalidTransactionError(
                "No such organization: {}".format(self._payee_id))

        payee = store[self._payee_id]

        # Verify that the object referenced by payee_id is an organization
        if ("object-type" not in payee or
                payee["object-type"] != "organization"):
            raise InvalidTransactionError(
                "Provided payee id does not "
                "reference an organization object: {}".format(self._payee_id))

        # Verify that payee has a holding in bond with qty > 0 and that
        # payee has a cash holding to receive the funds
        if ("holdings" not in payee or
                len(payee["holdings"]) == 0):
            raise InvalidTransactionError(
                "Referenced payee firm "
                "has no holdings: {}".format(payee["object-id"]))

        payee_bond_holding = None
        payee_cash_holding = None

        for payee_holding_id in payee["holdings"]:
            payee_holding = store[payee_holding_id]
            if payee_holding["asset-id"] == bond["object-id"]:
                payee_bond_holding = payee_holding
            if (payee_holding["asset-type"] == "Currency" and
                    payee_holding["asset-id"] == "USD"):
                payee_cash_holding = payee_holding

        if payee_bond_holding is None:
            raise InvalidTransactionError(
                "Referenced payee firm "
                "does not have a holding in "
                "the specified bond: {}".format(payee["object-id"]))

        if payee_bond_holding["amount"] <= 0:
            raise InvalidTransactionError(
                "Referenced payee firm "
                "does not have a non-zero holding in "
                "the specified bond: {}".format(payee["object-id"]))

        if payee_cash_holding is None:
            raise InvalidTransactionError(
                "Referenced payee firm "
                "has no cash holding: {}".format(payee["object-id"]))

        # Verify that the payer has cash money and that payer has a
        # holding to contain the bonds if this is a maturity
        # redemption
        try:
            payer = store.lookup('organization:ticker', bond["issuer"])
        except KeyError:
            raise InvalidTransactionError(
                "Bond's issuer is not a "
                "valid organization: {}".format(bond["issuer"]))

        if ("holdings" not in payer or
                len(payer["holdings"]) == 0):
            raise InvalidTransactionError(
                "Referenced payer firm "
                "has no holdings: {}".format(payer["object-id"]))

        payer_bond_holding = None
        payer_cash_holding = None

        for payer_holding_id in payer["holdings"]:
            payer_holding = store[payer_holding_id]
            if payer_holding["asset-id"] == bond["object-id"]:
                payer_bond_holding = payer_holding
            if (payer_holding["asset-type"] == "Currency" and
                    payer_holding["asset-id"] == "USD"):
                payer_cash_holding = payer_holding

        if (self._payment_type == "Redemption" and
                payer_bond_holding is None):
            raise InvalidTransactionError(
                "Referenced payer firm "
                "does not have a holding in "
                "the specified bond: {}".format(payer["object-id"]))

        if payer_cash_holding is None:
            raise InvalidTransactionError(
                "Referenced payer firm "
                "has no cash holding: {}".format(payer["object-id"]))

        if self._payment_type == "Coupon":
            amount = payee_bond_holding["amount"]

            rate = float(bond["coupon-rate"])

            if bond["coupon-type"] == "Floating":
                if "current_libor" not in store:
                    raise InvalidTransactionError("No current LIBOR "
                                                  "rates found")

                current_libor = store["current_libor"]

                if bond["coupon-benchmark"] not in current_libor["rates"]:
                    raise InvalidTransactionError("Coupon benchmark not "
                                                  "listed in LIBOR rates")

                libor_rate = current_libor["rates"][bond["coupon-benchmark"]]
                rate += float(libor_rate)

            if bond["coupon-frequency"] == "Quarterly":
                rate = rate / 4
            elif bond["coupon-frequency"] == "Monthly":
                rate = rate / 12
            elif bond["coupon-frequency"] == "Daily":
                rate = rate / 365

            amount = round(amount * rate, 2)
        elif self._payment_type == "Redemption":
            amount = payee_bond_holding["amount"]

        # Verify the payer org has the right amount of cash
        if payer_cash_holding["amount"] < amount:
            raise InvalidTransactionError(
                "Referenced payer firm "
                "does not have sufficient cash to "
                "pay the coupon/redemption: {}".format(payer["object-id"]))

        if self._payment_type == "Coupon":
            # Verify that coupon date is in the right format
            try:
                redeem_date = \
                    datetime.strptime(self._coupon_date, "%m/%d/%Y")
            except ValueError:
                raise InvalidTransactionError("Coupon Date is in the wrong "
                                              "format: "
                                              "{}".format(self._coupon_date))

            # Verify that coupon date is current date
            if redeem_date.date() != datetime.\
                    fromtimestamp(store["current_clock"]["timestamp"]).date():
                raise InvalidTransactionError("The requested coupon redemption"
                                              " date is not the current date")

            # Verify that coupon date is a valid coupon date for the bond
            if redeem_date <= \
                    datetime.strptime(bond["first-coupon-date"], "%m/%d/%Y"):
                raise InvalidTransactionError(
                    "Provided coupon redemption date is prior to "
                    "the first coupon date on the bond")

            if redeem_date > \
                    datetime.strptime(bond["maturity-date"], "%m/%d/%Y"):
                raise InvalidTransactionError(
                    "Provided coupon redemption date is after the "
                    "maturity date of the bond")

            if bond["coupon-frequency"] == "Quarterly":
                if (redeem_date.month not in [1, 4, 7, 10] or
                        redeem_date.day != 1):
                    raise InvalidTransactionError(
                        "Provided coupon date does not fall on a "
                        "start of quarter date as required by this bond")
            elif bond["coupon-frequency"] == "Monthly":
                if redeem_date.day != 1:
                    raise InvalidTransactionError(
                        "Provided coupon date does not fall on the "
                        "first of a month as required by this bond")

            # Verify that the payee doesn't already have a receipt for this
            # bond/date combo
            if "receipts" in payee:
                for receipt_id in payee["receipts"]:
                    if receipt_id not in store:
                        continue

                    receipt = store[receipt_id]

                    if ("object-type" not in receipt or
                            receipt["object-type"] != "receipt"):
                        continue

                    if (receipt["payee-id"] == payee["object-id"] and
                            receipt["bond-id"] == bond["object-id"] and
                            receipt["payment-type"] == "Coupon" and
                            receipt["coupon-date"] == self._coupon_date):
                        raise InvalidTransactionError(
                            "The payee has already received a coupon "
                            "payment for this period")

        elif self._payment_type == "Redemption":
            # Make sure maturity date has been reached
            if datetime.strptime(
                    bond["maturity-date"], "%m/%d/%Y").date() > \
               datetime.fromtimestamp(
                    store["current_clock"]["timestamp"]).date():
                raise InvalidTransactionError(
                    "Attempt to redeem a bond prior to its maturity date")

        # With this design (not tracking coupons to bond instances), I don't
        # see an effective way to prevent two organizations from claiming
        # coupon payments on the 'same' bonds before and after a trade

        self.__payee_bond_holding__ = payee_bond_holding
        self.__payee_cash_holding__ = payee_cash_holding
        self.__payer_bond_holding__ = payer_bond_holding
        self.__payer_cash_holding__ = payer_cash_holding
        self.__amount__ = amount

    def apply(self, store, txn):
        time = store.get("current_clock")["timestamp"]
        obj = {
            'object-id': self._object_id,
            'object-type': 'receipt',
            'bond-id': self._bond_id,
            'payee-id': self._payee_id,
            'payment-type': self._payment_type,
            'coupon-date': self._coupon_date,
            'amount': self.__amount__,
            'timestamp': time
        }
        store[self._object_id] = obj

        # Add this receipt to the payee's receipts list
        payee_obj = store[self._payee_id]
        if "receipts" in payee_obj:
            payee_obj["receipts"].append(self._object_id)
        else:
            payee_obj["receipts"] = [self._object_id]
        payee_obj["ref-count"] += 1
        store[self._payee_id] = payee_obj

        # Increment the bond's reference count
        bond_obj = store[self._bond_id]
        bond_obj["ref-count"] += 1
        store[self._bond_id] = bond_obj

        # Pay out cash for coupons or maturity redemptions
        self.__payer_cash_holding__["amount"] -= self.__amount__
        self.__payee_cash_holding__["amount"] += self.__amount__

        # For redemptions, return the bonds to the issuer
        if self._payment_type == "Redemption":
            self.__payer_bond_holding__["amount"] += \
                self.__payee_bond_holding__["amount"]
            self.__payee_bond_holding__["amount"] = 0
            store[self.__payer_bond_holding__["object-id"]] = \
                self.__payer_bond_holding__

        store[self.__payer_cash_holding__["object-id"]] = \
            self.__payer_cash_holding__
        store[self.__payee_cash_holding__["object-id"]] = \
            self.__payee_cash_holding__
        store[self.__payee_bond_holding__["object-id"]] = \
            self.__payee_bond_holding__

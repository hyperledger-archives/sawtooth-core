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

from sawtooth.exceptions import InvalidTransactionError

from sawtooth_bond import bond_utils
from journal.transaction import Update

LOGGER = logging.getLogger(__name__)


class CreateQuoteUpdate(Update):
    def __init__(self, update_type, firm, bid_price, bid_qty, ask_price,
                 ask_qty, object_id=None, cusip=None, isin=None, nonce=None):
        super(CreateQuoteUpdate, self).__init__(update_type)
        self._firm = firm
        self._isin = isin
        self._cusip = cusip
        self._bid_price = bid_price
        self._bid_qty = bid_qty
        self._ask_price = ask_price
        self._ask_qty = ask_qty
        self._nonce = nonce

        if object_id is None:
            self._object_id = self.create_id()
        else:
            self._object_id = object_id

    def check_valid(self, store, txn):
        if self._object_id in store:
            raise InvalidTransactionError(
                "Object with id already exists: {}".format(self._object_id))
        try:
            firm = store.lookup('organization:pricing-source', self._firm)
        except KeyError:
            raise InvalidTransactionError(
                "No such pricing source: {}".format(self._firm))

        if self._isin is None and self._cusip is None:
            raise InvalidTransactionError(
                "Cusip or Isin must be set: {}".format(self._object_id))

        if self._isin is not None and self._cusip is None:
            try:
                store.lookup('bond:isin', self._isin)
            except KeyError:
                raise InvalidTransactionError(
                    "No such Bond: {}".format(self._firm))

        if self._isin is None and self._cusip is not None:
            try:
                store.lookup('bond:cusip', self._cusip)
            except KeyError:
                raise InvalidTransactionError(
                    "No such Bond: {}".format(self._cusip))

        if self._isin is not None and self._cusip is not None:
            try:
                cusip_id = store.lookup('bond:cusip', self._cusip)["object-id"]
                isin_id = store.lookup('bond:isin', self._isin)["object-id"]
            except KeyError:
                raise InvalidTransactionError(
                    "No such Bond: {}, {}".format(self._cusip, self._isin))

            if cusip_id != isin_id:
                raise InvalidTransactionError("Cusip {} and Isin {} do not "
                                              "belong to the same bond"
                                              .format(cusip_id, isin_id))

        try:
            submitter = store.lookup("participant:key-id", txn.OriginatorID)
        except KeyError:
            raise InvalidTransactionError("Only an authorized marketmaker can"
                                          " create a quote")

        if "authorization" not in firm:
            raise InvalidTransactionError("Only an authorized marketmaker can"
                                          " create a quote")

        participant = {"participant-id": submitter["object-id"],
                       "role": "marketmaker"}
        if participant not in firm["authorization"]:
            raise InvalidTransactionError("Only an authorized marketmaker can"
                                          " create a quote")

        try:
            bond_utils.bondprice_to_float(self._bid_price)
        except Exception:
            raise InvalidTransactionError("Bid price is not formatted "
                                          "correctly for "
                                          "quote {}".format(self._object_id))

        try:
            bond_utils.bondprice_to_float(self._ask_price)
        except Exception:
            raise InvalidTransactionError("Ask price is not formatted "
                                          "correctly for "
                                          "quote {}".format(self._object_id))

    def apply(self, store, txn):
        creator = store.lookup("participant:key-id", txn.OriginatorID)
        time = store.get("current_clock")["timestamp"]
        firm = store.lookup('organization:pricing-source', self._firm)
        obj = {
            'object-id': self._object_id,
            'object-type': 'quote',
            'creator-id': creator["object-id"],
            'firm': self._firm,
            'ref-count': 0,
            'bid-price': self._bid_price,
            'bid-qty': self._bid_qty,
            'ask-price': self._ask_price,
            'ask-qty': self._ask_qty,
            'timestamp': time,
            'status': 'Open'
        }
        if self._isin is not None:
            obj['isin'] = self._isin
            bond = store.lookup('bond:isin', self._isin)
        if self._cusip is not None:
            obj['cusip'] = self._cusip
            bond = store.lookup('bond:cusip', self._cusip)
        store[self._object_id] = obj

        firm["ref-count"] += 1
        store[firm["object-id"]] = firm

        bond["ref-count"] += 1
        store[bond["object-id"]] = bond

        if obj['status'] == 'Open':
            if 'open-quotes' in store:
                oq_obj = store['open-quotes']
                oq_obj['quote-list'].append(self._object_id)
            else:
                oq_obj = {
                    'object-id': 'open-quotes',
                    'object-type': 'open-quote-list',
                    'quote-list': [self._object_id]
                }
            store['open-quotes'] = oq_obj


class DeleteQuoteUpdate(Update):
    def __init__(self, update_type, object_id, nonce=None):
        super(DeleteQuoteUpdate, self).__init__(update_type)
        self._object_id = object_id
        self._nonce = nonce

    def check_valid(self, store, txn):
        if self._object_id not in store:
            raise InvalidTransactionError(
                "Object with id does not exist: {}".format(self._object_id))

        quote = store.get(self._object_id)
        try:
            participant = store.lookup('participant:key-id', txn.OriginatorID)
        except:
            raise InvalidTransactionError("Participant does not exist.")

        if participant["object-id"] != quote["creator-id"]:
            raise InvalidTransactionError(
                "A quote can only be deleted by its creator {}"
                .format(participant["object-id"]))

        if quote["ref-count"] != 0:
            raise InvalidTransactionError(
                "A quote can only be deleted if its ref-count is zero {}"
                .format(quote["ref-count"]))

    def apply(self, store, txn):
        # decrement refcount for bond and organization
        quote = store.get(self._object_id)
        organization = store.lookup("organization:pricing-source",
                                    quote["firm"])
        organization["ref-count"] -= 1
        store[organization["object-id"]] = organization

        if "isin" in quote:
            bond = store.lookup("bond:isin", quote["isin"])

        elif "cusip" in quote:
            bond = store.lookup("bond:cusip", quote["cusip"])

        bond["ref-count"] -= 1
        store[bond["object-id"]] = bond

        store.delete(self._object_id)

        if 'open-quotes' in store:
            oq_obj = store['open-quotes']
            if self._object_id in oq_obj['quote-list']:
                oq_obj['quote-list'].remove(self._object_id)
                store['open-quotes'] = oq_obj


class CreateOrderUpdate(Update):
    def __init__(self, update_type, action, quantity, order_type,
                 firm_id, quote_id=None, isin=None, cusip=None,
                 limit_price=None, limit_yield=None, object_id=None,
                 nonce=None):
        super(CreateOrderUpdate, self).__init__(update_type)
        self._isin = isin
        self._cusip = cusip
        self._action = action
        self._quantity = quantity
        self._limit_price = limit_price
        self._limit_yield = limit_yield
        self._order_type = order_type
        self._firm_id = firm_id
        self._quote_id = quote_id
        self._nonce = nonce

        if object_id is None:
            self._object_id = self.create_id()
        else:
            self._object_id = object_id

        # set in check_valid for use in apply
        self.__bond__ = None
        self.__organization__ = None

    def check_valid(self, store, txn):
        if self._object_id in store:
            raise InvalidTransactionError(
                "Object with id already exists: {}".format(self._object_id))

        if self._action not in ['Buy', 'Sell']:
            raise InvalidTransactionError(
                "Action must be either Buy or Sell"
            )

        for att in [self._action, self._object_id, self._order_type,
                    self._firm_id, self._quantity]:
            if att is None:
                raise InvalidTransactionError("Action, ObjectId, "
                                              "OrderType, FirmId, and "
                                              "Quantity are "
                                              "required.")
        if self._firm_id not in store:
            raise InvalidTransactionError("No organization with FirmId")

        try:
            store.get(self._firm_id, 'organization')
        except KeyError:
            raise InvalidTransactionError(
                "FirmId does not reference an organization")
        try:
            _ = store.lookup("participant:key-id", txn.OriginatorID)
        except KeyError:
            raise InvalidTransactionError("Only participants can create an "
                                          "order")

        if self._order_type == 'Limit':
            if self._limit_yield is None and self._limit_price is None:
                raise InvalidTransactionError("For Limit orders,"
                                              "either limit yield or "
                                              "limit price "
                                              "must be specified.")
        elif self._order_type == 'Market':
            if self._limit_price is not None or self._limit_yield is not None:
                raise InvalidTransactionError("Cannot set a market order with "
                                              "limit yield or limit price")
        else:
            raise InvalidTransactionError("OrderType must either be Market "
                                          "or Limit.")

        if self._limit_price is not None:
            try:
                bond_utils.bondprice_to_float(self._limit_price)
            except Exception:
                raise InvalidTransactionError("Limit price is not formatted "
                                              "correctly for order "
                                              "{}".format(self._object_id))

        if self._isin is not None:
            if self._cusip is not None:
                try:
                    bond_by_isin = store.lookup('bond:isin', self._isin)
                    bond_by_cusip = store.lookup('bond:cusip', self._cusip)
                    if bond_by_isin != bond_by_cusip:
                        raise InvalidTransactionError("Isin and Cusip "
                                                      "reference "
                                                      "different bonds.")
                    self.__bond__ = bond_by_isin
                except KeyError:
                    raise InvalidTransactionError("Missing bond with isin or "
                                                  "cusip")
            else:
                try:
                    self.__bond__ = store.lookup('bond:isin', self._isin)
                except KeyError:
                    raise InvalidTransactionError("Bond with that isin "
                                                  "doesn't exist.")
        else:
            if self._cusip is not None:
                try:
                    self.__bond__ = store.lookup('bond:cusip', self._cusip)
                except KeyError:
                    raise InvalidTransactionError("Bond with that cusip "
                                                  "doesn't exist.")
            else:
                raise InvalidTransactionError("At least one of isin or cusip "
                                              "is needed.")
        try:
            self.__organization__ = store.get(self._firm_id, 'organization')
        except KeyError:
            raise InvalidTransactionError("FirmId does not reference an "
                                          "organization.")

    def apply(self, store, txn):
        creator = store.lookup("participant:key-id", txn.OriginatorID)
        time = store.get("current_clock")["timestamp"]
        obj = {
            'object-id': self._object_id,
            'object-type': 'order',
            'action': self._action,
            'creator-id': creator['object-id'],
            'quantity': self._quantity,
            'order-type': self._order_type,
            'firm-id': self._firm_id,
            'ref-count': 0,
            'status': 'Open',
            'timestamp': time
        }
        if self._isin is not None:
            obj['isin'] = self._isin
        if self._cusip is not None:
            obj['cusip'] = self._cusip

        if self._limit_price is not None:
            obj['limit-price'] = self._limit_price
        if self._limit_yield is not None:
            obj['limit-yield'] = self._limit_yield
        if self._quote_id is not None:
            obj['quote-id'] = self._quote_id
            obj['status'] = 'Matched'
            obj["ref-count"] += 1

        self.__organization__['ref-count'] += 1
        store.set(self.__organization__['object-id'], self.__organization__)

        self.__bond__['ref-count'] += 1
        store.set(self.__bond__['object-id'], self.__bond__)

        store[self._object_id] = obj

        if obj['status'] == 'Open':
            if 'open-orders' in store:
                oo_obj = store['open-orders']
                oo_obj['order-list'].append(self._object_id)
            else:
                oo_obj = {
                    'object-id': 'open-orders',
                    'object-type': 'open-order-list',
                    'order-list': [self._object_id]
                }
            store['open-orders'] = oo_obj


class UpdateOrderUpdate(Update):
    def __init__(self, update_type, object_id, quote_id=None, status=None,
                 nonce=None):
        super(UpdateOrderUpdate, self).__init__(update_type)

        self._object_id = object_id
        self._quote_id = quote_id
        self._status = status
        self._nonce = nonce

    def check_valid(self, store, txn):
        if self._object_id not in store:
            raise InvalidTransactionError(
                "Order with object-id doesn't exist: {}".
                format(self._object_id))
        try:
            order_obj = store.get(self._object_id, 'order')
        except KeyError:
            raise InvalidTransactionError(
                "Object id doesn't refer to an order.")

        if self._quote_id is not None:
            if self._quote_id not in store:
                raise InvalidTransactionError(
                    "No quote with quote id: {}".format(self._quote_id))
            try:
                quote_obj = store.get(self._quote_id, 'quote')
            except KeyError:
                raise InvalidTransactionError(
                    "Quote id does not reference a quote")

            if quote_obj['status'] != 'Open':
                raise InvalidTransactionError(
                    "Referenced quote id: {} on order update for order: {} "
                    "has been closed".format(self._quote_id, self._object_id))

            try:
                if 'cusip' in quote_obj:
                    quote_bond = store.lookup('bond:cusip', quote_obj['cusip'])
                elif 'isin' in quote_obj:
                    quote_bond = store.lookup('bond:isin', quote_obj['isin'])

                if 'cusip' in order_obj:
                    order_bond = store.lookup('bond:cusip', order_obj['cusip'])
                elif 'isin' in order_obj:
                    order_bond = store.lookup('bond:isin', order_obj['isin'])
            except KeyError:
                raise InvalidTransactionError(
                    "Referenced order or quote bond does not appear "
                    "in store.")

            if quote_bond is None or order_bond is None:
                raise InvalidTransactionError(
                    "Could not lookup bond for both quote: {} and "
                    "order: {}".format(self._quote_id, self._object_id))

            if quote_bond['object-id'] != order_bond['object-id']:
                raise InvalidTransactionError(
                    "Referenced quote id: {} on order update for order: {} "
                    "does not match the bond on "
                    "the order".format(self._quote_id, self._object_id))

            if order_obj['action'] == 'Buy':
                if quote_obj['ask-qty'] < order_obj['quantity']:
                    raise InvalidTransactionError(
                        "Quote id: {} does not have sufficient quantity to "
                        "satisfy order: {}".format(self._quote_id,
                                                   self._object_id))
            elif order_obj['action'] == 'Sell':
                if quote_obj['bid-qty'] < order_obj['quantity']:
                    raise InvalidTransactionError(
                        "Quote id: {} does not have sufficient quantity to "
                        "satisfy order: {}".format(self._quote_id,
                                                   self._object_id))

        if (self._status is not None and
                self._status not in ['Open', 'Matched', 'Settled']):
            raise InvalidTransactionError(
                "Status must be either Open, Matched, or Settled."
            )

    def apply(self, store, txn):
        order_obj = store.get(self._object_id, 'order')

        if self._status is not None:
            if (order_obj['status'] == 'Open' and
                    self._status == "Matched"):
                oo_obj = store['open-orders']
                oo_obj['order-list'].remove(self._object_id)
                store['open-orders'] = oo_obj
            order_obj['status'] = self._status

        if self._quote_id is not None:
            order_obj['quote-id'] = self._quote_id

            quote_obj = store.get(self._quote_id, 'quote')

            if 'ref-count' not in quote_obj:
                quote_obj['ref-count'] = 1
            else:
                quote_obj['ref-count'] += 1

            if order_obj['action'] == 'Buy':
                quote_obj['ask-qty'] -= order_obj['quantity']
            elif order_obj['action'] == 'Sell':
                quote_obj['bid-qty'] -= order_obj['quantity']

            # If there is less than a round lot available in
            # either bid or ask quantity after a match, close
            # the quote.
            if (quote_obj['ask-qty'] < 100000 or
                    quote_obj['bid-qty'] < 100000):
                quote_obj['status'] = "Closed"
                oq_obj = store['open-quotes']
                oq_obj['quote-list'].remove(self._quote_id)
                store['open-quotes'] = oq_obj

            store[self._quote_id] = quote_obj

        store[self._object_id] = order_obj


class DeleteOrderUpdate(Update):
    def __init__(self, update_type, object_id, nonce=None):
        super(DeleteOrderUpdate, self).__init__(update_type)
        self._object_id = object_id
        self._nonce = nonce

    def check_valid(self, store, txn):
        if self._object_id not in store:
            raise InvalidTransactionError(
                "Object with id does not exist: {}".format(self._object_id))

        order = store.get(self._object_id)
        try:
            participant = store.lookup('participant:key-id',
                                       txn.OriginatorID)
        except:
            raise InvalidTransactionError("Participant does not exist.")

        if participant["object-id"] != order["creator-id"]:
            raise InvalidTransactionError(
                "An order can only be deleted by its creator {}"
                .format(participant["object-id"]))

        if order["ref-count"] != 0:
            raise InvalidTransactionError(
                "An order can only be deleted if its ref-count is zero {}"
                .format(order["ref-count"]))

    def apply(self, store, txn):
        order = store.get(self._object_id)
        organization = store.get(order["firm-id"])
        organization["ref-count"] -= 1
        store[organization["object-id"]] = organization

        if "isin" in order:
            bond = store.lookup("bond:isin", order["isin"])

        elif "cusip" in order:
            bond = store.lookup("bond:cusip", order["cusip"])

        bond["ref-count"] -= 1
        store[bond["object-id"]] = bond

        store.delete(self._object_id)

        if 'open-orders' in store:
            oo_obj = store['open-orders']
            if self._object_id in oo_obj['order-list']:
                oo_obj['order-list'].remove(self._object_id)
                store['open-orders'] = oo_obj

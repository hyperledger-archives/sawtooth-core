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
import time
import copy
from datetime import datetime

from journal.messages import transaction_message
from journal import global_store_manager
from journal.object_store import ObjectStore
from journal.transaction import UpdatesTransaction

from sawtooth.exceptions import InvalidTransactionError

from sawtooth_bond.bond_utils import bondprice_to_float
from sawtooth_bond.updates.bond import CreateBondUpdate
from sawtooth_bond.updates.clock import ClockUpdate
from sawtooth_bond.updates.identity import CreateOrganizationUpdate
from sawtooth_bond.updates.identity import UpdateOrganizationUpdate
from sawtooth_bond.updates.identity import\
    UpdateOrganizationAuthorizationUpdate
from sawtooth_bond.updates.identity import DeleteOrganizationUpdate
from sawtooth_bond.updates.identity import CreateParticipantUpdate
from sawtooth_bond.updates.trading import CreateQuoteUpdate
from sawtooth_bond.updates.trading import DeleteQuoteUpdate
from sawtooth_bond.updates.identity import UpdateParticipantUpdate
from sawtooth_bond.updates.trading import CreateOrderUpdate
from sawtooth_bond.updates.trading import UpdateOrderUpdate
from sawtooth_bond.updates.trading import DeleteOrderUpdate
from sawtooth_bond.updates.settlement import CreateHoldingUpdate
from sawtooth_bond.updates.settlement import CreateSettlementUpdate
from sawtooth_bond.updates.settlement import CreateReceiptUpdate
from sawtooth_bond.updates.libor import CreateLIBORUpdate


LOGGER = logging.getLogger(__name__)


def _register_transaction_types(journal):
    """Registers the Bond transaction types on the journal.

    Args:
        journal (journal.journal_core.Journal): The journal to register
            the transaction type against.
    """
    journal.dispatcher.register_message_handler(
        BondTransactionMessage,
        transaction_message.transaction_message_handler)
    journal.add_transaction_store(BondTransaction)
    journal.on_pre_build_block += _pre_build_block
    journal.on_claim_block += _claim_block


def _pre_build_block(journal, block):
    # Clear the list of previously injected transactions
    # every time we build a new block.
    journal.injected_txns = []

    order_updates = _generate_match_orders(journal)
    coupon_updates = _generate_coupons(journal)

    updates = order_updates + coupon_updates

    for update in updates:
        LOGGER.debug('injecting transaction: %s', update)
        txn = BondTransaction(update)
        txn.sign_from_node(journal.local_node)
        journal.injected_txns.append(txn)

    minfo = {
        'Updates': [{
            'UpdateType': 'Clock',
            'Blocknum': block.BlockNum,
            'PreviousBlockId': block.PreviousBlockID,
            'Timestamp': time.time()
        }]
    }

    mytxn = BondTransaction(minfo)
    mytxn.sign_from_node(journal.local_node)
    LOGGER.debug('injecting clock transaction into pending queue: %s',
                 mytxn.Identifier)
    journal.add_pending_transaction(mytxn, prepend=True, build_block=False)


def _claim_block(journal, block):
    if not hasattr(journal, 'injected_txns'):
        return

    injected_txns = journal.injected_txns

    LOGGER.debug('claimed block - attempting to send %s transactions',
                 len(injected_txns))

    for txn in injected_txns:
        msg = BondTransactionMessage()
        msg.Transaction = txn
        msg.SenderID = journal.local_node.Identifier
        msg.sign_from_node(journal.local_node)
        msg.IsForward = True
        journal.gossip.broadcast_message(msg, initialize=False)
        if txn.Identifier not in journal.transaction_store:
            journal.transaction_store[txn.Identifier] = txn


def _is_coupon_date(bond, date):
    # Don't process coupons for bonds that have matured
    if not _is_mature(bond, date):
        if bond['coupon-frequency'] == "Quarterly":
            if date.month in [1, 4, 7, 10] and date.day == 1:
                return True
        elif bond['coupon-frequency'] == "Monthly":
            if date.day == 1:
                return True
        elif bond['coupon-frequency'] == "Daily":
            return True

    return False


def _is_mature(bond, date):
    # This would likely be a straight up equality comparison
    # but we want to catch test data for bonds that have
    # maturity dates in the past.
    if date.date() >= datetime.strptime(bond['maturity-date'],
                                        "%m/%d/%Y").date():
        return True
    else:
        return False


def _has_holding(store, org, bond):
    if "holdings" in org:
        for holding_id in org['holdings']:
            holding = store[holding_id]
            if holding['asset-id'] == bond['object-id']:
                if holding['amount'] > 0:
                    return True
    return False


def _coupon_exists(store, bond, org, date):
    if "receipts" in org:
        for receipt_id in org['receipts']:
            if receipt_id not in store:
                continue
            receipt = store[receipt_id]

            if (receipt['bond-id'] == bond['object-id'] and
                    receipt['payment-type'] == 'Coupon' and
                    datetime.strptime(receipt['coupon-date'],
                                      "%m/%d/%Y").date() == date.date()):
                return True
    return False


def _create_coupon(store, bond, org, date):
    upd = CreateReceiptUpdate('CreateReceipt',
                              'Coupon',
                              bond['object-id'],
                              org['object-id'],
                              coupon_date=date.strftime("%m/%d/%Y"))

    try:
        upd.check_valid(store, None)
    except InvalidTransactionError:
        return None
    else:
        return {
            'Updates': [{
                'UpdateType': 'CreateReceipt',
                'PaymentType': 'Coupon',
                'BondID': bond['object-id'],
                'PayeeID': org['object-id'],
                'CouponDate': date.strftime("%m/%d/%Y")
            }]
        }


def _create_redemption(store, bond, org):
    upd = CreateReceiptUpdate('CreateReceipt',
                              'Redemption',
                              bond['object-id'],
                              org['object-id'])

    try:
        upd.check_valid(store, None)
    except InvalidTransactionError:
        return None
    else:
        return {
            'Updates': [{
                'UpdateType': 'CreateReceipt',
                'PaymentType': 'Redemption',
                'BondID': bond['object-id'],
                'PayeeID': org['object-id']
            }]
        }


def _generate_coupons(journal):
    real_store_map = journal.global_store_map.get_block_store(
        journal.most_recent_committed_block_id)
    temp_store_map = global_store_manager.BlockStore(real_store_map)

    for txn_id in journal.pending_transactions.iterkeys():
        pend_txn = journal.transaction_store[txn_id]
        my_store = temp_store_map.get_transaction_store(
            pend_txn.TransactionTypeName)
        if pend_txn and pend_txn.is_valid(my_store):
            my_pend_txn = copy.copy(pend_txn)
            my_pend_txn.apply(my_store)

    temp_store = temp_store_map.get_transaction_store('/BondTransaction')
    store = journal.global_store.TransactionStores['/BondTransaction']

    if "current_clock" in store:
        journal_date = \
            datetime.fromtimestamp(store["current_clock"]["timestamp"])
    else:
        return []

    if ('bonds' not in temp_store or
            'organizations' not in temp_store):
        return []

    receipt_updates = []

    bond_list = temp_store['bonds']['bond-list']
    org_list = temp_store['organizations']['organization-list']

    for bond_id in bond_list:
        bond = temp_store[bond_id]
        bond_org = temp_store.lookup('organization:ticker', bond['issuer'])
        for org_id in org_list:
            org = temp_store[org_id]

            # Issuing organizations shouldn't pay themselves for
            # coupons or redemptions
            if bond_org['object-id'] == org['object-id']:
                continue

            if _is_coupon_date(bond, journal_date):
                if _has_holding(temp_store, org, bond):
                    if not _coupon_exists(temp_store, org, bond, journal_date):
                        update = _create_coupon(temp_store,
                                                bond, org,
                                                journal_date)
                        if update is not None:
                            receipt_updates.append(update)
            if _is_mature(bond, journal_date):
                if _has_holding(temp_store, org, bond):
                    update = _create_redemption(temp_store, bond, org)
                    if update is not None:
                        receipt_updates.append(update)

    return receipt_updates


def _create_order_update(store, order, quote):
    upd = UpdateOrderUpdate('UpdateOrder',
                            order['object-id'],
                            quote_id=quote['object-id'])

    try:
        upd.check_valid(store, None)
    except InvalidTransactionError:
        return None
    else:
        return {
            'Updates': [{
                'UpdateType': 'UpdateOrder',
                'ObjectId': order['object-id'],
                'QuoteId': quote['object-id'],
                'Status': 'Matched'
            }]
        }


def _generate_match_orders(journal):
    real_store_map = journal.global_store_map.get_block_store(
        journal.most_recent_committed_block_id)
    temp_store_map = global_store_manager.BlockStore(real_store_map)

    for txn_id in journal.pending_transactions.iterkeys():
        pend_txn = journal.transaction_store[txn_id]
        my_store = temp_store_map.get_transaction_store(
            pend_txn.TransactionTypeName)
        if pend_txn and pend_txn.is_valid(my_store):
            my_pend_txn = copy.copy(pend_txn)
            my_pend_txn.apply(my_store)

    temp_store = temp_store_map.get_transaction_store('/BondTransaction')

    # The special list tracking objects are created on the first
    # CreateOrderUpdate and CreateQuoteUpdate transactions. If
    # these don't exist yet, return an empty list
    if ('open-quotes' not in temp_store or
            'open-orders' not in temp_store):
        return []

    open_orders = temp_store['open-orders']['order-list']
    open_quotes = temp_store['open-quotes']['quote-list']

    # Build a dict of dicts with the top-level dict
    # containing quote object-id keys and the values containing
    # the quote object dicts
    quotes = {x: temp_store[x] for x in open_quotes}

    # Generate a sorted list of tuples containing the key-value
    # pairs of the top-level dict in ask-price and reverse
    # bid-price order
    sorted_quotes = {}
    sorted_quotes['Buy'] = sorted(quotes.items(),
                                  key=lambda k: k[1]['ask-price'])
    sorted_quotes['Sell'] = sorted(quotes.items(),
                                   key=lambda k: k[1]['bid-price'],
                                   reverse=True)

    order_updates = []
    for open_order_id in open_orders:
        order = temp_store[open_order_id]
        matched = False

        if 'cusip' in order:
            order_bond = temp_store.lookup('bond:cusip', order['cusip'])
        elif 'isin' in order:
            order_bond = temp_store.lookup('bond:isin', order['isin'])
        else:
            LOGGER.debug("Encountered an open order with a non-existent bond")
            continue

        for _, quote in sorted_quotes[order['action']]:
            if quote['status'] == "Closed":
                continue

            if 'cusip' in quote:
                quote_bond = temp_store.lookup('bond:cusip', quote['cusip'])
            elif 'isin' in quote:
                quote_bond = temp_store.lookup('bond:isin', quote['isin'])
            else:
                LOGGER.debug("Encountered an open quote with a "
                             "non-existent bond")
                continue

            if quote_bond['object-id'] == order_bond['object-id']:
                if order['action'] == 'Buy':
                    if order['order-type'] == 'Market':
                        if quote['ask-qty'] >= order['quantity']:
                            matched = True
                    elif order['order-type'] == 'Limit':
                        if (quote['ask-qty'] >= order['quantity'] and
                                bondprice_to_float(quote['ask-price']) <=
                                bondprice_to_float(order['limit-price'])):
                            matched = True
                elif order['action'] == 'Sell':
                    if order['order-type'] == 'Market':
                        if quote['bid-qty'] >= order['quantity']:
                            matched = True
                    else:
                        if (quote['bid-qty'] >= order['quantity'] and
                                bondprice_to_float(quote['bid-price']) >=
                                bondprice_to_float(order['limit-price'])):
                            matched = True

            if matched:
                update = _create_order_update(temp_store, order, quote)
                if update is not None:
                    order_updates.append(update)

                    # We need to do maintenance on our sorted_quotes
                    # to ensure that we don't generate invalid transactions.
                    # Both the buy and sell versions of the associative list
                    # need to be drawn down by the quantity of the matched
                    # order. These loops find the associated dictionary
                    # structure inside the tuple list, copy it out, and
                    # set a new tuple structure at that index.
                    for i, e in enumerate(sorted_quotes['Buy']):
                        if e[0] == quote['object-id']:
                            tmp_dict = sorted_quotes['Buy'][i][1]
                            tmp_dict['ask-qty'] -= order['quantity']
                            sorted_quotes['Buy'][i] = (quote['object-id'],
                                                       tmp_dict)

                    for i, e in enumerate(sorted_quotes['Sell']):
                        if e[0] == quote['object-id']:
                            tmp_dict = sorted_quotes['Sell'][i][1]
                            tmp_dict['bid-qty'] -= order['quantity']
                            sorted_quotes['Sell'][i] = (quote['object-id'],
                                                        tmp_dict)

                matched = False
                # We have a match, so stop inspecting quotes for
                # this order
                break

    return order_updates


class BondTransactionMessage(transaction_message.TransactionMessage):
    """Bond transaction message represent Bond transactions.

    Attributes:
        MessageType (str): The class name of the message.
        Transaction (BondTransaction): The transaction the
            message is associated with.
    """
    MessageType = "/Bond/Transaction"

    def __init__(self, minfo=None):
        if minfo is None:
            minfo = {}

        super(BondTransactionMessage, self).__init__(minfo)

        tinfo = minfo.get('Transaction', {})
        self.Transaction = BondTransaction(tinfo)


class BondTransaction(UpdatesTransaction):
    """A Transaction is a set of updates to be applied atomically
    to a journal.

    It has a unique identifier and a signature to validate the source.

    Attributes:
        TransactionTypeName (str): The name of the Bond
            transaction type.
        TransactionTypeStore (type): The type of transaction store.
        MessageType (type): The object type of the message associated
            with this transaction.
    """
    TransactionTypeName = '/BondTransaction'
    TransactionStoreType = ObjectStore
    MessageType = BondTransactionMessage

    def __init__(self, minfo=None):
        """Constructor for the BondTransaction class.

        Args:
            minfo: Dictionary of values for transaction fields.
        """

        if minfo is None:
            minfo = {}

        LOGGER.debug("minfo: %s", repr(minfo))

        super(BondTransaction, self).__init__(minfo)

    def register_updates(self, registry):
        registry.register('CreateOrganization', CreateOrganizationUpdate)
        registry.register('UpdateOrganization', UpdateOrganizationUpdate)
        registry.register('UpdateOrganizationAuthorization',
                          UpdateOrganizationAuthorizationUpdate)
        registry.register('DeleteOrganization', DeleteOrganizationUpdate)
        registry.register('CreateParticipant', CreateParticipantUpdate)
        registry.register('UpdateParticipant', UpdateParticipantUpdate)

        registry.register('CreateBond', CreateBondUpdate)
        registry.register('CreateQuote', CreateQuoteUpdate)
        registry.register('DeleteQuote', DeleteQuoteUpdate)
        registry.register('CreateOrder', CreateOrderUpdate)
        registry.register('UpdateOrder', UpdateOrderUpdate)
        registry.register('DeleteOrder', DeleteOrderUpdate)
        registry.register('Clock', ClockUpdate)
        registry.register('CreateHolding', CreateHoldingUpdate)
        registry.register('CreateSettlement', CreateSettlementUpdate)
        registry.register('CreateReceipt', CreateReceiptUpdate)

        registry.register('CreateLIBOR', CreateLIBORUpdate)

    def check_valid(self, store):
        if not isinstance(store, ObjectStore):
            # This is a workaround because sawtooth.client does not properly
            # give us the right store type.
            LOGGER.error("invalid store type: %s", type(store))
            LOGGER.error("ignoring error, check_value() returning True")
            return True

        return super(BondTransaction, self).check_valid(store)

    def apply(self, store):
        if not isinstance(store, ObjectStore):
            # This is a workaround because sawtooth.client does not properly
            # give us the right store type.
            LOGGER.error("invalid store type: %s", type(store))
            LOGGER.error("ignoring error, apply() doing nothing")
            return

        return super(BondTransaction, self).apply(store)

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
# -----------------------------------------------------------------------------

import json
import logging
import os
import requests

from journal import transaction, global_store_manager
from journal.messages import transaction_message

from sawtooth.exceptions import InvalidTransactionError

LOGGER = logging.getLogger(__name__)


def _register_transaction_types(journal):
    """Registers the Seg transaction types on the ledger.

    Args:
        ledger (journal.journal_core.Journal): The ledger to register
            the transaction type against.
    """
    journal.dispatcher.register_message_handler(
        SegTransactionMessage,
        transaction_message.transaction_message_handler)
    journal.add_transaction_store(SegTransaction)


class SegTransactionMessage(transaction_message.TransactionMessage):
    """Seg transaction message represent Seg transactions.

    Attributes:
        MessageType (str): The class name of the message.
        Transaction (SegTransaction): The transaction the
            message is associated with.
    """
    MessageType = "/Seg/Transaction"

    def __init__(self, minfo=None):
        if minfo is None:
            minfo = {}

        super(SegTransactionMessage, self).__init__(minfo)

        tinfo = minfo.get('Transaction', {})
        self.Transaction = SegTransaction(tinfo)


class SegTransaction(transaction.Transaction):
    """A Transaction is a set of updates to be applied atomically
    to a ledger.

    It has a unique identifier and a signature to validate the source.

    Attributes:
        TransactionTypeName (str): The name of the Seg
            transaction type.
        TransactionTypeStore (type): The type of transaction store.
        MessageType (type): The object type of the message associated
            with this transaction.
    """
    TransactionTypeName = '/SegTransaction'
    TransactionStoreType = global_store_manager.KeyValueStore
    MessageType = SegTransactionMessage

    def __init__(self, minfo=None):
        """Constructor for the SegTransaction class.

        Args:
            minfo: Dictionary of values for transaction fields.
        """

        if minfo is None:
            minfo = {}

        super(SegTransaction, self).__init__(minfo)

        LOGGER.debug("minfo: %s", repr(minfo))
        self._address = minfo['Address'] if 'Address' in minfo else None
        self._balance = minfo['Balance'] if 'Balance' in minfo else None
        self._block = minfo['Block'] if 'Block' in minfo else None

    def __str__(self):
        try:
            oid = self.OriginatorID
        except AssertionError:
            oid = "unknown"
        return "({0} {1} {2} {3})".format(oid,
                                          self._address,
                                          self._balance,
                                          self._block)

    def check_valid(self, store):
        """Determines if the transaction is valid.

        Args:
            store (dict): Transaction store mapping.
        """

        super(SegTransaction, self).check_valid(store)

        LOGGER.debug('checking %s', str(self))

        if self._address is None or self._address == '':
            raise InvalidTransactionError('address not set')

        if self._balance is None or self._balance == '':
            raise InvalidTransactionError('balance not set')

        if self._block is None or self._block == '':
            raise InvalidTransactionError('block not set')

    def _get_ethereum_balance(self):
        eth_url = os.environ.get('ETH_URL', 'http://localhost:8545')

        headers = {'content-type': 'application/json'}
        payload = {
            "jsonrpc": "2.0",
            "method": "eth_getBalance",
            "params": [self._address, self._block],
            "id": 1
        }
        response = requests.post(
            eth_url, data=json.dumps(payload), headers=headers).json()

        return round(int(response['result'], 0) / 10**18, 0)

    def apply(self, store):
        """Applies all the updates in the transaction to the transaction
        store.

        Args:
            store (dict): Transaction store mapping.
        """
        LOGGER.debug('apply %s', str(self))

        name = "game{}".format(len(store.keys()))
        game = {}
        game['Name'] = name
        game['Player'] = self.OriginatorID
        game['Address'] = self._address
        game['Guess'] = self._balance

        balance = self._get_ethereum_balance()
        if abs(balance - self._balance) <= 0.5:
            game['Result'] = 'correct'
        elif balance < self._balance:
            game['Result'] = 'too high'
        else:
            game['Result'] = 'too low'

        store[name] = game

    def dump(self):
        """Returns a dict with attributes from the transaction object.

        Returns:
            dict: The updates from the transaction object.
        """
        result = super(SegTransaction, self).dump()

        result['Address'] = self._address
        result['Balance'] = self._balance
        result['Block'] = self._block

        return result

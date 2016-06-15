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

import logging

from journal import transaction, global_store_manager
from journal.messages import transaction_message

from sawtooth_battleship.battleship_exceptions import BattleshipException

LOGGER = logging.getLogger(__name__)


def _register_transaction_types(ledger):
    """Registers the Battleship transaction types on the ledger.

    Args:
        ledger (journal.journal_core.Journal): The ledger to register
            the transaction type against.
    """
    ledger.register_message_handler(
        BattleshipTransactionMessage,
        transaction_message.transaction_message_handler)
    ledger.add_transaction_store(BattleshipTransaction)


class BattleshipTransactionMessage(transaction_message.TransactionMessage):
    """Battleship transaction message represent Battleship transactions.

    Attributes:
        MessageType (str): The class name of the message.
        Transaction (BattleshipTransaction): The transaction the
            message is associated with.
    """
    MessageType = "/Battleship/Transaction"

    def __init__(self, minfo=None):
        if minfo is None:
            minfo = {}

        super(BattleshipTransactionMessage, self).__init__(minfo)

        tinfo = minfo.get('Transaction', {})
        self.Transaction = BattleshipTransaction(tinfo)


class BattleshipTransaction(transaction.Transaction):
    """A Transaction is a set of updates to be applied atomically
    to a ledger.

    It has a unique identifier and a signature to validate the source.

    Attributes:
        TransactionTypeName (str): The name of the Battleship
            transaction type.
        TransactionTypeStore (type): The type of transaction store.
        MessageType (type): The object type of the message associated
            with this transaction.
    """
    TransactionTypeName = '/BattleshipTransaction'
    TransactionStoreType = global_store_manager.KeyValueStore
    MessageType = BattleshipTransactionMessage

    def __init__(self, minfo=None):
        """Constructor for the BattleshipTransaction class.

        Args:
            minfo: Dictionary of values for transaction fields.
        """

        if minfo is None:
            minfo = {}

        super(BattleshipTransaction, self).__init__(minfo)

        LOGGER.debug("minfo: %s", repr(minfo))
        LOGGER.error("BattleshipTransaction.__init__() not implemented")

    def __str__(self):
        LOGGER.error("BattleshipTransaction.__str__() not implemented")
        return "BattleshipTransaction"

    def is_valid(self, store):
        """Determines if the transaction is valid.

        Args:
            store (dict): Transaction store mapping.
        """

        try:
            self.check_valid(store)
        except BattleshipException as e:
            LOGGER.debug('invalid transaction (%s): %s', str(e), str(self))
            return False

        return True

    def check_valid(self, store):
        """Determines if the transaction is valid.

        Args:
            store (dict): Transaction store mapping.
        """

        raise BattleshipException("check_valid() not implemented")

    def apply(self, store):
        """Applies all the updates in the transaction to the transaction
        store.

        Args:
            store (dict): Transaction store mapping.
        """
        LOGGER.debug('apply %s', str(self))
        LOGGER.error('BattleshipTransaction.apply() not implemented')

    def dump(self):
        """Returns a dict with attributes from the transaction object.

        Returns:
            dict: The updates from the transaction object.
        """
        result = super(BattleshipTransaction, self).dump()

        LOGGER.error('BattleshipTransaction.dump() not implemented')

        return result

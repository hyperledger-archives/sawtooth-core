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

logger = logging.getLogger(__name__)


def _register_transaction_types(ledger):
    """Registers the Xo transaction types on the ledger.

    Args:
        ledger (journal.journal_core.Journal): The ledger to register
            the transaction type against.
    """
    logging.error("XO!")

    ledger.register_message_handler(
        XoTransactionMessage,
        transaction_message.transaction_message_handler)
    ledger.add_transaction_store(XoTransaction)


class XoTransactionMessage(transaction_message.TransactionMessage):
    """Integer key transaction message represent Xo transactions.

    Attributes:
        MessageType (str): The class name of the message.
        Transaction (XoTransaction): The transaction the
            message is associated with.
    """
    MessageType = "/Xo/Transaction"

    def __init__(self, minfo=None):
        if minfo is None:
            minfo = {}

        super(XoTransactionMessage, self).__init__(minfo)

        tinfo = minfo.get('Transaction', {})
        self.Transaction = XoTransaction(tinfo)


class XoUpdate(object):
    """Updates represent potential changes to the Xo registry.

    Attributes:
        KnownVerbs (list): A list of possible update actions.
    """
    KnownVerbs = ['set', 'inc', 'dec']

    def __init__(self, minfo=None):
        """Constructor for the Update class.

        Args:
            minfo (dict): Dictionary of values for update fields.
        """

        if minfo is None:
            minfo = {}

        self._verb = minfo['Verb'] if 'Verb' in minfo else 'set'
        self._name = minfo['Name'] if 'Name' in minfo else None
        self._value = long(minfo['Value']) if 'Value' in minfo else 0

    def __str__(self):
        return "({0} {1} {2})".format(self._verb, self._name, self._value)

    def is_valid(self, store):
        """Determines if the update is valid.

        Args:
            store (dict): Transaction store mapping.

        Returns:
            bool: Whether or not the update is valid.
        """
        logger.debug('check update %s', str(self))

        # in theory, the name should have been checked before the transaction
        # was submitted... not being too careful about this
        if not self._name or self._name == '':
            return False

        # in theory, the value should have been checked before the transaction
        # was submitted... not being too careful about this
        if not isinstance(self._value, (int, long)):
            return False

        # in theory, the value should have been checked before the transaction
        # was submitted... not being too careful about this
        if (self._verb == 'set'
                and self._name not in store
                and self._value >= 0):
            return True

        if self._verb == 'inc' and self._name in store:
            return True

        # value after a decrement operation must remain above zero
        if (self._verb == 'dec' and self._name in store
                and store[self._name] > self._value):
            return True

        return False

    def apply(self, store):
        """Applies the update to the asset in the transaction store.

        Args:
            store (dict): Transaction store mapping.
        """
        logger.debug('apply %s', str(self))

        if self._verb == 'set':
            store[self._name] = self._value
        elif self._verb == 'inc':
            store[self._name] += self._value
        elif self._verb == 'dec':
            store[self._name] -= self._value
        else:
            logger.info('unknown verb %s', self._verb)

    def dump(self):
        """Returns a dict with attributes from the update object.

        Returns:
            dict: The name, value, and verb from the update object.
        """
        result = {'Name': self._name, 'Value': self._value, 'Verb': self._verb}
        return result


class XoTransaction(transaction.Transaction):
    """A Transaction is a set of updates to be applied atomically
    to a ledger.

    It has a unique identifier and a signature to validate the source.

    Attributes:
        TransactionTypeName (str): The name of the Xo
            transaction type.
        TransactionTypeStore (type): The type of transaction store.
        MessageType (type): The object type of the message associated
            with this transaction.
        Updates (list): A list of Xo registry updates associated
            with this transaction.
    """
    TransactionTypeName = '/XoTransaction'
    TransactionStoreType = global_store_manager.KeyValueStore
    MessageType = XoTransactionMessage

    def __init__(self, minfo=None):
        """Constructor for the XoTransaction class.

        Args:
            minfo: Dictionary of values for transaction fields.
        """

        if minfo is None:
            minfo = {}

        super(XoTransaction, self).__init__(minfo)

        self.Updates = []

        if 'Updates' in minfo:
            for update in minfo['Updates']:
                self.Updates.append(XoUpdate(update))

    def __str__(self):
        return " and ".join([str(u) for u in self.Updates])

    def is_valid(self, store):
        """Determines if the transaction is valid.

        Args:
            store (dict): Transaction store mapping.
        """
        if not super(XoTransaction, self).is_valid(store):
            return False

        for update in self.Updates:
            if not update.is_valid(store):
                logger.debug('invalid transaction: %s', str(update))
                return False

        return True

    def apply(self, store):
        """Applies all the updates in the transaction to the transaction
        store.

        Args:
            store (dict): Transaction store mapping.
        """
        for update in self.Updates:
            update.apply(store)

    def dump(self):
        """Returns a dict with attributes from the transaction object.

        Returns:
            dict: The updates from the transaction object.
        """
        result = super(XoTransaction, self).dump()

        result['Updates'] = []
        for update in self.Updates:
            result['Updates'].append(update.dump())

        return result

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

from journal import transaction, global_store_manager
from journal.messages import transaction_message

logger = logging.getLogger(__name__)


def register_transaction_types(ledger):
    """Registers the integer key transaction types on the ledger.

    Args:
        ledger (journal.journal_core.Journal): The ledger to register
            the transaction type against.
    """
    ledger.register_message_handler(
        IntegerKeyTransactionMessage,
        transaction_message.transaction_message_handler)
    ledger.add_transaction_store(IntegerKeyTransaction)


class IntegerKeyTransactionMessage(transaction_message.TransactionMessage):
    """Integer key transaction message represent integer key transactions.

    Attributes:
        IntegerKeyTransactionMessage.MessageType (str): The class name of the
            message.
        Transaction (IntegerKeyTransaction): The transaction the
            message is associated with.
    """
    MessageType = "/ledger.transaction.IntegerKey/Transaction"

    def __init__(self, minfo=None):
        if minfo is None:
            minfo = {}
        super(IntegerKeyTransactionMessage, self).__init__(minfo)

        tinfo = minfo.get('Transaction', {})
        self.Transaction = IntegerKeyTransaction(tinfo)


class Update(object):
    """Updates represent potential changes to the integer key registry.

    Attributes:
        integer_key.Update.KnownVerbs (list): A list of possible update
            actions.
        Verb (str): The action of this update, defaults to 'set'.
        Name (str): The name of the integer key.
        Value (int): The value of the integer key.
    """
    KnownVerbs = ['set', 'inc', 'dec']

    def __init__(self, minfo=None):
        """Constructor for the Update class.

        Args:
            minfo (dict): Dictionary of values for update fields.
        """
        if minfo is None:
            minfo = {}
        self.Verb = minfo['Verb'] if 'Verb' in minfo else 'set'
        self.Name = minfo['Name'] if 'Name' in minfo else None
        self.Value = long(minfo['Value']) if 'Value' in minfo else 0

    def __str__(self):
        return "({0} {1} {2})".format(self.Verb, self.Name, self.Value)

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
        if not self.Name or self.Name == '':
            return False

        # in theory, the value should have been checked before the transaction
        # was submitted... not being too careful about this
        if not isinstance(self.Value, (int, long)):
            return False

        # in theory, the value should have been checked before the transaction
        # was submitted... not being too careful about this
        if self.Verb == 'set' and self.Name not in store and self.Value >= 0:
            return True

        if self.Verb == 'inc' and self.Name in store:
            return True

        # value after a decrement operation must remain above zero
        if (self.Verb == 'dec' and self.Name in store
                and store[self.Name] > self.Value):
            return True

        return False

    def apply(self, store):
        """Applies the update to the asset in the transaction store.

        Args:
            store (dict): Transaction store mapping.
        """
        logger.debug('apply %s', str(self))

        if self.Verb == 'set':
            store[self.Name] = self.Value
        elif self.Verb == 'inc':
            store[self.Name] += self.Value
        elif self.Verb == 'dec':
            store[self.Name] -= self.Value
        else:
            logger.info('unknown verb %s', self.Verb)

    def dump(self):
        """Returns a dict with attributes from the update object.

        Returns:
            dict: The name, value, and verb from the update object.
        """
        result = {'Name': self.Name, 'Value': self.Value, 'Verb': self.Verb}
        return result


class IntegerKeyTransaction(transaction.Transaction):
    """A Transaction is a set of updates to be applied atomically
    to a ledger.

    It has a unique identifier and a signature to validate the source.

    Attributes:
        IntegerKeyTransaction.TransactionTypeName (str): The name of the
            integer key transaction type.
        TransactionTypeStore (type): The type of
            transaction store.
        IntegerKeyTransaction.MessageType (type): The object type of the
            message associated with this transaction.
        Updates (list): A list of integer key registry updates associated
            with this transaction.
    """
    TransactionTypeName = '/IntegerKeyTransaction'
    TransactionStoreType = global_store_manager.KeyValueStore
    MessageType = IntegerKeyTransactionMessage

    def __init__(self, minfo=None):
        """Constructor for the IntegerKeyTransaction class.

        Args:
            minfo: Dictionary of values for transaction fields.
        """
        if minfo is None:
            minfo = {}
        super(IntegerKeyTransaction, self).__init__(minfo)

        self.Updates = []

        if 'Updates' in minfo:
            for update in minfo['Updates']:
                self.Updates.append(Update(update))

    def __str__(self):
        return " and ".join([str(u) for u in self.Updates])

    def is_valid(self, store):
        """Determines if the transaction is valid.

        Args:
            store (dict): Transaction store mapping.
        """
        if not super(IntegerKeyTransaction, self).is_valid(store):
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
        result = super(IntegerKeyTransaction, self).dump()

        result['Updates'] = []
        for update in self.Updates:
            result['Updates'].append(update.dump())

        return result

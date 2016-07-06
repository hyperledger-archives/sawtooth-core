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

from gossip import signed_object
from journal.messages import transaction_message
from sawtooth.exceptions import InvalidTransactionError


logger = logging.getLogger(__name__)


class SerializationError(Exception):
    """Exception raised for errors serializing or deserializing
    transaction messages.

    Attributes:
        TransactionType (str): The transaction type in which the
            error occurred.
        Message (str): The explanation of the error.
    """

    def __init__(self, txntype, msg):
        """Constructor for SerializationError class.

        Args:
            txntype (str): The transaction type in which the
                error occurred.
            msg (str): The explanation of the error.
        """

        super(SerializationError, self).__init__(self)
        self.TransactionType = txntype
        self.Message = msg

    def __str__(self):
        return "Serialization error in class {0}: {1}".format(
            self.TransactionType, self.Message)


class Status(object):
    """Enumeration for status.
    """
    unknown = 0
    pending = 1
    committed = 2
    failed = 3


class Transaction(signed_object.SignedObject):
    """A Transaction is a set of updates to be applied atomically
    to a ledger.

    It has a unique identifier and a signature to validate the source.

    Note:
        The OriginatorID in the transaction is the verifying key for an
        individual not a Node as is the case for the signer of a message.

    Attributes:
        Transaction.TransactionTypeName (str): The name of the transaction
            type.
        Transaction.MessageType (type): The transaction class.
        Nonce (float): A locally unique identifier.
        Transaction.Status (transaction.Status): The status of the transaction.
        Dependencies (list): A list of transactions that this transaction
            is dependent on.
    """

    TransactionTypeName = '/Transaction'
    MessageType = transaction_message.TransactionMessage

    def __init__(self, minfo={}):
        """Constructor for the Transaction class.

        Args:
            minfo (dict): A dict of key/values for transaction.
        """
        super(Transaction, self).__init__(minfo)

        self.Nonce = minfo.get('Nonce', time.time())

        self.Status = Status.unknown
        self.InBlock = None

        self.Dependencies = []
        for txnid in minfo.get('Dependencies', []):
            self.Dependencies.append(str(txnid))

        self._data = None

    def __str__(self):
        return self.TransactionTypeName

    def is_valid(self, store):
        """Determines if the transaction is valid.

        Args:
            store (dict): Transaction store mapping.
        """
        try:
            self.check_valid(store)
        except InvalidTransactionError as e:
            logger.debug('invalid transaction %s: %s', str(self), str(e))
            return False

        return True

    def check_valid(self, store):
        """Determines if the transaction is valid.

        Args:
            store (dict): Transaction store mapping.
        """
        if not super(Transaction, self).is_valid(store):
            raise InvalidTransactionError("invalid signature")

    def apply(self, store):
        pass

    def add_to_pending(self):
        """Predicate to note that a transaction should be added to pending
        transactions.

        In general incentive transactions should not be included in
        the pending transaction list.

        Returns:
            bool: True.
        """
        return True

    def build_message(self):
        """Constructs a message containing the transaction.

        Returns:
            msg (message.Message): A transaction message containing the
                transaction.
        """
        msg = self.MessageType()
        msg.Transaction = self
        return msg

    def dump(self):
        """Builds a dict containing information about the transaction.

        Returns:
            dict: A dict containing details about the transaction.
        """
        result = super(Transaction, self).dump()

        result['TransactionType'] = self.TransactionTypeName
        result['Nonce'] = self.Nonce

        result['Dependencies'] = []
        for txnid in self.Dependencies:
            result['Dependencies'].append(str(txnid))

        return result

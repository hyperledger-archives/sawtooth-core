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

import hashlib
import logging
import re
import time

from gossip.common import dict2cbor
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

    def __init__(self, minfo=None):
        """Constructor for the Transaction class.

        Args:
            minfo (dict): A dict of key/values for transaction.
        """
        if minfo is None:
            minfo = {}
        super(Transaction, self).__init__(minfo)

        self.Nonce = minfo.get('Nonce', time.time())

        self.Status = Status.unknown
        self.InBlock = None

        self.Dependencies = []
        for txnid in minfo.get('Dependencies', []):
            self.Dependencies.append(str(txnid))

        self._data = None

        self._age = 0

    def __str__(self):
        return self.TransactionTypeName

    @property
    def age(self):
        """Returns age, which is defined as the amount of time spent on the
        pending queue in terms of prepared blocks."""

        return self._age

    def increment_age(self):
        """Increments age by one."""

        self._age = self._age + 1

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


def _serialize(obj, update_type):
    serialized = {}
    serialized['UpdateType'] = update_type

    for attr in dir(obj):
        if (attr.startswith('_')
                and not attr.startswith('__')
                and not callable(getattr(obj, attr))):
            # key is attr converted from _snake_case to CamelCase
            key = ''.join(w.capitalize() for w in attr[1:].split('_'))
            if getattr(obj, attr) is not None:
                serialized[key] = getattr(obj, attr)

    return serialized


def _deserialize(minfo, class_):
    parameters = {}
    for key in minfo:
        parameter_name = re.sub('(?!^)([A-Z]+)', r'_\1', key).lower()
        parameters[parameter_name] = minfo[key]

    logger.debug("update: %s.__init__(%s)",
                 class_.__name__,
                 ', '.join(parameters.keys()))
    try:
        return class_(**parameters)
    except TypeError, te:
        raise TypeError("{}: {}".format(
            str(te), "{}.__init__({})".format(
                class_.__name__, ', '.join(parameters.keys()))))


class UpdatesTransaction(Transaction):
    """A Transaction is a set of updates to be applied atomically
    to a ledger.
    """

    def __init__(self, minfo=None):
        """Constructor for the UpdatesTransaction class.

        Args:
            minfo: Dictionary of values for transaction fields.
        """

        if minfo is None:
            minfo = {}

        super(UpdatesTransaction, self).__init__(minfo)

        logger.debug("minfo: %s", repr(minfo))

        self._registry = UpdateRegistry()
        self.register_updates(self._registry)

        self._updates = []
        if 'Updates' in minfo:
            for update_info in minfo['Updates']:
                self._updates.append(self._registry.deserialize(update_info))

    def __str__(self):
        return ",".join([u.update_type for u in self._updates]) + " Updates"

    def register_updates(self, registry):
        pass

    def check_valid(self, store):
        """Determines if the transaction is valid.

        Args:
            store (dict): Transaction store mapping.
        """

        super(UpdatesTransaction, self).check_valid(store)

        logger.debug(repr(store))

        logger.debug('checking %s with %d updates',
                     str(self), len(self._updates))

        for update in self._updates:
            logger.debug('update %s', repr(self._updates))
            update.check_valid(store, self)

    def apply(self, store):
        """Applies all the updates in the transaction to the transaction
        store.

        Args:
            store (dict): Transaction store mapping.
        """
        logger.debug('applying %s with %d updates',
                     str(self), len(self._updates))

        for update in self._updates:
            update.apply(store, self)

    def dump(self):
        """Returns a dict with attributes from the transaction object.

        Returns:
            dict: The updates from the transaction object.
        """
        result = super(UpdatesTransaction, self).dump()

        result['Updates'] = []
        for update in self._updates:
            result['Updates'].append(self._registry.serialize(update))

        return result


class Update(object):
    def __init__(self, update_type):
        self._update_type = update_type

    @property
    def update_type(self):
        return self._update_type

    def create_id(self):
        return hashlib.sha256(
            dict2cbor(_serialize(self, self._update_type))).hexdigest()

    def check_valid(self, store, txn):
        pass

    def apply(self, store, txn):
        pass


class UpdateRegistry(object):
    def __init__(self):
        self._type_to_class = {}
        self._class_to_type = {}

    def register(self, type_name, class_):
        self._type_to_class[type_name] = class_
        self._class_to_type[class_] = type_name

    def serialize(self, obj):
        update_type = self._class_to_type[obj.__class__]
        return _serialize(obj, update_type)

    def deserialize(self, minfo):
        class_ = self._type_to_class[minfo['UpdateType']]
        return _deserialize(minfo, class_)

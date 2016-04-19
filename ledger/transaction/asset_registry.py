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

from gossip import common
from journal import transaction, global_store_manager
from journal.messages import transaction_message

logger = logging.getLogger(__name__)


def register_transaction_types(ledger):
    """Registers the asset registry transaction types on the ledger.

    Args:
        ledger (journal.journal_core.Journal): The ledger to register
            the transaction type against.
    """
    ledger.register_message_handler(
        AssetRegistryTransactionMessage,
        transaction_message.transaction_message_handler)
    ledger.add_transaction_store(AssetRegistryTransaction)


class AssetRegistryTransactionMessage(transaction_message.TransactionMessage):
    """Asset registry transaction messages represent asset registry
    transactions.

    Attributes:
        AssetRegistryTransactionMessage.MessageType (str): The class name of
            the message.
        Transaction (AssetRegistryTransaction): The transaction the
            message is associated with.
    """
    MessageType = "/ledger.transaction.AssetRegistry/Transaction"

    def __init__(self, minfo={}):
        """Constructor for the AssetRegistryTransactionMessage class.

        Args:
            minfo (dict): Dictionary of values for message fields.
        """
        super(AssetRegistryTransactionMessage, self).__init__(minfo)

        tinfo = minfo.get('Transaction', {})
        self.Transaction = AssetRegistryTransaction(tinfo)


class Update(object):
    """Updates represent potential changes to the asset registry.

    Attributes:
        asset_registry.Update.KnownVerbs (list): A list of possible update
            actions.
        Verb (str): The action of this update, defaults to 'reg'.
        AssetID (str): The asset ID to be updated.
        OwnerID (str): The ID of the owner of the asset.
    """
    KnownVerbs = ['reg', 'own', 'unr']

    def __init__(self, minfo={}):
        """Constructor for Update class.

        Args:
            minfo (dict): Dictionary of values for update fields.
        """
        self.Verb = minfo.get('Verb', 'reg')
        self.AssetID = minfo.get('AssetID', common.NullIdentifier)
        self.OwnerID = minfo.get('OwnerID', common.NullIdentifier)

    def __str__(self):
        return "({0} {1} {2})".format(self.Verb, self.AssetID[:8],
                                      self.OwnerID[:8])

    def is_valid(self, store):
        """Determines if the update is valid.

        is_valid() checks to see if the specified operation is valid
        in the context of the asset provided. For example, it is not
        valid to register an asset that already exists.

        Args:
            store (dict): Transaction store mapping.

        Returns:
            bool: Whether or not the update action is valid.
        """
        logger.debug('check update %s', str(self))

        # check for an attempt to register an asset that already exists
        if self.Verb == 'reg' and self.AssetID in store:
            return False

        # check for an attempt to change owner of a non-existant asset
        if self.Verb == 'own' and self.AssetID not in store:
            return False

        # check for an attempt to unregister a non-existant asset
        if self.Verb == 'unr' and self.AssetID not in store:
            return False

        return True

    def apply(self, store):
        """Applies the update to the asset in the transaction store.

        Args:
            store (dict): Transaction store mapping.
        """
        logger.debug('apply %s', str(self))

        if self.Verb == 'reg' or self.Verb == 'own':
            store[self.AssetID] = self.OwnerID
        elif self.Verb == 'unr':
            store[self.AssetID] = common.NullIdentifier
        else:
            logger.info('unknown verb %s', self.Verb)

    def dump(self):
        """Returns a dict with attributes from the update object.

        Returns:
            dict: The asset ID, owner ID, and verb from the update object.
        """
        result = {
            'AssetID': self.AssetID,
            'OwnerID': self.OwnerID,
            'Verb': self.Verb
        }
        return result


class AssetRegistryTransaction(transaction.Transaction):
    """A Transaction is a set of updates to be applied atomically
    to a ledger.

    It has a unique identifier and a signature to validate the source.

    Attributes:
        AssetRegistryTransaction.TransactionTypeName (str): The name of the
            asset registry transaction type.
        AssetRegistryTransaction.TransactionStoreType (type): The type of
            transaction store.
        AssetRegistryTransaction.MessageType (type): The object type of the
            message associated with this transaction.
        Updates (list): A list of asset registry updates associated
            with this transaction.
    """

    TransactionTypeName = '/AssetRegistryTransaction'
    TransactionStoreType = global_store_manager.KeyValueStore
    MessageType = AssetRegistryTransactionMessage

    def __init__(self, minfo={}):
        """Constructor for the AssetRegistryTransaction class.

        Args:
            minfo: Dictionary of values for transaction fields.
        """
        super(AssetRegistryTransaction, self).__init__(minfo)

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

        Returns:
            bool: Whether or not the transaction is valid.
        """
        if not super(AssetRegistryTransaction, self).is_valid(store):
            return False

        for update in self.Updates:
            if not update.is_valid(store):
                logger.debug('invalid transaction: %s', str(update))
                return False

        return True

    def apply(self, store):
        """Applies all the updates in the transaction to the asset
        in the transaction store.

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
        result = super(AssetRegistryTransaction, self).dump()

        result['Updates'] = []
        for update in self.Updates:
            result['Updates'].append(update.dump())

        return result

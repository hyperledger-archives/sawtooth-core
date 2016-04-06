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
    """Registers the endpoint registry asset types on the ledger.

    Args:
        ledger (journal.journal_core.Journal): The ledger to register
            the transaction type against.
    """
    ledger.register_message_handler(
        EndpointRegistryTransactionMessage,
        transaction_message.transaction_message_handler)
    ledger.add_transaction_store(EndpointRegistryTransaction)


class EndpointRegistryTransactionMessage(
        transaction_message.TransactionMessage):
    """Endpoint registry transaction messages represent endpoint registry
    transactions.

    Attributes:
        MessageType (str): The class name of the message.
        Transaction (EndpointRegistryTransaction): The transaction the
            message is associated with.
    """
    MessageType = "/ledger.transaction.EndpointRegistry/Transaction"

    def __init__(self, minfo={}):
        super(EndpointRegistryTransactionMessage, self).__init__(minfo)

        tinfo = minfo.get('Transaction', {})
        self.Transaction = EndpointRegistryTransaction(tinfo)


class Update(object):
    """Updates represent potential changes to the endpoint registry.

    Attributes:
        KnownVerbs (list): A list of possible update actions.
        Verb (str): The action of this update, defaults to 'reg'.
        Domain (str): The domain of the endpoint.
        Name (str): The name of the endpoint.
        NodeIdentifier (str): The identifier of the endpoint.
        NetHost (str): The hostname or IP address of the endpoint.
        NetPort (int): The port number of the endpoint.
    """
    KnownVerbs = ['reg', 'unr']

    @staticmethod
    def create_from_node(node, domain='/'):
        """Creates a new Update object based on the attributes of a
        node.

        Args:
            node (Node): The node to create an endpoint registry update
                object based on.
            domain (str): The domain of the endpoint.

        Returns:
            Update: An update object for registering the node's details.
        """
        update = Update()

        update.Verb = 'reg'
        update.Domain = domain
        update.Name = node.Name
        update.NodeIdentifier = node.Identifier
        update.NetHost = node.NetHost
        update.NetPort = node.NetPort

        return update

    def __init__(self, minfo={}):
        """Constructor for Update class.

        Args:
            minfo (dict): Dictionary of values for update fields.
        """
        self.Verb = minfo.get('Verb', 'reg')

        self.Domain = minfo.get('Domain', '/')
        self.Name = minfo.get('Name', 'unknown')
        self.NodeIdentifier = minfo.get('NodeIdentifier', '')
        self.NetHost = minfo.get('NetHost', '0.0.0.0')
        self.NetPort = minfo.get('NetPort', 0)

    def __str__(self):
        return "({0} {1} {2} {3} {4}:{5})".format(
            self.Verb, self.NodeIdentifier, self.Name, self.Domain,
            self.NetHost, self.NetPort)

    def is_valid(self, store, originatorid):
        """Determines if the update is valid.

        Args:
            store (dict): Transaction store mapping.
            originatorid (str): Node identifier of transaction originator.
        """
        logger.debug('check update %s from %s', str(self), originatorid)

        # if the asset exists then the node must be the same as the transaction
        # originator
        if (self.NodeIdentifier in store
                and self.NodeIdentifier != originatorid):
            return False

        # check for an attempt to change owner of a non-existant asset
        if self.Verb == 'unr' and self.NodeIdentifier not in store:
            return False

        return True

    def apply(self, store):
        """Applies the update to the asset in the transaction store.

        Args:
            store (dict): Transaction store mapping.
        """
        logger.debug('apply %s', str(self))

        if self.Verb == 'reg':
            store[self.NodeIdentifier] = {
                'Name': self.Name,
                'Domain': self.Domain,
                'NodeIdentifier': self.NodeIdentifier,
                'Host': self.NetHost,
                'Port': self.NetPort
            }
        elif self.Verb == 'unr':
            del store[self.NodeIdentifier]
        else:
            logger.info('unknown verb %s', self.Verb)

    def dump(self):
        """Returns a dict with attributes from the update object.

        Returns:
            dict: A dictionary containing attributes from the update
                object.
        """
        result = {
            'Verb': self.Verb,
            'Domain': self.Domain,
            'Name': self.Name,
            'NodeIdentifier': self.NodeIdentifier,
            'NetHost': self.NetHost,
            'NetPort': self.NetPort
        }
        return result


class EndpointRegistryTransaction(transaction.Transaction):
    """A Transaction is a set of updates to be applied atomically
    to a ledger.

    It has a unique identifier and a signature to validate the source.

    Attributes:
        TransactionTypeName (str): The name of the endpoint registry
            transaction type.
        TransactionStoreType (type): The type of the transaction store.
        MessageType (type): The object type of the message associated
            with this transaction.
        Updates (list): A list of endpoint registry updates associated
            with this transaction.
    """
    TransactionTypeName = '/EndpointRegistryTransaction'
    TransactionStoreType = global_store_manager.KeyValueStore
    MessageType = EndpointRegistryTransactionMessage

    @staticmethod
    def create_from_node(node, domain='/'):
        """Creates a new EndpointRegistryTransaction object based on
        the attributes of a node.

        Args:
            node (Node): The node to create an endpoint registry update
                object based on.
            domain (str): The domain of the endpoint.

        Returns:
            Update: A transaction contiaining an update for
                registering the node's details.
        """
        regtxn = EndpointRegistryTransaction()
        regtxn.Updates.append(Update.create_from_node(node, domain))

        return regtxn

    def __init__(self, minfo={}):
        super(EndpointRegistryTransaction, self).__init__(minfo)

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
        if not super(EndpointRegistryTransaction, self).is_valid(store):
            return False

        for update in self.Updates:
            if not update.is_valid(store, self.OriginatorID):
                logger.debug('invalid transaction: %s', str(update))
                return False

        return True

    def apply(self, store):
        """Applies all the updates in the transaction to the endpoint
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
        result = super(EndpointRegistryTransaction, self).dump()

        result['Updates'] = []
        for update in self.Updates:
            result['Updates'].append(update.dump())

        return result

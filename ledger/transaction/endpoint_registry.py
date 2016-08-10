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
import pybitcointools as pbt

from journal import transaction, global_store_manager
from journal.messages import transaction_message

from gossip.common import NullIdentifier
from gossip import message, node

logger = logging.getLogger(__name__)


def register_transaction_types(ledger):
    """Registers the endpoint registry asset types on the ledger.

    Args:
        ledger (journal.journal_core.Journal): The ledger to register
            the transaction type against.
    """
    ledger.register_message_handler(
        SpecialPingMessage,
        _specpinghandler)
    ledger.register_message_handler(
        EndpointRegistryTransactionMessage,
        transaction_message.transaction_message_handler)
    ledger.add_transaction_store(EndpointRegistryTransaction)


def send_to_closest_nodes(ledger, msg, addr, count=1, initialize=True):
    """
    Send a message to a set of "close" nodes where close is defined
    by the distance metric in EndpointRegistryStore (XOR distance).
    If the nodes are not currently in the ledger's node map, then
    add them.
    """

    storemap = ledger.GlobalStore
    epstore = storemap.GetTransactionStore(
        EndpointRegistryTransaction.TransactionTypeName)
    assert epstore

    nodes = epstore.FindClosestNodes(addr, count)
    if ledger.LocalNode.Identifier in nodes:
        nodes.remove(ledger.LocalNode.Identifier)

    if nodes:
        # make sure the nodes are all in the node map
        for nodeid in nodes:
            if nodeid not in ledger.NodeMap:
                ninfo = epstore[nodeid]
                addr = (ninfo['Host'], int(ninfo['Port']))
                ledger.AddNode(node.Node(address=addr, identifier=nodeid,
                                         name=ninfo['Name']))

        logger.debug('send %s to %s', str(msg), ",".join(nodes))
        ledger.MulticastMessage(msg, nodes)

    return nodes


class SpecialPingMessage(message.Message):
    """
    A class for the "Special Ping" message used to test and debug
    multicast message transmission.
    """

    MessageType = "/" + __name__ + "/SpecialPing"

    def __init__(self, minfo=None):
        if minfo is None:
            minfo = {}
        super(SpecialPingMessage, self).__init__(minfo)

        self.IsSystemMessage = True
        self.IsForward = False
        self.IsReliable = False

        self.Address = minfo.get('Address')
        self.Count = int(minfo.get('Count', 1))

    def dump(self):
        result = super(SpecialPingMessage, self).dump()
        result['Address'] = self.Address or self.OriginatorID
        result['Count'] = self.Count

        return result


def _specpinghandler(msg, ledger):
    """
    Handle the special ping message. Dump message information into
    the log and forward if necessary.
    Args:
        message -- SpecialPingMessage
        ledger -- journal.Journal_core
    """
    identifier = "{0}, {1:0.2f}, {2}".format(ledger.LocalNode, time.time(),
                                             msg.Identifier[:8])
    logger.info('receive sping, %s, %s, %s', identifier, msg.Address,
                msg.Count)

    if msg.TimeToLive > 0:
        nodes = send_to_closest_nodes(ledger, msg, msg.Address,
                                      msg.Count, False)
        logger.info('send sping, %s, %s', identifier, ",".join(nodes))


class EndpointRegistryTransactionMessage(
        transaction_message.TransactionMessage):
    """Endpoint registry transaction messages represent endpoint registry
    transactions.

    Attributes:
        EndpointRegistryTransactionMessage.MessageType (str): The class name
            of the message.
        Transaction (EndpointRegistryTransaction): The transaction the
            message is associated with.
    """
    MessageType = "/ledger.transaction.EndpointRegistry/Transaction"

    def __init__(self, minfo=None):
        if minfo is None:
            minfo = {}
        super(EndpointRegistryTransactionMessage, self).__init__(minfo)

        tinfo = minfo.get('Transaction', {})
        self.Transaction = EndpointRegistryTransaction(tinfo)


class Update(object):
    """Updates represent potential changes to the endpoint registry.

    Attributes:
        endpoint_registry.Update.KnownVerbs (list): A list of possible update
            actions.
        Verb (str): The action of this update, defaults to 'reg'.
        Domain (str): The domain of the endpoint.
        Name (str): The name of the endpoint.
        NodeIdentifier (str): The identifier of the endpoint.
        NetHost (str): The hostname or IP address of the endpoint.
        NetPort (int): The port number of the endpoint.
    """
    KnownVerbs = ['reg', 'unr']

    @staticmethod
    def register_node(txn, nde, domain='/', httpport=None):
        """Creates a new Update object based on the attributes of a
        node.

        Args:
            nde (Node): The node to create an endpoint registry update
                object based on.
            domain (str): The domain of the endpoint.

        Returns:
            endpoint_registry.Update: An update object for registering the
                node's details.
        """
        update = Update(txn)

        update.Verb = 'reg'
        update.Domain = domain
        update.Name = nde.Name
        # Take the host/port form the endpoint host/port (i.e., the externally-
        # visible host/port) if it is present.  If not, take them from the
        # locally-bound host/port.
        update.NetHost = nde.endpoint_host
        update.NetPort = nde.endpoint_port
        update.HttpPort = httpport
        update.NodeIdentifier = nde.Identifier
        return update

    @staticmethod
    def unregister_node(txn, nde):
        update = Update(txn)

        update.Verb = 'unr'
        update.NodeIdentifier = nde.Identifier

        return update

    def __init__(self, txn=None, minfo=None):
        """Constructor for Update class.

        Args:
            minfo (dict): Dictionary of values for update fields.
        """

        if minfo is None:
            minfo = {}
        self.Transaction = txn
        self.Verb = minfo.get('Verb', 'reg')

        self.Domain = minfo.get('Domain', '/')
        self.Name = minfo.get('Name', '')
        self.NetHost = minfo.get('NetHost', '0.0.0.0')
        self.NetPort = minfo.get('NetPort', 0)
        self.HttpPort = minfo.get('HttpPort', 0)
        self.NodeIdentifier = minfo.get('NodeIdentifier', NullIdentifier)

    def __str__(self):
        return "({0} {1} {2} {3} {4}:{5} {4}:{6})".format(
            self.Verb, self.NodeIdentifier, self.Name, self.Domain,
            self.NetHost, self.NetPort, self.HttpPort)

    def is_valid(self, store):
        """Determines if the update is valid.

        Args:
            store (dict): Transaction store mapping.
            originatorid (str): Node identifier of transaction originator.
        """
        logger.debug('check update %s from %s', str(self), self.NodeIdentifier)

        assert (self.Transaction)

        # if the asset exists then the node must be the same as the transaction
        # originator
        if self.NodeIdentifier != self.Transaction.OriginatorID:
            return False

        # check for an attempt to change owner of a non-existent asset
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
                'Host': self.NetHost,
                'Port': self.NetPort,
                'HttpPort': self.HttpPort,
                'NodeIdentifier': self.NodeIdentifier,
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
        assert self.Transaction

        result = {
            'Verb': self.Verb,
            'Domain': self.Domain,
            'Name': self.Name,
            'NetHost': self.NetHost,
            'NetPort': self.NetPort,
            'HttpPort': self.HttpPort,
            'NodeIdentifier': self.NodeIdentifier
        }
        return result


class EndpointRegistryGlobalStore(global_store_manager.KeyValueStore):
    @staticmethod
    def address_distance(addr1, addr2):
        v1 = int(pbt.b58check_to_hex(addr1), 16)
        v2 = int(pbt.b58check_to_hex(addr2), 16)
        return v1 ^ v2

    def __init__(self, prevstore=None, storeinfo=None, readonly=False):
        super(EndpointRegistryGlobalStore, self).__init__(prevstore, storeinfo,
                                                          readonly)

    def clone_store(self, storeinfo=None, readonly=False):
        """
        Create a new checkpoint that can be modified
        :return: a new checkpoint that extends the current store
        :rtype: KeyValueStore
        """
        return EndpointRegistryGlobalStore(self, storeinfo, readonly)

    def find_closest_nodes(self, addr, count=1):
        """
        Find the nodes with identifiers closest to the specified address
        using XOR distance. Note that this implementation is very inefficient.
        :param string key: node identifier (address format)
        :param int count: number of matches to return
        """
        addrs = self.keys()
        addrs.sort(
            key=lambda a: EndpointRegistryGlobalStore.address_distance(
                addr, a))
        return addrs[:count]


class EndpointRegistryTransaction(transaction.Transaction):
    """A Transaction is a set of updates to be applied atomically
    to a ledger.

    It has a unique identifier and a signature to validate the source.

    Attributes:
        EndpointRegistryTransaction.TransactionTypeName (str): The name of the
            endpoint registry transaction type.
        EndpointRegistryTransaction.TransactionStoreType (type): The type of
            the transaction store.
        EndpointRegistryTransaction.MessageType (type): The object type of the
            message associated with this transaction.
        Updates (list): A list of endpoint registry updates associated
            with this transaction.
    """
    TransactionTypeName = '/EndpointRegistryTransaction'
    TransactionStoreType = EndpointRegistryGlobalStore
    MessageType = EndpointRegistryTransactionMessage

    @staticmethod
    def register_node(nde, domain='/', httpport=None):
        """Creates a new EndpointRegistryTransaction object based on
        the attributes of a node.

        Args:
            nde (Node): The node to create an endpoint registry update
                object based on.
            domain (str): The domain of the endpoint.

        Returns:
            endpoint_registry.Update: A transaction containing an update for
                registering the node's details.
        """
        regtxn = EndpointRegistryTransaction()
        regtxn.Update = Update.register_node(regtxn, nde, domain, httpport)

        return regtxn

    @staticmethod
    def unregister_node(nde):
        unrtxn = EndpointRegistryTransaction()
        unrtxn.Update = Update.unregister_node(unrtxn, nde)

        return unrtxn

    def __init__(self, minfo=None):
        if minfo is None:
            minfo = {}
        super(EndpointRegistryTransaction, self).__init__(minfo)

        self.Update = None

        if 'Update' in minfo:
            self.Update = Update(txn=self, minfo=minfo['Update'])

    def __str__(self):
        return str(self.Update)

    def is_valid(self, store):
        """Determines if the transaction is valid.

        Args:
            store (dict): Transaction store mapping.

        Returns:
            bool: Whether or not the transaction is valid.
        """
        if not super(EndpointRegistryTransaction, self).is_valid(store):
            return False

        assert self.Update

        if not self.Update.is_valid(store):
            logger.debug('invalid transaction: %s', str(self.Update))
            return False

        return True

    def apply(self, store):
        """Applies all the updates in the transaction to the endpoint
        in the transaction store.

        Args:
            store (dict): Transaction store mapping.
        """
        self.Update.apply(store)

    def dump(self):
        """Returns a dict with attributes from the transaction object.

        Returns:
            dict: The updates from the transaction object.
        """
        result = super(EndpointRegistryTransaction, self).dump()

        result['Update'] = self.Update.dump()

        return result

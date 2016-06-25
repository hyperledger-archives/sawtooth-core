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
import random
import signal
import socket

from twisted.internet import reactor

from txnserver import ledger_web_client
from gossip import node, signed_object, token_bucket
from gossip.messages import connect_message, shutdown_message
from gossip.topology import random_walk, barabasi_albert
from journal.protocol import journal_transfer
from ledger.transaction import endpoint_registry

logger = logging.getLogger(__name__)


class Validator(object):
    DefaultTransactionFamilies = [
        # IntegerKey,
        endpoint_registry
    ]

    def __init__(self, config, windows_service):

        self.Config = config

        self.windows_service = windows_service

        # this is going to be used as a flag to indicate that a
        # topology update is in progress
        self._connectionattempts = 0
        self.delaystart = self.Config['DelayStart']

        # set up signal handlers for shutdown
        if not windows_service:
            signal.signal(signal.SIGTERM, self.handle_shutdown_signal)
            signal.signal(signal.SIGINT, self.handle_shutdown_signal)

        # ---------- Initialize the configuration ----------
        self.initialize_common_configuration()
        self.initialize_ledger_specific_configuration()

        # ---------- Initialize the NodeMap ----------
        self.initialize_node_map()

        # ---------- Initialize the Ledger ----------
        self.initialize_ledger_object()

    def handle_shutdown_signal(self, signum, frame):
        logger.warn('received shutdown signal')
        self.shutdown()

    def shutdown(self):
        """
        Shutdown the validator. There are several things that need to happen
        on shutdown: 1) disconnect this node from the network, 2) close all the
        databases, and 3) shutdown twisted. We need time for each to finish.
        """

        # send the transaction to remove this node from the endpoint
        # registry (or send it to the web server)
        self.unregister_endpoint(self.Ledger.LocalNode, self.EndpointDomain)

        # Need to wait long enough for all the shutdown packets to be sent out
        reactor.callLater(1.0, self.handle_ledger_shutdown)

    def handle_ledger_shutdown(self):
        self.Ledger.shutdown()

        # Need to wait long enough for all the shutdown packets to be sent out
        # if a shutdown packet was the reason for the shutdown
        reactor.callLater(1.0, self.handle_shutdown)

    def handle_shutdown(self):
        reactor.stop()

    def initialize_common_configuration(self):
        self.GenesisLedger = self.Config.get('GenesisLedger', False)

        # Handle the common configuration variables
        if 'NetworkFlowRate' in self.Config:
            token_bucket.TokenBucket.DefaultDripRate = self.Config[
                'NetworkFlowRate']

        if 'NetworkBurstRate' in self.Config:
            token_bucket.TokenBucket.DefaultDripRate = self.Config[
                'NetworkBurstRate']

        if 'AdministrationNode' in self.Config:
            logger.info('set administration node to %s',
                        self.Config.get('AdministrationNode'))
            shutdown_message.AdministrationNode = self.Config[
                'AdministrationNode']

        if 'NetworkDelayRange' in self.Config:
            node.Node.DelayRange = self.Config['NetworkDelayRange']

        if 'UseFixedDelay' in self.Config:
            node.Node.UseFixedDelay = self.Config['UseFixedDelay']

    def initialize_ledger_specific_configuration(self):
        """
        Initialize any ledger type specific configuration options, expected to
        be overridden
        """
        pass

    def initialize_node_map(self):
        self.NodeMap = {}
        for nodedata in self.Config.get("Nodes", []):
            addr = (socket.gethostbyname(nodedata["Host"]), nodedata["Port"])
            nd = node.Node(address=addr,
                           identifier=nodedata["Identifier"],
                           name=nodedata["ShortName"])
            nd.disable()
            self.NodeMap[nodedata["ShortName"]] = nd

    def initialize_ledger_object(self):
        # Create the local ledger instance
        name = self.Config['NodeName']
        if name in self.NodeMap:
            nd = self.NodeMap[name]
        else:
            host = self.Config['Host']
            port = self.Config['Port']
            addr = (socket.gethostbyname(host), port)
            signingkey = signed_object.generate_signing_key(
                wifstr=self.Config.get('SigningKey'))
            identifier = signed_object.generate_identifier(signingkey)
            nd = node.Node(address=addr,
                           identifier=identifier,
                           signingkey=signingkey,
                           name=name)

        self.initialize_ledger_from_node(nd)
        assert self.Ledger

        for txnfamily in self.DefaultTransactionFamilies:
            txnfamily.register_transaction_types(self.Ledger)

        self.Ledger.onNodeDisconnect += self.handle_node_disconnect_event

        logger.info("starting ledger %s with id %s at network address %s",
                    self.Ledger.LocalNode,
                    self.Ledger.LocalNode.Identifier[:8],
                    self.Ledger.LocalNode.NetAddress)

    def initialize_ledger_from_node(self, node):
        """
        Initialize the ledger object for the local node, expected to be
        overridden
        """
        self.Ledger = None

    def post_initialize_ledger(self):
        """
        Run optional ledger-specific post-initialization tasks
        """
        pass

    def add_transaction_family(self, txnfamily):
        txnfamily.register_transaction_types(self.Ledger)

    def pre_start(self):
        if self.delaystart is True:
            logger.debug("DelayStart is in effect, waiting for /start")
            reactor.callLater(1, self.pre_start)
        else:
            self.start()

    def start(self):
        # if this is the genesis ledger then there isn't anything left to do
        if self.GenesisLedger:
            self.start_ledger()
            return

        # if this isn't the genesis ledger then we need to connect
        # this node into the validator network, first set up a handler
        # in case of failure during initialization
        reactor.callLater(60.0, self._verify_initialization)
        self.initialize_ledger_connection()
        self.post_initialize_ledger()

    def handle_node_disconnect_event(self, nodeid):
        """
        Handle the situation where a peer is marked as disconnected.
        """

        logger.info('node %s dropped, reassess connectivity', nodeid)

        # first see if we are already handling the situation
        if self._connectionattempts > 0:
            logger.info('topology update already in progress')
            return

        # there are many possible policies for when to kick off
        # new topology probes. for the moment, just use the initial
        # connectivity as a lower threshhold
        minpeercount = self.Config.get("InitialConnectivity", 1)
        peerlist = self.Ledger.peer_list()
        if len(peerlist) <= minpeercount and self._connectionattempts == 0:
            def disconnect_callback():
                logger.info('topology update finished, %s peers connected',
                            len(self.Ledger.peer_list()))

            logger.info('connectivity has dropped below mimimal levels, '
                        'kick off topology update')
            self._connectionattempts = 3
            reactor.callLater(2.0, self.initialize_ledger_topology,
                              disconnect_callback)

    def initialize_ledger_connection(self):
        """
        Connect the ledger to the rest of the network; in addition to the
        list of nodes directly specified in the configuration file, pull
        a list from the LedgerURL. Once the list of potential peers is
        constructed, pick from it those specified in the Peers configuration
        variable. If that is not enough, then pick more at random from the
        list.
        """

        assert self.Ledger

        # Continue to support existing config files with single
        # string values.
        if isinstance(self.Config.get('LedgerURL'), basestring):
            urls = [self.Config.get('LedgerURL')]
        else:
            urls = self.Config.get('LedgerURL', ['**none**'])

        if not self.GenesisLedger:
            for url in urls:
                logger.info('attempting to load peers using url %s', url)
                try:
                    peers = self.get_endpoints(url, self.EndpointDomain)
                    for peer in peers:
                        self.NodeMap[peer.Name] = peer
                    break
                except ledger_web_client.MessageException as e:
                    logger.error("Unable to get endpoints from LedgerURL: %s",
                                 str(e))
        else:
            logger.info('not loading peers since **none** was provided as '
                        'a url option.')

        # Build a list of nodes that we can use for the initial connection
        minpeercount = self.Config.get("InitialConnectivity", 1)
        peerset = set(self.Config.get('Peers', []))
        nodeset = set(self.NodeMap.keys())
        if len(peerset) < minpeercount and len(nodeset) > 0:
            nodeset.discard(self.Ledger.LocalNode.Name)
            nodeset = nodeset.difference(peerset)
            peerset = peerset.union(random.sample(list(nodeset), min(
                minpeercount - len(peerset), len(nodeset))))

        # Add the candidate nodes to the gossip object so we can send connect
        # requests to them
        connections = 0
        for peername in peerset:
            peer = self.NodeMap.get(peername)
            if peer:
                logger.info('add peer %s with identifier %s', peername,
                            peer.Identifier)
                connect_message.send_connection_request(self.Ledger, peer)
                connections += 1
                self.Ledger.add_node(peer)
            else:
                logger.info('requested connection to unknown peer %s',
                            peername)

        # the pathological case is that there was nothing specified and since
        # we already know we aren't the genesis block, we can just shut down
        if connections == 0:
            logger.critical('unable to find a valid peer')
            self.shutdown()
            return

        logger.debug("initial ledger connection requests sent")

        # Wait for the connection message to be processed before jumping to the
        # next state a better technique would be to add an event in sawtooth
        # when a new node is connected
        self._connectionattempts = 3
        reactor.callLater(2.0, self.initialize_ledger_topology,
                          self.start_journal_transfer)

    def initialize_ledger_topology(self, callback):
        """
        Make certain that there is at least one connected peer and then
        kick off the configured topology generation protocol.
        """

        logger.debug('initialize ledger topology')

        # make sure there is at least one connection already confirmed
        if len(self.Ledger.peer_list()) == 0:
            self._connectionattempts -= 1
            if self._connectionattempts > 0:
                logger.info('initial connection attempts failed, '
                            'try again [%s]', self._connectionattempts)
                for peer in self.Ledger.peer_list(allflag=True):
                    connect_message.send_connection_request(self.Ledger, peer)
                reactor.callLater(2.0, self.initialize_ledger_topology,
                                  callback)
                return
            else:
                logger.critical('failed to connect to selected peers, '
                                'shutting down')
                self.shutdown()
                return

        self._connectionattempts = 0

        # and now its time to pick the topology protocol
        topology = self.Config.get("TopologyAlgorithm", "RandomWalk")
        if topology == "RandomWalk":
            if 'TargetConnectivity' in self.Config:
                random_walk.TargetConnectivity = self.Config[
                    'TargetConnectivity']
            self.random_walk_initialization(callback)

        elif topology == "BarabasiAlbert":
            if 'MaximumConnectivity' in self.Config:
                barabasi_albert.MaximumConnectivity = self.Config[
                    'MaximumConnectivity']
            if 'MinimumConnectivity' in self.Config:
                barabasi_albert.MinimumConnectivity = self.Config[
                    'MinimumConnectivity']
            self.barabasi_initialization(callback)

        else:
            logger.error("unknown topology protocol %s", topology)
            self.shutdown()
            return

    def barabasi_initialization(self, callback):
        logger.info("ledger connections using BarabasiAlbert topology")
        barabasi_albert.start_topology_update(self.Ledger, callback)

    def random_walk_initialization(self, callback):
        logger.info("ledger connections using RandomWalk topology")
        random_walk.start_topology_update(self.Ledger, callback)

    def start_journal_transfer(self):
        if not journal_transfer.start_journal_transfer(self.Ledger,
                                                       self.start_ledger):
            # this generally happens because there are no valid peers, for now
            # assume that we are the first validator and go with it
            self.start_ledger()

    def start_ledger(self):
        logger.info('ledger initialization complete')
        self.Ledger.initialization_complete()

        self.register_endpoint(self.Ledger.LocalNode, self.EndpointDomain)

    def _verify_initialization(self):
        """
        Callback to determine if the initialization failed fatally. This
        happens most often if there are no peers and this is not the root
        validator.
        """

        # this case should never happen, change to an assert later
        if not self.Ledger:
            logger.error('failed to initialize, no ledger, shutting down')
            self.shutdown()
            return

        logger.info('check for valid initialization; peers=%s',
                    [p.Name for p in self.Ledger.peer_list()])

        # if this is not the root validator and there are no peers, something
        # bad happened and we are just going to bail out
        if len(self.Ledger.peer_list()) == 0:
            logger.error('failed to connect to peers, shutting down')
            self.shutdown()
            return

        # if we are still initializing, e.g. waiting for a large ledger
        # transfer to complete, then come back and check again
        if self.Ledger.Initializing:
            logger.info('still initializing')
            reactor.callLater(60.0, self._verify_initialization)

    def register_endpoint(self, node, domain='/'):
        txn = endpoint_registry.EndpointRegistryTransaction.register_node(
            node, domain, httpport=self.Config["HttpPort"])
        txn.sign_from_node(node)

        msg = endpoint_registry.EndpointRegistryTransactionMessage()
        msg.Transaction = txn
        msg.SenderID = str(node.Identifier)
        msg.sign_from_node(node)

        logger.info('register endpoint %s with name %s', node.Identifier[:8],
                    node.Name)
        self.Ledger.handle_message(msg)

    def unregister_endpoint(self, node, domain='/'):
        txn = endpoint_registry.EndpointRegistryTransaction \
            .unregister_node(node)
        txn.sign_from_node(node)
        # Since unregister is often called on shutdown, we really need to make
        # this a system message for the purpose of sending it out from our own
        # queue
        msg = endpoint_registry.EndpointRegistryTransactionMessage()
        msg.Transaction = txn
        msg.SenderID = str(node.Identifier)
        msg.sign_from_node(node)
        logger.info('unregister endpoint %s with name %s', node.Identifier[:8],
                    node.Name)
        self.Ledger.handle_message(msg)

    def get_endpoints(self, url, domain='/'):
        client = ledger_web_client.LedgerWebClient(url)

        endpoints = []

        eplist = client.get_store(
            endpoint_registry.EndpointRegistryTransaction)
        if not eplist:
            return endpoints

        for ep in eplist:
            epinfo = client.get_store(
                endpoint_registry.EndpointRegistryTransaction, ep)
            if epinfo.get('Domain', '/').startswith(domain):
                addr = (socket.gethostbyname(epinfo["Host"]), epinfo["Port"])
                endpoint = node.Node(address=addr,
                                     identifier=epinfo["NodeIdentifier"],
                                     name=epinfo["Name"])
                endpoints.append(endpoint)

        logger.info('found %d endpoints', len(endpoints))

        return endpoints

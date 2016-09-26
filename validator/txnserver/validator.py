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
import os
import cProfile

from twisted.internet import reactor
from twisted.python.threadpool import ThreadPool

from sawtooth.endpoint_client import EndpointClient
from sawtooth.exceptions import MessageException
from sawtooth.validator_config import parse_listen_directives

from gossip import node, signed_object, token_bucket
from gossip.messages import connect_message, shutdown_message
from gossip.topology import random_walk, barabasi_albert
from journal.protocol import journal_transfer
from ledger.transaction import endpoint_registry

logger = logging.getLogger(__name__)


def parse_networking_info(config):
    '''
    Provides a DRY location for parsing a validator's intended network
    interface specifications from that validator's configuration
    Args:
        config: (dict) - fully resolved configuration dictionary (c.f.
            sawtooth.Config)
    Returns:
        (nd, http_port): an ordered pair, where:
            nd:         (gossip.Node)
            http_port:  (int) or (None)

    '''
    # Parse the listen directives from the configuration so
    # we know what to bind gossip protocol to
    listen_directives = parse_listen_directives(config)

    # If the gossip listen address is 0.0.0.0, then there must be
    # an Endpoint.Host entry as we don't know what to put in the
    # endpoint registry otherwise.
    if listen_directives['gossip'].host == '0.0.0.0' and \
            ('Endpoint' not in config or
             'Port' not in config['Endpoint']):
        raise Exception(
            'gossip listen address is 0.0.0.0, but endpoint host '
            'missing from configuration')

    gossip_host = listen_directives['gossip'].host
    gossip_port = listen_directives['gossip'].port

    # The endpoint host/port and HTTP port come from the listen data, but
    # can be overridden by the configuration.
    endpoint_host = gossip_host
    endpoint_port = gossip_port
    endpoint_http_port = None
    if 'http' in listen_directives:
        endpoint_http_port = listen_directives['http'].port

    # See if we need to override the endpoint data
    endpoint_cfg = config.get('Endpoint', None)
    if endpoint_cfg is not None:
        if 'Host' in endpoint_cfg:
            endpoint_host = endpoint_cfg['Host']
        if 'Port' in endpoint_cfg:
            endpoint_port = int(endpoint_cfg['Port'])
        if 'HttpPort' in endpoint_cfg:
            endpoint_http_port = int(endpoint_cfg['HttpPort'])

    # Finally, if the endpoint host is 'localhost', we need to convert it
    # because to another host, obviously 'localhost' won't mean "us"
    if endpoint_host == 'localhost':
        endpoint_host = socket.gethostbyname(endpoint_host)
    name = config['NodeName']
    addr = (socket.gethostbyname(gossip_host), gossip_port)
    endpoint_addr = (endpoint_host, endpoint_port)
    signingkey = signed_object.generate_signing_key(
        wifstr=config.get('SigningKey'))
    identifier = signed_object.generate_identifier(signingkey)
    nd = node.Node(address=addr,
                   identifier=identifier,
                   signingkey=signingkey,
                   name=name,
                   endpoint_address=endpoint_addr)
    return (nd, endpoint_http_port)


class Validator(object):
    DefaultTransactionFamilies = [
        # IntegerKey,
        endpoint_registry
    ]

    def __init__(self,
                 gossip_obj,
                 ledger_obj,
                 config,
                 windows_service=False,
                 http_port=None,
                 ):
        '''
        Creates a validator.  As a current side-effect, does some
        initialization on it's ledger_obj argumenet
        Args:
            node_obj: (gossip.Node)
            ledger_obj: (journal.Journal)
            config: (dict)
            windows_service: (bool)
            http_port: (int)
        '''
        self.status = 'stopped'
        self.Config = config

        self.gossip = gossip_obj
        node_obj = gossip_obj.LocalNode
        self._gossip_host = node_obj.NetHost
        self._gossip_port = node_obj.NetAddress

        self._endpoint_host = node_obj.endpoint_host
        self._endpoint_port = node_obj.endpoint_port
        self._endpoint_http_port = http_port

        self.Ledger = ledger_obj

        self.profile = self.Config.get('Profile', False)

        if self.profile:
            self.pr = cProfile.Profile()
            self.pr.enable()

        self.windows_service = windows_service

        # flag to indicate that a topology update is in progress
        self._topology_update_in_progress = False
        self.delaystart = self.Config['DelayStart']

        # set up signal handlers for shutdown
        if not windows_service:
            signal.signal(signal.SIGTERM, self.handle_shutdown_signal)
            signal.signal(signal.SIGINT, self.handle_shutdown_signal)

        # ---------- Initialize the configuration ----------
        self.initialize_common_configuration()

        # ---------- Initialize the NodeMap ----------
        self.initialize_node_map()

        # ---------- Initialize the Ledger ----------
        self.initialize_ledger_object()

        maxsize = self.Config.get("WebPoolSize", 8)
        self.web_thread_pool = ThreadPool(0, maxsize, "WebThreadPool")

    def handle_shutdown_signal(self, signum, frame):
        logger.warn('received shutdown signal')
        self.shutdown()

    def shutdown(self):
        """
        Shutdown the validator. There are several things that need to happen
        on shutdown: 1) disconnect this node from the network, 2) close all the
        databases, and 3) shutdown twisted. We need time for each to finish.
        """
        self.status = 'stopping'
        if self.profile:
            self.pr.create_stats()
            loc = os.path.join(self.Config.get('DataDirectory', '/tmp'),
                               '{0}.cprofile'.format(
                                   self.Config.get('NodeName',
                                                   str(os.getpid()))))
            self.pr.dump_stats(loc)

        # send the transaction to remove this node from the endpoint
        # registry (or send it to the web server)
        if self.gossip is not None:
            self.unregister_endpoint(self.gossip.LocalNode)

        # Need to wait long enough for all the shutdown packets to be sent out
        reactor.callLater(1.0, self.handle_ledger_shutdown)

    def handle_ledger_shutdown(self):
        self.Ledger.shutdown()
        self.gossip.shutdown()

        # Need to wait long enough for all the shutdown packets to be sent out
        # if a shutdown packet was the reason for the shutdown
        reactor.callLater(1.0, self.handle_shutdown)

    def handle_shutdown(self):
        self.web_thread_pool.stop()
        reactor.stop()
        self.status = 'stopped'

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

    def initialize_node_map(self):
        self.NodeMap = {}
        for nodedata in self.Config.get("Nodes", []):
            addr = (socket.gethostbyname(nodedata["Host"]), nodedata["Port"])
            nd = node.Node(address=addr,
                           identifier=nodedata["Identifier"],
                           name=nodedata["NodeName"])
            self.NodeMap[nodedata["NodeName"]] = nd

    def initialize_ledger_object(self):
        assert self.Ledger

        for txnfamily in self.DefaultTransactionFamilies:
            txnfamily.register_transaction_types(self.Ledger)

        self.gossip.onNodeDisconnect += self.handle_node_disconnect_event

        logger.info("starting ledger %s with id %s at network address %s",
                    self.gossip.LocalNode,
                    self.gossip.LocalNode.Identifier[:8],
                    self.gossip.LocalNode.NetAddress)

    def add_transaction_family(self, txnfamily):
        txnfamily.register_transaction_types(self.Ledger)

    def pre_start(self):
        if self.delaystart is True:
            logger.debug("DelayStart is in effect, waiting for /start")
            reactor.callLater(1, self.pre_start)
        else:
            self.status = 'starting'
            self.start()

    def start(self):
        # add blacklist before we attempt any peering
        self.gossip.blacklist = self.Config.get('Blacklist', [])
        # if this is the genesis ledger then there isn't anything left to do
        if self.GenesisLedger:
            self.start_ledger()
            return

        # if this isn't the genesis ledger then we need to connect
        # this node into the validator network
        self.initialize_ledger_connection()

    def handle_node_disconnect_event(self, nodeid):
        """
        Handle the situation where a peer is marked as disconnected.
        """

        logger.info('node %s dropped, reassess connectivity', nodeid)

        # first see if we are already handling the situation
        if self._topology_update_in_progress:
            logger.info('topology update already in progress')
            return

        # there are many possible policies for when to kick off
        # new topology probes. for the moment, just use the initial
        # connectivity as a lower threshhold
        minpeercount = self.Config.get("InitialConnectivity", 1)
        peerlist = self.gossip.peer_list()
        if len(peerlist) <= minpeercount:
            def disconnect_callback():
                logger.info('topology update finished, %s peers connected',
                            len(self.gossip.peer_list()))

            logger.info('connectivity has dropped below mimimal levels, '
                        'kick off topology update')
            self._topology_update_in_progress = True
            reactor.callLater(2.0, self.initialize_ledger_topology,
                              disconnect_callback)

    def _get_candidate_peers(self):
        """
        Return the candidate (potential) peers to send connection requests; in
        addition to the list of nodes directly specified in the configuration
        file, pull a list from the LedgerURL. Once the list of potential peers
        is constructed, pick from it those specified in the Peers configuration
        variable. If that is not enough, then pick more at random from the
        list.
        """

        # Continue to support existing config files with single
        # string values.
        if isinstance(self.Config.get('LedgerURL'), basestring):
            urls = [self.Config.get('LedgerURL')]
        else:
            urls = self.Config.get('LedgerURL', [])

        # We randomize the url list here so that we avoid the
        # condition of a small number of validators referencing
        # each other's empty EndpointRegistries forever.
        random.shuffle(urls)
        for url in urls:
            logger.info('attempting to load peers using url %s', url)
            try:
                peers = self.get_endpoint_nodes(url)
                # If the Endpoint Registry is empty, try the next
                # url in the shuffled list
                if len(peers) == 0:
                    continue
                for peer in peers:
                    self.NodeMap[peer.Name] = peer
                break
            except MessageException as e:
                logger.error("Unable to get endpoints from LedgerURL: %s",
                             str(e))

        # We may also be able to rediscover peers via the persistence layer.
        if self.Ledger.Restore:
            for blockid in self.Ledger.GlobalStoreMap.persistmap_keys():
                blk = self.Ledger.GlobalStoreMap.get_block_store(blockid)
                sto = blk.get_transaction_store('/EndpointRegistryTransaction')
                for key in sto:
                    nd = self._endpoint_info_to_node(sto[key])
                    self.NodeMap[nd.Name] = nd

        # Build a list of nodes that we can use for the initial connection
        minpeercount = self.Config.get("InitialConnectivity", 1)
        peerset = set(self.Config.get('Peers', []))
        nodeset = set(self.NodeMap.keys())
        if len(peerset) < minpeercount and len(nodeset) > 0:
            nodeset.discard(self.gossip.LocalNode.Name)
            nodeset = nodeset.difference(peerset)
            peerset = peerset.union(random.sample(list(nodeset), min(
                minpeercount - len(peerset), len(nodeset))))

        return peerset

    def _connect_to_peers(self):
        min_peer_count = self.Config.get("InitialConnectivity", 1)
        current_peer_count = len(self.gossip.peer_list())

        logger.debug("peer count is %d of %d",
                     current_peer_count, min_peer_count)

        if current_peer_count < min_peer_count:
            peerset = self._get_candidate_peers()

            # Add the candidate nodes to the gossip object so we can send
            # connect requests to them
            for peername in peerset:
                peer = self.NodeMap.get(peername)
                if peer:
                    logger.info('add peer %s with identifier %s', peername,
                                peer.Identifier)
                    connect_message.send_connection_request(self.gossip, peer)
                    self.gossip.add_node(peer)
                else:
                    logger.info('requested connection to unknown peer %s',
                                peername)

            return False
        else:
            return True

    def initialize_ledger_connection(self):
        """
        Connect the ledger to the rest of the network.
        """

        assert self.Ledger

        self.status = 'waiting for initial connections'

        if not self._connect_to_peers():
            reactor.callLater(2.0, self.initialize_ledger_connection)
        else:
            reactor.callLater(2.0, self.initialize_ledger_topology,
                              self.start_journal_transfer)

    def initialize_ledger_topology(self, callback):
        """
        Make certain that there is at least one connected peer and then
        kick off the configured topology generation protocol.
        """

        logger.debug('initialize ledger topology')

        if not self._connect_to_peers():
            reactor.callLater(2.0, self.initialize_ledger_topology,
                              callback)
            return

        self._topology_update_in_progress = False

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
        barabasi_albert.start_topology_update(self.gossip, callback)

    def random_walk_initialization(self, callback):
        logger.info("ledger connections using RandomWalk topology")
        random_walk.start_topology_update(self.gossip, callback)

    def start_journal_transfer(self):
        self.status = 'transferring ledger'
        if not journal_transfer.start_journal_transfer(self.Ledger,
                                                       self.start_ledger):
            self.start_ledger()

    def start_ledger(self):
        logger.info('ledger initialization complete')
        self.Ledger.initialization_complete()
        self.status = 'started'
        self.register_endpoint(self.gossip.LocalNode)

    def register_endpoint(self, node):
        txn = endpoint_registry.EndpointRegistryTransaction.register_node(
            node, httpport=self._endpoint_http_port)
        txn.sign_from_node(node)

        msg = endpoint_registry.EndpointRegistryTransactionMessage()
        msg.Transaction = txn
        msg.SenderID = str(node.Identifier)
        msg.sign_from_node(node)

        logger.info('register endpoint %s with name %s', node.Identifier[:8],
                    node.Name)
        self.gossip.handle_message(msg)

    def unregister_endpoint(self, node):
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
        self.gossip.handle_message(msg)

    def get_endpoint_nodes(self, url):
        client = EndpointClient(url)

        nodes = []
        for epinfo in client.get_endpoint_list():
            nodes.append(self._endpoint_info_to_node(epinfo))
        return nodes

    @staticmethod
    def _endpoint_info_to_node(epinfo):
        addr = (socket.gethostbyname(epinfo["Host"]), epinfo["Port"])
        nd = node.Node(address=addr,
                       identifier=epinfo["NodeIdentifier"],
                       name=epinfo["Name"])
        return nd

# Copyright 2017 Intel Corporation
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
import copy
import time
import random
from threading import Thread
from threading import Condition
from functools import partial
from enum import Enum

from sawtooth_validator.protobuf.network_pb2 import DisconnectMessage
from sawtooth_validator.protobuf.network_pb2 import GossipMessage
from sawtooth_validator.protobuf.network_pb2 import GossipBatchByBatchIdRequest
from sawtooth_validator.protobuf.network_pb2 import \
    GossipBatchByTransactionIdRequest
from sawtooth_validator.protobuf.network_pb2 import GossipBlockRequest
from sawtooth_validator.protobuf import validator_pb2
from sawtooth_validator.protobuf.network_pb2 import PeerRegisterRequest
from sawtooth_validator.protobuf.network_pb2 import PeerUnregisterRequest
from sawtooth_validator.protobuf.network_pb2 import GetPeersRequest
from sawtooth_validator.protobuf.network_pb2 import GetPeersResponse
from sawtooth_validator.protobuf.network_pb2 import NetworkAcknowledgement
from sawtooth_validator.exceptions import PeeringException

LOGGER = logging.getLogger(__name__)


class PeerStatus(Enum):
    CLOSED = 1
    TEMP = 2
    PEER = 3


class EndpointStatus(Enum):
    # Endpoint will be used for peering
    PEERING = 1
    # Endpoint will be used to request peers
    TOPOLOGY = 2


class Gossip(object):
    def __init__(self, network,
                 endpoint=None,
                 peering_mode='static',
                 initial_seed_endpoints=None,
                 initial_peer_endpoints=None,
                 minimum_peer_connectivity=3,
                 maximum_peer_connectivity=10,
                 topology_check_frequency=1):
        """Constructor for the Gossip object. Gossip defines the
        overlay network above the lower level networking classes.

        Args:
            network (networking.Interconnect): Provides inbound and
                outbound network connections.
            endpoint (str): The publically accessible zmq-style uri
                endpoint for this validator.
            peering_mode (str): The type of peering approach. Either 'static'
                or 'dynamic'. In 'static' mode, no attempted topology
                buildout occurs -- the validator only attempts to initiate
                peering connections with endpoints specified in the
                peer_list. In 'dynamic' mode, the validator will first
                attempt to initiate peering connections with endpoints
                specified in the peer_list and then attempt to do a
                topology buildout starting with peer lists obtained from
                endpoints in the seeds_list. In either mode, the validator
                will accept incoming peer requests up to max_peers.
            initial_seed_endpoints ([str]): A list of initial endpoints
                to attempt to connect and gather initial topology buildout
                information from. These are specified as zmq-compatible
                URIs (e.g. tcp://hostname:port).
            initial_peer_endpoints ([str]): A list of initial peer endpoints
                to attempt to connect and peer with. These are specified
                as zmq-compatible URIs (e.g. tcp://hostname:port).
            minimum_peer_connectivity (int): If the number of connected
                peers is below this threshold, the topology builder will
                continue to attempt to identify new candidate peers to
                connect with.
            maximum_peer_connectivity (int): The validator will reject
                new peer requests if the number of connected peers
                reaches this threshold.
            topology_check_frequency (int): The time in seconds between
                topology update checks.
        """
        self._peering_mode = peering_mode
        self._condition = Condition()
        self._network = network
        self._endpoint = endpoint
        self._initial_seed_endpoints = initial_seed_endpoints \
            if initial_seed_endpoints else []
        self._initial_peer_endpoints = initial_peer_endpoints \
            if initial_peer_endpoints else []
        self._minimum_peer_connectivity = minimum_peer_connectivity
        self._maximum_peer_connectivity = maximum_peer_connectivity
        self._topology_check_frequency = topology_check_frequency

        self._topology = None
        self._peers = {}

    def send_peers(self, connection_id):
        """Sends a message containing our peers to the
        connection identified by connection_id.

        Args:
            connection_id (str): A unique identifier which identifies an
                connection on the network server socket.
        """
        with self._condition:
            # Needs to actually be the list of advertised endpoints of
            # our peers
            peer_endpoints = list(self._peers.values())
            if self._endpoint:
                peer_endpoints.append(self._endpoint)
            peers_response = GetPeersResponse(peer_endpoints=peer_endpoints)
            self._network.send(validator_pb2.Message.GOSSIP_GET_PEERS_RESPONSE,
                               peers_response.SerializeToString(),
                               connection_id)

    def add_candidate_peer_endpoints(self, peer_endpoints):
        """Adds candidate endpoints to the list of endpoints to
        attempt to peer with.

        Args:
            peer_endpoints ([str]): A list of public uri's which the
                validator can attempt to peer with.
        """
        if self._topology:
            self._topology.add_candidate_peer_endpoints(peer_endpoints)
        else:
            LOGGER.debug("Could not add peer endpoints to topology. "
                         "Topology does not exist.")

    def get_peers(self):
        """Returns a copy of the gossip peers.
        """
        with self._condition:
            return copy.copy(self._peers)

    def register_peer(self, connection_id, endpoint):
        """Registers a connected connection_id.

        Args:
            connection_id (str): A unique identifier which identifies an
                connection on the network server socket.
            endpoint (str): The publically reachable endpoint of the new
                peer
        """
        with self._condition:
            if len(self._peers) < self._maximum_peer_connectivity:
                self._peers[connection_id] = endpoint
                self._topology.set_connection_status(connection_id,
                                                     PeerStatus.PEER)
                LOGGER.debug("Added connection_id %s with endpoint %s, "
                             "connected identities are now %s",
                             connection_id, endpoint, self._peers)
            else:
                LOGGER.debug("At maximum configured number of peers: %s "
                             "Rejecting peering request from %s.",
                             self._maximum_peer_connectivity,
                             endpoint)
                raise PeeringException()

    def unregister_peer(self, connection_id):
        """Removes a connection_id from the registry.

        Args:
            connection_id (str): A unique identifier which identifies an
                connection on the network server socket.
        """
        with self._condition:
            if connection_id in self._peers:
                del self._peers[connection_id]
                LOGGER.debug("Removed connection_id %s, "
                             "connected identities are now %s",
                             connection_id, self._peers)
                self._topology.set_connection_status(connection_id,
                                                     PeerStatus.TEMP)
            else:
                LOGGER.debug("Attempt to unregister connection_id %s failed: "
                             "connection_id was not registered")

    def broadcast_block(self, block, exclude=None):
        gossip_message = GossipMessage(
            content_type="BLOCK",
            content=block.SerializeToString())

        self.broadcast(
            gossip_message, validator_pb2.Message.GOSSIP_MESSAGE, exclude)

    def broadcast_block_request(self, block_id):
        # Need to define node identity to be able to route directly back
        block_request = GossipBlockRequest(block_id=block_id)
        self.broadcast(block_request,
                       validator_pb2.Message.GOSSIP_BLOCK_REQUEST)

    def send_block_request(self, block_id, connection_id):
        block_request = GossipBlockRequest(block_id=block_id)
        self.send(validator_pb2.Message.GOSSIP_BLOCK_REQUEST,
                  block_request.SerializeToString(),
                  connection_id)

    def broadcast_batch(self, batch, exclude=None):
        gossip_message = GossipMessage(
            content_type="BATCH",
            content=batch.SerializeToString())

        self.broadcast(
            gossip_message, validator_pb2.Message.GOSSIP_MESSAGE, exclude)

    def broadcast_batch_by_transaction_id_request(self, transaction_ids):
        # Need to define node identity to be able to route directly back
        batch_request = GossipBatchByTransactionIdRequest(
            ids=transaction_ids
        )
        self.broadcast(
            batch_request,
            validator_pb2.Message.GOSSIP_BATCH_BY_TRANSACTION_ID_REQUEST)

    def broadcast_batch_by_batch_id_request(self, batch_id):
        # Need to define node identity to be able to route directly back
        batch_request = GossipBatchByBatchIdRequest(
            id=batch_id
        )
        self.broadcast(
            batch_request,
            validator_pb2.Message.GOSSIP_BATCH_BY_BATCH_ID_REQUEST)

    def send(self, message_type, message, connection_id):
        """Sends a message via the network.

        Args:
            message_type (str): The type of the message.
            message (bytes): The message to be sent.
            connection_id (str): The connection to send it to.
        """
        self._network.send(message_type, message, connection_id)

    def broadcast(self, gossip_message, message_type, exclude=None):
        """Broadcast gossip messages.

        Broadcast the message to all peers unless they are in the excluded
        list.

        Args:
            gossip_message: The message to be broadcast.
            message_type: Type of the message.
            exclude: A list of connection_ids that should be excluded from this
                broadcast.
        """
        with self._condition:
            if exclude is None:
                exclude = []
            for connection_id in self._peers.copy():
                if connection_id not in exclude:
                    try:
                        self._network.send(message_type,
                                           gossip_message.SerializeToString(),
                                           connection_id)
                    except ValueError:
                        LOGGER.debug("Connection %s is no longer valid. "
                                     "Removing from list of peers.",
                                     connection_id)
                        del self._peers[connection_id]

    def connect_success(self, connection_id):
        """
        Notify topology that a connection has been properly authorized

        Args:
            connection_id: The connection id for the authorized connection.

        """
        if self._topology:
            self._topology.connect_success(connection_id)

    def remove_temp_endpoint(self, endpoint):
        """
        Remove temporary endpoints that never finished authorization.

        Args:
            endpoint: The endpoint that is not authorized to connect to the
                network.
        """
        if self._topology:
            self._topology.remove_temp_endpoint(endpoint)

    def start(self):
        self._topology = Topology(
            gossip=self,
            network=self._network,
            endpoint=self._endpoint,
            initial_peer_endpoints=self._initial_peer_endpoints,
            initial_seed_endpoints=self._initial_seed_endpoints,
            peering_mode=self._peering_mode,
            min_peers=self._minimum_peer_connectivity,
            max_peers=self._maximum_peer_connectivity,
            check_frequency=self._topology_check_frequency)

        self._topology.start()

    def stop(self):
        for peer in self.get_peers():
            request = PeerUnregisterRequest()
            try:
                self._network.send(validator_pb2.Message.GOSSIP_UNREGISTER,
                                   request.SerializeToString(),
                                   peer)
            except ValueError:
                pass
        if self._topology:
            self._topology.stop()


class Topology(Thread):
    def __init__(self, gossip, network, endpoint,
                 initial_peer_endpoints, initial_seed_endpoints,
                 peering_mode, min_peers=3, max_peers=10,
                 check_frequency=1):
        """Constructor for the Topology class.

        Args:
            gossip (gossip.Gossip): The gossip overlay network.
            network (network.Interconnect): The underlying network.
            endpoint (str): A zmq-style endpoint uri representing
                this validator's publically reachable endpoint.
            initial_peer_endpoints ([str]): A list of static peers
                to attempt to connect and peer with.
            initial_seed_endpoints ([str]): A list of endpoints to
                connect to and get candidate peer lists to attempt
                to reach min_peers threshold.
            peering_mode (str): Either 'static' or 'dynamic'. 'static'
                only connects to peers in initial_peer_endpoints.
                'dynamic' connects to peers in initial_peer_endpoints
                and gets candidate peer lists from initial_seed_endpoints.
            min_peers (int): The minimum number of peers required to stop
                attempting candidate connections.
            max_peers (int): The maximum number of active peer connections
                to allow.
            check_frequency (int): How often to attempt dynamic connectivity.
        """
        super().__init__(name="Topology")
        self._condition = Condition()
        self._stopped = False
        self._peers = []
        self._gossip = gossip
        self._network = network
        self._endpoint = endpoint
        self._initial_peer_endpoints = initial_peer_endpoints
        self._initial_seed_endpoints = initial_seed_endpoints
        self._peering_mode = peering_mode
        self._min_peers = min_peers
        self._max_peers = max_peers
        self._check_frequency = check_frequency

        self._candidate_peer_endpoints = []
        # Seconds to wait for messages to arrive
        self._response_duration = 2
        self._connection_statuses = {}
        self._temp_endpoints = {}

    def start(self):
        # First, attempt to connect to explicit peers
        for endpoint in self._initial_peer_endpoints:
            LOGGER.debug("attempting to peer with %s", endpoint)
            self._network.add_outbound_connection(endpoint)
            self._temp_endpoints[endpoint] = EndpointStatus.PEERING

        if self._peering_mode == 'dynamic':
            super().start()

    def run(self):
        while not self._stopped:
            try:
                peers = self._gossip.get_peers()
                if len(peers) < self._min_peers:
                    LOGGER.debug("Below minimum peer threshold. "
                                 "Doing topology search.")

                    self._reset_candidate_peer_endpoints()
                    self._refresh_peer_list(peers)
                    # Cleans out any old connections that have disconnected
                    self._refresh_connection_list()

                    peers = self._gossip.get_peers()

                    self._get_peers_of_peers(peers)
                    self._get_peers_of_endpoints(peers,
                                                 self._initial_seed_endpoints)

                    # Wait for GOSSIP_GET_PEER_RESPONSE messages to arrive
                    time.sleep(self._response_duration)

                    peered_endpoints = list(peers.values())

                    with self._condition:
                        unpeered_candidates = list(
                            set(self._candidate_peer_endpoints) -
                            set(peered_endpoints) -
                            set([self._endpoint]))

                    LOGGER.debug("Number of peers: %s",
                                 len(peers))
                    LOGGER.debug("Peers are: %s",
                                 list(peers.values()))
                    LOGGER.debug("Unpeered candidates are: %s",
                                 unpeered_candidates)

                    if unpeered_candidates:
                        self._attempt_to_peer_with_endpoint(
                            random.choice(unpeered_candidates))

                time.sleep(self._check_frequency)
            except Exception:  # pylint: disable=broad-except
                LOGGER.exception("Unhandled exception during peer refresh")

    def stop(self):
        self._stopped = True
        for connection_id in self._connection_statuses:
            try:
                if self._connection_statuses[connection_id] == \
                        PeerStatus.CLOSED:
                    continue

                msg = DisconnectMessage()
                self._network.send(
                    validator_pb2.Message.NETWORK_DISCONNECT,
                    msg.SerializeToString(),
                    connection_id)
                self._connection_statuses[connection_id] = PeerStatus.CLOSED
            except ValueError:
                # Connection has already been disconnected.
                pass

    def add_candidate_peer_endpoints(self, peer_endpoints):
        """Adds candidate endpoints to the list of endpoints to
        attempt to peer with.

        Args:
            peer_endpoints ([str]): A list of public uri's which the
                validator can attempt to peer with.
        """
        with self._condition:
            for endpoint in peer_endpoints:
                if endpoint not in self._candidate_peer_endpoints:
                    self._candidate_peer_endpoints.append(endpoint)

    def set_connection_status(self, connection_id, status):
        self._connection_statuses[connection_id] = status

    def remove_temp_endpoint(self, endpoint):
        if endpoint in self._temp_endpoints:
            del self._temp_endpoints[endpoint]

    def _refresh_peer_list(self, peers):
        for conn_id in peers:
            try:
                self._network.get_connection_id_by_endpoint(
                    peers[conn_id])
            except KeyError:
                LOGGER.debug("removing peer %s because "
                             "connection went away",
                             peers[conn_id])

                self._gossip.unregister_peer(conn_id)
                if conn_id in self._connection_statuses:
                    del self._connection_statuses[conn_id]

    def _refresh_connection_list(self):
        with self._condition:
            closed_connections = []
            for connection_id in self._connection_statuses:
                if not self._network.has_connection(connection_id):
                    closed_connections.append(connection_id)

            for connection_id in closed_connections:
                del self._connection_statuses[connection_id]

    def _get_peers_of_peers(self, peers):
        get_peers_request = GetPeersRequest()

        for conn_id in peers:
            self._network.send(
                validator_pb2.Message.GOSSIP_GET_PEERS_REQUEST,
                get_peers_request.SerializeToString(),
                conn_id)

    def _get_peers_of_endpoints(self, peers, endpoints):
        get_peers_request = GetPeersRequest()

        for endpoint in endpoints:
            try:
                if endpoint in self._temp_endpoints:
                    LOGGER.debug("Endpoint is not ready to be asked about "
                                 "peers: %s", endpoint)
                else:
                    conn_id = self._network.get_connection_id_by_endpoint(
                        endpoint)
                    if conn_id in peers:
                        # connected and peered - we've already sent
                        continue
                    else:
                        # connected but not peered
                        self._network.send(
                            validator_pb2.Message.GOSSIP_GET_PEERS_REQUEST,
                            get_peers_request.SerializeToString(),
                            conn_id)
            except KeyError:
                self._network.add_outbound_connection(
                    endpoint)
                self._temp_endpoints[endpoint] = EndpointStatus.TOPOLOGY

    def _attempt_to_peer_with_endpoint(self, endpoint):
        LOGGER.debug("Attempting to connect/peer with %s", endpoint)

        # check if the connection exists, if it does - send,
        # otherwise create it
        try:
            connection_id = \
                self._network.get_connection_id_by_endpoint(
                    endpoint)

            register_request = PeerRegisterRequest(
                endpoint=self._endpoint)

            self._network.send(
                validator_pb2.Message.GOSSIP_REGISTER,
                register_request.SerializeToString(),
                connection_id,
                callback=partial(self._peer_callback,
                                 endpoint=endpoint,
                                 connection_id=connection_id))
        except KeyError:
            # if the connection uri wasn't found in the network's
            # connections, it raises a KeyError and we need to add
            # a new outbound connection
            self._temp_endpoints[endpoint] = EndpointStatus.PEERING
            self._network.add_outbound_connection(endpoint)

    def _reset_candidate_peer_endpoints(self):
        with self._condition:
            self._candidate_peer_endpoints = []

    def _peer_callback(self, request, result, connection_id, endpoint=None):
        with self._condition:
            ack = NetworkAcknowledgement()
            ack.ParseFromString(result.content)

            if ack.status == ack.ERROR:
                LOGGER.debug("Peering request to %s was NOT successful",
                             connection_id)
                self._remove_temporary_connection(connection_id)
            elif ack.status == ack.OK:
                LOGGER.debug("Peering request to %s was successful",
                             connection_id)
                if endpoint:
                    self._gossip.register_peer(connection_id, endpoint)
                    self._connection_statuses[connection_id] = PeerStatus.PEER
                else:
                    LOGGER.debug("Cannot register peer with no endpoint for "
                                 "connection_id: %s",
                                 connection_id)
                    self._remove_temporary_connection(connection_id)

                self._gossip.send_block_request("HEAD", connection_id)

    def _remove_temporary_connection(self, connection_id):
        status = self._connection_statuses.get(connection_id)
        if status == PeerStatus.TEMP:
            LOGGER.debug("Closing connection to %s", connection_id)
            msg = DisconnectMessage()
            self._network.send(validator_pb2.Message.NETWORK_DISCONNECT,
                               msg.SerializeToString(),
                               connection_id)
            del self._connection_statuses[connection_id]
            self._network.remove_connection(connection_id)
        elif status == PeerStatus.PEER:
            LOGGER.debug("Connection is a peer, do not close.")
        elif status is None:
            LOGGER.debug("Connection is not found")

    def connect_success(self, connection_id):
        """
        Check to see if the successful connection is meant to be peered with.
        If not, it should be used to get the peers from the connection.
        """
        endpoint = self._network.connection_id_to_endpoint(connection_id)
        if self._temp_endpoints.get(endpoint) == EndpointStatus.PEERING:
            self._connect_success_peering(connection_id)
            del self._temp_endpoints[endpoint]

        elif self._temp_endpoints.get(endpoint) == EndpointStatus.TOPOLOGY:
            self._connect_success_topology(connection_id)
            del self._temp_endpoints[endpoint]

        else:
            LOGGER.debug("Received unknown endpoint: %s.", endpoint)
            if endpoint in self._temp_endpoints:
                del self._temp_endpoints[endpoint]

    def _connect_success_peering(self, connection_id):
        LOGGER.debug("Connection to %s succeeded", connection_id)

        register_request = PeerRegisterRequest(
            endpoint=self._endpoint)
        self._connection_statuses[connection_id] = PeerStatus.TEMP

        endpoint = self._network.connection_id_to_endpoint(connection_id)
        self._network.send(validator_pb2.Message.GOSSIP_REGISTER,
                           register_request.SerializeToString(),
                           connection_id,
                           callback=partial(self._peer_callback,
                                            connection_id=connection_id,
                                            endpoint=endpoint))

    def _connect_success_topology(self, connection_id):
        LOGGER.debug("Connection to %s succeeded for topology request",
                     connection_id)
        self._connection_statuses[connection_id] = PeerStatus.TEMP
        get_peers_request = GetPeersRequest()

        def callback(request, result):
            # request, result are ignored, but required by the callback
            self._remove_temporary_connection(connection_id)

        self._network.send(validator_pb2.Message.GOSSIP_GET_PEERS_REQUEST,
                           get_peers_request.SerializeToString(),
                           connection_id,
                           callback=callback)

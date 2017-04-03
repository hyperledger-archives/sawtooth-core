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
from threading import Condition
from functools import partial

from sawtooth_validator.protobuf.network_pb2 import GossipMessage
from sawtooth_validator.protobuf.network_pb2 import GossipBatchByBatchIdRequest
from sawtooth_validator.protobuf.network_pb2 import \
    GossipBatchByTransactionIdRequest
from sawtooth_validator.protobuf.network_pb2 import GossipBlockRequest
from sawtooth_validator.protobuf import validator_pb2
from sawtooth_validator.protobuf.network_pb2 import PeerRegisterRequest
from sawtooth_validator.protobuf.network_pb2 import NetworkAcknowledgement

LOGGER = logging.getLogger(__name__)


class Gossip(object):
    def __init__(self, network, initial_peer_endpoints=None):
        """Constructor for the Gossip object. Gossip defines the
        overlay network above the lower level networking classes.

        Args:
            network (networking.Interconnect): Provides inbound and
                outbound network connections.
            initial_peer_endpoints ([str]): A list of initial peer endpoints
                to attempt to connect and peer with. These are specified
                as zmq-compatible URIs (e.g. tcp://hostname:port).
        """
        self._condition = Condition()
        self._network = network
        self._initial_peer_endpoints = initial_peer_endpoints \
            if initial_peer_endpoints else []
        self._peers = []

    def register_peer(self, connection_id):
        """Registers a connected connection_id.

        Args:
            connection_id (str): A unique identifier which identifies an
                connection on the network server socket.
        """
        with self._condition:
            self._peers.append(connection_id)
        LOGGER.debug("Added connection_id %s, connected identities are now %s",
                     connection_id, self._peers)

    def unregister_peer(self, connection_id):
        """Removes a connection_id from the registry.

        Args:
            connection_id (str): A unique identifier which identifies an
                connection on the network server socket.
        """
        with self._condition:
            if connection_id in self._peers:
                self._peers.remove(connection_id)
                LOGGER.debug("Removed connection_id %s, "
                             "connected identities are now %s",
                             connection_id, self._peers)
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
        if exclude is None:
            exclude = []
        for connection_id in self._peers:
            if connection_id not in exclude:
                try:
                    self._network.send(message_type,
                                       gossip_message.SerializeToString(),
                                       connection_id)
                except ValueError:
                    LOGGER.debug("Connection %s is no longer valid. "
                                 "Removing from list of peers.",
                                 connection_id)
                    self._peers.remove(connection_id)

    def _peer_callback(self, request, result, connection_id):
        ack = NetworkAcknowledgement()
        ack.ParseFromString(result.content)

        if ack.status == ack.ERROR:
            LOGGER.debug("Peering request to %s was NOT successful",
                         connection_id)
        elif ack.status == ack.OK:
            LOGGER.debug("Peering request to %s was successful",
                         connection_id)
            self._peers.append(connection_id)
            self.broadcast_block_request("HEAD")

    def _connect_success_callback(self, connection_id):
        LOGGER.debug("Connection to %s succeeded", connection_id)

        register_request = PeerRegisterRequest()
        self._network.send(validator_pb2.Message.GOSSIP_REGISTER,
                           register_request.SerializeToString(),
                           connection_id,
                           callback=partial(self._peer_callback,
                                            connection_id=connection_id))

    def _connect_failure_callback(self, connection_id):
        LOGGER.debug("Connection to %s failed", connection_id)

    def start(self):
        for endpoint in self._initial_peer_endpoints:
            self._network.add_outbound_connection(
                endpoint,
                self._connect_success_callback,
                self._connect_failure_callback)

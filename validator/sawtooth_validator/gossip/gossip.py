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
import hashlib
from threading import Condition

from sawtooth_validator.protobuf.network_pb2 import GossipMessage
from sawtooth_validator.protobuf.network_pb2 import GossipBatchByBatchIdRequest
from sawtooth_validator.protobuf.network_pb2 import \
    GossipBatchByTransactionIdRequest
from sawtooth_validator.protobuf.network_pb2 import GossipBlockRequest
from sawtooth_validator.protobuf import validator_pb2
from sawtooth_validator.protobuf.network_pb2 import PeerRegisterRequest

LOGGER = logging.getLogger(__name__)


class Gossip(object):
    def __init__(self, network):
        self._condition = Condition()
        self._network = network
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
                self._network.send(message_type,
                                   gossip_message.SerializeToString(),
                                   connection_id)

    def start(self):
        for uri in self._network.outbound_connections:
            connection = self._network.outbound_connections[uri]
            connection_id = \
                hashlib.sha512(connection.local_id.encode()).hexdigest()
            self._peers.append(connection_id)
        register_request = PeerRegisterRequest()
        self.broadcast(
            register_request,
            validator_pb2.Message.GOSSIP_REGISTER)

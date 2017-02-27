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
        self._identities = []

    def register_identity(self, identity):
        """Registers a connected identity.

        Args:
            identity (str): A unique identifier which identifies an
                incoming connection on the network server socket.
        """
        with self._condition:
            self._identities.append(identity)
        LOGGER.debug("Added identity %s, connected identities are now %s",
                     identity, self._identities)

    def unregister_identity(self, identity):
        """Removes an identity from the registry.

        Args:
            identity (str): A unique identifier which identifies an
                incoming connection on the network server socket.
        """
        with self._condition:
            if identity in self._identities:
                self._identities.remove(identity)
                LOGGER.debug("Removed identity %s, "
                             "connected identities are now %s",
                             identity, self._identities)
            else:
                LOGGER.debug("Attempt to unregister identity %s failed: "
                             "identity was not registered")

    def broadcast_block(self, block):
        gossip_message = GossipMessage(
            content_type="BLOCK",
            content=block.SerializeToString())

        self.broadcast(gossip_message, validator_pb2.Message.GOSSIP_MESSAGE)

    def broadcast_block_request(self, block_id):
        # Need to define node identity to be able to route directly back
        block_request = GossipBlockRequest(block_id=block_id)
        self.broadcast(block_request,
                       validator_pb2.Message.GOSSIP_BLOCK_REQUEST)

    def broadcast_batch(self, batch):
        gossip_message = GossipMessage(
            content_type="BATCH",
            content=batch.SerializeToString())

        self.broadcast(gossip_message, validator_pb2.Message.GOSSIP_MESSAGE)

    def broadcast_batch_by_transaction_id_request(self, batch_id):
        # Need to define node identity to be able to route directly back
        batch_request = GossipBatchByTransactionIdRequest(
            id=batch_id
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

    def broadcast(self, gossip_message, message_type):
        # Gossip broadcasts are sent out in two different ways.
        # 1) To connected identities on our server socket
        # 2) To outbound connections we have originated
        for identity in self._identities:
            self._network.send(message_type,
                               gossip_message.SerializeToString(),
                               identity)
        for connection in self._network.connections:
            connection.send(message_type, gossip_message.SerializeToString())

    def broadcast_peer_request(self, message_type, message):
        for connection in self._network.connections:
            connection.send(message_type, message.SerializeToString())

    def start(self):
        for connection in self._network.connections:
            connection.start(daemon=True)
        register_request = PeerRegisterRequest()
        self.broadcast_peer_request(
            validator_pb2.Message.GOSSIP_REGISTER,
            register_request)

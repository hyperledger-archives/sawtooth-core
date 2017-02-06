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

from sawtooth_validator.server.dispatch import Handler
from sawtooth_validator.server.dispatch import HandlerResult
from sawtooth_validator.server.dispatch import HandlerStatus
from sawtooth_validator.protobuf import validator_pb2
from sawtooth_validator.protobuf.batch_pb2 import Batch
from sawtooth_validator.protobuf.block_pb2 import Block
from sawtooth_validator.protobuf.network_pb2 import GossipMessage
from sawtooth_validator.protobuf.network_pb2 import PeerRegisterRequest
from sawtooth_validator.protobuf.network_pb2 import PeerUnregisterRequest
from sawtooth_validator.protobuf.network_pb2 import PingRequest
from sawtooth_validator.protobuf.network_pb2 import NetworkAcknowledgement


LOGGER = logging.getLogger(__name__)


class Gossip(object):
    def __init__(self, network):
        self._network = network

    def broadcast_block(self, block):
        gossip_message = GossipMessage(
            content_type="BLOCK",
            content=block.SerializeToString())

        self._broadcast(gossip_message)

    def broadcast_batch(self, batch):
        gossip_message = GossipMessage(
            content_type="BATCH",
            content=batch.SerializeToString())

        self._broadcast(gossip_message)

    def _broadcast(self, gossip_message):
        message_type = validator_pb2.Message.GOSSIP_MESSAGE
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


class PeerRegisterHandler(Handler):

    def handle(self, identity, message_content):
        request = PeerRegisterRequest()
        request.ParseFromString(message_content)
        LOGGER.debug("got peer register message "
                     "from %s. sending ack", identity)
        ack = NetworkAcknowledgement()
        ack.status = ack.OK

        return HandlerResult(
            HandlerStatus.RETURN,
            message_out=ack,
            message_type=validator_pb2.Message.GOSSIP_ACK)


class PeerUnregisterHandler(Handler):

    def handle(self, identity, message_content):
        request = PeerUnregisterRequest()
        request.ParseFromString(message_content)
        LOGGER.debug("got peer unregister message "
                     "from %s. sending ack", identity)

        ack = NetworkAcknowledgement()
        ack.status = ack.OK

        return HandlerResult(
            HandlerStatus.RETURN,
            message_out=ack,
            message_type=validator_pb2.Message.GOSSIP_ACK)


class GossipMessageHandler(Handler):
    def handle(self, identity, message_content):

        ack = NetworkAcknowledgement()
        ack.status = ack.OK
        gossip_message = GossipMessage()
        gossip_message.ParseFromString(message_content)

        return HandlerResult(
            HandlerStatus.RETURN_AND_PASS,
            message_out=ack,
            message_type=validator_pb2.Message.GOSSIP_ACK)


class GossipBroadcastHandler(Handler):

    def __init__(self, gossip):
        self._gossip = gossip

    def handle(self, identity, message_content):
        gossip_message = GossipMessage()
        gossip_message.ParseFromString(message_content)
        if gossip_message.content_type == "BATCH":
            batch = Batch()
            batch.ParseFromString(gossip_message.content)
            self._gossip.broadcast_batch(batch)
        elif gossip_message.content_type == "BLOCK":
            block = Block()
            block.ParseFromString(gossip_message.content)
            self._gossip.broadcast_block(block)
        else:
            LOGGER.info("received %s, not BATCH or BLOCK",
                        gossip_message.content_type)
        return HandlerResult(
            status=HandlerStatus.PASS
        )


class PingHandler(Handler):

    def handle(self, identity, message_content):
        request = PingRequest()
        request.ParseFromString(message_content)

        LOGGER.debug("got ping message "
                     "from %s. sending ack",
                     identity)

        ack = NetworkAcknowledgement()
        ack.status = ack.OK

        return HandlerResult(
            HandlerStatus.RETURN,
            message_out=ack,
            message_type=validator_pb2.Message.GOSSIP_ACK)

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

from sawtooth_validator.networking.dispatch import Handler
from sawtooth_validator.networking.dispatch import HandlerResult
from sawtooth_validator.networking.dispatch import HandlerStatus
from sawtooth_validator.protobuf import validator_pb2
from sawtooth_validator.protobuf.batch_pb2 import Batch
from sawtooth_validator.protobuf.block_pb2 import Block
from sawtooth_validator.protobuf.network_pb2 import GossipMessage
from sawtooth_validator.protobuf.network_pb2 import GossipBlockResponse
from sawtooth_validator.protobuf.network_pb2 import GossipBatchResponse
from sawtooth_validator.protobuf.network_pb2 import GetPeersRequest
from sawtooth_validator.protobuf.network_pb2 import GetPeersResponse
from sawtooth_validator.protobuf.network_pb2 import PeerRegisterRequest
from sawtooth_validator.protobuf.network_pb2 import PeerUnregisterRequest
from sawtooth_validator.protobuf.network_pb2 import NetworkAcknowledgement
from sawtooth_validator.exceptions import PeeringException

LOGGER = logging.getLogger(__name__)


class GetPeersRequestHandler(Handler):
    def __init__(self, gossip):
        self._gossip = gossip

    def handle(self, connection_id, message_content):
        request = GetPeersRequest()
        request.ParseFromString(message_content)
        LOGGER.debug("got peers request message "
                     "from %s. sending ack", connection_id)

        self._gossip.send_peers(connection_id)

        ack = NetworkAcknowledgement()
        ack.status = ack.OK

        return HandlerResult(
            HandlerStatus.RETURN,
            message_out=ack,
            message_type=validator_pb2.Message.NETWORK_ACK)


class GetPeersResponseHandler(Handler):
    def __init__(self, gossip):
        self._gossip = gossip

    def handle(self, connection_id, message_content):
        response = GetPeersResponse()
        response.ParseFromString(message_content)
        LOGGER.debug("got peers response message "
                     "from %s. sending ack", connection_id)

        LOGGER.debug("PEERS RESPONSE ENDPOINTS: %s", response.peer_endpoints)

        self._gossip.add_candidate_peer_endpoints(response.peer_endpoints)

        ack = NetworkAcknowledgement()
        ack.status = ack.OK

        return HandlerResult(
            HandlerStatus.RETURN,
            message_out=ack,
            message_type=validator_pb2.Message.NETWORK_ACK)


class PeerRegisterHandler(Handler):
    def __init__(self, gossip):
        self._gossip = gossip

    def handle(self, connection_id, message_content):
        request = PeerRegisterRequest()
        request.ParseFromString(message_content)
        LOGGER.debug("got peer register message "
                     "from %s. sending ack", connection_id)

        ack = NetworkAcknowledgement()
        try:
            self._gossip.register_peer(connection_id, request.endpoint)
            ack.status = ack.OK
        except PeeringException:
            ack.status = ack.ERROR

        return HandlerResult(
            HandlerStatus.RETURN,
            message_out=ack,
            message_type=validator_pb2.Message.NETWORK_ACK)


class PeerUnregisterHandler(Handler):
    def __init__(self, gossip):
        self._gossip = gossip

    def handle(self, connection_id, message_content):
        request = PeerUnregisterRequest()
        request.ParseFromString(message_content)
        LOGGER.debug("got peer unregister message "
                     "from %s. sending ack", connection_id)
        self._gossip.unregister_peer(connection_id)
        ack = NetworkAcknowledgement()
        ack.status = ack.OK

        return HandlerResult(
            HandlerStatus.RETURN,
            message_out=ack,
            message_type=validator_pb2.Message.NETWORK_ACK)


class GossipMessageHandler(Handler):
    def handle(self, connection_id, message_content):

        ack = NetworkAcknowledgement()
        ack.status = ack.OK
        gossip_message = GossipMessage()
        gossip_message.ParseFromString(message_content)

        return HandlerResult(
            HandlerStatus.RETURN_AND_PASS,
            message_out=ack,
            message_type=validator_pb2.Message.NETWORK_ACK)


class GossipBlockResponseHandler(Handler):
    def handle(self, connection_id, message_content):
        ack = NetworkAcknowledgement()
        ack.status = ack.OK
        block_response_message = GossipBlockResponse()
        block_response_message.ParseFromString(message_content)

        return HandlerResult(
            HandlerStatus.RETURN_AND_PASS,
            message_out=ack,
            message_type=validator_pb2.Message.NETWORK_ACK)


class GossipBatchResponseHandler(Handler):
    def handle(self, connection_id, message_content):
        ack = NetworkAcknowledgement()
        ack.status = ack.OK
        batch_response_message = GossipBatchResponse()
        batch_response_message.ParseFromString(message_content)

        return HandlerResult(
            HandlerStatus.RETURN_AND_PASS,
            message_out=ack,
            message_type=validator_pb2.Message.NETWORK_ACK)


class GossipBroadcastHandler(Handler):

    def __init__(self, gossip, completer):
        self._gossip = gossip
        self._completer = completer

    def handle(self, connection_id, message_content):
        exclude = [connection_id]
        gossip_message = GossipMessage()
        gossip_message.ParseFromString(message_content)
        if gossip_message.content_type == GossipMessage.BATCH:
            batch = Batch()
            batch.ParseFromString(gossip_message.content)
            # If we already have this batch, don't forward it
            if not self._completer.get_batch(batch.header_signature):
                self._gossip.broadcast_batch(batch, exclude)
        elif gossip_message.content_type == GossipMessage.BLOCK:
            block = Block()
            block.ParseFromString(gossip_message.content)
            # If we already have this block, don't forward it
            if not self._completer.get_block(block.header_signature):
                self._gossip.broadcast_block(block, exclude)
        else:
            LOGGER.info("received %s, not BATCH or BLOCK",
                        gossip_message.content_type)
        return HandlerResult(
            status=HandlerStatus.PASS
        )

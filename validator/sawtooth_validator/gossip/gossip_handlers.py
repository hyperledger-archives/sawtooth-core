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

        LOGGER.debug("Got peers request message from %s", connection_id)

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

        LOGGER.debug(
            "Got peers response message from %s. Endpoints: %s",
            connection_id,
            response.peer_endpoints)

        self._gossip.add_candidate_peer_endpoints(response.peer_endpoints)

        return HandlerResult(HandlerStatus.PASS)


class PeerRegisterHandler(Handler):
    def __init__(self, gossip):
        self._gossip = gossip

    def handle(self, connection_id, message_content):
        request = PeerRegisterRequest()
        request.ParseFromString(message_content)

        LOGGER.debug("Got peer register message from %s (%s, protocol v%s)",
                     connection_id, request.endpoint, request.protocol_version)

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

        LOGGER.debug("Got peer unregister message from %s", connection_id)

        self._gossip.unregister_peer(connection_id)
        ack = NetworkAcknowledgement()
        ack.status = ack.OK

        return HandlerResult(
            HandlerStatus.RETURN,
            message_out=ack,
            message_type=validator_pb2.Message.NETWORK_ACK)


class GossipMessageDuplicateHandler(Handler):
    def __init__(self, completer, has_block, has_batch):
        self._completer = completer
        self._has_block = has_block
        self._has_batch = has_batch

    def handle(self, connection_id, message_content):
        gossip_message = GossipMessage()
        gossip_message.ParseFromString(message_content)
        if gossip_message.content_type == gossip_message.BLOCK:
            block = Block()
            block.ParseFromString(gossip_message.content)
            has_block = False
            if self._completer.get_block(block.header_signature) is not None:
                has_block = True

            if not has_block and self._has_block(block.header_signature):
                has_block = True

            if has_block:
                return HandlerResult(HandlerStatus.DROP)

        if gossip_message.content_type == gossip_message.BATCH:
            batch = Batch()
            batch.ParseFromString(gossip_message.content)
            has_batch = False
            if self._completer.get_batch(batch.header_signature) is not None:
                has_batch = True

            if not has_batch and self._has_batch(batch.header_signature):
                has_batch = True

            if has_batch:
                return HandlerResult(HandlerStatus.DROP)

        return HandlerResult(HandlerStatus.PASS)


class GossipBlockResponseHandler(Handler):
    def __init__(self, completer, responder, chain_controller_has_block):
        self._completer = completer
        self._responder = responder
        self._chain_controller_has_block = chain_controller_has_block

    def handle(self, connection_id, message_content):
        block_response_message = GossipBlockResponse()
        block_response_message.ParseFromString(message_content)
        block = Block()
        block.ParseFromString(block_response_message.content)

        block_id = block.header_signature

        ack = NetworkAcknowledgement()
        ack.status = ack.OK

        if not self._has_open_requests(block_id) and self._has_block(block_id):
            return HandlerResult(
                HandlerStatus.RETURN,
                message_out=ack,
                message_type=validator_pb2.Message.NETWORK_ACK
            )

        return HandlerResult(
            HandlerStatus.RETURN_AND_PASS,
            message_out=ack,
            message_type=validator_pb2.Message.NETWORK_ACK)

    def _has_block(self, block_id):
        return (self._completer.get_block(block_id) is not None
                or self._chain_controller_has_block(block_id))

    def _has_open_requests(self, block_id):
        return self._responder.get_request(block_id)


class GossipBatchResponseHandler(Handler):
    def __init__(self, completer, responder, block_publisher_has_batch):
        self._completer = completer
        self._responder = responder
        self._block_publisher_has_batch = block_publisher_has_batch

    def handle(self, connection_id, message_content):
        batch_response_message = GossipBatchResponse()
        batch_response_message.ParseFromString(message_content)
        batch = Batch()
        batch.ParseFromString(batch_response_message.content)

        batch_id = batch.header_signature

        ack = NetworkAcknowledgement()
        ack.status = ack.OK

        if not self._has_open_requests(batch_id) and self._has_batch(batch_id):
            return HandlerResult(
                HandlerStatus.RETURN,
                message_out=ack,
                message_type=validator_pb2.Message.NETWORK_ACK
            )

        return HandlerResult(
            HandlerStatus.RETURN_AND_PASS,
            message_out=ack,
            message_type=validator_pb2.Message.NETWORK_ACK)

    def _has_batch(self, batch_id):
        return (self._completer.get_batch(batch_id) is not None
                or self._block_publisher_has_batch(batch_id))

    def _has_open_requests(self, batch_id):
        return self._responder.get_request(batch_id)


class GossipBroadcastHandler(Handler):
    def __init__(self, gossip, completer):
        self._gossip = gossip
        self._completer = completer

    def handle(self, connection_id, message_content):
        exclude = [connection_id]
        gossip_message = GossipMessage()
        gossip_message.ParseFromString(message_content)
        if gossip_message.time_to_live == 0:
            # Do not forward message if it has reached its time to live limit
            return HandlerResult(status=HandlerStatus.PASS)

        else:
            # decrement time_to_live
            time_to_live = gossip_message.time_to_live
            gossip_message.time_to_live = time_to_live - 1

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
        return HandlerResult(status=HandlerStatus.PASS)

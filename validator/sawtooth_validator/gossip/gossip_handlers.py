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
from sawtooth_validator.networking.dispatch import PreprocessorResult
from sawtooth_validator.protobuf import validator_pb2
from sawtooth_validator.protobuf.batch_pb2 import Batch
from sawtooth_validator.protobuf.block_pb2 import Block
from sawtooth_validator.protobuf.consensus_pb2 import ConsensusPeerMessage
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
        obj, tag, _ = message_content

        header_signature = obj.header_signature

        if tag == GossipMessage.BLOCK:
            has_block = False
            if self._completer.get_block(header_signature) is not None:
                has_block = True

            if not has_block and self._has_block(header_signature):
                has_block = True

            if has_block:
                return HandlerResult(HandlerStatus.DROP)

        if tag == GossipMessage.BATCH:
            has_batch = False
            if self._completer.get_batch(header_signature) is not None:
                has_batch = True

            if not has_batch and self._has_batch(header_signature):
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
        block, _ = message_content

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
        batch, _ = message_content

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


class GossipConsensusHandler(Handler):
    def __init__(self, gossip, notifier):
        self._gossip = gossip
        self._notifier = notifier

    def handle(self, connection_id, message_content):
        obj, tag, _ = message_content

        if tag == GossipMessage.CONSENSUS:
            self._notifier.notify_peer_message(
                message=obj,
                sender_id=bytes.fromhex(
                    self._gossip.peer_to_public_key(connection_id)))
        return HandlerResult(status=HandlerStatus.PASS)


class GossipBroadcastHandler(Handler):
    def __init__(self, gossip, completer):
        self._gossip = gossip
        self._completer = completer

    def handle(self, connection_id, message_content):
        obj, tag, ttl = message_content

        exclude = [connection_id]

        ttl -= 1

        if ttl <= 0:
            # Do not forward message if it has reached its time to live limit
            return HandlerResult(status=HandlerStatus.PASS)

        if tag == GossipMessage.BATCH:
            # If we already have this batch, don't forward it
            if not self._completer.get_batch(obj.header_signature):
                self._gossip.broadcast_batch(obj, exclude, time_to_live=ttl)
        elif tag == GossipMessage.BLOCK:
            # If we already have this block, don't forward it
            if not self._completer.get_block(obj.header_signature):
                self._gossip.broadcast_block(obj, exclude, time_to_live=ttl)
        elif tag == GossipMessage.CONSENSUS:
            # We do not want to forward consensus messages
            pass
        else:
            LOGGER.info("received %s, not BATCH or BLOCK or CONSENSUS", tag)
        return HandlerResult(status=HandlerStatus.PASS)


def gossip_message_preprocessor(message_content_bytes):
    gossip_message = GossipMessage()
    gossip_message.ParseFromString(message_content_bytes)

    tag = gossip_message.content_type

    if tag == GossipMessage.BLOCK:
        obj = Block()
        obj.ParseFromString(gossip_message.content)
    elif tag == GossipMessage.BATCH:
        obj = Batch()
        obj.ParseFromString(gossip_message.content)
    elif tag == GossipMessage.CONSENSUS:
        obj = ConsensusPeerMessage()
        obj.ParseFromString(gossip_message.content)

    content = obj, tag, gossip_message.time_to_live

    return PreprocessorResult(content=content)


def gossip_block_response_preprocessor(message_content_bytes):
    block_response = GossipBlockResponse()
    block_response.ParseFromString(message_content_bytes)
    block = Block()
    block.ParseFromString(block_response.content)

    content = block, message_content_bytes

    return PreprocessorResult(content=content)


def gossip_batch_response_preprocessor(message_content_bytes):
    batch_response = GossipBatchResponse()
    batch_response.ParseFromString(message_content_bytes)
    batch = Batch()
    batch.ParseFromString(batch_response.content)

    content = batch, message_content_bytes

    return PreprocessorResult(content=content)

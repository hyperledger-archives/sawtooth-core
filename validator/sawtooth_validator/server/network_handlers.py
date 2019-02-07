# Copyright 2016, 2017 Intel Corporation
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

from sawtooth_validator.protobuf import validator_pb2

from sawtooth_validator.journal.completer import CompleterGossipHandler
from sawtooth_validator.journal.completer import \
    CompleterGossipBlockResponseHandler
from sawtooth_validator.journal.completer import \
    CompleterGossipBatchResponseHandler
from sawtooth_validator.gossip import structure_verifier

from sawtooth_validator.journal.responder import BlockResponderHandler
from sawtooth_validator.journal.responder import ResponderBlockResponseHandler
from sawtooth_validator.journal.responder import BatchByBatchIdResponderHandler
from sawtooth_validator.journal.responder import ResponderBatchResponseHandler
from sawtooth_validator.journal.responder import \
    BatchByTransactionIdResponderHandler

from sawtooth_validator.gossip import signature_verifier

from sawtooth_validator.gossip.permission_verifier import \
    NetworkPermissionHandler
from sawtooth_validator.gossip.permission_verifier import \
    NetworkConsensusPermissionHandler

from sawtooth_validator.gossip.gossip_handlers import GossipConsensusHandler
from sawtooth_validator.gossip.gossip_handlers import GossipBroadcastHandler
from sawtooth_validator.gossip.gossip_handlers import \
    GossipMessageDuplicateHandler
from sawtooth_validator.gossip.gossip_handlers import \
    GossipBlockResponseHandler
from sawtooth_validator.gossip.gossip_handlers import \
    GossipBatchResponseHandler
from sawtooth_validator.gossip.gossip_handlers import \
    gossip_message_preprocessor
from sawtooth_validator.gossip.gossip_handlers import \
    gossip_batch_response_preprocessor
from sawtooth_validator.gossip.gossip_handlers import \
    gossip_block_response_preprocessor
from sawtooth_validator.gossip.gossip_handlers import PeerRegisterHandler
from sawtooth_validator.gossip.gossip_handlers import PeerUnregisterHandler
from sawtooth_validator.gossip.gossip_handlers import GetPeersRequestHandler
from sawtooth_validator.gossip.gossip_handlers import GetPeersResponseHandler
from sawtooth_validator.networking.dispatch import Priority
from sawtooth_validator.networking.handlers import PingHandler
from sawtooth_validator.networking.handlers import ConnectHandler
from sawtooth_validator.networking.handlers import DisconnectHandler
from sawtooth_validator.networking.handlers import \
    AuthorizationTrustRequestHandler
from sawtooth_validator.networking.handlers import \
    AuthorizationChallengeRequestHandler
from sawtooth_validator.networking.handlers import \
    AuthorizationChallengeSubmitHandler
from sawtooth_validator.networking.handlers import \
    AuthorizationViolationHandler

LOGGER = logging.getLogger(__name__)


def add(
        dispatcher,
        interconnect,
        gossip,
        completer,
        responder,
        thread_pool,
        sig_pool,
        has_block,
        has_batch,
        permission_verifier,
        block_publisher,
        consensus_notifier,
):

    # -- Basic Networking -- #
    dispatcher.add_handler(
        validator_pb2.Message.PING_REQUEST,
        PingHandler(network=interconnect),
        thread_pool,
        priority=Priority.HIGH)

    dispatcher.add_handler(
        validator_pb2.Message.NETWORK_CONNECT,
        ConnectHandler(network=interconnect),
        thread_pool)

    dispatcher.add_handler(
        validator_pb2.Message.NETWORK_DISCONNECT,
        DisconnectHandler(network=interconnect),
        thread_pool)

    # -- Authorization -- #
    dispatcher.set_message_priority(
        validator_pb2.Message.AUTHORIZATION_CONNECTION_RESPONSE,
        Priority.MEDIUM)

    dispatcher.add_handler(
        validator_pb2.Message.AUTHORIZATION_VIOLATION,
        AuthorizationViolationHandler(
            network=interconnect,
            gossip=gossip),
        thread_pool)

    dispatcher.add_handler(
        validator_pb2.Message.AUTHORIZATION_TRUST_REQUEST,
        AuthorizationTrustRequestHandler(
            network=interconnect,
            permission_verifier=permission_verifier,
            gossip=gossip),
        thread_pool,
        priority=Priority.MEDIUM)

    challenge_request_handler = AuthorizationChallengeRequestHandler(
        network=interconnect)
    dispatcher.add_handler(
        validator_pb2.Message.AUTHORIZATION_CHALLENGE_REQUEST,
        challenge_request_handler,
        thread_pool,
        priority=Priority.MEDIUM)

    dispatcher.add_handler(
        validator_pb2.Message.AUTHORIZATION_CHALLENGE_SUBMIT,
        AuthorizationChallengeSubmitHandler(
            network=interconnect,
            permission_verifier=permission_verifier,
            gossip=gossip,
            cache=challenge_request_handler.get_challenge_payload_cache()),
        thread_pool,
        priority=Priority.MEDIUM)

    # -- Gossip -- #
    dispatcher.add_handler(
        validator_pb2.Message.GOSSIP_GET_PEERS_REQUEST,
        NetworkPermissionHandler(
            network=interconnect,
            permission_verifier=permission_verifier,
            gossip=gossip
        ),
        thread_pool)

    dispatcher.add_handler(
        validator_pb2.Message.GOSSIP_GET_PEERS_REQUEST,
        GetPeersRequestHandler(gossip=gossip),
        thread_pool)

    dispatcher.set_message_priority(
        validator_pb2.Message.GOSSIP_GET_PEERS_REQUEST,
        Priority.MEDIUM)

    dispatcher.add_handler(
        validator_pb2.Message.GOSSIP_GET_PEERS_RESPONSE,
        NetworkPermissionHandler(
            network=interconnect,
            permission_verifier=permission_verifier,
            gossip=gossip
        ),
        thread_pool)

    dispatcher.add_handler(
        validator_pb2.Message.GOSSIP_GET_PEERS_RESPONSE,
        GetPeersResponseHandler(gossip=gossip),
        thread_pool)

    dispatcher.add_handler(
        validator_pb2.Message.GOSSIP_REGISTER,
        NetworkPermissionHandler(
            network=interconnect,
            permission_verifier=permission_verifier,
            gossip=gossip
        ),
        thread_pool)

    dispatcher.add_handler(
        validator_pb2.Message.GOSSIP_REGISTER,
        PeerRegisterHandler(gossip=gossip),
        thread_pool)

    dispatcher.set_message_priority(
        validator_pb2.Message.GOSSIP_REGISTER,
        Priority.MEDIUM)

    dispatcher.add_handler(
        validator_pb2.Message.GOSSIP_UNREGISTER,
        PeerUnregisterHandler(gossip=gossip),
        thread_pool)

    # GOSSIP_MESSAGE ) Check if this is a block and if we already have it

    dispatcher.set_preprocessor(
        validator_pb2.Message.GOSSIP_MESSAGE,
        gossip_message_preprocessor,
        thread_pool)

    dispatcher.add_handler(
        validator_pb2.Message.GOSSIP_MESSAGE,
        GossipMessageDuplicateHandler(completer, has_block, has_batch),
        thread_pool)

    # GOSSIP_MESSAGE ) Verify Network Permissions
    dispatcher.add_handler(
        validator_pb2.Message.GOSSIP_MESSAGE,
        NetworkPermissionHandler(
            network=interconnect,
            permission_verifier=permission_verifier,
            gossip=gossip
        ),
        thread_pool)

    # GOSSIP_MESSAGE ) Verifies signature
    dispatcher.add_handler(
        validator_pb2.Message.GOSSIP_MESSAGE,
        signature_verifier.GossipMessageSignatureVerifier(),
        sig_pool)

    # GOSSIP_MESSAGE ) Verifies batch structure
    dispatcher.add_handler(
        validator_pb2.Message.GOSSIP_MESSAGE,
        structure_verifier.GossipHandlerStructureVerifier(),
        thread_pool)

    # GOSSIP_MESSAGE ) Verifies that the node is allowed to publish a
    # block
    dispatcher.add_handler(
        validator_pb2.Message.GOSSIP_MESSAGE,
        NetworkConsensusPermissionHandler(
            network=interconnect,
            permission_verifier=permission_verifier,
            gossip=gossip
        ),
        thread_pool)

    # GOSSIP_MESSAGE ) Determines if this is a consensus message and notifies
    # the consensus engine if it is
    dispatcher.add_handler(
        validator_pb2.Message.GOSSIP_MESSAGE,
        GossipConsensusHandler(gossip=gossip, notifier=consensus_notifier),
        thread_pool)

    # GOSSIP_MESSAGE ) Determines if we should broadcast the
    # message to our peers. It is important that this occur prior
    # to the sending of the message to the completer, as this step
    # relies on whether the  gossip message has previously been
    # seen by the validator to determine whether or not forwarding
    # should occur
    dispatcher.add_handler(
        validator_pb2.Message.GOSSIP_MESSAGE,
        GossipBroadcastHandler(gossip=gossip, completer=completer),
        thread_pool)

    # GOSSIP_MESSAGE ) Send message to completer
    dispatcher.add_handler(
        validator_pb2.Message.GOSSIP_MESSAGE,
        CompleterGossipHandler(
            completer),
        thread_pool)

    dispatcher.add_handler(
        validator_pb2.Message.GOSSIP_BLOCK_REQUEST,
        NetworkPermissionHandler(
            network=interconnect,
            permission_verifier=permission_verifier,
            gossip=gossip
        ),
        thread_pool)

    dispatcher.add_handler(
        validator_pb2.Message.GOSSIP_BLOCK_REQUEST,
        BlockResponderHandler(responder, gossip),
        thread_pool)

    dispatcher.set_preprocessor(
        validator_pb2.Message.GOSSIP_BLOCK_RESPONSE,
        gossip_block_response_preprocessor,
        thread_pool)

    # GOSSIP_BLOCK_RESPONSE 1) Check for duplicate responses
    dispatcher.add_handler(
        validator_pb2.Message.GOSSIP_BLOCK_RESPONSE,
        GossipBlockResponseHandler(completer, responder, has_block),
        thread_pool)

    # GOSSIP_MESSAGE 2) Verify Network Permissions
    dispatcher.add_handler(
        validator_pb2.Message.GOSSIP_BLOCK_RESPONSE,
        NetworkPermissionHandler(
            network=interconnect,
            permission_verifier=permission_verifier,
            gossip=gossip
        ),
        thread_pool)

    # GOSSIP_BLOCK_RESPONSE 3) Verifies signature
    dispatcher.add_handler(
        validator_pb2.Message.GOSSIP_BLOCK_RESPONSE,
        signature_verifier.GossipBlockResponseSignatureVerifier(),
        sig_pool)

    # GOSSIP_BLOCK_RESPONSE 4) Check batch structure
    dispatcher.add_handler(
        validator_pb2.Message.GOSSIP_BLOCK_RESPONSE,
        structure_verifier.GossipBlockResponseStructureVerifier(),
        thread_pool)

    # GOSSIP_BLOCK_RESPONSE 5) Send message to completer
    dispatcher.add_handler(
        validator_pb2.Message.GOSSIP_BLOCK_RESPONSE,
        CompleterGossipBlockResponseHandler(
            completer),
        thread_pool)

    dispatcher.add_handler(
        validator_pb2.Message.GOSSIP_BLOCK_RESPONSE,
        ResponderBlockResponseHandler(responder, gossip),
        thread_pool)

    dispatcher.add_handler(
        validator_pb2.Message.GOSSIP_BATCH_BY_BATCH_ID_REQUEST,
        NetworkPermissionHandler(
            network=interconnect,
            permission_verifier=permission_verifier,
            gossip=gossip
        ),
        thread_pool)

    dispatcher.add_handler(
        validator_pb2.Message.GOSSIP_BATCH_BY_BATCH_ID_REQUEST,
        BatchByBatchIdResponderHandler(responder, gossip),
        thread_pool)

    dispatcher.add_handler(
        validator_pb2.Message.GOSSIP_BATCH_BY_TRANSACTION_ID_REQUEST,
        NetworkPermissionHandler(
            network=interconnect,
            permission_verifier=permission_verifier,
            gossip=gossip
        ),
        thread_pool)

    dispatcher.add_handler(
        validator_pb2.Message.GOSSIP_BATCH_BY_TRANSACTION_ID_REQUEST,
        BatchByTransactionIdResponderHandler(responder, gossip),
        thread_pool)

    dispatcher.add_handler(
        validator_pb2.Message.GOSSIP_BATCH_RESPONSE,
        NetworkPermissionHandler(
            network=interconnect,
            permission_verifier=permission_verifier,
            gossip=gossip
        ),
        thread_pool)

    dispatcher.set_preprocessor(
        validator_pb2.Message.GOSSIP_BATCH_RESPONSE,
        gossip_batch_response_preprocessor,
        thread_pool)

    # GOSSIP_BATCH_RESPONSE 1) Check for duplicate responses
    dispatcher.add_handler(
        validator_pb2.Message.GOSSIP_BATCH_RESPONSE,
        GossipBatchResponseHandler(completer, responder, has_batch),
        thread_pool)

    # GOSSIP_BATCH_RESPONSE 2) Verifies signature
    dispatcher.add_handler(
        validator_pb2.Message.GOSSIP_BATCH_RESPONSE,
        signature_verifier.GossipBatchResponseSignatureVerifier(),
        sig_pool)

    # GOSSIP_BATCH_RESPONSE 3) Check batch structure
    dispatcher.add_handler(
        validator_pb2.Message.GOSSIP_BATCH_RESPONSE,
        structure_verifier.GossipBatchResponseStructureVerifier(),
        thread_pool)

    # GOSSIP_BATCH_RESPONSE 4) Send message to completer
    dispatcher.add_handler(
        validator_pb2.Message.GOSSIP_BATCH_RESPONSE,
        CompleterGossipBatchResponseHandler(
            completer),
        thread_pool)

    dispatcher.add_handler(
        validator_pb2.Message.GOSSIP_BATCH_RESPONSE,
        ResponderBatchResponseHandler(responder, gossip),
        thread_pool)

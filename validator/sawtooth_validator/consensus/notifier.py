# Copyright 2018 Intel Corporation
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

import hashlib
import logging

from sawtooth_validator.protobuf import consensus_pb2
from sawtooth_validator.protobuf import validator_pb2

LOGGER = logging.getLogger(__name__)


class ConsensusNotifier:
    """Handles sending notifications to the consensus engine using the provided
    interconnect service."""

    def __init__(self, consensus_service, consensus_registry):
        self._service = consensus_service
        self._consensus_registry = consensus_registry

    def _notify(self, message_type, message):
        if self._consensus_registry:
            futures = self._service.send_all(
                message_type,
                message.SerializeToString())
            for future in futures:
                future.result()

    def notify_peer_connected(self, peer_id):
        """A new peer was added"""
        self._notify(
            validator_pb2.Message.CONSENSUS_NOTIFY_PEER_CONNECTED,
            consensus_pb2.ConsensusNotifyPeerConnected(
                peer_info=consensus_pb2.ConsensusPeerInfo(
                    peer_id=bytes.fromhex(peer_id))))

    def notify_peer_disconnected(self, peer_id):
        """An existing peer was dropped"""
        self._notify(
            validator_pb2.Message.CONSENSUS_NOTIFY_PEER_DISCONNECTED,
            consensus_pb2.ConsensusNotifyPeerDisconnected(
                peer_id=bytes.fromhex(peer_id)))

    def notify_peer_message(self, message, sender_id):
        """A new message was received from a peer"""
        self._notify(
            validator_pb2.Message.CONSENSUS_NOTIFY_PEER_MESSAGE,
            consensus_pb2.ConsensusNotifyPeerMessage(
                message=message,
                sender_id=sender_id))

    def notify_block_new(self, block):
        """A new block was received and passed initial consensus validation"""
        summary = hashlib.sha256()
        for batch in block.batches:
            summary.update(batch.header_signature.encode())
        self._notify(
            validator_pb2.Message.CONSENSUS_NOTIFY_BLOCK_NEW,
            consensus_pb2.ConsensusNotifyBlockNew(
                block=consensus_pb2.ConsensusBlock(
                    block_id=bytes.fromhex(block.identifier),
                    previous_id=bytes.fromhex(block.previous_block_id),
                    signer_id=bytes.fromhex(block.header.signer_public_key),
                    block_num=block.block_num,
                    payload=block.consensus,
                    summary=summary.digest())))

    def notify_block_valid(self, block_id):
        """This block can be committed successfully"""
        self._notify(
            validator_pb2.Message.CONSENSUS_NOTIFY_BLOCK_VALID,
            consensus_pb2.ConsensusNotifyBlockValid(
                block_id=bytes.fromhex(block_id)))

    def notify_block_invalid(self, block_id):
        """This block cannot be committed successfully"""
        self._notify(
            validator_pb2.Message.CONSENSUS_NOTIFY_BLOCK_INVALID,
            consensus_pb2.ConsensusNotifyBlockInvalid(
                block_id=bytes.fromhex(block_id)))

    def notify_block_commit(self, block_id):
        """This block has been committed"""
        self._notify(
            validator_pb2.Message.CONSENSUS_NOTIFY_BLOCK_COMMIT,
            consensus_pb2.ConsensusNotifyBlockCommit(
                block_id=bytes.fromhex(block_id)))

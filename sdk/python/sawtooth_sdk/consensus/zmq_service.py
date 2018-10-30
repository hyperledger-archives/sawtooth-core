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
# -----------------------------------------------------------------------------

from sawtooth_sdk.consensus.service import Service
from sawtooth_sdk.consensus.service import Block
from sawtooth_sdk.consensus import exceptions
from sawtooth_sdk.protobuf import consensus_pb2
from sawtooth_sdk.protobuf.validator_pb2 import Message


class ZmqService(Service):
    def __init__(self, stream, timeout):
        self._stream = stream
        self._timeout = timeout

    def _send(self, request, message_type, response_type):
        response_bytes = self._stream.send(
            message_type=message_type,
            content=request.SerializeToString(),
        ).result(self._timeout).content

        response = response_type()
        response.ParseFromString(response_bytes)

        return response

    # -- P2P --

    def send_to(self, receiver_id, message_type, payload):
        request = consensus_pb2.ConsensusSendToRequest(
            message_type=message_type,
            content=payload,
            receiver_id=receiver_id)

        response = self._send(
            request=request,
            message_type=Message.CONSENSUS_SEND_TO_REQUEST,
            response_type=consensus_pb2.ConsensusSendToResponse)

        if response.status != consensus_pb2.ConsensusSendToResponse.OK:
            raise exceptions.ReceiveError(
                'Failed with status {}'.format(response.status))

    def broadcast(self, message_type, payload):
        request = consensus_pb2.ConsensusBroadcastRequest(
            message_type=message_type,
            content=payload)

        response = self._send(
            request=request,
            message_type=Message.CONSENSUS_BROADCAST_REQUEST,
            response_type=consensus_pb2.ConsensusBroadcastResponse)

        if response.status != consensus_pb2.ConsensusBroadcastResponse.OK:
            raise exceptions.ReceiveError(
                'Failed with status {}'.format(response.status))

    # -- Block Creation --

    def initialize_block(self, previous_id=None):
        request = (
            consensus_pb2.ConsensusInitializeBlockRequest(
                previous_id=previous_id)
            if previous_id
            else consensus_pb2.ConsensusInitializeBlockRequest()
        )

        response_type = consensus_pb2.ConsensusInitializeBlockResponse

        response = self._send(
            request=request,
            message_type=Message.CONSENSUS_INITIALIZE_BLOCK_REQUEST,
            response_type=response_type)

        status = response.status

        if status == response_type.INVALID_STATE:
            raise exceptions.InvalidState(
                'Cannot initialize block in current state')

        if status == response_type.UNKNOWN_BLOCK:
            raise exceptions.UnknownBlock()

        if status != response_type.OK:
            raise exceptions.ReceiveError(
                'Failed with status {}'.format(status))

    def summarize_block(self):
        request = consensus_pb2.ConsensusSummarizeBlockRequest()

        response_type = consensus_pb2.ConsensusSummarizeBlockResponse

        response = self._send(
            request=request,
            message_type=Message.CONSENSUS_SUMMARIZE_BLOCK_REQUEST,
            response_type=response_type)

        status = response.status

        if status == response_type.INVALID_STATE:
            raise exceptions.InvalidState(
                'Cannot summarize block in current state')

        if status == response_type.BLOCK_NOT_READY:
            raise exceptions.BlockNotReady(
                'Block not ready to be summarize')

        if status != response_type.OK:
            raise exceptions.ReceiveError(
                'Failed with status {}'.format(status))

        return response.summary

    def finalize_block(self, data):
        request = consensus_pb2.ConsensusFinalizeBlockRequest(data=data)

        response_type = consensus_pb2.ConsensusFinalizeBlockResponse

        response = self._send(
            request=request,
            message_type=Message.CONSENSUS_FINALIZE_BLOCK_REQUEST,
            response_type=response_type)

        status = response.status

        if status == response_type.INVALID_STATE:
            raise exceptions.InvalidState(
                'Cannot finalize block in current state')

        if status == response_type.BLOCK_NOT_READY:
            raise exceptions.BlockNotReady(
                'Block not ready to be finalized')

        if status != response_type.OK:
            raise exceptions.ReceiveError(
                'Failed with status {}'.format(status))

        return response.block_id

    def cancel_block(self):
        request = consensus_pb2.ConsensusCancelBlockRequest()

        response_type = consensus_pb2.ConsensusCancelBlockResponse

        response = self._send(
            request=request,
            message_type=Message.CONSENSUS_CANCEL_BLOCK_REQUEST,
            response_type=response_type)

        status = response.status

        if status == response_type.INVALID_STATE:
            raise exceptions.InvalidState(
                'Cannot cancel block in current state')

        if status != response_type.OK:
            raise exceptions.ReceiveError(
                'Failed with status {}'.format(status))

    # -- Block Directives --

    def check_blocks(self, priority):
        request = consensus_pb2.ConsensusCheckBlocksRequest(block_ids=priority)

        response_type = consensus_pb2.ConsensusCheckBlocksResponse

        response = self._send(
            request=request,
            message_type=Message.CONSENSUS_CHECK_BLOCKS_REQUEST,
            response_type=response_type)

        status = response.status

        if status == response_type.UNKNOWN_BLOCK:
            raise exceptions.UnknownBlock()

        if status != response_type.OK:
            raise exceptions.ReceiveError(
                'Failed with status {}'.format(status))

    def commit_block(self, block_id):
        request = consensus_pb2.ConsensusCommitBlockRequest(block_id=block_id)

        response_type = consensus_pb2.ConsensusCommitBlockResponse

        response = self._send(
            request=request,
            message_type=Message.CONSENSUS_COMMIT_BLOCK_REQUEST,
            response_type=response_type)

        status = response.status

        if status == response_type.UNKNOWN_BLOCK:
            raise exceptions.UnknownBlock()

        if status != response_type.OK:
            raise exceptions.ReceiveError(
                'Failed with status {}'.format(status))

    def ignore_block(self, block_id):
        request = consensus_pb2.ConsensusIgnoreBlockRequest(block_id=block_id)

        response_type = consensus_pb2.ConsensusIgnoreBlockResponse

        response = self._send(
            request=request,
            message_type=Message.CONSENSUS_IGNORE_BLOCK_REQUEST,
            response_type=response_type)

        status = response.status

        if status == response_type.UNKNOWN_BLOCK:
            raise exceptions.UnknownBlock()

        if status != response_type.OK:
            raise exceptions.ReceiveError(
                'Failed with status {}'.format(status))

    def fail_block(self, block_id):
        request = consensus_pb2.ConsensusFailBlockRequest(block_id=block_id)

        response_type = consensus_pb2.ConsensusFailBlockResponse

        response = self._send(
            request=request,
            message_type=Message.CONSENSUS_FAIL_BLOCK_REQUEST,
            response_type=response_type)

        status = response.status

        if status == response_type.UNKNOWN_BLOCK:
            raise exceptions.UnknownBlock()

        if status != response_type.OK:
            raise exceptions.ReceiveError(
                'Failed with status {}'.format(status))

    # -- Queries --

    def get_blocks(self, block_ids):
        request = consensus_pb2.ConsensusBlocksGetRequest(block_ids=block_ids)

        response_type = consensus_pb2.ConsensusBlocksGetResponse

        response = self._send(
            request=request,
            message_type=Message.CONSENSUS_BLOCKS_GET_REQUEST,
            response_type=response_type)

        status = response.status

        if status == response_type.UNKNOWN_BLOCK:
            raise exceptions.UnknownBlock()

        if status != response_type.OK:
            raise exceptions.ReceiveError(
                'Failed with status {}'.format(status))

        return {
            block.block_id: Block(block)
            for block in response.blocks
        }

    def get_chain_head(self):
        request = consensus_pb2.ConsensusChainHeadGetRequest()

        response_type = consensus_pb2.ConsensusChainHeadGetResponse

        response = self._send(
            request=request,
            message_type=Message.CONSENSUS_CHAIN_HEAD_GET_REQUEST,
            response_type=response_type)

        status = response.status

        if status == response_type.NO_CHAIN_HEAD:
            raise exceptions.NoChainHead()

        if status != response_type.OK:
            raise exceptions.ReceiveError(
                'Failed with status {}'.format(status))

        return Block(response.block)

    def get_settings(self, block_id, settings):
        request = consensus_pb2.ConsensusSettingsGetRequest(
            block_id=block_id,
            keys=settings)

        response_type = consensus_pb2.ConsensusSettingsGetResponse

        response = self._send(
            request=request,
            message_type=Message.CONSENSUS_SETTINGS_GET_REQUEST,
            response_type=response_type)

        status = response.status

        if status == response_type.UNKNOWN_BLOCK:
            raise exceptions.UnknownBlock()

        if status != response_type.OK:
            raise exceptions.ReceiveError(
                'Failed with status {}'.format(status))

        return {
            entry.key: entry.value
            for entry in response.entries
        }

    def get_state(self, block_id, addresses):
        request = consensus_pb2.ConsensusStateGetRequest(
            block_id=block_id,
            addresses=addresses)

        response_type = consensus_pb2.ConsensusStateGetResponse

        response = self._send(
            request=request,
            message_type=Message.CONSENSUS_STATE_GET_REQUEST,
            response_type=response_type)

        status = response.status

        if status == response_type.UNKNOWN_BLOCK:
            raise exceptions.UnknownBlock()

        if status != response_type.OK:
            raise exceptions.ReceiveError(
                'Failed with status {}'.format(status))

        return {
            entry.address: entry.data
            for entry in response.entries
        }

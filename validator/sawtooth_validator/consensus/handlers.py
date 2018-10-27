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

from google.protobuf.message import DecodeError

from sawtooth_validator.consensus.proxy import UnknownBlock

from sawtooth_validator.protobuf import consensus_pb2
from sawtooth_validator.protobuf import validator_pb2

from sawtooth_validator.networking.dispatch import Handler
from sawtooth_validator.networking.dispatch import HandlerResult
from sawtooth_validator.networking.dispatch import HandlerStatus

from sawtooth_validator.journal.block_wrapper import BlockStatus
from sawtooth_validator.journal.publisher import BlockEmpty
from sawtooth_validator.journal.publisher import BlockInProgress
from sawtooth_validator.journal.publisher import BlockNotInitialized
from sawtooth_validator.journal.publisher import MissingPredecessor

from sawtooth_validator.protobuf.consensus_pb2 import ConsensusSettingsEntry
from sawtooth_validator.protobuf.consensus_pb2 import ConsensusStateEntry


LOGGER = logging.getLogger(__name__)


class ConsensusServiceHandler(Handler):
    def __init__(
        self,
        request_class,
        request_type,
        response_class,
        response_type,
    ):
        self._request_class = request_class
        self._request_type = request_type
        self._response_class = response_class
        self._response_type = response_type

    def handle_request(self, request, response, connection_id):
        raise NotImplementedError()

    @property
    def request_class(self):
        return self._request_class

    @property
    def response_class(self):
        return self._response_class

    @property
    def response_type(self):
        return self._response_type

    @property
    def request_type(self):
        return self._request_type

    def handle(self, connection_id, message_content):
        request = self._request_class()
        response = self._response_class()
        response.status = response.OK

        try:
            request.ParseFromString(message_content)
        except DecodeError:
            response.status = response.BAD_REQUEST
            handler_status = HandlerStatus.RETURN
        else:
            handler_status = self.handle_request(
                request, response, connection_id)

        return HandlerResult(
            status=handler_status,
            message_out=response,
            message_type=self._response_type)


class ConsensusRegisterHandler(ConsensusServiceHandler):
    def __init__(self, proxy):
        super().__init__(
            consensus_pb2.ConsensusRegisterRequest,
            validator_pb2.Message.CONSENSUS_REGISTER_REQUEST,
            consensus_pb2.ConsensusRegisterResponse,
            validator_pb2.Message.CONSENSUS_REGISTER_RESPONSE)

        self._proxy = proxy

    def handle_request(self, request, response, connection_id):
        startup_info = self._proxy.register(
            request.name, request.version, connection_id)

        if startup_info is None:
            response.status = consensus_pb2.ConsensusRegisterResponse.NOT_READY
            return HandlerStatus.RETURN

        chain_head = startup_info.chain_head
        peers = [bytes.fromhex(peer_id) for peer_id in startup_info.peers]
        local_peer_info = startup_info.local_peer_info

        response.chain_head.block_id = bytes.fromhex(chain_head.identifier)
        response.chain_head.previous_id =\
            bytes.fromhex(chain_head.previous_block_id)
        response.chain_head.signer_id =\
            bytes.fromhex(chain_head.signer_public_key)
        response.chain_head.block_num = chain_head.block_num
        response.chain_head.payload = chain_head.consensus

        response.peers.extend([
            consensus_pb2.ConsensusPeerInfo(peer_id=peer_id)
            for peer_id in peers
        ])

        response.local_peer_info.peer_id = local_peer_info

        LOGGER.info(
            "Consensus engine registered: %s %s",
            request.name,
            request.version)

        return HandlerStatus.RETURN_AND_PASS


class ConsensusRegisterBlockNewSyncHandler(Handler):
    def __init__(self, proxy, consensus_notifier):
        self._proxy = proxy
        self._consensus_notifier = consensus_notifier

    @property
    def request_type(self):
        return validator_pb2.Message.CONSENSUS_REGISTER_REQUEST

    def handle(self, connection_id, message_content):
        forks = self._proxy.forks()

        if not forks:
            return HandlerResult(status=HandlerStatus.PASS)

        for block in forks:
            self._consensus_notifier.notify_block_new(block)

        return HandlerResult(status=HandlerStatus.PASS)


class ConsensusSendToHandler(ConsensusServiceHandler):
    def __init__(self, proxy):
        super().__init__(
            consensus_pb2.ConsensusSendToRequest,
            validator_pb2.Message.CONSENSUS_SEND_TO_REQUEST,
            consensus_pb2.ConsensusSendToResponse,
            validator_pb2.Message.CONSENSUS_SEND_TO_RESPONSE)
        self._proxy = proxy

    def handle_request(self, request, response, connection_id):
        try:
            self._proxy.send_to(
                request.receiver_id,
                request.message_type,
                request.content,
                connection_id)
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception("ConsensusSendTo")
            response.status =\
                consensus_pb2.ConsensusSendToResponse.SERVICE_ERROR

        return HandlerStatus.RETURN


class ConsensusBroadcastHandler(ConsensusServiceHandler):
    def __init__(self, proxy):
        super().__init__(
            consensus_pb2.ConsensusBroadcastRequest,
            validator_pb2.Message.CONSENSUS_BROADCAST_REQUEST,
            consensus_pb2.ConsensusBroadcastResponse,
            validator_pb2.Message.CONSENSUS_BROADCAST_RESPONSE)

        self._proxy = proxy

    def handle_request(self, request, response, connection_id):
        try:
            self._proxy.broadcast(
                request.message_type,
                request.content,
                connection_id)
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception("ConsensusBroadcast")
            response.status =\
                consensus_pb2.ConsensusBroadcastResponse.SERVICE_ERROR

        return HandlerStatus.RETURN


class ConsensusInitializeBlockHandler(ConsensusServiceHandler):
    def __init__(self, proxy):
        super().__init__(
            consensus_pb2.ConsensusInitializeBlockRequest,
            validator_pb2.Message.CONSENSUS_INITIALIZE_BLOCK_REQUEST,
            consensus_pb2.ConsensusInitializeBlockResponse,
            validator_pb2.Message.CONSENSUS_INITIALIZE_BLOCK_RESPONSE)

        self._proxy = proxy

    def handle_request(self, request, response, connection_id):
        try:
            self._proxy.initialize_block(request.previous_id)
        except MissingPredecessor:
            response.status =\
                consensus_pb2.ConsensusInitializeBlockResponse.UNKNOWN_BLOCK
        except BlockInProgress:
            response.status =\
                consensus_pb2.ConsensusInitializeBlockResponse.INVALID_STATE
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception("ConsensusInitializeBlock")
            response.status =\
                consensus_pb2.ConsensusInitializeBlockResponse.SERVICE_ERROR

        return HandlerStatus.RETURN


class ConsensusSummarizeBlockHandler(ConsensusServiceHandler):
    def __init__(self, proxy):
        super().__init__(
            consensus_pb2.ConsensusSummarizeBlockRequest,
            validator_pb2.Message.CONSENSUS_SUMMARIZE_BLOCK_REQUEST,
            consensus_pb2.ConsensusSummarizeBlockResponse,
            validator_pb2.Message.CONSENSUS_SUMMARIZE_BLOCK_RESPONSE)

        self._proxy = proxy

    def handle_request(self, request, response, connection_id):
        try:
            summary = self._proxy.summarize_block()
            response.summary = summary
        except BlockNotInitialized:
            response.status =\
                consensus_pb2.ConsensusSummarizeBlockResponse.INVALID_STATE
        except BlockEmpty:
            response.status =\
                consensus_pb2.ConsensusSummarizeBlockResponse.BLOCK_NOT_READY
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception("ConsensusSummarizeBlock")
            response.status =\
                consensus_pb2.ConsensusSummarizeBlockResponse.SERVICE_ERROR

        return HandlerStatus.RETURN


class ConsensusFinalizeBlockHandler(ConsensusServiceHandler):
    def __init__(self, proxy):
        super().__init__(
            consensus_pb2.ConsensusFinalizeBlockRequest,
            validator_pb2.Message.CONSENSUS_FINALIZE_BLOCK_REQUEST,
            consensus_pb2.ConsensusFinalizeBlockResponse,
            validator_pb2.Message.CONSENSUS_FINALIZE_BLOCK_RESPONSE)

        self._proxy = proxy

    def handle_request(self, request, response, connection_id):
        try:
            response.block_id = self._proxy.finalize_block(request.data)
        except BlockNotInitialized:
            response.status =\
                consensus_pb2.ConsensusFinalizeBlockResponse.INVALID_STATE
        except BlockEmpty:
            response.status =\
                consensus_pb2.ConsensusFinalizeBlockResponse.BLOCK_NOT_READY
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception("ConsensusFinalizeBlock")
            response.status =\
                consensus_pb2.ConsensusFinalizeBlockResponse.SERVICE_ERROR

        return HandlerStatus.RETURN


class ConsensusCancelBlockHandler(ConsensusServiceHandler):
    def __init__(self, proxy):
        super().__init__(
            consensus_pb2.ConsensusCancelBlockRequest,
            validator_pb2.Message.CONSENSUS_CANCEL_BLOCK_REQUEST,
            consensus_pb2.ConsensusCancelBlockResponse,
            validator_pb2.Message.CONSENSUS_CANCEL_BLOCK_RESPONSE)

        self._proxy = proxy

    def handle_request(self, request, response, connection_id):
        try:
            self._proxy.cancel_block()
        except BlockNotInitialized:
            response.status =\
                consensus_pb2.ConsensusCancelBlockResponse.INVALID_STATE
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception("ConsensusCancelBlock")
            response.status =\
                consensus_pb2.ConsensusCancelBlockResponse.SERVICE_ERROR

        return HandlerStatus.RETURN


class ConsensusCheckBlocksHandler(ConsensusServiceHandler):
    def __init__(self, proxy):
        super().__init__(
            consensus_pb2.ConsensusCheckBlocksRequest,
            validator_pb2.Message.CONSENSUS_CHECK_BLOCKS_REQUEST,
            consensus_pb2.ConsensusCheckBlocksResponse,
            validator_pb2.Message.CONSENSUS_CHECK_BLOCKS_RESPONSE)

        self._proxy = proxy

    def handle_request(self, request, response, connection_id):
        try:
            self._proxy.check_blocks(request.block_ids)
        except UnknownBlock:
            response.status =\
                consensus_pb2.ConsensusCheckBlocksResponse.UNKNOWN_BLOCK
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception("ConsensusCheckBlocks")
            response.status =\
                consensus_pb2.ConsensusCheckBlocksResponse.SERVICE_ERROR

        return HandlerStatus.RETURN_AND_PASS


class ConsensusCheckBlocksNotifier(Handler):
    request_type = validator_pb2.Message.CONSENSUS_CHECK_BLOCKS_REQUEST

    def __init__(self, proxy, consensus_notifier):
        self._proxy = proxy
        self._consensus_notifier = consensus_notifier

    def handle(self, connection_id, message_content):
        request = consensus_pb2.ConsensusCheckBlocksRequest()

        try:
            request.ParseFromString(message_content)
        except DecodeError:
            LOGGER.exception("Unable to decode ConsensusCheckBlocksRequest")
            return HandlerResult(status=HandlerResult.DROP)

        block_statuses = self._proxy.get_block_statuses(request.block_ids)
        for (block_id, block_status) in block_statuses:
            if block_status == BlockStatus.Valid:
                self._consensus_notifier.notify_block_valid(block_id)
            elif block_status == BlockStatus.Invalid:
                self._consensus_notifier.notify_block_invalid(block_id)

        return HandlerResult(status=HandlerStatus.PASS)


class ConsensusCommitBlockHandler(ConsensusServiceHandler):
    def __init__(self, proxy):
        super().__init__(
            consensus_pb2.ConsensusCommitBlockRequest,
            validator_pb2.Message.CONSENSUS_COMMIT_BLOCK_REQUEST,
            consensus_pb2.ConsensusCommitBlockResponse,
            validator_pb2.Message.CONSENSUS_COMMIT_BLOCK_RESPONSE)

        self._proxy = proxy

    def handle_request(self, request, response, connection_id):
        try:
            self._proxy.commit_block(request.block_id)
        except UnknownBlock:
            response.status =\
                consensus_pb2.ConsensusCommitBlockResponse.UNKNOWN_BLOCK
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception("ConsensusCommitBlock")
            response.status =\
                consensus_pb2.ConsensusCommitBlockResponse.SERVICE_ERROR

        return HandlerStatus.RETURN


class ConsensusIgnoreBlockHandler(ConsensusServiceHandler):
    def __init__(self, proxy):
        super().__init__(
            consensus_pb2.ConsensusIgnoreBlockRequest,
            validator_pb2.Message.CONSENSUS_IGNORE_BLOCK_REQUEST,
            consensus_pb2.ConsensusIgnoreBlockResponse,
            validator_pb2.Message.CONSENSUS_IGNORE_BLOCK_RESPONSE)

        self._proxy = proxy

    def handle_request(self, request, response, connection_id):
        try:
            self._proxy.ignore_block(request.block_id)
        except UnknownBlock:
            response.status =\
                consensus_pb2.ConsensusIgnoreBlockResponse.UNKNOWN_BLOCK
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception("ConsensusIgnoreBlock")
            response.status =\
                consensus_pb2.ConsensusIgnoreBlockResponse.SERVICE_ERROR

        return HandlerStatus.RETURN


class ConsensusFailBlockHandler(ConsensusServiceHandler):
    def __init__(self, proxy):
        super().__init__(
            consensus_pb2.ConsensusFailBlockRequest,
            validator_pb2.Message.CONSENSUS_FAIL_BLOCK_REQUEST,
            consensus_pb2.ConsensusFailBlockResponse,
            validator_pb2.Message.CONSENSUS_FAIL_BLOCK_RESPONSE)

        self._proxy = proxy

    def handle_request(self, request, response, connection_id):
        try:
            self._proxy.fail_block(request.block_id)
        except UnknownBlock:
            response.status =\
                consensus_pb2.ConsensusFailBlockResponse.UNKNOWN_BLOCK
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception("ConsensusFailBlock")
            response.status =\
                consensus_pb2.ConsensusFailBlockResponse.SERVICE_ERROR

        return HandlerStatus.RETURN


class ConsensusBlocksGetHandler(ConsensusServiceHandler):
    def __init__(self, proxy):
        super().__init__(
            consensus_pb2.ConsensusBlocksGetRequest,
            validator_pb2.Message.CONSENSUS_BLOCKS_GET_REQUEST,
            consensus_pb2.ConsensusBlocksGetResponse,
            validator_pb2.Message.CONSENSUS_BLOCKS_GET_RESPONSE)

        self._proxy = proxy

    def handle_request(self, request, response, connection_id):
        try:
            response.blocks.extend([
                consensus_pb2.ConsensusBlock(
                    block_id=bytes.fromhex(block.identifier),
                    previous_id=bytes.fromhex(block.previous_block_id),
                    signer_id=bytes.fromhex(block.signer_public_key),
                    block_num=block.block_num,
                    payload=block.consensus)
                for block in self._proxy.blocks_get(request.block_ids)
            ])
        except UnknownBlock:
            response.status =\
                consensus_pb2.ConsensusBlocksGetResponse.UNKNOWN_BLOCK
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception("ConsensusBlocksGet")
            response.status =\
                consensus_pb2.ConsensusBlocksGetResponse.SERVICE_ERROR

        return HandlerStatus.RETURN


class ConsensusChainHeadGetHandler(ConsensusServiceHandler):
    def __init__(self, proxy):
        super().__init__(
            consensus_pb2.ConsensusChainHeadGetRequest,
            validator_pb2.Message.CONSENSUS_CHAIN_HEAD_GET_REQUEST,
            consensus_pb2.ConsensusChainHeadGetResponse,
            validator_pb2.Message.CONSENSUS_CHAIN_HEAD_GET_RESPONSE)

        self._proxy = proxy

    def handle_request(self, request, response, connection_id):
        try:
            chain_head = self._proxy.chain_head_get()
            response.block.block_id = bytes.fromhex(chain_head.identifier)
            response.block.previous_id =\
                bytes.fromhex(chain_head.previous_block_id)
            response.block.signer_id =\
                bytes.fromhex(chain_head.signer_public_key)
            response.block.block_num = chain_head.block_num
            response.block.payload = chain_head.consensus
        except UnknownBlock:
            response.status =\
                consensus_pb2.ConsensusChainHeadGetResponse.NO_CHAIN_HEAD
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception("ConsensusChainHeadGet")
            response.status =\
                consensus_pb2.ConsensusChainHeadGetResponse.SERVICE_ERROR

        return HandlerStatus.RETURN


class ConsensusSettingsGetHandler(ConsensusServiceHandler):
    def __init__(self, proxy):
        super().__init__(
            consensus_pb2.ConsensusSettingsGetRequest,
            validator_pb2.Message.CONSENSUS_SETTINGS_GET_REQUEST,
            consensus_pb2.ConsensusSettingsGetResponse,
            validator_pb2.Message.CONSENSUS_SETTINGS_GET_RESPONSE)

        self._proxy = proxy

    def handle_request(self, request, response, connection_id):
        try:
            response.entries.extend([
                ConsensusSettingsEntry(
                    key=key,
                    value=value)
                for key, value in self._proxy.settings_get(
                    request.block_id, request.keys)
            ])
        except UnknownBlock:
            response.status = \
                consensus_pb2.ConsensusSettingsGetResponse.UNKNOWN_BLOCK
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception("ConsensusSettingsGet")
            response.status =\
                consensus_pb2.ConsensusSettingsGetResponse.SERVICE_ERROR

        return HandlerStatus.RETURN


class ConsensusStateGetHandler(ConsensusServiceHandler):
    def __init__(self, proxy):
        super().__init__(
            consensus_pb2.ConsensusStateGetRequest,
            validator_pb2.Message.CONSENSUS_STATE_GET_REQUEST,
            consensus_pb2.ConsensusStateGetResponse,
            validator_pb2.Message.CONSENSUS_STATE_GET_RESPONSE)

        self._proxy = proxy

    def handle_request(self, request, response, connection_id):
        try:
            response.entries.extend([
                ConsensusStateEntry(
                    address=address,
                    data=data)
                for address, data in self._proxy.state_get(
                    request.block_id, request.addresses)
            ])
        except UnknownBlock:
            response.status = \
                consensus_pb2.ConsensusStateGetResponse.UNKNOWN_BLOCK
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception("ConsensusStateGet")
            response.status =\
                consensus_pb2.ConsensusStateGetResponse.SERVICE_ERROR

        return HandlerStatus.RETURN

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

from sawtooth_validator.protobuf.block_pb2 import BlockHeader
from sawtooth_validator.protobuf.consensus_pb2 import ConsensusSettingsEntry
from sawtooth_validator.protobuf.consensus_pb2 import ConsensusStateEntry


LOGGER = logging.getLogger(__name__)


class ConsensusServiceHandler(Handler):
    def __init__(
        self,
        request_class,
        request_type,
        response_class,
        response_type
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

        if not (
            self._request_type
                == validator_pb2.Message.CONSENSUS_REGISTER_REQUEST
                or self._proxy.is_active_engine_id(connection_id)
        ):
            response.status = response.NOT_ACTIVE_ENGINE
            return HandlerResult(
                status=HandlerStatus.RETURN,
                message_out=response,
                message_type=self._response_type)

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
        if request.additional_protocols is not None:
            additional_protocols = \
                [(p.name, p.version) for p in request.additional_protocols]
        else:
            additional_protocols = []

        self._proxy.register(
            request.name, request.version, additional_protocols, connection_id)

        LOGGER.info(
            "Consensus engine registered: %s %s (additional protocols: %s)",
            request.name,
            request.version,
            request.additional_protocols)

        return HandlerStatus.RETURN_AND_PASS


class ConsensusRegisterActivateHandler(Handler):
    def __init__(self, proxy):
        self._proxy = proxy
        self._request_type = validator_pb2.Message.CONSENSUS_REGISTER_REQUEST

    @property
    def request_type(self):
        return self._request_type

    def handle(self, connection_id, message_content):
        # If this is the configured consensus engine, make it active. This is
        # necessary for setting the active engine when the configured engine is
        # changed to an engine that is not registered yet
        request = consensus_pb2.ConsensusRegisterRequest()

        try:
            request.ParseFromString(message_content)
        except DecodeError:
            LOGGER.exception("Unable to decode ConsensusRegisterRequest")
            return HandlerResult(status=HandlerResult.DROP)

        if request.additional_protocols is not None:
            additional_protocols = \
                [(p.name, p.version) for p in request.additional_protocols]
        else:
            additional_protocols = []

        self._proxy.activate_if_configured(
            request.name, request.version, additional_protocols)

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
    def __init__(self, proxy, consensus_notifier):
        self._proxy = proxy
        self._consensus_notifier = consensus_notifier
        self._request_type = \
            validator_pb2.Message.CONSENSUS_CHECK_BLOCKS_REQUEST

    @property
    def request_type(self):
        return self._request_type

    def handle(self, connection_id, message_content):
        # No need to verify this is a valid consensus engine; previous handler
        # ConsensusCheckBlocksHandler has already verifified
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
            elif block_status == BlockStatus.Unknown:
                # No need to worry about unknown block, this is checked in the
                # previous handler.
                self._proxy.validate_block(block_id)
            elif block_status == BlockStatus.Missing:
                LOGGER.error("Missing block: %s", block_id)
            elif block_status == BlockStatus.InValidation:
                # Block is already being validated, notification will be sent
                # when it's complete
                pass

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
            blocks = []
            for block in self._proxy.blocks_get(request.block_ids):
                block_header = BlockHeader()
                block_header.ParseFromString(block.header)

                blocks.append(consensus_pb2.ConsensusBlock(
                    block_id=bytes.fromhex(block.header_signature),
                    previous_id=bytes.fromhex(block_header.previous_block_id),
                    signer_id=bytes.fromhex(block_header.signer_public_key),
                    block_num=block_header.block_num,
                    payload=block_header.consensus))
            response.blocks.extend(blocks)
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

            block_header = BlockHeader()
            block_header.ParseFromString(chain_head.header)

            response.block.block_id = bytes.fromhex(
                chain_head.header_signature)
            response.block.previous_id =\
                bytes.fromhex(block_header.previous_block_id)
            response.block.signer_id =\
                bytes.fromhex(block_header.signer_public_key)
            response.block.block_num = block_header.block_num
            response.block.payload = block_header.consensus
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

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

from sawtooth_validator.protobuf import consensus_pb2
from sawtooth_validator.protobuf import validator_pb2

from sawtooth_validator.networking.dispatch import Handler
from sawtooth_validator.networking.dispatch import HandlerResult
from sawtooth_validator.networking.dispatch import HandlerStatus

from sawtooth_validator.journal.publisher_ce import BlockEmpty
from sawtooth_validator.journal.publisher_ce import BlockInProgress
from sawtooth_validator.journal.publisher_ce import BlockNotInitialized


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

    def handle_request(self, request, response):
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
        else:
            self.handle_request(request, response)

        return HandlerResult(
            status=HandlerStatus.RETURN,
            message_out=response,
            message_type=self._response_type)


class ConsensusRegisterHandler(ConsensusServiceHandler):
    def __init__(self):
        super().__init__(
            consensus_pb2.ConsensusRegisterRequest,
            validator_pb2.Message.CONSENSUS_REGISTER_REQUEST,
            consensus_pb2.ConsensusRegisterResponse,
            validator_pb2.Message.CONSENSUS_REGISTER_RESPONSE)

    def handle_request(self, request, response):
        LOGGER.info(
            "Consensus engine registered: %s %s",
            request.name,
            request.version)


class ConsensusSendToHandler(ConsensusServiceHandler):
    def __init__(self, proxy):
        super().__init__(
            consensus_pb2.ConsensusSendToRequest,
            validator_pb2.Message.CONSENSUS_SEND_TO_REQUEST,
            consensus_pb2.ConsensusSendToResponse,
            validator_pb2.Message.CONSENSUS_SEND_TO_RESPONSE)
        self._proxy = proxy

    def handle_request(self, request, response):
        self._proxy.send_to(request.peer_id, request.message)


class ConsensusBroadcastHandler(ConsensusServiceHandler):
    def __init__(self, proxy):
        super().__init__(
            consensus_pb2.ConsensusBroadcastRequest,
            validator_pb2.Message.CONSENSUS_BROADCAST_REQUEST,
            consensus_pb2.ConsensusBroadcastResponse,
            validator_pb2.Message.CONSENSUS_BROADCAST_RESPONSE)

        self._proxy = proxy

    def handle_request(self, request, response):
        self._proxy.broadcast(request.message)


class ConsensusInitializeBlockHandler(ConsensusServiceHandler):
    def __init__(self, proxy):
        super().__init__(
            consensus_pb2.ConsensusInitializeBlockRequest,
            validator_pb2.Message.CONSENSUS_INITIALIZE_BLOCK_REQUEST,
            consensus_pb2.ConsensusInitializeBlockResponse,
            validator_pb2.Message.CONSENSUS_INITIALIZE_BLOCK_RESPONSE)

        self._proxy = proxy

    def handle_request(self, request, response):
        try:
            self._proxy.initialize_block(request.previous_id)
        except BlockInProgress:
            response.status =\
                consensus_pb2.ConsensusInitializeBlockResponse.INVALID_STATE
        except Exception:  # pylint: disable=broad-except
            response.status =\
                consensus_pb2.ConsensusInitializeBlockResponse.SERVICE_ERROR


class ConsensusFinalizeBlockHandler(ConsensusServiceHandler):
    def __init__(self, proxy):
        super().__init__(
            consensus_pb2.ConsensusFinalizeBlockRequest,
            validator_pb2.Message.CONSENSUS_FINALIZE_BLOCK_REQUEST,
            consensus_pb2.ConsensusFinalizeBlockResponse,
            validator_pb2.Message.CONSENSUS_FINALIZE_BLOCK_RESPONSE)

        self._proxy = proxy

    def handle_request(self, request, response):
        try:
            self._proxy.finalize_block(request.data)
        except KeyError:
            response.status =\
                consensus_pb2.ConsensusFinalizeBlockResponse.UNKNOWN_BLOCK
        except BlockNotInitialized:
            response.status =\
                consensus_pb2.ConsensusFinalizeBlockResponse.INVALID_STATE
        except BlockEmpty:
            response.status =\
                consensus_pb2.ConsensusFinalizeBlockResponse.BLOCK_NOT_READY
        except Exception:  # pylint: disable=broad-except
            response.status =\
                consensus_pb2.ConsensusFinalizeBlockResponse.SERVICE_ERROR


class ConsensusCancelBlockHandler(ConsensusServiceHandler):
    def __init__(self, proxy):
        super().__init__(
            consensus_pb2.ConsensusCancelBlockRequest,
            validator_pb2.Message.CONSENSUS_CANCEL_BLOCK_REQUEST,
            consensus_pb2.ConsensusCancelBlockResponse,
            validator_pb2.Message.CONSENSUS_CANCEL_BLOCK_RESPONSE)

        self._proxy = proxy

    def handle_request(self, request, response):
        try:
            self._proxy.cancel_block()
        except BlockNotInitialized:
            response.status =\
                consensus_pb2.ConsensusCancelBlockResponse.INVALID_STATE
        except Exception:  # pylint: disable=broad-except
            response.status =\
                consensus_pb2.ConsensusCancelBlockResponse.SERVICE_ERROR


class ConsensusCheckBlockHandler(ConsensusServiceHandler):
    def __init__(self, proxy):
        super().__init__(
            consensus_pb2.ConsensusCheckBlockRequest,
            validator_pb2.Message.CONSENSUS_CHECK_BLOCK_REQUEST,
            consensus_pb2.ConsensusCheckBlockResponse,
            validator_pb2.Message.CONSENSUS_CHECK_BLOCK_RESPONSE)

        self._proxy = proxy

    def handle_request(self, request, response):
        self._proxy.check_block(request.block_ids)


class ConsensusCommitBlockHandler(ConsensusServiceHandler):
    def __init__(self, proxy):
        super().__init__(
            consensus_pb2.ConsensusCommitBlockRequest,
            validator_pb2.Message.CONSENSUS_COMMIT_BLOCK_REQUEST,
            consensus_pb2.ConsensusCommitBlockResponse,
            validator_pb2.Message.CONSENSUS_COMMIT_BLOCK_RESPONSE)

        self._proxy = proxy

    def handle_request(self, request, response):
        self._proxy.commit_block(request.block_id)


class ConsensusIgnoreBlockHandler(ConsensusServiceHandler):
    def __init__(self, proxy):
        super().__init__(
            consensus_pb2.ConsensusIgnoreBlockRequest,
            validator_pb2.Message.CONSENSUS_IGNORE_BLOCK_REQUEST,
            consensus_pb2.ConsensusIgnoreBlockResponse,
            validator_pb2.Message.CONSENSUS_IGNORE_BLOCK_RESPONSE)

        self._proxy = proxy

    def handle_request(self, request, response):
        self._proxy.ignore_block(request.block_id)


class ConsensusFailBlockHandler(ConsensusServiceHandler):
    def __init__(self, proxy):
        super().__init__(
            consensus_pb2.ConsensusFailBlockRequest,
            validator_pb2.Message.CONSENSUS_FAIL_BLOCK_REQUEST,
            consensus_pb2.ConsensusFailBlockResponse,
            validator_pb2.Message.CONSENSUS_FAIL_BLOCK_RESPONSE)

        self._proxy = proxy

    def handle_request(self, request, response):
        self._proxy.fail_block(request.block_id)


class ConsensusBlocksGetHandler(ConsensusServiceHandler):
    def __init__(self, proxy):
        super().__init__(
            consensus_pb2.ConsensusBlocksGetRequest,
            validator_pb2.Message.CONSENSUS_BLOCKS_GET_REQUEST,
            consensus_pb2.ConsensusBlocksGetResponse,
            validator_pb2.Message.CONSENSUS_BLOCKS_GET_RESPONSE)

        self._proxy = proxy

    def handle_request(self, request, response):
        self._proxy.blocks_get(request.block_ids)


class ConsensusSettingsGetHandler(ConsensusServiceHandler):
    def __init__(self, proxy):
        super().__init__(
            consensus_pb2.ConsensusSettingsGetRequest,
            validator_pb2.Message.CONSENSUS_SETTINGS_GET_REQUEST,
            consensus_pb2.ConsensusSettingsGetResponse,
            validator_pb2.Message.CONSENSUS_SETTINGS_GET_RESPONSE)

        self._proxy = proxy

    def handle_request(self, request, response):
        self._proxy.settings_get(request.block_id, request.keys)


class ConsensusStateGetHandler(ConsensusServiceHandler):
    def __init__(self, proxy):
        super().__init__(
            consensus_pb2.ConsensusStateGetRequest,
            validator_pb2.Message.CONSENSUS_STATE_GET_REQUEST,
            consensus_pb2.ConsensusStateGetResponse,
            validator_pb2.Message.CONSENSUS_STATE_GET_RESPONSE)

        self._proxy = proxy

    def handle_request(self, request, response):
        self._proxy.state_get(request.block_id, request.addresses)

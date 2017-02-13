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
# pylint: disable=import-error,no-name-in-module
# needed for google.protobuf import
from google.protobuf.message import DecodeError

from sawtooth_validator.state.merkle import MerkleDatabase
from sawtooth_validator.networking.dispatch import Handler
from sawtooth_validator.networking.dispatch import HandlerResult
from sawtooth_validator.networking.dispatch import HandlerStatus

from sawtooth_validator.protobuf import client_pb2
from sawtooth_validator.protobuf.block_pb2 import BlockHeader
from sawtooth_validator.protobuf import validator_pb2


LOGGER = logging.getLogger(__name__)


class _ClientHandler(Handler):
    """
    Base Client Handler, with some useful helper methods to standardize
    building results, and setting up the merkle tree.

    "Try" methods may fail, and will return an enum status in that case.
    This can be checked for with _is_status.

    Args:
        request_proto - protobuf class for the request
        response_proto - protobuf class for the response
        result_type - the Message enum for the response
    """
    def __init__(self, request_proto, response_proto, result_type):
        self._request_proto = request_proto
        self._response_proto = response_proto
        self._result_type = result_type

    def _init_result(self):
        return HandlerResult(
            status=HandlerStatus.RETURN,
            message_type=self._result_type)

    def _finish_result(self, result, status, **kwargs):
        result.message_out = self._response_proto(status=status, **kwargs)
        return result

    def _try_parse_request(self, content):
        try:
            request = self._request_proto()
            request.ParseFromString(content)
        except DecodeError:
            LOGGER.info('Protobuf %s failed to deserialize', request)
            return self._response_proto.INTERNAL_ERROR

        return request

    def _is_status(self, obj):
        return type(obj) == int

    def _set_root(self, request):
        """
        Used by handlers that fetch data from the merkle tree. Sets the tree
        with the proper root.
        """
        assert hasattr(self, '_tree'), '_set_root missing _tree attribute'
        self._tree.set_merkle_root(request.merkle_root)


class StateCurrentRequest(_ClientHandler):
    def __init__(self, current_root_func):
        self._current_root_func = current_root_func
        super().__init__(
            client_pb2.ClientStateCurrentRequest,
            client_pb2.ClientStateCurrentResponse,
            validator_pb2.Message.CLIENT_STATE_CURRENT_RESPONSE)

    def handle(self, identity, message_content):
        result = self._init_result()

        request = self._try_parse_request(message_content)
        if self._is_status(request):
            return self._finish_result(result, request)

        return self._finish_result(
            result,
            self._response_proto.OK,
            merkle_root=self._current_root_func())


class StateListRequest(_ClientHandler):
    def __init__(self, database, block_store):
        self._tree = MerkleDatabase(database)
        self._block_store = block_store
        super().__init__(
            client_pb2.ClientStateListRequest,
            client_pb2.ClientStateListResponse,
            validator_pb2.Message.CLIENT_STATE_LIST_RESPONSE)

    def handle(self, identity, message_content):
        result = self._init_result()

        request = self._try_parse_request(message_content)
        if self._is_status(request):
            return self._finish_result(result, request)

        self._set_root(request)

        # Fetch leaves and encode as protobuf
        leaves = [
            client_pb2.Leaf(address=a, data=v) for a, v in \
            self._tree.leaves(request.address or '').items()]

        if not leaves:
            return self._finish_result(
                result,
                self._response_proto.NO_RESOURCE,
                head_id=head_id)

        return self._finish_result(
            result,
            self._response_proto.OK,
            head_id=head_id,
            leaves=leaves)


class StateGetRequest(_ClientHandler):
    def __init__(self, database, block_store):
        self._tree = MerkleDatabase(database)
        self._block_store = block_store
        super().__init__(
            client_pb2.ClientStateGetRequest,
            client_pb2.ClientStateGetResponse,
            validator_pb2.Message.CLIENT_STATE_GET_RESPONSE)

    def handle(self, identity, message_content):
        result = self._init_result()

        request = self._try_parse_request(message_content)
        if self._is_status(request):
            return self._finish_result(result, request)

        self._set_root(request)

        # Fetch leaf value
        value = None
        address = request.address
        try:
            value = self._tree.get(address)
        except KeyError:
            LOGGER.debug('Unable to find entry at address %s', address)
            return self._finish_result(
                result,
                self._response_proto.NO_RESOURCE)
        except ValueError as e:
            LOGGER.debug('Address %s is a nonleaf', address)
            LOGGER.debug(e)
            return self._finish_result(
                result,
                self._response_proto.INVALID_ADDRESS)

        return self._finish_result(
            result,
            self._response_proto.OK,
            value=value)


class BlockListRequest(_ClientHandler):
    def __init__(self, block_store):
        self._block_store = block_store
        super().__init__(
            client_pb2.ClientBlockListRequest,
            client_pb2.ClientBlockListResponse,
            validator_pb2.Message.CLIENT_BLOCK_LIST_RESPONSE)

    def handle(self, identity, message_content):
        result = self._init_result()

        request = self._try_parse_request(message_content)
        if self._is_status(request):
            return self._finish_result(result, request)

        if not self._block_store.chain_head:
            LOGGER.debug('Unable to get chain head from block store')
            return self._finish_result(result, self._response_proto.NO_GENESIS)

        current_id = self._block_store.chain_head.header_signature
        blocks = []

        # Build block list
        while current_id in self._block_store:
            block = self._block_store[current_id].block
            blocks.append(block)
            header = BlockHeader()
            header.ParseFromString(block.header)
            current_id = header.previous_block_id

        if not blocks:
            return self._finish_result(result, self._response_proto.NO_ROOT)

        return self._finish_result(
            result,
            self._response_proto.OK,
            blocks=blocks)


class BlockGetRequest(_ClientHandler):
    def __init__(self, block_store):
        self._block_store = block_store
        super().__init__(
            client_pb2.ClientBlockGetRequest,
            client_pb2.ClientBlockGetResponse,
            validator_pb2.Message.CLIENT_BLOCK_GET_RESPONSE)

    def handle(self, identity, message_content):
        result = self._init_result()

        request = self._try_parse_request(message_content)
        if self._is_status(request):
            return self._finish_result(result, request)

        block_id = request.block_id

        if block_id not in self._block_store:
            LOGGER.debug('Unable to find block "%s" in store', block_id)
            return self._finish_result(
                result,
                self._response_proto.NO_RESOURCE)

        return self._finish_result(
            result,
            self._response_proto.OK,
            block=self._block_store[block_id].block)

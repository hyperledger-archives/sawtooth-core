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


class StateCurrentRequest(Handler):
    def __init__(self, current_root_func):
        self._current_root_func = current_root_func

    def handle(self, identity, message_content):
        helper = _ClientHelper(
            message_content,
            client_pb2.ClientStateCurrentRequest,
            client_pb2.ClientStateCurrentResponse,
            validator_pb2.Message.CLIENT_STATE_CURRENT_RESPONSE)

        if not helper.has_response():
            helper.set_response(
                helper.status.OK,
                merkle_root=self._current_root_func())

        return helper.result


class StateListRequest(Handler):
    def __init__(self, database, block_store):
        self._tree = MerkleDatabase(database)
        self._block_store = block_store

    def handle(self, identity, message_content):
        helper = _ClientHelper(
            message_content,
            client_pb2.ClientStateListRequest,
            client_pb2.ClientStateListResponse,
            validator_pb2.Message.CLIENT_STATE_LIST_RESPONSE,
            tree=self._tree,
            block_store=self._block_store)

        helper.set_root()
        if helper.has_response():
            return helper.result

        # Fetch leaves and encode as protobuf
        leaves = [
            client_pb2.Leaf(address=a, data=v) for a, v in
            self._tree.leaves(helper.request.address or '').items()]

        if leaves:
            helper.set_response(
                helper.status.OK,
                head_id=helper.head_id,
                leaves=leaves)
        else:
            helper.set_response(
                helper.status.NO_RESOURCE,
                head_id=helper.head_id)

        return helper.result


class StateGetRequest(Handler):
    def __init__(self, database, block_store):
        self._tree = MerkleDatabase(database)
        self._block_store = block_store

    def handle(self, identity, message_content):
        helper = _ClientHelper(
            message_content,
            client_pb2.ClientStateGetRequest,
            client_pb2.ClientStateGetResponse,
            validator_pb2.Message.CLIENT_STATE_GET_RESPONSE,
            tree=self._tree,
            block_store=self._block_store)

        helper.set_root()
        if helper.has_response():
            return helper.result

        # Fetch leaf value
        address = helper.request.address
        try:
            value = self._tree.get(address)
        except KeyError:
            LOGGER.debug('Unable to find entry at address %s', address)
            helper.set_response(helper.status.NO_RESOURCE)
        except ValueError as e:
            LOGGER.debug('Address %s is a nonleaf', address)
            LOGGER.debug(e)
            helper.set_response(helper.status.MISSING_ADDRESS)

        if not helper.has_response():
            helper.set_response(
                helper.status.OK,
                head_id=helper.head_id,
                value=value)

        return helper.result


class BlockListRequest(Handler):
    def __init__(self, block_store):
        self._block_store = block_store

    def handle(self, identity, message_content):
        helper = _ClientHelper(
            message_content,
            client_pb2.ClientBlockListRequest,
            client_pb2.ClientBlockListResponse,
            validator_pb2.Message.CLIENT_BLOCK_LIST_RESPONSE,
            block_store=self._block_store)

        blocks = [helper.get_head_block()]
        if helper.has_response():
            return helper.result

        # Build block list
        while True:
            header = BlockHeader()
            header.ParseFromString(blocks[-1].header)
            previous_id = header.previous_block_id
            if previous_id not in self._block_store:
                break
            blocks.append(self._block_store[previous_id].block)

        helper.set_response(
            helper.status.OK,
            head_id=helper.head_id,
            blocks=blocks)

        return helper.result


class BlockGetRequest(Handler):
    def __init__(self, block_store):
        self._block_store = block_store

    def handle(self, identity, message_content):
        helper = _ClientHelper(
            message_content,
            client_pb2.ClientBlockGetRequest,
            client_pb2.ClientBlockGetResponse,
            validator_pb2.Message.CLIENT_BLOCK_GET_RESPONSE)

        if helper.has_response():
            return helper.result

        block_id = helper.request.block_id
        if block_id in self._block_store:
            helper.set_response(
                helper.status.OK,
                block=self._block_store[block_id].block)
        else:
            LOGGER.debug('Unable to find block "%s" in store', block_id)
            helper.set_response(helper.status.NO_RESOURCE)

        return helper.result


class _ClientHelper(object):
    """
    Utility class for Client Handlers that simplifies message handling by
    providing a response that can be set only once, and a single source
    of frequently used methods.

    Args:
        handler - the Client Handler using the helper
        content - the message_content being handled
        req_proto - protobuf class for the request
        resp_proto - protobuf class for the response
        result_type - the Message enum for the response
    """
    def __init__(self, content, req_proto, resp_proto, result_type,
                 tree=None, block_store=None):
        self._tree = tree
        self._block_store = block_store
        self._resp_proto = resp_proto
        self.status = resp_proto
        self.head_id = None

        self.result = HandlerResult(
            status=HandlerStatus.RETURN,
            message_type=result_type)

        try:
            self.request = req_proto()
            self.request.ParseFromString(content)
        except DecodeError:
            LOGGER.info('Protobuf %s failed to deserialize', self.request)
            self.set_response(self.status.INTERNAL_ERROR)

    def has_response(self):
        return self.result.message_out is not None

    def set_response(self, status, **kwargs):
        if not self.has_response():
            self.result.message_out = self._resp_proto(status=status, **kwargs)

    def get_head_block(self):
        """
        Sets the helper's 'head_id' property, and returns the head block.
        Uses either a specified head id or the current chain head.
        """
        if self.has_response():
            return

        if self.request.head_id:
            self.head_id = self.request.head_id
            try:
                return self._block_store[self.request.head_id].block
            except KeyError as e:
                LOGGER.debug('Unable to find block "%s" in store', e)
                self.set_response(self.status.NO_ROOT)

        elif self._block_store.chain_head:
            self.head_id = self._block_store.chain_head.block.header_signature
            return self._block_store.chain_head.block

        else:
            LOGGER.debug('Unable to get chain head from block store')
            self.set_response(self.status.NOT_READY)

    def set_root(self):
        """
        Used by handlers that fetch data from the merkle tree. Sets the tree
        with the proper root, and returns the chain head id if used.
        """
        if self.has_response():
            return

        if self.request.merkle_root:
            try:
                self._tree.set_merkle_root(self.request.merkle_root)
            except KeyError as e:
                LOGGER.debug('Unable to find root "%s" in database', e)
                self.set_response(self.status.NO_ROOT)
            return

        head = self.get_head_block()
        if self.has_response():
            return

        header = BlockHeader()
        header.ParseFromString(head.header)
        self._tree.set_merkle_root(header.state_root_hash)

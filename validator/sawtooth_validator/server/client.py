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
from sawtooth_validator.protobuf import client_pb2
from sawtooth_validator.protobuf.block_pb2 import BlockHeader
from sawtooth_validator.protobuf.state_context_pb2 import Entry
from sawtooth_validator.protobuf import validator_pb2


LOGGER = logging.getLogger(__name__)


class StateCurrentRequestHandler(object):
    def __init__(self, current_root_func):
        self._current_root_func = current_root_func

    def handle(self, message, responder):
        request = client_pb2.ClientStateCurrentRequest()
        resp_proto = client_pb2.ClientStateCurrentResponse
        status = resp_proto.OK

        try:
            request.ParseFromString(message.content)
            current_root = self._current_root_func()
        except DecodeError:
            LOGGER.info("Expected protobuf of class %s failed to "
                        "deserialize.", request)
            status = resp_proto.ERROR

        if status != resp_proto.OK:
            response = resp_proto(status=resp_proto.ERROR)
        else:
            response = resp_proto(status=status, merkle_root=current_root)

        responder.send(validator_pb2.Message(
            sender=message.sender,
            message_type=validator_pb2.Message.CLIENT_STATE_CURRENT_RESPONSE,
            correlation_id=message.correlation_id,
            content=response.SerializeToString()))


class StateListRequestHandler(object):
    def __init__(self, database):
        self._tree = MerkleDatabase(database)

    def handle(self, message, responder):
        request = client_pb2.ClientStateListRequest()
        resp_proto = client_pb2.ClientStateListResponse
        status = resp_proto.OK

        try:
            request.ParseFromString(message.content)
            self._tree.set_merkle_root(request.merkle_root)
        except KeyError as e:
            status = resp_proto.NORESOURCE
            LOGGER.debug(e)
        except DecodeError:
            status = resp_proto.ERROR
            LOGGER.info("Expected protobuf of class %s failed to "
                        "deserialize", request)

        if status != resp_proto.OK:
            response = resp_proto(status=status)
        else:
            prefix = request.prefix
            leaves = self._tree.leaves(prefix)

            if len(leaves) == 0:
                status = resp_proto.NORESOURCE
                response = resp_proto(status=status)
            else:
                entries = [Entry(address=a, data=v) for a, v in leaves.items()]
                response = resp_proto(status=status, entries=entries)

        responder.send(validator_pb2.Message(
            sender=message.sender,
            message_type=validator_pb2.Message.CLIENT_STATE_LIST_RESPONSE,
            correlation_id=message.correlation_id,
            content=response.SerializeToString()))


class StateGetRequestHandler(object):
    def __init__(self, database):
        self._tree = MerkleDatabase(database)

    def handle(self, message, responder):
        request = client_pb2.ClientStateGetRequest()
        resp_proto = client_pb2.ClientStateGetResponse
        status = resp_proto.OK

        try:
            request.ParseFromString(message.content)
            self._tree.set_merkle_root(request.merkle_root)
        except KeyError as e:
            status = resp_proto.NORESOURCE
            LOGGER.debug(e)
        except DecodeError:
            status = resp_proto.ERROR
            LOGGER.info("Expected protobuf of class %s failed to "
                        "deserialize", request)

        if status != resp_proto.OK:
            response = resp_proto(status=status)
        else:
            address = request.address
            try:
                value = self._tree.get(address)
            except KeyError:
                status = resp_proto.NORESOURCE
                LOGGER.debug("No entry at state address %s", address)
            except ValueError:
                status = resp_proto.NONLEAF
                LOGGER.debug("Node at state address %s is a nonleaf", address)

            response = resp_proto(status=status)
            if status == resp_proto.OK:
                response.value = value

        responder.send(validator_pb2.Message(
            sender=message.sender,
            message_type=validator_pb2.Message.CLIENT_STATE_GET_RESPONSE,
            correlation_id=message.correlation_id,
            content=response.SerializeToString()))


class BlockListRequestHandler(object):
    def __init__(self, block_store):
        self._block_store = block_store

    def handle(self, message, responder):
        request = client_pb2.ClientBlockListRequest()
        resp_proto = client_pb2.ClientBlockListResponse
        status = resp_proto.OK

        try:
            request.ParseFromString(message.content)
        except DecodeError:
            LOGGER.info("Expected protobuf of class %s failed to "
                        "deserialize", request)
            status = resp_proto.ERROR

        if status != resp_proto.OK:
            response = resp_proto(status=status)
        else:
            response = resp_proto(status=status, blocks=self._list_blocks())

        responder.send(validator_pb2.Message(
            sender=message.sender,
            message_type=validator_pb2.Message.CLIENT_BLOCK_LIST_RESPONSE,
            correlation_id=message.correlation_id,
            content=response.SerializeToString()))

    def _list_blocks(self):
        blocks = []
        current_id = self._block_store['chain_head_id']

        while current_id in self._block_store:
            block = self._block_store[current_id].block.get_block()
            blocks.append(block)

            header = BlockHeader()
            header.ParseFromString(block.header)
            current_id = header.previous_block_id

        return blocks


class BlockGetRequestHandler(object):
    def __init__(self, block_store):
        self._block_store = block_store

    def handle(self, message, responder):
        request = client_pb2.ClientBlockGetRequest()
        resp_proto = client_pb2.ClientBlockGetResponse
        status = resp_proto.OK

        try:
            request.ParseFromString(message.content)
            block = self._block_store[request.block_id].block.get_block()
        except DecodeError:
            LOGGER.info("Expected protobuf of class %s failed to "
                        "deserialize", request)
            status = resp_proto.ERROR
        except KeyError as e:
            status = client_pb2.ClientStateListResponse.NORESOURCE
            LOGGER.info(e)

        if status != resp_proto.OK:
            response = resp_proto(status=status)
        else:
            response = resp_proto(status=status, block=block)

        responder.send(validator_pb2.Message(
            sender=message.sender,
            message_type=validator_pb2.Message.CLIENT_BLOCK_LIST_RESPONSE,
            correlation_id=message.correlation_id,
            content=response.SerializeToString()))

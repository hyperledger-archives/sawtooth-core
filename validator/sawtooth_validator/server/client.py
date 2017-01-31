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
from sawtooth_validator.protobuf.state_context_pb2 import Entry
from sawtooth_validator.protobuf import validator_pb2


LOGGER = logging.getLogger(__name__)


class ClientStateCurrentRequestHandler(object):

    def __init__(self, current_root_func):
        self._current_root_func = current_root_func

    def handle(self, message, responder):
        error = False
        current_root = None
        try:
            client_pb2.ClientStateCurrentRequest().ParseFromString(
                message.content)
            current_root = self._current_root_func()
        except DecodeError:
            LOGGER.info("Expected protobuf of class %s failed to "
                        "deserialize.",
                        client_pb2.ClientStateCurrentRequest())
            error = True
        if error:
            response = client_pb2.ClientStateCurrentResponse(
                status=client_pb2.ClientStateCurrentResponse.ERROR)
        else:
            response = client_pb2.ClientStateCurrentResponse(
                status=client_pb2.ClientStateCurrentResponse.OK,
                merkle_root=current_root)
        responder.send(validator_pb2.Message(
            sender=message.sender,
            message_type=validator_pb2.Message.CLIENT_STATE_CURRENT_RESPONSE,
            correlation_id=message.correlation_id,
            content=response.SerializeToString()))


class ClientStateGetRequestHandler(object):
    def __init__(self, database):
        self._tree = MerkleDatabase(database)

    def handle(self, message, responder):
        error = False
        status = None
        request = client_pb2.ClientStateGetRequest()
        try:
            request.ParseFromString(
                message.content)
            self._tree.set_merkle_root(request.merkle_root)
        except KeyError as e:
            status = client_pb2.ClientStateGetResponse.NORESOURCE
            LOGGER.info(e)
            error = True
        except DecodeError:
            LOGGER.info("Expected protobuf of class %s failed to "
                        "deserialize", request)
            error = True
        if error:
            response = client_pb2.ClientStateGetResponse(
                status=status or client_pb2.ClientStateGetResponse.ERROR)
        else:
            address = request.address
            try:
                value = self._tree.get(address)
                status = client_pb2.ClientStateGetResponse.OK
            except KeyError:
                status = client_pb2.ClientStateGetResponse.NORESOURCE
                LOGGER.debug("No entry at state address %s", address)
                error = True
            except ValueError:
                status = client_pb2.ClientStateGetResponse.NONLEAF
                LOGGER.debug("Node at state address %s is a nonleaf", address)
                error = True
            response = client_pb2.ClientStateGetResponse(status=status)
            if not error:
                response.value = value
        responder.send(validator_pb2.Message(
            sender=message.sender,
            message_type=validator_pb2.Message.CLIENT_STATE_GET_RESPONSE,
            correlation_id=message.correlation_id,
            content=response.SerializeToString()))


class ClientStateListRequestHandler(object):
    def __init__(self, database):
        self._tree = MerkleDatabase(database)

    def handle(self, message, responder):
        error = False
        status = None
        request = client_pb2.ClientStateListRequest()
        try:
            request.ParseFromString(
                message.content)
            self._tree.set_merkle_root(request.merkle_root)
        except KeyError as e:
            status = client_pb2.ClientStateListResponse.NORESOURCE
            LOGGER.info(e)
            error = True
        except DecodeError:
            LOGGER.info("Expected protobuf of class %s failed to "
                        "deserialize", request)
            error = True
        if error:
            response = client_pb2.ClientStateListResponse(
                status=status or client_pb2.ClientStateListResponse.ERROR)
        else:
            prefix = request.prefix
            leaves = self._tree.leaves(prefix)
            if len(leaves) == 0:
                status = client_pb2.ClientStateListResponse.NORESOURCE
                response = client_pb2.ClientStateListResponse(status=status)
            else:
                status = client_pb2.ClientStateListResponse.OK
                entries = [
                    Entry(address=a, data=v) for a, v in leaves.items()]
                response = client_pb2.ClientStateListResponse(
                    status=status,
                    entries=entries)

        responder.send(validator_pb2.Message(
            sender=message.sender,
            message_type=validator_pb2.Message.CLIENT_STATE_LIST_RESPONSE,
            correlation_id=message.correlation_id,
            content=response.SerializeToString()))

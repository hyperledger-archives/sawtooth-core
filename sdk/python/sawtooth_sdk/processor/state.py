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
from sawtooth_sdk.protobuf.validator_pb2 import Message
from sawtooth_sdk.protobuf import state_context_pb2
from sawtooth_sdk.processor.exceptions import InvalidTransaction


class StateEntry(object):
    def __init__(self, address, data):
        self.address = address
        self.data = data

    def __str__(self):
        return "{}: {}".format(self.address, self.data)

    def __repr__(self):
        return "{}: {}".format(self.address, self.data)


class State(object):
    """
    Attributes:
        _stream (sawtooth.client.stream.Stream): client grpc communication
        _context_id (str): the context_id passed in from the validator
    """
    def __init__(self, stream, context_id):
        self._stream = stream
        self._context_id = context_id

    def get(self, addresses, timeout=None):
        """
        Get the value at a given list of address in the validator's merkle
        state.
        Args:
            addressses (list): the addresss to fetch
            timeout: optional timeout, in seconds
        Returns:
            results ((map): a map of address to StateEntry values, for the
            addresses that have a value
        """
        request = state_context_pb2.TpStateGetRequest(
            context_id=self._context_id,
            addresses=addresses)
        response_string = self._stream.send(
            Message.TP_STATE_GET_REQUEST,
            request.SerializeToString()).result(timeout).content
        response = state_context_pb2.TpStateGetResponse()
        response.ParseFromString(response_string)
        if response.status == \
                state_context_pb2.TpStateGetResponse.AUTHORIZATION_ERROR:
            raise InvalidTransaction(
                'Tried to get unauthorized address: {}'.format(addresses))
        entries = response.entries if response is not None else []
        results = [StateEntry(address=e.address, data=e.data)
                   for e in entries if len(e.data) != 0]
        return results

    def set(self, entries, timeout=None):
        """
        set an address to a value in the validator's merkle state
        Args:
            entries (list): list of StateEntry
            timeout: optional timeout, in seconds

        Returns:
            addresses (list): a list of addresses that were set

        """
        state_entries = [state_context_pb2.Entry(
            address=e.address,
            data=e.data) for e in entries]
        request = state_context_pb2.TpStateSetRequest(
            entries=state_entries,
            context_id=self._context_id).SerializeToString()
        response = state_context_pb2.TpStateSetResponse()
        response.ParseFromString(
            self._stream.send(Message.TP_STATE_SET_REQUEST,
                              request).result(timeout).content)
        if response.status == \
                state_context_pb2.TpStateSetResponse.AUTHORIZATION_ERROR:
            addresses = [e.address for e in entries]
            raise InvalidTransaction(
                'Tried to set unauthorized address: {}'.format(addresses))
        return response.addresses

    def delete(self, addresses, timeout=None):
        """
        delete an address in the validator's merkle state
        Args:
            entries (list): list of StateEntry
            timeout: optional timeout, in seconds

        Returns:
            addresses (list): a list of addresses that were deleted

        """
        request = state_context_pb2.TpStateDeleteRequest(
            context_id=self._context_id,
            addresses=addresses).SerializeToString()
        response = state_context_pb2.TpStateDeleteResponse()
        response.ParseFromString(
            self._stream.send(Message.TP_STATE_DEL_REQUEST,
                              request).result(timeout).content)
        if response.status == \
                state_context_pb2.TpStateDeleteResponse.AUTHORIZATION_ERROR:
            raise InvalidTransaction(
                'Tried to delete unauthorized address: {}'.format(addresses))
        return response.addresses

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
from sawtooth_sdk.protobuf import events_pb2
from sawtooth_sdk.processor.exceptions import InternalError
from sawtooth_sdk.processor.exceptions import AuthorizationException


class Context(object):
    """
    Attributes:
        _stream (sawtooth.client.stream.Stream): client grpc communication
        _context_id (str): the context_id passed in from the validator
    """
    def __init__(self, stream, context_id):
        self._stream = stream
        self._context_id = context_id

    def get_state(self, addresses, timeout=None):
        """
        Get the value at a given list of address in the validator's merkle
        state.
        Args:
            addressses (list): the addresss to fetch
            timeout: optional timeout, in seconds
        Returns:
            results (list): a list of Entries (address, data), for the
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
            raise AuthorizationException(
                'Tried to get unauthorized address: {}'.format(addresses))
        entries = response.entries if response is not None else []
        results = [e for e in entries if len(e.data) != 0]
        return results

    def set_state(self, entries, timeout=None):
        """
        set an address to a value in the validator's merkle state
        Args:
            entries (dict): dictionary where addresses are the keys and data is
                the value.
            timeout: optional timeout, in seconds

        Returns:
            addresses (list): a list of addresses that were set

        """
        state_entries = [state_context_pb2.TpStateEntry(
            address=e,
            data=entries[e]) for e in entries]
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
            raise AuthorizationException(
                'Tried to set unauthorized address: {}'.format(addresses))
        return response.addresses

    def delete_state(self, addresses, timeout=None):
        """
        delete an address in the validator's merkle state
        Args:
            addresses (list): list of addresses
            timeout: optional timeout, in seconds

        Returns:
            addresses (list): a list of addresses that were deleted

        """
        request = state_context_pb2.TpStateDeleteRequest(
            context_id=self._context_id,
            addresses=addresses).SerializeToString()
        response = state_context_pb2.TpStateDeleteResponse()
        response.ParseFromString(
            self._stream.send(Message.TP_STATE_DELETE_REQUEST,
                              request).result(timeout).content)
        if response.status == \
                state_context_pb2.TpStateDeleteResponse.AUTHORIZATION_ERROR:
            raise AuthorizationException(
                'Tried to delete unauthorized address: {}'.format(addresses))
        return response.addresses

    def add_receipt_data(self, data, timeout=None):
        """Add a blob to the execution result for this transaction.

        Args:
            data (bytes): The data to add.
        """
        request = state_context_pb2.TpReceiptAddDataRequest(
            context_id=self._context_id,
            data=data).SerializeToString()
        response = state_context_pb2.TpReceiptAddDataResponse()
        response.ParseFromString(
            self._stream.send(
                Message.TP_RECEIPT_ADD_DATA_REQUEST,
                request).result(timeout).content)
        if response.status == state_context_pb2.TpReceiptAddDataResponse.ERROR:
            raise InternalError(
                "Failed to add receipt data: {}".format((data)))

    def add_event(self, event_type, attributes=None, data=None, timeout=None):
        """Add a new event to the execution result for this transaction.

        Args:
            event_type (str): This is used to subscribe to events. It should be
                globally unique and describe what, in general, has occured.
            attributes (list of (str, str) tuples): Additional information
                about the event that is transparent to the validator.
                Attributes can be used by subscribers to filter the type of
                events they receive.
            data (bytes): Additional information about the event that is opaque
                to the validator.
        """
        if attributes is None:
            attributes = []

        event = events_pb2.Event(
            event_type=event_type,
            attributes=[
                events_pb2.Event.Attribute(key=key, value=value)
                for key, value in attributes
            ],
            data=data,
        )
        request = state_context_pb2.TpEventAddRequest(
            context_id=self._context_id, event=event).SerializeToString()
        response = state_context_pb2.TpEventAddResponse()
        response.ParseFromString(
            self._stream.send(
                Message.TP_EVENT_ADD_REQUEST,
                request).result(timeout).content)
        if response.status == state_context_pb2.TpEventAddResponse.ERROR:
            raise InternalError(
                "Failed to add event: ({}, {}, {})".format(
                    event_type, attributes, data))

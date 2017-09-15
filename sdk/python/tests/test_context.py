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

import unittest
from unittest.mock import Mock

from sawtooth_sdk.processor.context import Context
from sawtooth_sdk.processor.context import StateEntry
from sawtooth_sdk.messaging.future import Future
from sawtooth_sdk.messaging.future import FutureResult

from sawtooth_sdk.protobuf.validator_pb2 import Message
from sawtooth_sdk.protobuf.state_context_pb2 import Entry
from sawtooth_sdk.protobuf.state_context_pb2 import TpStateGetRequest
from sawtooth_sdk.protobuf.state_context_pb2 import TpStateGetResponse
from sawtooth_sdk.protobuf.state_context_pb2 import TpStateSetRequest
from sawtooth_sdk.protobuf.state_context_pb2 import TpStateSetResponse
from sawtooth_sdk.protobuf.state_context_pb2 import TpStateDeleteRequest
from sawtooth_sdk.protobuf.state_context_pb2 import TpStateDeleteResponse
from sawtooth_sdk.protobuf.state_context_pb2 import TpAddReceiptDataRequest
from sawtooth_sdk.protobuf.state_context_pb2 import TpAddReceiptDataResponse
from sawtooth_sdk.protobuf.state_context_pb2 import TpAddEventRequest
from sawtooth_sdk.protobuf.state_context_pb2 import TpAddEventResponse
from sawtooth_sdk.protobuf.events_pb2 import Event


class ContextTest(unittest.TestCase):
    def setUp(self):
        self.context_id = "test"
        self.mock_stream = Mock()
        self.context = Context(self.mock_stream, self.context_id)
        self.addresses = ["a", "b", "c"]
        self.data = [addr.encode() for addr in self.addresses]

    def _make_future(self, message_type, content):
        f = Future(self.context_id)
        f.set_result(FutureResult(
            message_type=message_type,
            content=content))
        return f

    def _make_entries(self, protobuf=True):
        if protobuf:
            return [Entry(address=a, data=d)
                    for a, d in zip(self.addresses, self.data)]
        return [StateEntry(address=a, data=d)
                for a, d in zip(self.addresses, self.data)]

    def test_state_get(self):
        """Tests that State gets addresses correctly."""
        self.mock_stream.send.return_value = self._make_future(
            message_type=Message.TP_STATE_GET_RESPONSE,
            content=TpStateGetResponse(
                status=TpStateGetResponse.OK,
                entries=self._make_entries()).SerializeToString())

        self.context.get_state(self.addresses)

        self.mock_stream.send.assert_called_with(
            Message.TP_STATE_GET_REQUEST,
            TpStateGetRequest(
                context_id=self.context_id,
                addresses=self.addresses).SerializeToString())

    def test_state_set(self):
        """Tests that State sets addresses correctly."""
        self.mock_stream.send.return_value = self._make_future(
            message_type=Message.TP_STATE_SET_RESPONSE,
            content=TpStateSetResponse(
                status=TpStateSetResponse.OK,
                addresses=self.addresses).SerializeToString())

        self.context.set_state(self._make_entries(protobuf=False))

        self.mock_stream.send.assert_called_with(
            Message.TP_STATE_SET_REQUEST,
            TpStateSetRequest(
                context_id=self.context_id,
                entries=self._make_entries()).SerializeToString())

    def test_state_delete(self):
        """Tests that State deletes addresses correctly."""
        self.mock_stream.send.return_value = self._make_future(
            message_type=Message.TP_STATE_DEL_RESPONSE,
            content=TpStateDeleteResponse(
                status=TpStateDeleteResponse.OK,
                addresses=self.addresses).SerializeToString())

        self.context.delete_state(self.addresses)

        self.mock_stream.send.assert_called_with(
            Message.TP_STATE_DEL_REQUEST,
            TpStateDeleteRequest(
                context_id=self.context_id,
                addresses=self.addresses).SerializeToString())

    def test_add_receipt_data(self):
        """Tests that State adds receipt data correctly."""
        self.mock_stream.send.return_value = self._make_future(
            message_type=Message.TP_ADD_RECEIPT_DATA_RESPONSE,
            content=TpAddReceiptDataResponse(
                status=TpAddReceiptDataResponse.OK).SerializeToString())

        self.context.add_receipt_data("test", b"test")

        self.mock_stream.send.assert_called_with(
            Message.TP_ADD_RECEIPT_DATA_REQUEST,
            TpAddReceiptDataRequest(
                context_id=self.context_id,
                data_type="test",
                data=b"test").SerializeToString())

    def test_add_event(self):
        """Tests that State adds events correctly."""
        self.mock_stream.send.return_value = self._make_future(
            message_type=Message.TP_ADD_EVENT_RESPONSE,
            content=TpAddEventResponse(
                status=TpAddEventResponse.OK).SerializeToString())

        self.context.add_event("test", [("test", "test")], b"test")

        self.mock_stream.send.assert_called_with(
            Message.TP_ADD_EVENT_REQUEST,
            TpAddEventRequest(
                context_id=self.context_id,
                event=Event(
                    event_type="test",
                    attributes=[Event.Attribute(key="test", value="test")],
                    data=b"test")).SerializeToString())

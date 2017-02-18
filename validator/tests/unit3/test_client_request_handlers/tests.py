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
import unittest

import sawtooth_validator.state.client_handlers as handlers
from sawtooth_validator.protobuf import client_pb2


class _ClientHandlerTestCase(unittest.TestCase):
    """
    Parent class for Client Request Handler tests that handles making requests.
    Run _initialize as part of setUp, and then call _make_request in each test.
    """
    def _initialize(self, handler, request_proto, response_proto):
        self._identity = '1234567'
        self._handler = handler
        self._status = response_proto
        self._request_proto = request_proto

    def _make_request(self, **kwargs):
        return self._handle(self._serialize(**kwargs))

    def _serialize(self, **kwargs):
        request = self._request_proto(**kwargs)
        return request.SerializeToString()

    def _handle(self, request):
        result = self._handler.handle(self._identity, request)
        return result.message_out


class TestStateCurrentRequests(_ClientHandlerTestCase):
    def setUp(self):
        def mock_current_root():
            return '123'

        self._initialize(
            handlers.StateCurrentRequest(mock_current_root),
            client_pb2.ClientStateCurrentRequest,
            client_pb2.ClientStateCurrentResponse)

    def test_state_current_request(self):
        """Verifies requests for the current merkle root work properly.
        Compares response to a mock merkle root of '123'.
        """
        response = self._make_request()

        self.assertEqual(self._status.OK, response.status)
        self.assertEqual('123', response.merkle_root)

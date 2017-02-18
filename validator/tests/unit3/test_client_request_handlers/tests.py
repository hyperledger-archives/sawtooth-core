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
from sawtooth_validator.protobuf.block_pb2 import Block
from test_client_request_handlers.mocks import MockBlockStore


class _ClientHandlerTestCase(unittest.TestCase):
    """
    Parent class for Client Request Handler tests that handles making requests.
    Run _initialize as part of setUp, and then call _make_request in each test.
    """
    def _initialize(self, handler, request_proto, response_proto, store=None):
        self._identity = '1234567'
        self._handler = handler
        self._status = response_proto
        self._request_proto = request_proto
        self._store = store

    def _make_request(self, **kwargs):
        return self._handle(self._serialize(**kwargs))

    def _serialize(self, **kwargs):
        request = self._request_proto(**kwargs)
        return request.SerializeToString()

    def _handle(self, request):
        result = self._handler.handle(self._identity, request)
        return result.message_out

    def _make_bad_request(self, **kwargs):
        return self._handle(self._serialize(**kwargs)[0:-1])

    def _break_genesis(self):
        self._store.store.pop('chain_head_id')


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


class TestBlockListRequests(_ClientHandlerTestCase):
    def setUp(self):
        store = MockBlockStore()
        self._initialize(
            handlers.BlockListRequest(store),
            client_pb2.ClientBlockListRequest,
            client_pb2.ClientBlockListResponse,
            store=store)

    def test_block_list_request(self):
        """Verifies requests for block lists without parameters work properly.
        Checks status, head_id, and length and type of blocks list.
        """
        response = self._make_request()

        self.assertEqual(self._status.OK, response.status)
        self.assertEqual('2', response.head_id)
        self.assertEqual(3, len(response.blocks))
        self.assertIsInstance(response.blocks[0], Block)

    def test_block_list_bad_request(self):
        """Verifies requests for lists of blocks break with bad protobufs.
        Checks status, and that head_id blocks list are missing.
        """
        response = self._make_bad_request(head_id='1')

        self.assertEqual(self._status.INTERNAL_ERROR, response.status)
        self.assertFalse(response.head_id)
        self.assertFalse(response.blocks)

    def test_block_list_bad_request(self):
        """Verifies requests for lists of blocks break with no genesis.
        Checks status, and that head_id blocks list are missing.
        """
        self._break_genesis()
        response = self._make_bad_request()

        self.assertEqual(self._status.NOT_READY, response.status)
        self.assertFalse(response.head_id)
        self.assertFalse(response.blocks)

    def test_block_list_with_head(self):
        """Verifies requests for lists of blocks work properly with a head id.
        Checks status, head_id, and length and type of blocks list.
        """
        response = self._make_request(head_id='1')

        self.assertEqual(self._status.OK, response.status)
        self.assertEqual('1', response.head_id)
        self.assertEqual(2, len(response.blocks))
        self.assertIsInstance(response.blocks[0], Block)

    def test_block_list_with_bad_head(self):
        """Verifies requests for lists of blocks break with a bad head.
        Checks status, and that head_id blocks list are missing.
        """
        response = self._make_request(head_id='bad')

        self.assertEqual(self._status.NO_ROOT, response.status)
        self.assertFalse(response.head_id)
        self.assertFalse(response.blocks)


class TestBlockGetRequests(_ClientHandlerTestCase):
    def setUp(self):
        store = MockBlockStore()
        self._initialize(
            handlers.BlockGetRequest(store),
            client_pb2.ClientBlockGetRequest,
            client_pb2.ClientBlockGetResponse)

    def test_block_get_request(self):
        """Verifies requests for a specific block by id work properly.
        Checks status, and type and id of block.
        """
        response = self._make_request(block_id='1')

        self.assertEqual(self._status.OK, response.status)
        self.assertIsInstance(response.block, Block)
        self.assertEqual('1', response.block.header_signature)

    def test_block_get_bad_request(self):
        """Verifies requests for a specific block break with a bad protobuf.
        Checks status, and that the block is missing.
        """
        response = self._make_bad_request(block_id='1')

        self.assertEqual(self._status.INTERNAL_ERROR, response.status)
        self.assertFalse(response.block.SerializeToString())

    def test_block_get_with_bad_id(self):
        """Verifies requests for a specific block break with a bad id.
        Checks status, and that the block is missing.
        """
        response = self._make_request(block_id='bad')

        self.assertEqual(self._status.NO_RESOURCE, response.status)
        self.assertFalse(response.block.SerializeToString())

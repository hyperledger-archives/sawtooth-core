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
from test_client_request_handlers.mocks import make_db_and_store


class _ClientHandlerTestCase(unittest.TestCase):
    """
    Parent class for Client Request Handler tests that handles making requests.
    Run _initialize as part of setUp, and then call _make_request in each test.
    """
    def _initialize(self, handler, request_proto, response_proto,
                    store=None, roots=None):
        self._identity = '1234567'
        self._handler = handler
        self._status = response_proto
        self._request_proto = request_proto
        self._store = store
        self._roots = roots

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


class TestStateListRequests(_ClientHandlerTestCase):
    def setUp(self):
        db, store, roots = make_db_and_store()
        self._initialize(
            handlers.StateListRequest(db, store),
            client_pb2.ClientStateListRequest,
            client_pb2.ClientStateListResponse,
            store=store,
            roots=roots)

    def test_state_list_request(self):
        """Verifies requests for data lists without parameters work properly.
        Checks status, head_id, and length and type of leaves list.
        """
        response = self._make_request()

        self.assertEqual(self._status.OK, response.status)
        self.assertEqual('2', response.head_id)
        self.assertEqual(3, len(response.leaves))
        self.assertIsInstance(response.leaves[0], client_pb2.Leaf)

    def test_state_list_bad_request(self):
        """Verifies requests for lists of data break with bad protobufs.
        Checks response status and that data is missing.
        """
        response = self._make_bad_request(head_id='1')

        self.assertEqual(self._status.INTERNAL_ERROR, response.status)
        self.assertFalse(response.leaves)
        self.assertFalse(response.head_id)

    def test_state_list_no_genesis(self):
        """Verifies requests for lists of data break properly with no genesis.
        Checks status and that response data is missing.
        """
        self._break_genesis()
        response = self._make_request()

        self.assertEqual(self._status.NOT_READY, response.status)
        self.assertFalse(response.leaves)
        self.assertFalse(response.head_id)

    def test_state_list_with_root(self):
        """Verifies requests for data lists work properly with a merkle root.
        Checks status, and length, type and content of leaves list.
        """
        response = self._make_request(merkle_root=self._roots[0])

        self.assertEqual(self._status.OK, response.status)
        self.assertEqual(1, len(response.leaves))

        self.assertIsInstance(response.leaves[0], client_pb2.Leaf)
        self.assertEqual('a', response.leaves[0].address)
        self.assertEqual(b'1', response.leaves[0].data)

    def test_state_list_with_bad_root(self):
        """Verifies requests for lists of data break properly with a bad root.
        Checks status and that response data is missing.
        """
        response = self._make_request(merkle_root='bad')

        self.assertEqual(self._status.NO_ROOT, response.status)
        self.assertFalse(response.leaves)

    def test_state_list_with_head(self):
        """Verifies requests for lists of data work properly with a head_id.
        Checks status, head_id, and length, type and content of leaves list.
        """
        response = self._make_request(head_id='1')

        self.assertEqual(self._status.OK, response.status)
        self.assertEqual('1', response.head_id)
        self.assertEqual(2, len(response.leaves))

        self.assertIsInstance(response.leaves[0], client_pb2.Leaf)
        a = list(filter(lambda l: l.address == 'a', response.leaves))[0]
        self.assertEqual(b'2', a.data)

    def test_state_list_with_bad_head(self):
        """Verifies requests for lists of data break with a bad head_id.
        Checks status and that response data is missing.
        """
        response = self._make_request(head_id='bad')

        self.assertEqual(self._status.NO_ROOT, response.status)
        self.assertFalse(response.head_id)
        self.assertFalse(response.leaves)

    def test_state_list_with_address(self):
        """Verifies requests for data lists filtered by address work properly.
        Checks status, head_id, and length, type and content of leaves list.
        """
        response = self._make_request(address='c')

        self.assertEqual(self._status.OK, response.status)
        self.assertEqual('2', response.head_id)
        self.assertEqual(1, len(response.leaves))

        self.assertIsInstance(response.leaves[0], client_pb2.Leaf)
        self.assertEqual('c', response.leaves[0].address)
        self.assertEqual(b'7', response.leaves[0].data)

    def test_state_list_with_bad_address(self):
        """Verifies requests for data filtered by a bad address break properly.
        Checks status and that response data is missing.
        """
        response = self._make_request(address='bad')

        self.assertEqual(self._status.NO_RESOURCE, response.status)
        self.assertEqual('2', response.head_id)
        self.assertFalse(response.leaves)

    def test_state_list_with_head_and_address(self):
        """Verifies requests for data work with a head and address filter.
        Checks status, head_id, and length, type and content of leaves list.
        """
        response = self._make_request(head_id='1', address='b')

        self.assertEqual(self._status.OK, response.status)
        self.assertEqual('1', response.head_id)
        self.assertEqual(1, len(response.leaves))

        self.assertIsInstance(response.leaves[0], client_pb2.Leaf)
        self.assertEqual('b', response.leaves[0].address)
        self.assertEqual(b'4', response.leaves[0].data)

    def test_state_list_with_early_state(self):
        """Verifies requests for data break when the state predates an address.
        Checks status, head_id, and that response data is missing.
        """
        response = self._make_request(address='c', head_id='1')

        self.assertEqual(self._status.NO_RESOURCE, response.status)
        self.assertEqual('1', response.head_id)
        self.assertFalse(response.leaves)


class TestStateGetRequests(_ClientHandlerTestCase):
    def setUp(self):
        db, store, roots = make_db_and_store()
        self._initialize(
            handlers.StateGetRequest(db, store),
            client_pb2.ClientStateGetRequest,
            client_pb2.ClientStateGetResponse,
            store=store,
            roots=roots)

    def test_state_get_request(self):
        """Verifies requests for specific data by address work properly.
        Checks status, head_id, and value returned.
        """
        response = self._make_request(address='b')

        self.assertEqual(self._status.OK, response.status)
        self.assertEqual('2', response.head_id)
        self.assertEqual(b'5', response.value)

    def test_state_get_bad_request(self):
        """Verifies requests for specfic data break with bad protobufs.
        Checks status, and that head_id and response data are missing.
        """
        response = self._make_bad_request(address='b')

        self.assertEqual(self._status.INTERNAL_ERROR, response.status)
        self.assertFalse(response.head_id)
        self.assertFalse(response.value)

    def test_state_get_no_genesis(self):
        """Verifies requests for specfic data with break properly no genesis.
        Checks status, and that head_id and response data are missing.
        """
        self._break_genesis()
        response = self._make_request(address='b')

        self.assertEqual(self._status.NOT_READY, response.status)
        self.assertFalse(response.head_id)
        self.assertFalse(response.value)

    def test_state_get_with_bad_address(self):
        """Verifies requests for specific data break properly by a bad address.
        Checks status, and that head_id and response data are missing.
        """
        response = self._make_request(address='bad')

        self.assertEqual(self._status.NO_RESOURCE, response.status)
        self.assertFalse(response.head_id)
        self.assertFalse(response.value)

    def test_state_get_with_root(self):
        """Verifies requests for specific data work with a merkle root.
        Checks status, head_id, and value returned.
        """
        response = self._make_request(address='b', merkle_root=self._roots[1])

        self.assertEqual(self._status.OK, response.status)
        self.assertEqual(b'4', response.value)

    def test_state_get_with_bad_root(self):
        """Verifies requests for specific data break properly with a bad root.
        Checks status, and that response data is missing.
        """
        response = self._make_request(address='b', merkle_root='bad')

        self.assertEqual(self._status.NO_ROOT, response.status)
        self.assertFalse(response.value)

    def test_state_get_with_head(self):
        """Verifies requests for specific data work properly with a head id.
        Checks status, head_id, and value returned.
        """
        response = self._make_request(address='a', head_id='0')

        self.assertEqual(self._status.OK, response.status)
        self.assertEqual('0', response.head_id)
        self.assertEqual(b'1', response.value)

    def test_state_get_with_bad_head(self):
        """Verifies requests for specific data break properly with a bad head.
        Checks status, and that response data is missing.
        """
        response = self._make_request(address='a', head_id='bad')

        self.assertEqual(self._status.NO_ROOT, response.status)
        self.assertFalse(response.head_id)
        self.assertFalse(response.value)

    def test_state_get_with_early_state(self):
        """Verifies requests for a datum break when state predates the address.
        Checks status, and that head_id response data are missing.
        """
        response = self._make_request(address='c', head_id='1')

        self.assertEqual(self._status.NO_RESOURCE, response.status)
        self.assertFalse(response.head_id)
        self.assertFalse(response.value)


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

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

import sawtooth_validator.state.client_handlers as handlers
from sawtooth_validator.protobuf import client_pb2
from sawtooth_validator.protobuf.block_pb2 import Block
from test_client_request_handlers.mocks import MockBlockStore
from test_client_request_handlers.mocks import make_db_and_store


class _ClientHandlerTestCase(unittest.TestCase):
    """Parent for Client Request Handler tests that simplifies making requests.
    Run initialize as part of setUp, and then call make_request in each test.
    """
    def initialize(self, handler, request_proto, response_proto,
                    store=None, roots=None):
        self._identity = '1234567'
        self._handler = handler
        self._request_proto = request_proto
        self._store = store
        self.status = response_proto
        self.roots = roots

    def make_request(self, **kwargs):
        return self._handle(self._serialize(**kwargs))

    def _serialize(self, **kwargs):
        request = self._request_proto(**kwargs)
        return request.SerializeToString()

    def _handle(self, request):
        result = self._handler.handle(self._identity, request)
        return result.message_out

    def make_bad_request(self, **kwargs):
        """Truncates the protobuf request, which will break it as long as
        the protobuf is not empty.
        """
        return self._handle(self._serialize(**kwargs)[0:-1])

    def break_genesis(self):
        """Breaks the chain head causing certain "latest" requests to fail.
        Simulates what block store would look like if genesis had not been run.
        """
        del self._store.store['chain_head_id']

    def assertAllInstances(self, items, cls):
        """Checks that all items in a collection are instances of a class
        """
        for item in items:
            self.assertIsInstance(item, cls)


class TestStateCurrentRequests(_ClientHandlerTestCase):
    def setUp(self):
        def mock_current_root():
            return '123'

        self.initialize(
            handlers.StateCurrentRequest(mock_current_root),
            client_pb2.ClientStateCurrentRequest,
            client_pb2.ClientStateCurrentResponse)

    def test_state_current_request(self):
        """Verifies requests for the current merkle root work properly.
        Should respond with a the hard-coded mock merkle_root of '123'.
        """
        response = self.make_request()

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('123', response.merkle_root)


class TestStateListRequests(_ClientHandlerTestCase):
    def _find_value(self, leaves, address):
        """The ordering of leaves is fairly arbitrary, so some tests
        need to filter for the matching address.
        """
        matches = filter(lambda leaf: leaf.address == address, leaves)
        return list(matches)[0].data

    def setUp(self):
        db, store, roots = make_db_and_store()
        self.initialize(
            handlers.StateListRequest(db, store),
            client_pb2.ClientStateListRequest,
            client_pb2.ClientStateListResponse,
            store=store,
            roots=roots)

    def test_state_list_request(self):
        """Verifies requests for data lists without parameters work properly.

        Queries the latest state in the default mock db:
            state: {'a': b'3', 'b': b'5', 'c': b'7'}

        the tests expect to find:
            - a status of OK
            - a head_id of '2' (the latest)
            - a list of leaves with 3 items
            - that the list contains instances of Leaf
            - that there is a leaf with an address of 'a' and data of b'3'
        """
        response = self.make_request()

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('2', response.head_id)
        self.assertEqual(3, len(response.leaves))
        self.assertAllInstances(response.leaves, client_pb2.Leaf)
        self.assertEqual(b'3', self._find_value(response.leaves, 'a'))

    def test_state_list_bad_request(self):
        """Verifies requests for lists of data break with bad protobufs.

        Expects to find:
            - a status of INTERNAL_ERROR
            - that leaves and head_id are missing
        """
        response = self.make_bad_request(head_id='1')

        self.assertEqual(self.status.INTERNAL_ERROR, response.status)
        self.assertFalse(response.leaves)
        self.assertFalse(response.head_id)

    def test_state_list_no_genesis(self):
        """Verifies requests for lists of data break properly with no genesis.

        Expects to find:
            - a status of NOT_READY
            - that leaves and head_id are missing
        """
        self.break_genesis()
        response = self.make_request()

        self.assertEqual(self.status.NOT_READY, response.status)
        self.assertFalse(response.leaves)
        self.assertFalse(response.head_id)

    def test_state_list_with_root(self):
        """Verifies requests for data lists work properly with a merkle root.

        Queries the first state in the default mock db:
            {'a': b'1'}

        Expects to find:
            - a status of OK
            - that head_id is missing (queried by root)
            - a list of leaves with 1 item
            - that the list contains instances of Leaf
            - that Leaf has an address of 'a' and data of b'1'
        """
        response = self.make_request(merkle_root=self.roots[0])

        self.assertEqual(self.status.OK, response.status)
        self.assertFalse(response.head_id)
        self.assertEqual(1, len(response.leaves))

        self.assertAllInstances(response.leaves, client_pb2.Leaf)
        self.assertEqual('a', response.leaves[0].address)
        self.assertEqual(b'1', response.leaves[0].data)

    def test_state_list_with_bad_root(self):
        """Verifies requests for lists of data break properly with a bad root.

        Expects to find:
            - a status of NO_ROOT
            - that leaves and head_id are missing
        """
        response = self.make_request(merkle_root='bad')

        self.assertEqual(self.status.NO_ROOT, response.status)
        self.assertFalse(response.head_id)
        self.assertFalse(response.leaves)

    def test_state_list_with_head(self):
        """Verifies requests for lists of data work properly with a head_id.

        Queries the second state in the default mock db:
            {'a': b'2', 'b': b'4'}

        Expects to find:
            - a status of OK
            - a head_id of '1'
            - a list of leaves with 2 items
            - that the list contains instances of Leaf
            - that there is a leaf with an address of 'a' and data of b'1'
        """
        response = self.make_request(head_id='1')

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('1', response.head_id)
        self.assertEqual(2, len(response.leaves))

        self.assertAllInstances(response.leaves, client_pb2.Leaf)
        self.assertEqual(b'2', self._find_value(response.leaves, 'a'))

    def test_state_list_with_bad_head(self):
        """Verifies requests for lists of data break with a bad head_id.

        Expects to find:
            - a status of NO_ROOT
            - that leaves and head_id are missing
        """
        response = self.make_request(head_id='bad')

        self.assertEqual(self.status.NO_ROOT, response.status)
        self.assertFalse(response.head_id)
        self.assertFalse(response.leaves)

    def test_state_list_with_address(self):
        """Verifies requests for data lists filtered by address work properly.

        Queries the latest state in the default mock db:
            {'a': b'3', 'b': b'5', 'c': b'7'}

        Expects to find:
            - a status of OK
            - a head_id of '2' (the latest)
            - a list of leaves with 1 item
            - that the list contains instances of Leaf
            - that Leaf matches the address of 'c' and has data of b'7'
        """
        response = self.make_request(address='c')

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('2', response.head_id)
        self.assertEqual(1, len(response.leaves))

        self.assertAllInstances(response.leaves, client_pb2.Leaf)
        self.assertEqual('c', response.leaves[0].address)
        self.assertEqual(b'7', response.leaves[0].data)

    def test_state_list_with_bad_address(self):
        """Verifies requests for data filtered by a bad address break properly.

        Expects to find:
            - a status of NO_RESOURCE
            - a head_id of '2' (the latest chain head id)
            - that leaves is missing
        """
        response = self.make_request(address='bad')

        self.assertEqual(self.status.NO_RESOURCE, response.status)
        self.assertEqual('2', response.head_id)
        self.assertFalse(response.leaves)

    def test_state_list_with_head_and_address(self):
        """Verifies requests for data work with a head and address filter.

        Queries the second state in the default mock db:
            {'a': b'2', 'b': b'4'}

        Expects to find:
            - a status of OK
            - a head_id of '1'
            - a list of leaves with 1 item
            - that the list contains instances of Leaf
            - that Leaf matches the address of 'b', and has data of b'4'
        """
        response = self.make_request(head_id='1', address='b')

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('1', response.head_id)
        self.assertEqual(1, len(response.leaves))

        self.assertAllInstances(response.leaves, client_pb2.Leaf)
        self.assertEqual('b', response.leaves[0].address)
        self.assertEqual(b'4', response.leaves[0].data)

    def test_state_list_with_early_state(self):
        """Verifies requests for data break when the state predates an address.

        Attempts to query the second state in the default mock db:
            {'a': b'2', 'b': b'4'}

        Expects to find:
            - a status of NO_RESOURCE
            - a head_id of '1'
            - that leaves is missing
        """
        response = self.make_request(address='c', head_id='1')

        self.assertEqual(self.status.NO_RESOURCE, response.status)
        self.assertEqual('1', response.head_id)
        self.assertFalse(response.leaves)


class TestStateGetRequests(_ClientHandlerTestCase):
    def setUp(self):
        db, store, roots = make_db_and_store()
        self.initialize(
            handlers.StateGetRequest(db, store),
            client_pb2.ClientStateGetRequest,
            client_pb2.ClientStateGetResponse,
            store=store,
            roots=roots)

    def test_state_get_request(self):
        """Verifies requests for specific data by address work properly.

        Queries the latest state in the default mock db:
            {'a': b'3', 'b': b'5', 'c': b'7'}

        Expects to find:
            - a status of OK
            - a head_id of '2' (the latest)
            - a value of b'5'
        """
        response = self.make_request(address='b')

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('2', response.head_id)
        self.assertEqual(b'5', response.value)

    def test_state_get_bad_request(self):
        """Verifies requests for specfic data break with bad protobufs.

        Expects to find:
            - a status of INTERNAL_ERROR
            - that value and head_id are missing
        """
        response = self.make_bad_request(address='b')

        self.assertEqual(self.status.INTERNAL_ERROR, response.status)
        self.assertFalse(response.head_id)
        self.assertFalse(response.value)

    def test_state_get_no_genesis(self):
        """Verifies requests for specfic data with break properly no genesis.

        Expects to find:
            - a status of NOT_READY
            - that value and head_id are missing
        """
        self.break_genesis()
        response = self.make_request(address='b')

        self.assertEqual(self.status.NOT_READY, response.status)
        self.assertFalse(response.head_id)
        self.assertFalse(response.value)

    def test_state_get_with_bad_address(self):
        """Verifies requests for specific data break properly by a bad address.

        Expects to find:
            - a status of NO_RESOURCE
            - that value and head_id are missing
        """
        response = self.make_request(address='bad')

        self.assertEqual(self.status.NO_RESOURCE, response.status)
        self.assertFalse(response.head_id)
        self.assertFalse(response.value)

    def test_state_get_with_root(self):
        """Verifies requests for specific data work with a merkle root.

        Queries the second state in the default mock db:
            {'a': b'2', 'b': b'4'}

        Expects to find:
            - a status of OK
            - that head_id is missing (queried by root)
            - a value of b'4'
        """
        response = self.make_request(address='b', merkle_root=self.roots[1])

        self.assertEqual(self.status.OK, response.status)
        self.assertFalse(response.head_id)
        self.assertEqual(b'4', response.value)

    def test_state_get_with_bad_root(self):
        """Verifies requests for specific data break properly with a bad root.

        Expects to find:
            - a status of NO_ROOT
            - that value and head_id are missing
        """
        response = self.make_request(address='b', merkle_root='bad')

        self.assertEqual(self.status.NO_ROOT, response.status)
        self.assertFalse(response.value)
        self.assertFalse(response.value)

    def test_state_get_with_head(self):
        """Verifies requests for specific data work properly with a head id.

        Queries the first state in the default mock db:
            {'a': b'1'}

        Expects to find:
            - a status of OK
            - a head_id of '0'
            - a value of b'1'
        """
        response = self.make_request(address='a', head_id='0')

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('0', response.head_id)
        self.assertEqual(b'1', response.value)

    def test_state_get_with_bad_head(self):
        """Verifies requests for specific data break properly with a bad head.

        Expects to find:
            - a status of NO_ROOT
            - that value and head_id are missing
        """
        response = self.make_request(address='a', head_id='bad')

        self.assertEqual(self.status.NO_ROOT, response.status)
        self.assertFalse(response.head_id)
        self.assertFalse(response.value)

    def test_state_get_with_early_state(self):
        """Verifies requests for a datum break when state predates the address.

        Attempts to query the second state in the default mock db:
            {'a': b'2', 'b': b'4'}

        Expects to find:
            - a status of NO_RESOURCE
            - that value and head_id are missing
        """
        response = self.make_request(address='c', head_id='1')

        self.assertEqual(self.status.NO_RESOURCE, response.status)
        self.assertFalse(response.head_id)
        self.assertFalse(response.value)


class TestBlockListRequests(_ClientHandlerTestCase):
    def setUp(self):
        store = MockBlockStore()
        self.initialize(
            handlers.BlockListRequest(store),
            client_pb2.ClientBlockListRequest,
            client_pb2.ClientBlockListResponse,
            store=store)

    def test_block_list_request(self):
        """Verifies requests for block lists without parameters work properly.

        Queries the default mock block store with three blocks:
            {header: {block_num: 2 ...}, header_signature: '2' ...},
            {header: {block_num: 1 ...}, header_signature: '1' ...},
            {header: {block_num: 0 ...}, header_signature: '0' ...}

        Expects to find:
            - a status of OK
            - a head_id of '2' (the latest)
            - a list of blocks with 3 items
            - the items are instances of Block
            - The first item has a header_signature of '2'
        """
        response = self.make_request()

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('2', response.head_id)
        self.assertEqual(3, len(response.blocks))
        self.assertAllInstances(response.blocks, Block)
        self.assertEqual('2', response.blocks[0].header_signature)

    def test_block_list_bad_request(self):
        """Verifies requests for lists of blocks break with bad protobufs.

        Expects to find:
            - a status of INBTERNAL_ERROR
            - that blocks and head_id are missing
        """
        response = self.make_bad_request(head_id='1')

        self.assertEqual(self.status.INTERNAL_ERROR, response.status)
        self.assertFalse(response.head_id)
        self.assertFalse(response.blocks)

    def test_block_list_bad_request(self):
        """Verifies requests for lists of blocks break with no genesis.

        Expects to find:
            - a status of NOT_READY
            - that blocks and head_id are missing
        """
        self.break_genesis()
        response = self.make_bad_request()

        self.assertEqual(self.status.NOT_READY, response.status)
        self.assertFalse(response.head_id)
        self.assertFalse(response.blocks)

    def test_block_list_with_head(self):
        """Verifies requests for lists of blocks work properly with a head id.

        Queries the default mock block store with '1' as the head:
            {header: {block_num: 1 ...}, header_signature: '1' ...},
            {header: {block_num: 0 ...}, header_signature: '0' ...}

        Expects to find:
            - a status of OK
            - a head_id of '1'
            - a list of blocks with 2 items
            - the items are instances of Block
            - The first item has a header_signature of '1'
        """
        response = self.make_request(head_id='1')

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('1', response.head_id)
        self.assertEqual(2, len(response.blocks))
        self.assertAllInstances(response.blocks, Block)
        self.assertEqual('1', response.blocks[0].header_signature)

    def test_block_list_with_bad_head(self):
        """Verifies requests for lists of blocks break with a bad head.

        Expects to find:
            - a status of NO_ROOT
            - that blocks and head_id are missing
        """
        response = self.make_request(head_id='bad')

        self.assertEqual(self.status.NO_ROOT, response.status)
        self.assertFalse(response.head_id)
        self.assertFalse(response.blocks)


class TestBlockGetRequests(_ClientHandlerTestCase):
    def setUp(self):
        store = MockBlockStore()
        self.initialize(
            handlers.BlockGetRequest(store),
            client_pb2.ClientBlockGetRequest,
            client_pb2.ClientBlockGetResponse)

    def test_block_get_request(self):
        """Verifies requests for a specific block by id work properly.

        Queries the default three block mock store for an id of '1'.
        Expects to find:
            - a status of OK
            - the block property which is an instances of Block
            - The block has a header_signature of '1'
        """
        response = self.make_request(block_id='1')

        self.assertEqual(self.status.OK, response.status)
        self.assertIsInstance(response.block, Block)
        self.assertEqual('1', response.block.header_signature)

    def test_block_get_bad_request(self):
        """Verifies requests for a specific block break with a bad protobuf.

        Expects to find:
            - a status of INTERNAL_ERROR
            - that the Block returned, when serialized, is empty
        """
        response = self.make_bad_request(block_id='1')

        self.assertEqual(self.status.INTERNAL_ERROR, response.status)
        self.assertFalse(response.block.SerializeToString())

    def test_block_get_with_bad_id(self):
        """Verifies requests for a specific block break with a bad id.

        Expects to find:
            - a status of INTERNAL_ERROR
            - that the Block returned, when serialized, is empty
        """
        response = self.make_request(block_id='bad')

        self.assertEqual(self.status.NO_RESOURCE, response.status)
        self.assertFalse(response.block.SerializeToString())

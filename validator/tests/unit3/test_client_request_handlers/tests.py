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
from threading import Thread
from time import time, sleep
from collections import Hashable

import sawtooth_validator.state.client_handlers as handlers
from sawtooth_validator.protobuf import client_pb2
from sawtooth_validator.protobuf.block_pb2 import Block
from sawtooth_validator.protobuf.batch_pb2 import Batch
from test_client_request_handlers.mocks import MockBlockStore
from test_client_request_handlers.mocks import make_mock_batch
from test_client_request_handlers.mocks import make_db_and_store
from test_client_request_handlers.mocks import make_store_and_cache


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

    def assert_all_instances(self, items, cls):
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


class TestBatchSubmitFinisher(_ClientHandlerTestCase):
    def setUp(self):
        store, cache = make_store_and_cache()

        self.initialize(
            handlers.BatchSubmitFinisher(store, cache),
            client_pb2.ClientBatchSubmitRequest,
            client_pb2.ClientBatchSubmitResponse,
            store=store)

    def test_batch_submit_without_wait(self):
        """Verifies finisher simply returns OK when not set to wait.

        Expects to find:
            - a response status of OK
            - no batch_statusus
        """
        response = self.make_request(batches=[make_mock_batch('new')])

        self.assertEqual(self.status.OK, response.status)
        self.assertFalse(response.batch_statuses)

    def test_batch_submit_bad_request(self):
        """Verifies finisher breaks properly when sent a bad request.

        Expects to find:
            - a response status of INTERNAL_ERROR
        """
        response = self.make_bad_request(batches=[make_mock_batch('new')])

        self.assertEqual(self.status.INTERNAL_ERROR, response.status)

    def test_batch_submit_with_wait(self):
        """Verifies finisher works properly when waiting for commit.

        Queries the default mock block store which will have no block with
        the id 'new' until added by a separate thread.

        Expects to find:
            - less than 8 seconds to have passed (i.e. did not wait for timeout)
            - a response status of OK
            - a status of COMMITTED at key 'b-new' in batch_statuses
        """
        start_time = time()
        def delayed_add():
            sleep(2)
            self._store.add_block('new')
        Thread(target=delayed_add).start()

        response = self.make_request(
            batches=[make_mock_batch('new')],
            wait_for_commit=True,
            timeout=10)

        self.assertGreater(8, time() - start_time)
        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(response.batch_statuses['b-new'], self.status.COMMITTED)


class TestBatchStatusRequests(_ClientHandlerTestCase):
    def setUp(self):
        store, cache = make_store_and_cache()

        self.initialize(
            handlers.BatchStatusRequest(store, cache),
            client_pb2.ClientBatchStatusRequest,
            client_pb2.ClientBatchStatusResponse,
            store=store)

    def test_batch_status_in_store(self):
        """Verifies requests for status of a batch in the block store work.

        Queries the default mock block store with three blocks/batches:
            {header: {batch_ids: ['b-2'] ...}, header_signature: 'B-2' ...},
            {header: {batch_ids: ['b-1'] ...}, header_signature: 'B-1' ...},
            {header: {batch_ids: ['b-0'] ...}, header_signature: 'B-0' ...}

        Expects to find:
            - a response status of OK
            - a status of COMMITTED at key '0' in batch_statuses
        """
        response = self.make_request(batch_ids=['b-0'])

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(response.batch_statuses['b-0'], self.status.COMMITTED)

    def test_batch_status_bad_request(self):
        """Verifies bad requests for status of a batch break properly.

        Expects to find:
            - a response status of INTERNAL_ERROR
        """
        response = self.make_bad_request(batch_ids=['b-0'])

        self.assertEqual(self.status.INTERNAL_ERROR, response.status)

    def test_batch_status_when_empty(self):
        """Verifies requests for batch statuses with no ids break properly.

        Expects to find:
            - a response status of NO_RESOURCE
            - that batch_statuses is empty
        """
        response = self.make_request(batch_ids=[])

        self.assertEqual(self.status.NO_RESOURCE, response.status)
        self.assertFalse(response.batch_statuses)

    def test_batch_status_in_cache(self):
        """Verifies requests for status of a batch in the batch cache work.

        Queries the default mock batch cache with two batches:
            {header_signature: 'b-3' ...},
            {header_signature: 'b-2' ...}

        Expects to find:
            - a response status of OK
            - a status of PENDING at key 'b-3' in batch_statuses
        """
        response = self.make_request(batch_ids=['b-3'])

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(response.batch_statuses['b-3'], self.status.PENDING)

    def test_batch_status_when_missing(self):
        """Verifies requests for status of a batch that is not found work.

        Expects to find:
            - a response status of OK
            - a status of UNKNOWN at key 'z' in batch_statuses
        """
        response = self.make_request(batch_ids=['z'])

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(response.batch_statuses['z'], self.status.UNKNOWN)

    def test_batch_status_in_store_and_cache(self):
        """Verifies requests for status of batch in both store and cache work.

        Queries the default mock block store with three blocks/batches:
            {header: {batch_ids: ['b-2'] ...}, header_signature: 'B-2' ...},
            {header: {batch_ids: ['b-1'] ...}, header_signature: 'B-1' ...},
            {header: {batch_ids: ['b-0'] ...}, header_signature: 'B-0' ...}

        ...and the default mock batch cache with two batches:
            {header_signature: 'B-3' ...},
            {header_signature: 'B-2' ...}

        Expects to find:
            - a response status of OK
            - a status of COMMITTED at key '2' in batch_statuses
        """
        response = self.make_request(batch_ids=['b-2'])

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(response.batch_statuses['b-2'], self.status.COMMITTED)

    def test_batch_status_for_many_batches(self):
        """Verifies requests for status of many batches work properly.

        Queries the default mock block store with three blocks/batches:
            {header: {batch_ids: ['b-2'] ...}, header_signature: 'B-2' ...},
            {header: {batch_ids: ['b-1'] ...}, header_signature: 'B-1' ...},
            {header: {batch_ids: ['b-0'] ...}, header_signature: 'B-0' ...}

        ...and the default mock batch cache with two batches:
            {header_signature: 'B-3' ...},
            {header_signature: 'B-2' ...}

        Expects to find:
            - a response status of OK
            - a status of COMMITTED at key '1' in batch_statuses
            - a status of COMMITTED at key '2' in batch_statuses
            - a status of PENDING at key '3' in batch_statuses
            - a status of UNKNOWN at key 'y' in batch_statuses
        """
        response = self.make_request(batch_ids=['b-1', 'b-2', 'b-3', 'y'])

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(response.batch_statuses['b-1'], self.status.COMMITTED)
        self.assertEqual(response.batch_statuses['b-2'], self.status.COMMITTED)
        self.assertEqual(response.batch_statuses['b-3'], self.status.PENDING)
        self.assertEqual(response.batch_statuses['y'], self.status.UNKNOWN)

    def test_batch_status_with_wait(self):
        """Verifies requests for status that wait for commit work properly.

        Queries the default mock block store which will have no block with
        the id 'awaited' until added by a separate thread.

        Expects to find:
            - less than 8 seconds to have passed (i.e. did not wait for timeout)
            - a response status of OK
            - a status of COMMITTED at key 'b-new' in batch_statuses
        """
        start_time = time()
        def delayed_add():
            sleep(2)
            self._store.add_block('new')
        Thread(target=delayed_add).start()

        response = self.make_request(
            batch_ids=['b-new'],
            wait_for_commit=True,
            timeout=10)

        self.assertGreater(8, time() - start_time)
        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(response.batch_statuses['b-new'], self.status.COMMITTED)


class TestStateListRequests(_ClientHandlerTestCase):
    def _find_value(self, leaves, address):
        """The ordering of leaves is fairly arbitrary, so some tests
        need to filter for the matching address.
        """
        return [l for l in leaves if l.address == address][0].data

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
            - a head_id of 'B-2' (the latest)
            - a list of leaves with 3 items
            - that the list contains instances of Leaf
            - that there is a leaf with an address of 'a' and data of b'3'
        """
        response = self.make_request()

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('B-2', response.head_id)
        self.assertEqual(3, len(response.leaves))
        self.assert_all_instances(response.leaves, client_pb2.Leaf)
        self.assertEqual(b'3', self._find_value(response.leaves, 'a'))

    def test_state_list_bad_request(self):
        """Verifies requests for lists of data break with bad protobufs.

        Expects to find:
            - a status of INTERNAL_ERROR
            - that leaves and head_id are missing
        """
        response = self.make_bad_request(head_id='B-1')

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

        self.assert_all_instances(response.leaves, client_pb2.Leaf)
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
        response = self.make_request(head_id='B-1')

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('B-1', response.head_id)
        self.assertEqual(2, len(response.leaves))

        self.assert_all_instances(response.leaves, client_pb2.Leaf)
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
            - a head_id of 'B-2' (the latest)
            - a list of leaves with 1 item
            - that the list contains instances of Leaf
            - that Leaf matches the address of 'c' and has data of b'7'
        """
        response = self.make_request(address='c')

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('B-2', response.head_id)
        self.assertEqual(1, len(response.leaves))

        self.assert_all_instances(response.leaves, client_pb2.Leaf)
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
        self.assertEqual('B-2', response.head_id)
        self.assertFalse(response.leaves)

    def test_state_list_with_head_and_address(self):
        """Verifies requests for data work with a head and address filter.

        Queries the second state in the default mock db:
            {'a': b'2', 'b': b'4'}

        Expects to find:
            - a status of OK
            - a head_id of 'B-1'
            - a list of leaves with 1 item
            - that the list contains instances of Leaf
            - that Leaf matches the address of 'b', and has data of b'4'
        """
        response = self.make_request(head_id='B-1', address='b')

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('B-1', response.head_id)
        self.assertEqual(1, len(response.leaves))

        self.assert_all_instances(response.leaves, client_pb2.Leaf)
        self.assertEqual('b', response.leaves[0].address)
        self.assertEqual(b'4', response.leaves[0].data)

    def test_state_list_with_early_state(self):
        """Verifies requests for data break when the state predates an address.

        Attempts to query the second state in the default mock db:
            {'a': b'2', 'b': b'4'}

        Expects to find:
            - a status of NO_RESOURCE
            - a head_id of 'B-1'
            - that leaves is missing
        """
        response = self.make_request(address='c', head_id='B-1')

        self.assertEqual(self.status.NO_RESOURCE, response.status)
        self.assertEqual('B-1', response.head_id)
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
            - a head_id of 'B-2' (the latest)
            - a value of b'5'
        """
        response = self.make_request(address='b')

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('B-2', response.head_id)
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
            - a head_id of 'B-0'
            - a value of b'1'
        """
        response = self.make_request(address='a', head_id='B-0')

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('B-0', response.head_id)
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
        response = self.make_request(address='c', head_id='B-1')

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
            {header: {block_num: 2 ...}, header_signature: 'B-2' ...},
            {header: {block_num: 1 ...}, header_signature: 'B-1' ...},
            {header: {block_num: 0 ...}, header_signature: 'B-0' ...}

        Expects to find:
            - a status of OK
            - a head_id of 'B-2' (the latest)
            - a list of blocks with 3 items
            - the items are instances of Block
            - The first item has a header_signature of 'B-2'
        """
        response = self.make_request()

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('B-2', response.head_id)
        self.assertEqual(3, len(response.blocks))
        self.assert_all_instances(response.blocks, Block)
        self.assertEqual('B-2', response.blocks[0].header_signature)

    def test_block_list_bad_request(self):
        """Verifies requests for lists of blocks break with bad protobufs.

        Expects to find:
            - a status of INTERNAL_ERROR
            - that blocks and head_id are missing
        """
        response = self.make_bad_request(head_id='B-1')

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
        response = self.make_request()

        self.assertEqual(self.status.NOT_READY, response.status)
        self.assertFalse(response.head_id)
        self.assertFalse(response.blocks)

    def test_block_list_with_head(self):
        """Verifies requests for lists of blocks work properly with a head id.

        Queries the default mock block store with '1' as the head:
            {header: {block_num: 1 ...}, header_signature: 'B-1' ...},
            {header: {block_num: 0 ...}, header_signature: 'B-0' ...}

        Expects to find:
            - a status of OK
            - a head_id of 'B-1'
            - a list of blocks with 2 items
            - the items are instances of Block
            - The first item has a header_signature of 'B-1'
        """
        response = self.make_request(head_id='B-1')

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('B-1', response.head_id)
        self.assertEqual(2, len(response.blocks))
        self.assert_all_instances(response.blocks, Block)
        self.assertEqual('B-1', response.blocks[0].header_signature)

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

        Queries the default three block mock store for an id of 'B-1'.
        Expects to find:
            - a status of OK
            - the block property which is an instances of Block
            - The block has a header_signature of 'B-1'
        """
        response = self.make_request(block_id='B-1')

        self.assertEqual(self.status.OK, response.status)
        self.assertIsInstance(response.block, Block)
        self.assertEqual('B-1', response.block.header_signature)

    def test_block_get_bad_request(self):
        """Verifies requests for a specific block break with a bad protobuf.

        Expects to find:
            - a status of INTERNAL_ERROR
            - that the Block returned, when serialized, is empty
        """
        response = self.make_bad_request(block_id='B-1')

        self.assertEqual(self.status.INTERNAL_ERROR, response.status)
        self.assertFalse(response.block.SerializeToString())

    def test_block_get_with_bad_id(self):
        """Verifies requests for a specific block break with a bad id.

        Expects to find:
            - a status of NO_RESOURCE
            - that the Block returned, when serialized, is empty
        """
        response = self.make_request(block_id='bad')

        self.assertEqual(self.status.NO_RESOURCE, response.status)
        self.assertFalse(response.block.SerializeToString())

    def test_block_get_with_batch_id(self):
        """Verifies requests for a block break properly with a batch id.

        Expects to find:
            - a status of INVALID_ID
            - that the Block returned, when serialized, is empty
        """
        response = self.make_request(block_id='b-1')

        self.assertEqual(self.status.INVALID_ID, response.status)
        self.assertFalse(response.block.SerializeToString())


class TestBatchListRequests(_ClientHandlerTestCase):
    def setUp(self):
        store = MockBlockStore()
        self.initialize(
            handlers.BatchListRequest(store),
            client_pb2.ClientBatchListRequest,
            client_pb2.ClientBatchListResponse,
            store=store)

    def test_batch_list_request(self):
        """Verifies requests for batch lists without parameters work properly.

        Queries the default mock block store with three blocks:
            {header_signature: 'B-2', batches: [{header_signature: 'b-2' ...}] ...}
            {header_signature: 'B-1', batches: [{header_signature: 'b-1' ...}] ...}
            {header_signature: 'B-0', batches: [{header_signature: 'b-0' ...}] ...}

        Expects to find:
            - a status of OK
            - a head_id of 'B-2' (the latest)
            - a list of batches with 3 items
            - the items are instances of Batch
            - the first item has a header_signature of 'b-2'
        """
        response = self.make_request()

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('B-2', response.head_id)
        self.assertEqual(3, len(response.batches))
        self.assert_all_instances(response.batches, Batch)
        self.assertEqual('b-2', response.batches[0].header_signature)

    def test_batch_list_bad_request(self):
        """Verifies requests for lists of batches break with bad protobufs.

        Expects to find:
            - a status of INTERNAL_ERROR
            - that batches and head_id are missing
        """
        response = self.make_bad_request(head_id='B-1')

        self.assertEqual(self.status.INTERNAL_ERROR, response.status)
        self.assertFalse(response.head_id)
        self.assertFalse(response.batches)

    def test_batch_list_bad_request(self):
        """Verifies requests for lists of batches break with no genesis.

        Expects to find:
            - a status of NOT_READY
            - that batches and head_id are missing
        """
        self.break_genesis()
        response = self.make_request()

        self.assertEqual(self.status.NOT_READY, response.status)
        self.assertFalse(response.head_id)
        self.assertFalse(response.batches)

    def test_batch_list_with_head(self):
        """Verifies requests for lists of batches work properly with a head id.

        Queries the default mock block store with '1' as the head:
            {header_signature: 'B-1', batches: [{header_signature: 'b-1' ...}] ...}
            {header_signature: 'B-0', batches: [{header_signature: 'b-0' ...}] ...}

        Expects to find:
            - a status of OK
            - a head_id of 'B-1'
            - a list of batches with 2 items
            - the items are instances of Batch
            - the first item has a header_signature of 'b-1'
        """
        response = self.make_request(head_id='B-1')

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('B-1', response.head_id)
        self.assertEqual(2, len(response.batches))
        self.assert_all_instances(response.batches, Batch)
        self.assertEqual('b-1', response.batches[0].header_signature)

    def test_batch_list_with_bad_head(self):
        """Verifies requests for lists of batches break with a bad head.

        Expects to find:
            - a status of NO_ROOT
            - that batches and head_id are missing
        """
        response = self.make_request(head_id='bad')

        self.assertEqual(self.status.NO_ROOT, response.status)
        self.assertFalse(response.head_id)
        self.assertFalse(response.batches)


class TestBatchGetRequests(_ClientHandlerTestCase):
    def setUp(self):
        store = MockBlockStore()
        self.initialize(
            handlers.BatchGetRequest(store),
            client_pb2.ClientBatchGetRequest,
            client_pb2.ClientBatchGetResponse)

    def test_batch_get_request(self):
        """Verifies requests for a specific batch by id work properly.

        Queries the default three block mock store for a batch id of 'b-1'.
        Expects to find:
            - a status of OK
            - a batch property which is an instances of Batch
            - the batch has a header_signature of 'b-1'
        """
        response = self.make_request(batch_id='b-1')

        self.assertEqual(self.status.OK, response.status)
        self.assertIsInstance(response.batch, Batch)
        self.assertEqual('b-1', response.batch.header_signature)

    def test_batch_get_bad_request(self):
        """Verifies requests for a specific batch break with a bad protobuf.

        Expects to find:
            - a status of INTERNAL_ERROR
            - that the Batch returned, when serialized, is actually empty
        """
        response = self.make_bad_request(batch_id='b-1')

        self.assertEqual(self.status.INTERNAL_ERROR, response.status)
        self.assertFalse(response.batch.SerializeToString())

    def test_batch_get_with_bad_id(self):
        """Verifies requests for a specific batch break with a bad id.

        Expects to find:
            - a status of NO_RESOURCE
            - that the Batch returned, when serialized, is actually empty
        """
        response = self.make_request(batch_id='bad')

        self.assertEqual(self.status.NO_RESOURCE, response.status)
        self.assertFalse(response.batch.SerializeToString())

    def test_batch_get_with_block_id(self):
        """Verifies requests for a batch break properly with a block id.

        Expects to find:
            - a status of INVALID_ID
            - that the Batch returned, when serialized, is actually empty
        """
        response = self.make_request(batch_id='B-1')

        self.assertEqual(self.status.INVALID_ID, response.status)
        self.assertFalse(response.batch.SerializeToString())

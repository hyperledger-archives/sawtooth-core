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

import sawtooth_validator.state.client_handlers as handlers
from sawtooth_validator.protobuf import client_block_pb2
from sawtooth_validator.protobuf.block_pb2 import Block
from test_client_request_handlers.base_case import ClientHandlerTestCase
from test_client_request_handlers.mocks import MockBlockStore


B_0 = 'b' * 127 + '0'
B_1 = 'b' * 127 + '1'
B_2 = 'b' * 127 + '2'
A_1 = 'a' * 127 + '1'
C_1 = 'c' * 127 + '1'


class TestBlockListRequests(ClientHandlerTestCase):
    def setUp(self):
        store = MockBlockStore()
        self.initialize(
            handlers.BlockListRequest(store),
            client_block_pb2.ClientBlockListRequest,
            client_block_pb2.ClientBlockListResponse,
            store=store)

    def test_block_list_request(self):
        """Verifies requests for block lists without parameters work properly.

        Queries the default mock block store with three blocks:
            {header: {block_num: 2 ...}, header_signature: 'bbb...2' ...},
            {header: {block_num: 1 ...}, header_signature: 'bbb...1' ...},
            {header: {block_num: 0 ...}, header_signature: 'bbb...0' ...}

        Expects to find:
            - a status of OK
            - a head_id of 'bbb...2' (the latest)
            - a paging response with start of 'b' * 127 + '2' and limit 100
            - a list of blocks with 3 items
            - the items are instances of Block
            - The first item has a header_signature of 'bbb...2'
        """
        response = self.make_request()

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(B_2, response.head_id)
        self.assert_valid_paging(response, '0x0000000000000002', 100)
        self.assertEqual(3, len(response.blocks))
        self.assert_all_instances(response.blocks, Block)
        self.assertEqual(B_2, response.blocks[0].header_signature)

    def test_block_list_bad_protobufs(self):
        """Verifies requests for lists of blocks break with bad protobufs.

        Expects to find:
            - a status of INTERNAL_ERROR
            - that blocks, head_id, and paging are missing
        """
        response = self.make_bad_request(head_id=B_1)

        self.assertEqual(self.status.INTERNAL_ERROR, response.status)
        self.assertFalse(response.head_id)
        self.assertFalse(response.paging.SerializeToString())
        self.assertFalse(response.blocks)

    def test_block_list_no_genesis(self):
        """Verifies requests for lists of blocks break with no genesis.

        Expects to find:
            - a status of NOT_READY
            - that blocks, head_id, and paging are missing
        """
        self.break_genesis()
        response = self.make_request()

        self.assertEqual(self.status.NOT_READY, response.status)
        self.assertFalse(response.head_id)
        self.assertFalse(response.paging.SerializeToString())
        self.assertFalse(response.blocks)

    def test_block_list_with_head(self):
        """Verifies requests for lists of blocks work properly with a head id.

        Queries the default mock block store with '1' as the head:
            {header: {block_num: 1 ...}, header_signature: 'bbb...1' ...},
            {header: {block_num: 0 ...}, header_signature: 'bbb...0' ...}

        Expects to find:
            - a status of OK
            - a head_id of 'bbb...1'
            - a paging response with start of B_2 and limit 100
            - a list of blocks with 2 items
            - the items are instances of Block
            - The first item has a header_signature of 'bbb...1'
        """
        response = self.make_request(head_id=B_1)

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(B_1, response.head_id)
        self.assert_valid_paging(response, '0x0000000000000001', 100)
        self.assertEqual(2, len(response.blocks))
        self.assert_all_instances(response.blocks, Block)
        self.assertEqual(B_1, response.blocks[0].header_signature)

    def test_block_list_with_bad_head(self):
        """Verifies requests for lists of blocks break with a bad head.

        Expects to find:
            - a status of NO_ROOT
            - that blocks, head_id, and paging are missing
        """
        response = self.make_request(head_id='f' * 128)

        self.assertEqual(self.status.NO_ROOT, response.status)
        self.assertFalse(response.head_id)
        self.assertFalse(response.paging.SerializeToString())
        self.assertFalse(response.blocks)

    def test_block_list_filtered_by_ids(self):
        """Verifies requests for lists of blocks work filtered by block ids.

        Queries the default mock block store with three blocks:
            {header: {block_num: 2 ...}, header_signature: 'bbb...2' ...},
            {header: {block_num: 1 ...}, header_signature: 'bbb...1' ...},
            {header: {block_num: 0 ...}, header_signature: 'bbb...0' ...},

        Expects to find:
            - a status of OK
            - a head_id of 'bbb...2', the latest
            - an empty paging response
            - a list of blocks with 2 items
            - the items are instances of Block
            - the first item has a header_signature of 'bbb...0'
            - the second item has a header_signature of 'bbb...2'
        """
        response = self.make_request(block_ids=[B_0, B_2])

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(B_2, response.head_id)
        self.assert_valid_paging(response, "", 0)
        self.assertEqual(2, len(response.blocks))
        self.assert_all_instances(response.blocks, Block)
        self.assertEqual(B_0, response.blocks[0].header_signature)
        self.assertEqual(B_2, response.blocks[1].header_signature)

    def test_block_list_by_missing_ids(self):
        """Verifies block list requests break when ids are not found.

        Queries the default mock block store with three blocks:
            {header: {block_num: 2 ...}, header_signature: 'bbb...2' ...},
            {header: {block_num: 1 ...}, header_signature: 'bbb...1' ...},
            {header: {block_num: 0 ...}, header_signature: 'bbb...0' ...},

        Expects to find:
            - a status of NO_RESOURCE
            - a head_id of 'bbb...2', the latest
            - that blocks and paging are missing
        """
        response = self.make_request(block_ids=['f' * 128, 'e' * 128])

        self.assertEqual(self.status.NO_RESOURCE, response.status)
        self.assertEqual(B_2, response.head_id)
        self.assertFalse(response.paging.SerializeToString())
        self.assertFalse(response.blocks)

    def test_block_list_by_found_and_missing_ids(self):
        """Verifies block list requests work filtered by good and bad ids.

        Queries the default mock block store with three blocks:
            {header: {block_num: 2 ...}, header_signature: 'bbb...2' ...},
            {header: {block_num: 1 ...}, header_signature: 'bbb...1' ...},
            {header: {block_num: 0 ...}, header_signature: 'bbb...0' ...},

        Expects to find:
            - a status of OK
            - a head_id of 'bbb...2', the latest
            - an empty paging response
            - a list of blocks with 1 items
            - that item is an instances of Block
            - that item has a header_signature of 'bbb...1'
        """
        response = self.make_request(block_ids=['f' * 128, B_1])

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(B_2, response.head_id)
        self.assert_valid_paging(response, "", 0)
        self.assertEqual(1, len(response.blocks))
        self.assert_all_instances(response.blocks, Block)
        self.assertEqual(B_1, response.blocks[0].header_signature)

    def test_block_list_by_invalid_ids(self):
        """Verifies block list requests break when invalid ids are sent.

        Expects to find:
            - a status of INVALID_ID
            - that paging and blocks are missing
        """
        response = self.make_request(block_ids=['not', 'valid'])

        self.assertEqual(self.status.INVALID_ID, response.status)
        self.assertFalse(response.paging.SerializeToString())
        self.assertFalse(response.blocks)

    def test_block_list_by_head_and_ids(self):
        """Verifies block list requests work with both head and block ids.

        Queries the default mock block store with '1' as the head:
            {header: {block_num: 1 ...}, header_signature: 'bbb...1' ...},
            {header: {block_num: 0 ...}, header_signature: 'bbb...0' ...},

        Expects to find:
            - a status of OK
            - a head_id of 'bbb...1'
                - an empty paging response
            - a list of blocks with 1 item
            - that item is an instance of Block
            - that item has a header_signature of 'bbb...0'
        """
        response = self.make_request(head_id=B_1, block_ids=[B_0])

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(B_1, response.head_id)
        self.assert_valid_paging(response, "", 0)
        self.assertEqual(1, len(response.blocks))
        self.assert_all_instances(response.blocks, Block)
        self.assertEqual(B_0, response.blocks[0].header_signature)

    def test_block_list_head_ids_mismatch(self):
        """Verifies block list requests break when ids not found with head.

        Queries the default mock block store with '0' as the head:
            {header: {block_num: 0 ...}, header_signature: 'bbb...0' ...},

        Expects to find:
            - a status of NO_RESOURCE
            - a head_id of 'bbb...0'
            - that paging and blocks are missing
        """
        response = self.make_request(head_id=B_0, block_ids=[B_1, B_2])
        self.assertEqual(self.status.NO_RESOURCE, response.status)
        self.assertEqual(B_0, response.head_id)
        self.assertFalse(response.paging.SerializeToString())
        self.assertFalse(response.blocks)

    def test_block_list_paginated(self):
        """Verifies requests for block lists work when paginated just by limit.

        Queries the default mock block store with three blocks:
            {header: {block_num: 2 ...}, header_signature: B_2 ...},
            {header: {block_num: 1 ...}, header_signature: 'bbb...1' ...},
            {header: {block_num: 0 ...}, header_signature: 'bbb...0' ...},

        Expects to find:
            - a status of OK
            - a head_id of 'bbb...2', the latest
             a paging response with start of B_@, limit 100 and
                next of B_0
            - a list of blocks with 2 items
            - those items are instances of Block
            - the first item has a header_signature of 'bbb...2'
        """
        response = self.make_paged_request(limit=2)

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(B_2, response.head_id)
        self.assertEqual(2, len(response.blocks))
        self.assert_all_instances(response.blocks, Block)
        self.assertEqual(B_2, response.blocks[0].header_signature)
        self.assert_valid_paging(
            response,
            '0x0000000000000002',
            2,
            next_id=handlers.block_num_to_hex(0))

    def test_block_list_paginated_by_start(self):
        """Verifies block list requests work paginated by limit and start.

        Queries the default mock block store with three blocks:
            {header: {block_num: 2 ...}, header_signature: 'bbb...2' ...},
            {header: {block_num: 1 ...}, header_signature: 'bbb...1' ...},
            {header: {block_num: 0 ...}, header_signature: 'bbb...0' ...},

        Expects to find:
            - a status of OK
            - a head_id of 'bbb...2', the latest
            - a paging response with:
                * a next_id of '0x0000000000000000
                * a limit of 100
                * start of '0x0000000000000001'
            - a list of blocks with 1 item
            - that item is an instance of Block
            - that item has a header_signature of 'bbb...1'
        """
        response = self.make_paged_request(
            limit=1, start=handlers.block_num_to_hex(1))

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(B_2, response.head_id)
        self.assert_valid_paging(
            response,
            '0x0000000000000001',
            1,
            next_id=handlers.block_num_to_hex(0))
        self.assertEqual(1, len(response.blocks))
        self.assert_all_instances(response.blocks, Block)
        self.assertEqual(B_1, response.blocks[0].header_signature)

    def test_block_list_with_bad_pagination(self):
        """Verifies block requests break when paging specifies missing blocks.

        Queries the default mock block store with three blocks:
            {header: {block_num: 2 ...}, header_signature: 'bbb...2' ...},
            {header: {block_num: 1 ...}, header_signature: 'bbb...1' ...},
            {header: {block_num: 0 ...}, header_signature: 'bbb...0' ...},

        Expects to find:
            - a status of INVALID_PAGING
            - that head_id, paging, and blocks are missing
        """
        response = self.make_paged_request(limit=3, start='f' * 128)

        self.assertEqual(self.status.INVALID_PAGING, response.status)
        self.assertFalse(response.head_id)
        self.assertFalse(response.paging.SerializeToString())
        self.assertFalse(response.blocks)

    def test_block_list_sorted_by_bad_key(self):
        """Verifies block list requests break properly sorted by a bad key.

        Queries the default mock block store with three blocks:
            {header: {block_num: 2 ...}, header_signature: 'bbb...2' ...},
            {header: {block_num: 1 ...}, header_signature: 'bbb...1' ...},
            {header: {block_num: 0 ...}, header_signature: 'bbb...0' ...},

        Expects to find:
            - a status of INVALID_SORT
            - that head_id, paging, and blocks are missing
        """
        controls = self.make_sort_controls('f' * 128)
        response = self.make_request(sorting=controls)

        self.assertEqual(self.status.INVALID_SORT, response.status)
        self.assertFalse(response.head_id)
        self.assertFalse(response.paging.SerializeToString())
        self.assertFalse(response.blocks)

    def test_block_list_sorted_in_reverse(self):
        """Verifies block list requests work sorted in reverse.

        Queries the default mock block store with three blocks:
            {header: {block_num: 2 ...}, header_signature: 'bbb...2' ...},
            {header: {block_num: 1 ...}, header_signature: 'bbb...1' ...},
            {header: {block_num: 0 ...}, header_signature: 'bbb...0' ...},

        Expects to find:
            - a status of OK
            - a head_id of 'bbb...2', the latest
            - a paging response with start of B_) and limit 100
            - a list of blocks with 3 items
            - the items are instances of Block
            - the first item has a header_signature of 'bbb...2'
            - the last item has a header_signature of 'bbb...0'
        """
        controls = self.make_sort_controls('block_num', reverse=True)
        response = self.make_request(sorting=controls)

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(B_2, response.head_id)
        self.assert_valid_paging(response, '0x0000000000000000', 100)
        self.assertEqual(3, len(response.blocks))
        self.assert_all_instances(response.blocks, Block)
        self.assertEqual(B_0, response.blocks[0].header_signature)
        self.assertEqual(B_2, response.blocks[2].header_signature)


class TestBlockGetByIdRequests(ClientHandlerTestCase):
    def setUp(self):
        store = MockBlockStore()
        self.initialize(
            handlers.BlockGetByIdRequest(store),
            client_block_pb2.ClientBlockGetByIdRequest,
            client_block_pb2.ClientBlockGetResponse)

    def test_block_get_request(self):
        """Verifies requests for a specific block by id work properly.

        Queries the default three block mock store for an id of 'bbb...1'.
        Expects to find:
            - a status of OK
            - the block property which is an instances of Block
            - The block has a header_signature of 'bbb...1'
        """
        response = self.make_request(block_id=B_1)

        self.assertEqual(self.status.OK, response.status)
        self.assertIsInstance(response.block, Block)
        self.assertEqual(B_1, response.block.header_signature)

    def test_block_get_bad_request(self):
        """Verifies requests for a specific block break with a bad protobuf.

        Expects to find:
            - a status of INTERNAL_ERROR
            - that the Block returned, when serialized, is empty
        """
        response = self.make_bad_request(block_id=B_1)

        self.assertEqual(self.status.INTERNAL_ERROR, response.status)
        self.assertFalse(response.block.SerializeToString())

    def test_block_get_with_missing_id(self):
        """Verifies requests for a specific block break with an unfound id.

        Expects to find:
            - a status of NO_RESOURCE
            - that the Block returned, when serialized, is empty
        """
        response = self.make_request(block_id='f' * 128)

        self.assertEqual(self.status.NO_RESOURCE, response.status)
        self.assertFalse(response.block.SerializeToString())

    def test_block_get_with_invalid_id(self):
        """Verifies requests for a specific block break with an invalid id.

        Expects to find:
            - a status of INVALID_ID
            - that the Block returned, when serialized, is actually empty
        """
        response = self.make_request(block_id='invalid')

        self.assertEqual(self.status.INVALID_ID, response.status)
        self.assertFalse(response.block.SerializeToString())

    def test_block_get_with_batch_id(self):
        """Verifies requests for a block break properly with a batch id.

        Expects to find:
            - a status of NO_RESOURCE
            - that the Block returned, when serialized, is empty
        """
        response = self.make_request(block_id=A_1)

        self.assertEqual(self.status.NO_RESOURCE, response.status)
        self.assertFalse(response.block.SerializeToString())


class TestBlockGetByTransactionRequests(ClientHandlerTestCase):
    def setUp(self):
        store = MockBlockStore()
        self.initialize(
            handlers.BlockGetByTransactionRequest(store),
            client_block_pb2.ClientBlockGetByTransactionIdRequest,
            client_block_pb2.ClientBlockGetResponse)

    def test_block_get_request(self):
        """Verifies requests for a specific block by transaction work properly.

        Expects to find:
            - a status of OK
            - the block property which is an instances of Block
            - The block has a header_signature of 'bbb...1'
        """
        response = self.make_request(transaction_id=C_1)

        self.assertEqual(self.status.OK, response.status)
        self.assertIsInstance(response.block, Block)
        self.assertEqual(B_1, response.block.header_signature)

    def test_block_get_bad_request(self):
        """Verifies requests for a specific block break with a bad protobuf.

        Expects to find:
            - a status of INTERNAL_ERROR
            - that the Block returned, when serialized, is empty
        """
        response = self.make_bad_request(transaction_id=C_1)

        self.assertEqual(self.status.INTERNAL_ERROR, response.status)
        self.assertFalse(response.block.SerializeToString())

    def test_block_get_with_bad_id(self):
        """Verifies requests for a specific block break with a bad id.

        Expects to find:
            - a status of NO_RESOURCE
            - that the Block returned, when serialized, is empty
        """
        response = self.make_request(transaction_id='f' * 128)

        self.assertEqual(self.status.NO_RESOURCE, response.status)
        self.assertFalse(response.block.SerializeToString())


class TestBlockGetByBatchRequests(ClientHandlerTestCase):
    def setUp(self):
        store = MockBlockStore()
        self.initialize(
            handlers.BlockGetByBatchRequest(store),
            client_block_pb2.ClientBlockGetByBatchIdRequest,
            client_block_pb2.ClientBlockGetResponse)

    def test_block_get_request(self):
        """Verifies requests for a specific block by batch work properly.

        Expects to find:
            - a status of OK
            - the block property which is an instances of Block
            - The block has a header_signature of 'bbb...1'
        """
        response = self.make_request(batch_id=A_1)

        self.assertEqual(self.status.OK, response.status)
        self.assertIsInstance(response.block, Block)
        self.assertEqual(B_1, response.block.header_signature)

    def test_block_get_bad_request(self):
        """Verifies requests for a specific block break with a bad protobuf.

        Expects to find:
            - a status of INTERNAL_ERROR
            - that the Block returned, when serialized, is empty
        """
        response = self.make_bad_request(batch_id=A_1)

        self.assertEqual(self.status.INTERNAL_ERROR, response.status)
        self.assertFalse(response.block.SerializeToString())

    def test_block_get_with_bad_id(self):
        """Verifies requests for a specific block break with a bad id.

        Expects to find:
            - a status of NO_RESOURCE
            - that the Block returned, when serialized, is empty
        """
        response = self.make_request(batch_id='f' * 128)

        self.assertEqual(self.status.NO_RESOURCE, response.status)
        self.assertFalse(response.block.SerializeToString())

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
from sawtooth_validator.protobuf import client_pb2
from sawtooth_validator.protobuf.block_pb2 import Block
from test_client_request_handlers.base_case import ClientHandlerTestCase
from test_client_request_handlers.mocks import MockBlockStore


class TestBlockListRequests(ClientHandlerTestCase):
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

    def test_block_list_filtered_by_ids(self):
        """Verifies requests for lists of blocks work filtered by block ids.

        Queries the default mock block store with three blocks:
            {header: {block_num: 2 ...}, header_signature: 'B-2' ...},
            {header: {block_num: 1 ...}, header_signature: 'B-1' ...},
            {header: {block_num: 0 ...}, header_signature: 'B-0' ...},

        Expects to find:
            - a status of OK
            - a head_id of 'B-2', the latest
            - a list of blocks with 2 items
            - the items are instances of Block
            - the first item has a header_signature of 'B-0'
            - the second item has a header_signature of 'B-2'
        """
        response = self.make_request(block_ids=['B-0', 'B-2'])

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('B-2', response.head_id)
        self.assertEqual(2, len(response.blocks))
        self.assert_all_instances(response.blocks, Block)
        self.assertEqual('B-0', response.blocks[0].header_signature)
        self.assertEqual('B-2', response.blocks[1].header_signature)

    def test_block_list_by_bad_ids(self):
        """Verifies block list requests break when ids are not found.

        Queries the default mock block store with three blocks:
            {header: {block_num: 2 ...}, header_signature: 'B-2' ...},
            {header: {block_num: 1 ...}, header_signature: 'B-1' ...},
            {header: {block_num: 0 ...}, header_signature: 'B-0' ...},

        Expects to find:
            - a status of NO_RESOURCE
            - a head_id of 'B-2', the latest
            - that blocks is missing
        """
        response = self.make_request(block_ids=['bad', 'also-bad'])

        self.assertEqual(self.status.NO_RESOURCE, response.status)
        self.assertEqual('B-2', response.head_id)
        self.assertFalse(response.blocks)

    def test_block_list_by_good_and_bad_ids(self):
        """Verifies block list requests work filtered by good and bad ids.

        Queries the default mock block store with three blocks:
            {header: {block_num: 2 ...}, header_signature: 'B-2' ...},
            {header: {block_num: 1 ...}, header_signature: 'B-1' ...},
            {header: {block_num: 0 ...}, header_signature: 'B-0' ...},

        Expects to find:
            - a status of OK
            - a head_id of 'B-2', the latest
            - a list of blocks with 1 items
            - that item is an instances of Block
            - that item has a header_signature of 'B-1'
        """
        response = self.make_request(block_ids=['bad', 'B-1'])

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('B-2', response.head_id)
        self.assertEqual(1, len(response.blocks))
        self.assert_all_instances(response.blocks, Block)
        self.assertEqual('B-1', response.blocks[0].header_signature)

    def test_block_list_by_head_and_ids(self):
        """Verifies block list requests work with both head and block ids.

        Queries the default mock block store with '1' as the head:
            {header: {block_num: 1 ...}, header_signature: 'B-1' ...},
            {header: {block_num: 0 ...}, header_signature: 'B-0' ...},

        Expects to find:
            - a status of OK
            - a head_id of 'B-1'
            - a list of blocks with 1 item
            - that item is an instance of Block
            - that item has a header_signature of 'B-0'
        """
        response = self.make_request(head_id='B-1', block_ids=['B-0'])

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('B-1', response.head_id)
        self.assertEqual(1, len(response.blocks))
        self.assert_all_instances(response.blocks, Block)
        self.assertEqual('B-0', response.blocks[0].header_signature)

    def test_block_list_head_ids_mismatch(self):
        """Verifies block list requests break when ids not found with head.

        Queries the default mock block store with '0' as the head:
            {header: {block_num: 0 ...}, header_signature: 'B-0' ...},

        Expects to find:
            - a status of NO_RESOURCE
            - a head_id of 'B-0'
            - that blocks is missing
        """
        response = self.make_request(head_id='B-0', block_ids=['B-1', 'B-2'])
        self.assertEqual(self.status.NO_RESOURCE, response.status)
        self.assertEqual('B-0', response.head_id)
        self.assertFalse(response.blocks)

    def test_block_list_paginated(self):
        """Verifies requests for block lists work when paginated just by count.

        Queries the default mock block store with three blocks:
            {header: {block_num: 2 ...}, header_signature: 'B-2' ...},
            {header: {block_num: 1 ...}, header_signature: 'B-1' ...},
            {header: {block_num: 0 ...}, header_signature: 'B-0' ...},

        Expects to find:
            - a status of OK
            - a head_id of 'B-2', the latest
            - a paging response with a next_id of 'B-0'
            - a list of blocks with 2 items
            - those items are instances of Block
            - the first item has a header_signature of 'B-2'
        """
        response = self.make_paged_request(count=2)

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('B-2', response.head_id)
        self.assert_valid_paging(response, next_id='B-0')
        self.assertEqual(2, len(response.blocks))
        self.assert_all_instances(response.blocks, Block)
        self.assertEqual('B-2', response.blocks[0].header_signature)

    def test_block_list_paginated_by_start_id (self):
        """Verifies block list requests work paginated by count and start_id.

        Queries the default mock block store with three blocks:
            {header: {block_num: 2 ...}, header_signature: 'B-2' ...},
            {header: {block_num: 1 ...}, header_signature: 'B-1' ...},
            {header: {block_num: 0 ...}, header_signature: 'B-0' ...},

        Expects to find:
            - a status of OK
            - a head_id of 'B-2', the latest
            - a paging response with:
                * a next_id of 'B-0'
                * a previous_id of 'B-2'
                * a start_index of 1
                * the default total resource count of 3
            - a list of blocks with 1 item
            - that item is an instance of Block
            - that item has a header_signature of 'B-1'
        """
        response = self.make_paged_request(count=1, start_id='B-1')

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('B-2', response.head_id)
        self.assert_valid_paging(response, 'B-0', 'B-2', 1)
        self.assertEqual(1, len(response.blocks))
        self.assert_all_instances(response.blocks, Block)
        self.assertEqual('B-1', response.blocks[0].header_signature)

    def test_block_list_paginated_by_end_id (self):
        """Verifies block list requests work paginated by count and end_id.

        Queries the default mock block store with three blocks:
            {header: {block_num: 2 ...}, header_signature: 'B-2' ...},
            {header: {block_num: 1 ...}, header_signature: 'B-1' ...},
            {header: {block_num: 0 ...}, header_signature: 'B-0' ...},

        Expects to find:
            - a status of OK
            - a head_id of 'B-2', the latest
            - a paging response with:
                * the default missing next_id
                * a previous_id of 'B-2'
                * a start_index of 1
                * the default total resource count of 3
            - a list of blocks with 2 items
            - those items are instances of Block
            - the first item has a header_signature of 'B-1'
        """
        response = self.make_paged_request(count=2, end_id='B-0')

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('B-2', response.head_id)
        self.assert_valid_paging(response, previous_id='B-2', start_index=1)
        self.assertEqual(2, len(response.blocks))
        self.assert_all_instances(response.blocks, Block)
        self.assertEqual('B-1', response.blocks[0].header_signature)

    def test_block_list_paginated_by_index (self):
        """Verifies block list requests work paginated by count and min_index.

        Queries the default mock block store with three blocks:
            {header: {block_num: 2 ...}, header_signature: 'B-2' ...},
            {header: {block_num: 1 ...}, header_signature: 'B-1' ...},
            {header: {block_num: 0 ...}, header_signature: 'B-0' ...},

        Expects to find:
            - a status of OK
            - a head_id of 'B-2', the latest
            - a paging response with a next_id of 'B-1'
            - a list of blocks with 1 item
            - that item is an instance of Block
            - that item has a header_signature of 'B-2'
        """
        response = self.make_paged_request(count=1, start_index=0)

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('B-2', response.head_id)
        self.assert_valid_paging(response, next_id='B-1')
        self.assertEqual(1, len(response.blocks))
        self.assert_all_instances(response.blocks, Block)
        self.assertEqual('B-2', response.blocks[0].header_signature)

    def test_block_list_with_bad_pagination(self):
        """Verifies block requests break when paging specifies missing blocks.

        Queries the default mock block store with three blocks:
            {header: {block_num: 2 ...}, header_signature: 'B-2' ...},
            {header: {block_num: 1 ...}, header_signature: 'B-1' ...},
            {header: {block_num: 0 ...}, header_signature: 'B-0' ...},

        Expects to find:
            - a status of NO_RESOURCE
            - a head_id of 'B-2', the latest
            - that paging and blocks are missing
        """
        response = self.make_paged_request(count=3, start_id='bad')

        self.assertEqual(self.status.NO_RESOURCE, response.status)
        self.assertEqual('B-2', response.head_id)
        self.assertFalse(response.paging.SerializeToString())
        self.assertFalse(response.blocks)

    def test_block_list_paginated_with_head (self):
        """Verifies block list requests work with both paging and a head id.

        Queries the default mock block store with 'B-1' as the head:
            {header: {block_num: 1 ...}, header_signature: 'B-1' ...},
            {header: {block_num: 0 ...}, header_signature: 'B-0' ...}

        Expects to find:
            - a status of OK
            - a head_id of 'B-1'
            - a paging response with:
                * a missing next_id
                * a previous_id of 'B-1'
                * a start_index of 1
                * a total resource count of 2
            - a list of blocks with 1 item
            - that item is an instance of Block
            - that has a header_signature of 'B-0'
        """
        response = self.make_paged_request(count=1, start_index=1, head_id='B-1')

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('B-1', response.head_id)
        self.assert_valid_paging(response, '', 'B-1', 1, 2)
        self.assertEqual(1, len(response.blocks))
        self.assert_all_instances(response.blocks, Block)
        self.assertEqual('B-0', response.blocks[0].header_signature)


class TestBlockGetRequests(ClientHandlerTestCase):
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

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
from sawtooth_validator.protobuf import client_batch_pb2
from sawtooth_validator.protobuf.batch_pb2 import Batch
from test_client_request_handlers.base_case import ClientHandlerTestCase
from test_client_request_handlers.mocks import MockBlockStore


B_0 = 'b' * 127 + '0'
B_1 = 'b' * 127 + '1'
B_2 = 'b' * 127 + '2'
A_0 = 'a' * 127 + '0'
A_1 = 'a' * 127 + '1'
A_2 = 'a' * 127 + '2'


class TestBatchListRequests(ClientHandlerTestCase):
    def setUp(self):
        store = MockBlockStore()
        self.initialize(
            handlers.BatchListRequest(store),
            client_batch_pb2.ClientBatchListRequest,
            client_batch_pb2.ClientBatchListResponse,
            store=store)

    def test_batch_list_request(self):
        """Verifies requests for batch lists without parameters work properly.

        Queries the default mock block store with three blocks:
            {
                header_signature: 'bbb...2',
                 batches: [{header_signature: 'aaa...2' ...}] ...
            }
            {
                header_signature: 'bbb...1',
                 batches: [{header_signature: 'aaa...1' ...}] ...
            }
            {
                header_signature: 'bbb...0',
                 batches: [{header_signature: 'aaa...0' ...}] ...
            }

        Expects to find:
            - a status of OK
            - a head_id of 'bbb...2' (the latest)
            - a paging response with a start of A_2 and 100
            - a list of batches with 3 items
            - the items are instances of Batch
            - the first item has a header_signature of 'aaa...2'
        """
        response = self.make_request()

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(B_2, response.head_id)
        self.assert_valid_paging(response, A_2, 100)
        self.assertEqual(3, len(response.batches))
        self.assert_all_instances(response.batches, Batch)
        self.assertEqual(A_2, response.batches[0].header_signature)

    def test_batch_list_bad_protobufs(self):
        """Verifies requests for lists of batches break with bad protobufs.

        Expects to find:
            - a status of INTERNAL_ERROR
            - that head_id, paging, and batches are missing
        """
        response = self.make_bad_request(head_id=B_1)

        self.assertEqual(self.status.INTERNAL_ERROR, response.status)
        self.assertFalse(response.head_id)
        self.assertFalse(response.paging.SerializeToString())
        self.assertFalse(response.batches)

    def test_batch_list_no_genesis(self):
        """Verifies requests for lists of batches break with no genesis.

        Expects to find:
            - a status of NOT_READY
            - that head_id, paging, and batches are missing
        """
        self.break_genesis()
        response = self.make_request()

        self.assertEqual(self.status.NOT_READY, response.status)
        self.assertFalse(response.head_id)
        self.assertFalse(response.paging.SerializeToString())
        self.assertFalse(response.batches)

    def test_batch_list_with_head(self):
        """Verifies requests for lists of batches work properly with a head id.

        Queries the default mock block store with '1' as the head:
            {
                header_signature: 'bbb...1',
                 batches: [{header_signature: 'aaa...1' ...}] ...
            }
            {
                header_signature: 'bbb...0',
                 batches: [{header_signature: 'aaa...0' ...}] ...
            }

        Expects to find:
            - a status of OK
            - a head_id of 'bbb...1'
            - a paging response with start of A_1 and limit 100
            - a list of batches with 2 items
            - the items are instances of Batch
            - the first item has a header_signature of 'aaa...1'
        """
        response = self.make_request(head_id=B_1)

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(B_1, response.head_id)
        self.assert_valid_paging(response, A_1, 100)
        self.assertEqual(2, len(response.batches))
        self.assert_all_instances(response.batches, Batch)
        self.assertEqual(A_1, response.batches[0].header_signature)

    def test_batch_list_with_bad_head(self):
        """Verifies requests for lists of batches break with a bad head.

        Expects to find:
            - a status of NO_ROOT
            - that head_id, paging, and batches are missing
        """
        response = self.make_request(head_id='f' * 128)

        self.assertEqual(self.status.NO_ROOT, response.status)
        self.assertFalse(response.head_id)
        self.assertFalse(response.paging.SerializeToString())
        self.assertFalse(response.batches)

    def test_batch_list_filtered_by_ids(self):
        """Verifies requests for lists of batches work filtered by batch ids.

        Queries the default mock block store with three blocks:
            {
                header_signature: 'bbb...2',
                 batches: [{header_signature: 'aaa...2' ...}] ...
            }
            {
                header_signature: 'bbb...1',
                 batches: [{header_signature: 'aaa...1' ...}] ...
            }
            {
                header_signature: 'bbb...0',
                 batches: [{header_signature: 'aaa...0' ...}] ...
            }

        Expects to find:
            - a status of OK
            - a head_id of 'bbb...2', the latest
            - a paging response with start of A_0 and limit 100
            - a list of batches with 2 items
            - the items are instances of Batch
            - the first item has a header_signature of 'aaa...0'
            - the second item has a header_signature of 'aaa...2'
        """
        response = self.make_request(batch_ids=[A_0, A_2])

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(B_2, response.head_id)
        self.assert_valid_paging(response, A_0, 100)
        self.assertEqual(2, len(response.batches))
        self.assert_all_instances(response.batches, Batch)
        self.assertEqual(A_0, response.batches[0].header_signature)
        self.assertEqual(A_2, response.batches[1].header_signature)

    def test_batch_list_by_missing_ids(self):
        """Verifies batch list requests break when ids are not found.

        Queries the default mock block store with three blocks:
            {
                header_signature: 'bbb...2',
                 batches: [{header_signature: 'aaa...2' ...}] ...
            }
            {
                header_signature: 'bbb...1',
                 batches: [{header_signature: 'aaa...1' ...}] ...
            }
            {
                header_signature: 'bbb...0',
                 batches: [{header_signature: 'aaa...0' ...}] ...
            }

        Expects to find:
            - a status of NO_RESOURCE
            - a head_id of 'bbb...2', the latest
            - that paging and batches are missing
        """
        response = self.make_request(batch_ids=['f' * 128, 'e' * 128])

        self.assertEqual(self.status.NO_RESOURCE, response.status)
        self.assertEqual(B_2, response.head_id)
        self.assertFalse(response.paging.SerializeToString())
        self.assertFalse(response.batches)

    def test_batch_list_by_found_and_missing_ids(self):
        """Verifies batch list requests work filtered by good and bad ids.

        Queries the default mock block store with three blocks:
            {
                header_signature: 'bbb...2',
                 batches: [{header_signature: 'aaa...2' ...}] ...
            }
            {
                header_signature: 'bbb...1',
                 batches: [{header_signature: 'aaa...1' ...}] ...
            }
            {
                header_signature: 'bbb...0',
                 batches: [{header_signature: 'aaa...0' ...}] ...
            }

        Expects to find:
            - a status of OK
            - a head_id of 'bbb...2', the latest
            - a paging response with start of A_1 and limit 100
            - a list of batches with 1 items
            - that item is an instances of Batch
            - that item has a header_signature of 'aaa...1'
        """
        response = self.make_request(batch_ids=['f' * 128, A_1])

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(B_2, response.head_id)
        self.assert_valid_paging(response, A_1, 100)
        self.assertEqual(1, len(response.batches))
        self.assert_all_instances(response.batches, Batch)
        self.assertEqual(A_1, response.batches[0].header_signature)

    def test_batch_list_by_invalid_ids(self):
        """Verifies batch list requests break when invalid ids are sent.

        Expects to find:
            - a status of INVALID_ID
            - that paging and batches are missing
        """
        response = self.make_request(batch_ids=['not', 'valid'])

        self.assertEqual(self.status.INVALID_ID, response.status)
        self.assertFalse(response.paging.SerializeToString())
        self.assertFalse(response.batches)

    def test_batch_list_by_head_and_ids(self):
        """Verifies batch list requests work with both head and batch ids.

        Queries the default mock block store with '1' as the head:
            {
                header_signature: 'bbb...1',
                 batches: [{header_signature: 'aaa...1' ...}] ...
            }
            {
                header_signature: 'bbb...0',
                 batches: [{header_signature: 'aaa...0' ...}] ...
            }

        Expects to find:
            - a status of OK
            - a head_id of 'bbb...1'
            - a paging response with start of A_0 and limit 100
            - a list of batches with 1 item
            - that item is an instance of Batch
            - that item has a header_signature of 'aaa...0'
        """
        response = self.make_request(head_id=B_1, batch_ids=[A_0])

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(B_1, response.head_id)
        self.assert_valid_paging(response, A_0, 100)
        self.assertEqual(1, len(response.batches))
        self.assert_all_instances(response.batches, Batch)
        self.assertEqual(A_0, response.batches[0].header_signature)

    def test_batch_list_head_ids_mismatch(self):
        """Verifies batch list requests break when ids not found with head.

        Queries the default mock block store with '0' as the head:
            {
                header_signature: 'bbb...0',
                 batches: [{header_signature: 'aaa...0' ...}] ...
            }

        Expects to find:
            - a status of NO_RESOURCE
            - a head_id of 'bbb...0'
            - that paging and batches are missing
        """
        response = self.make_request(head_id=B_0, batch_ids=[A_1, A_2])

        self.assertEqual(self.status.NO_RESOURCE, response.status)
        self.assertEqual(B_0, response.head_id)
        self.assertFalse(response.paging.SerializeToString())
        self.assertFalse(response.batches)

    def test_batch_list_paginated(self):
        """Verifies requests for batch lists work when paginated just by limit.

        Queries the default mock block store:
            {
                header_signature: 'bbb...2',
                 batches: [{header_signature: 'aaa...1' ...}] ...
            }
            {
                header_signature: 'bbb...1',
                 batches: [{header_signature: 'aaa...1' ...}] ...
            }
            {
                header_signature: 'bbb...0',
                 batches: [{header_signature: 'aaa...0' ...}] ...
            }

        Expects to find:
            - a status of OK
            - a head_id of 'bbb...2', the latest
            - a paging response with start of A_2, limit 2, and next b-0
            - a list of batches with 2 items
            - those items are instances of Batch
            - the first item has a header_signature of 'aaa...2'
        """
        response = self.make_paged_request(limit=2)

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(B_2, response.head_id)
        self.assert_valid_paging(response, A_2, 2, next_id=A_0)
        self.assertEqual(2, len(response.batches))
        self.assert_all_instances(response.batches, Batch)
        self.assertEqual(A_2, response.batches[0].header_signature)

    def test_batch_list_paginated_by_start_id(self):
        """Verifies batch list requests work paginated by limit and start_id.

        Queries the default mock block store:
            {
                header_signature: 'bbb...2',
                 batches: [{header_signature: 'aaa...2' ...}] ...
            }
            {
                header_signature: 'bbb...1',
                 batches: [{header_signature: 'aaa...1' ...}] ...
            }
            {
                header_signature: 'bbb...0',
                 batches: [{header_signature: 'aaa...0' ...}] ...
            }

        Expects to find:
            - a status of OK
            - a head_id of 'bbb...2', the latest
            - a paging response with start of A_1 and limit 1, next A_2
            - a list of batches with 1 item
            - that item is an instance of Batch
            - that item has a header_signature of 'aaa...1'
        """
        response = self.make_paged_request(limit=1, start=A_1)

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(B_2, response.head_id)
        self.assert_valid_paging(response, A_1, 1, A_0)
        self.assertEqual(1, len(response.batches))
        self.assert_all_instances(response.batches, Batch)
        self.assertEqual(A_1, response.batches[0].header_signature)

    def test_batch_list_with_bad_pagination(self):
        """Verifies batch requests break when paging specifies missing batches.

        Queries the default mock block store:
            {
                header_signature: 'bbb...2',
                 batches: [{header_signature: 'aaa...2' ...}] ...
            }
            {
                header_signature: 'bbb...1',
                 batches: [{header_signature: 'aaa...1' ...}] ...
            }
            {
                header_signature: 'bbb...0',
                 batches: [{header_signature: 'aaa...0' ...}] ...
            }

        Expects to find:
            - a status of INVALID_PAGING
            - that head_id, paging, and batches are missing
        """
        response = self.make_paged_request(limit=3, start='f' * 128)

        self.assertEqual(self.status.INVALID_PAGING, response.status)
        self.assertFalse(response.head_id)
        self.assertFalse(response.paging.SerializeToString())
        self.assertFalse(response.batches)

    def test_batch_list_paginated_with_head(self):
        """Verifies batch list requests work with both paging and a head id.

        Queries the default mock block store with 'bbb...1' as the head:
            {
                header_signature: 'bbb...1',
                 batches: [{header_signature: 'aaa...1' ...}] ...
            }
            {
                header_signature: 'bbb...0',
                 batches: [{header_signature: 'aaa...0' ...}] ...
            }

        Expects to find:
            - a status of OK
            - a head_id of 'bbb...1'
            - a paging response with start of A_0 and limit 1
            - a list of batches with 1 item
            - that item is an instance of Batch
            - that has a header_signature of 'aaa...0'
        """
        response = self.make_paged_request(limit=1, start=A_0, head_id=B_1)

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(B_1, response.head_id)
        self.assert_valid_paging(response, A_0, 1)
        self.assertEqual(1, len(response.batches))
        self.assert_all_instances(response.batches, Batch)
        self.assertEqual(A_0, response.batches[0].header_signature)

    def test_batch_list_sorted_in_reverse(self):
        """Verifies batch list requests work sorted in reverse.

        Queries the default mock block store with three blocks:
            {
                header_signature: 'bbb...2',
                 batches: [{header_signature: 'aaa...2' ...}] ...
            }
            {
                header_signature: 'bbb...1',
                 batches: [{header_signature: 'aaa...1' ...}] ...
            }
            {
                header_signature: 'bbb...0',
                 batches: [{header_signature: 'aaa...0' ...}] ...
            }

        Expects to find:
            - a status of OK
            - a head_id of 'bbb...2', the latest
             a paging response with start of A_0 and limit 100
            - a list of batches with 3 items
            - the items are instances of Batch
            - the first item has a header_signature of 'aaa...2'
            - the last item has a header_signature of 'aaa...0'
        """
        controls = self.make_sort_controls('default', reverse=True)
        response = self.make_request(sorting=controls)

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(B_2, response.head_id)
        self.assert_valid_paging(response, A_0, 100)
        self.assertEqual(3, len(response.batches))
        self.assert_all_instances(response.batches, Batch)
        self.assertEqual(A_0, response.batches[0].header_signature)
        self.assertEqual(A_2, response.batches[2].header_signature)


class TestBatchGetRequests(ClientHandlerTestCase):
    def setUp(self):
        store = MockBlockStore()
        self.initialize(
            handlers.BatchGetRequest(store),
            client_batch_pb2.ClientBatchGetRequest,
            client_batch_pb2.ClientBatchGetResponse)

    def test_batch_get_request(self):
        """Verifies requests for a specific batch by id work properly.

        Queries the default three block mock store for a batch id of 'aaa...1'.
        Expects to find:
            - a status of OK
            - a batch property which is an instances of Batch
            - the batch has a header_signature of 'aaa...1'
        """
        response = self.make_request(batch_id=A_1)

        self.assertEqual(self.status.OK, response.status)
        self.assertIsInstance(response.batch, Batch)
        self.assertEqual(A_1, response.batch.header_signature)

    def test_batch_get_bad_request(self):
        """Verifies requests for a specific batch break with a bad protobuf.

        Expects to find:
            - a status of INTERNAL_ERROR
            - that the Batch returned, when serialized, is actually empty
        """
        response = self.make_bad_request(batch_id=A_1)

        self.assertEqual(self.status.INTERNAL_ERROR, response.status)
        self.assertFalse(response.batch.SerializeToString())

    def test_batch_get_with_missing_id(self):
        """Verifies requests for a specific batch break with an unfound id.

        Expects to find:
            - a status of NO_RESOURCE
            - that the Batch returned, when serialized, is actually empty
        """
        response = self.make_request(batch_id='f' * 128)

        self.assertEqual(self.status.NO_RESOURCE, response.status)
        self.assertFalse(response.batch.SerializeToString())

    def test_batch_get_with_invalid_id(self):
        """Verifies requests for a specific batch break with an invalid id.

        Expects to find:
            - a status of INVALID_ID
            - that the Batch returned, when serialized, is actually empty
        """
        response = self.make_request(batch_id='invalid')

        self.assertEqual(self.status.INVALID_ID, response.status)
        self.assertFalse(response.batch.SerializeToString())

    def test_batch_get_with_block_id(self):
        """Verifies requests for a batch break properly with a block id.

        Expects to find:
            - a status of NO_RESOURCE
            - that the Batch returned, when serialized, is actually empty
        """
        response = self.make_request(batch_id=B_1)

        self.assertEqual(self.status.NO_RESOURCE, response.status)
        self.assertFalse(response.batch.SerializeToString())

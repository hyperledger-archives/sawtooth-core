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
            {header_signature: 'b' * 127 + '2', batches: [{header_signature: 'b-2' ...}] ...}
            {header_signature: 'b' * 127 + '1', batches: [{header_signature: 'b-1' ...}] ...}
            {header_signature: 'b' * 127 + '0', batches: [{header_signature: 'b-0' ...}] ...}

        Expects to find:
            - a status of OK
            - a head_id of 'b' * 127 + '2' (the latest)
            - the default paging response, showing all 3 resources returned
            - a list of batches with 3 items
            - the items are instances of Batch
            - the first item has a header_signature of 'b-2'
        """
        response = self.make_request()

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('b' * 127 + '2', response.head_id)
        self.assert_valid_paging(response)
        self.assertEqual(3, len(response.batches))
        self.assert_all_instances(response.batches, Batch)
        self.assertEqual('b-2', response.batches[0].header_signature)

    def test_batch_list_bad_request(self):
        """Verifies requests for lists of batches break with bad protobufs.

        Expects to find:
            - a status of INTERNAL_ERROR
            - that head_id, paging, and batches are missing
        """
        response = self.make_bad_request(head_id='b' * 127 + '1')

        self.assertEqual(self.status.INTERNAL_ERROR, response.status)
        self.assertFalse(response.head_id)
        self.assertFalse(response.paging.SerializeToString())
        self.assertFalse(response.batches)

    def test_batch_list_bad_request(self):
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
            {header_signature: 'b' * 127 + '1', batches: [{header_signature: 'b-1' ...}] ...}
            {header_signature: 'b' * 127 + '0', batches: [{header_signature: 'b-0' ...}] ...}

        Expects to find:
            - a status of OK
            - a head_id of 'b' * 127 + '1'
            - a paging response showing all 2 resources returned
            - a list of batches with 2 items
            - the items are instances of Batch
            - the first item has a header_signature of 'b-1'
        """
        response = self.make_request(head_id='b' * 127 + '1')

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('b' * 127 + '1', response.head_id)
        self.assert_valid_paging(response, total=2)
        self.assertEqual(2, len(response.batches))
        self.assert_all_instances(response.batches, Batch)
        self.assertEqual('b-1', response.batches[0].header_signature)

    def test_batch_list_with_bad_head(self):
        """Verifies requests for lists of batches break with a bad head.

        Expects to find:
            - a status of NO_ROOT
            - that head_id, paging, and batches are missing
        """
        response = self.make_request(head_id='bad')

        self.assertEqual(self.status.NO_ROOT, response.status)
        self.assertFalse(response.head_id)
        self.assertFalse(response.paging.SerializeToString())
        self.assertFalse(response.batches)

    def test_batch_list_filtered_by_ids(self):
        """Verifies requests for lists of batches work filtered by batch ids.

        Queries the default mock block store with three blocks:
            {header_signature: 'b' * 127 + '2', batches: [{header_signature: 'b-2' ...}] ...}
            {header_signature: 'b' * 127 + '1', batches: [{header_signature: 'b-1' ...}] ...}
            {header_signature: 'b' * 127 + '0', batches: [{header_signature: 'b-0' ...}] ...}

        Expects to find:
            - a status of OK
            - a head_id of 'b' * 127 + '2', the latest
            - a paging response showing all 2 resources returned
            - a list of batches with 2 items
            - the items are instances of Batch
            - the first item has a header_signature of 'b-0'
            - the second item has a header_signature of 'b-2'
        """
        response = self.make_request(batch_ids=['b-0', 'b-2'])

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('b' * 127 + '2', response.head_id)
        self.assert_valid_paging(response, total=2)
        self.assertEqual(2, len(response.batches))
        self.assert_all_instances(response.batches, Batch)
        self.assertEqual('b-0', response.batches[0].header_signature)
        self.assertEqual('b-2', response.batches[1].header_signature)

    def test_batch_list_by_bad_ids(self):
        """Verifies batch list requests break when ids are not found.

        Queries the default mock block store with three blocks:
            {header_signature: 'b' * 127 + '2', batches: [{header_signature: 'b-2' ...}] ...}
            {header_signature: 'b' * 127 + '1', batches: [{header_signature: 'b-1' ...}] ...}
            {header_signature: 'b' * 127 + '0', batches: [{header_signature: 'b-0' ...}] ...}

        Expects to find:
            - a status of NO_RESOURCE
            - a head_id of 'b' * 127 + '2', the latest
            - that paging and batches are missing
        """
        response = self.make_request(batch_ids=['bad', 'also-bad'])

        self.assertEqual(self.status.NO_RESOURCE, response.status)
        self.assertEqual('b' * 127 + '2', response.head_id)
        self.assertFalse(response.paging.SerializeToString())
        self.assertFalse(response.batches)

    def test_batch_list_by_good_and_bad_ids(self):
        """Verifies batch list requests work filtered by good and bad ids.

        Queries the default mock block store with three blocks:
            {header_signature: 'b' * 127 + '2', batches: [{header_signature: 'b-2' ...}] ...}
            {header_signature: 'b' * 127 + '1', batches: [{header_signature: 'b-1' ...}] ...}
            {header_signature: 'b' * 127 + '0', batches: [{header_signature: 'b-0' ...}] ...}

        Expects to find:
            - a status of OK
            - a head_id of 'b' * 127 + '2', the latest
            - a paging response showing all 1 resources returned
            - a list of batches with 1 items
            - that item is an instances of Batch
            - that item has a header_signature of 'b-1'
        """
        response = self.make_request(batch_ids=['bad', 'b-1'])

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('b' * 127 + '2', response.head_id)
        self.assert_valid_paging(response, total=1)
        self.assertEqual(1, len(response.batches))
        self.assert_all_instances(response.batches, Batch)
        self.assertEqual('b-1', response.batches[0].header_signature)

    def test_batch_list_by_head_and_ids(self):
        """Verifies batch list requests work with both head and batch ids.

        Queries the default mock block store with '1' as the head:
            {header_signature: 'b' * 127 + '1', batches: [{header_signature: 'b-1' ...}] ...}
            {header_signature: 'b' * 127 + '0', batches: [{header_signature: 'b-0' ...}] ...}

        Expects to find:
            - a status of OK
            - a head_id of 'b' * 127 + '1'
            - a paging response showing all 1 resources returned
            - a list of batches with 1 item
            - that item is an instance of Batch
            - that item has a header_signature of 'b-0'
        """
        response = self.make_request(head_id='b' * 127 + '1', batch_ids=['b-0'])

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('b' * 127 + '1', response.head_id)
        self.assert_valid_paging(response, total=1)
        self.assertEqual(1, len(response.batches))
        self.assert_all_instances(response.batches, Batch)
        self.assertEqual('b-0', response.batches[0].header_signature)

    def test_batch_list_head_ids_mismatch(self):
        """Verifies batch list requests break when ids not found with head.

        Queries the default mock block store with '0' as the head:
            {header_signature: 'b' * 127 + '0', batches: [{header_signature: 'b-0' ...}] ...}

        Expects to find:
            - a status of NO_RESOURCE
            - a head_id of 'b' * 127 + '0'
            - that paging and batches are missing
        """
        response = self.make_request(head_id='b' * 127 + '0', batch_ids=['b-1', 'b-2'])

        self.assertEqual(self.status.NO_RESOURCE, response.status)
        self.assertEqual('b' * 127 + '0', response.head_id)
        self.assertFalse(response.paging.SerializeToString())
        self.assertFalse(response.batches)

    def test_batch_list_paginated(self):
        """Verifies requests for batch lists work when paginated just by count.

        Queries the default mock block store:
            {header_signature: 'b' * 127 + '2', batches: [{header_signature: 'b-2' ...}] ...}
            {header_signature: 'b' * 127 + '1', batches: [{header_signature: 'b-1' ...}] ...}
            {header_signature: 'b' * 127 + '0', batches: [{header_signature: 'b-0' ...}] ...}

        Expects to find:
            - a status of OK
            - a head_id of 'b' * 127 + '2', the latest
            - a paging response with:
                * a next_id of 'b-0'
                * the default empty previous_id
                * the default start_index of 0
                * the default total resource count of 3
            - a list of batches with 2 items
            - those items are instances of Batch
            - the first item has a header_signature of 'b-2'
        """
        response = self.make_paged_request(count=2)

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('b' * 127 + '2', response.head_id)
        self.assert_valid_paging(response, next_id='b-0')
        self.assertEqual(2, len(response.batches))
        self.assert_all_instances(response.batches, Batch)
        self.assertEqual('b-2', response.batches[0].header_signature)

    def test_batch_list_paginated_by_start_id (self):
        """Verifies batch list requests work paginated by count and start_id.

        Queries the default mock block store:
            {header_signature: 'b' * 127 + '2', batches: [{header_signature: 'b-2' ...}] ...}
            {header_signature: 'b' * 127 + '1', batches: [{header_signature: 'b-1' ...}] ...}
            {header_signature: 'b' * 127 + '0', batches: [{header_signature: 'b-0' ...}] ...}

        Expects to find:
            - a status of OK
            - a head_id of 'b' * 127 + '2', the latest
            - a paging response with:
                * a next_id of 'b-0'
                * a previous_id of 'b-2'
                * a start_index of 1
                * the default total resource count of 3
            - a list of batches with 1 item
            - that item is an instance of Batch
            - that item has a header_signature of 'b-1'
        """
        response = self.make_paged_request(count=1, start_id='b-1')

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('b' * 127 + '2', response.head_id)
        self.assert_valid_paging(response, 'b-0', 'b-2', 1)
        self.assertEqual(1, len(response.batches))
        self.assert_all_instances(response.batches, Batch)
        self.assertEqual('b-1', response.batches[0].header_signature)

    def test_batch_list_paginated_by_end_id (self):
        """Verifies batch list requests work paginated by count and end_id.

        Queries the default mock block store:
            {header_signature: 'b' * 127 + '2', batches: [{header_signature: 'b-2' ...}] ...}
            {header_signature: 'b' * 127 + '1', batches: [{header_signature: 'b-1' ...}] ...}
            {header_signature: 'b' * 127 + '0', batches: [{header_signature: 'b-0' ...}] ...}

        Expects to find:
            - a status of OK
            - a head_id of 'b' * 127 + '2', the latest
            - a paging response with:
                * the default empty next_id
                * a previous_id of 'b-2'
                * a start_index of 1
                * the default total resource count of 3
            - a list of batches with 2 items
            - those items are instances of Batch
            - the first item has a header_signature of 'b-1'
        """
        response = self.make_paged_request(count=2, end_id='b-0')

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('b' * 127 + '2', response.head_id)
        self.assert_valid_paging(response, previous_id='b-2', start_index=1)
        self.assertEqual(2, len(response.batches))
        self.assert_all_instances(response.batches, Batch)
        self.assertEqual('b-1', response.batches[0].header_signature)

    def test_batch_list_paginated_by_index (self):
        """Verifies batch list requests work paginated by count and min_index.

        Queries the default mock block store:
            {header_signature: 'b' * 127 + '2', batches: [{header_signature: 'b-2' ...}] ...}
            {header_signature: 'b' * 127 + '1', batches: [{header_signature: 'b-1' ...}] ...}
            {header_signature: 'b' * 127 + '0', batches: [{header_signature: 'b-0' ...}] ...}

        Expects to find:
            - a status of OK
            - a head_id of 'b' * 127 + '2', the latest
            - a paging response with a next_id of 'b-1'
            - a list of batches with 1 item
            - that item is an instance of Batch
            - that item has a header_signature of 'b-2'
        """
        response = self.make_paged_request(count=1, start_index=0)

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('b' * 127 + '2', response.head_id)
        self.assert_valid_paging(response, next_id='b-1')
        self.assertEqual(1, len(response.batches))
        self.assert_all_instances(response.batches, Batch)
        self.assertEqual('b-2', response.batches[0].header_signature)

    def test_batch_list_with_bad_pagination(self):
        """Verifies batch requests break when paging specifies missing batches.

        Queries the default mock block store:
            {header_signature: 'b' * 127 + '2', batches: [{header_signature: 'b-2' ...}] ...}
            {header_signature: 'b' * 127 + '1', batches: [{header_signature: 'b-1' ...}] ...}
            {header_signature: 'b' * 127 + '0', batches: [{header_signature: 'b-0' ...}] ...}

        Expects to find:
            - a status of INVALID_PAGING
            - that head_id, paging, and batches are missing
        """
        response = self.make_paged_request(count=3, start_id='bad')

        self.assertEqual(self.status.INVALID_PAGING, response.status)
        self.assertFalse(response.head_id)
        self.assertFalse(response.paging.SerializeToString())
        self.assertFalse(response.batches)

    def test_batch_list_paginated_with_head (self):
        """Verifies batch list requests work with both paging and a head id.

        Queries the default mock block store with 'b' * 127 + '1' as the head:
            {header_signature: 'b' * 127 + '1', batches: [{header_signature: 'b-1' ...}] ...}
            {header_signature: 'b' * 127 + '0', batches: [{header_signature: 'b-0' ...}] ...}

        Expects to find:
            - a status of OK
            - a head_id of 'b' * 127 + '1'
            - a paging response with:
                * an empty next_id
                * a previous_id of 'b-1'
                * a start_index of 1
                * a total resource count of 2
            - a list of batches with 1 item
            - that item is an instance of Batch
            - that has a header_signature of 'b-0'
        """
        response = self.make_paged_request(count=1, start_index=1, head_id='b' * 127 + '1')

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('b' * 127 + '1', response.head_id)
        self.assert_valid_paging(response, '', 'b-1', 1, 2)
        self.assertEqual(1, len(response.batches))
        self.assert_all_instances(response.batches, Batch)
        self.assertEqual('b-0', response.batches[0].header_signature)

    def test_batch_list_sorted_by_key(self):
        """Verifies batch list requests work sorted by header_signature.

        Queries the default mock block store with three blocks:
            {header_signature: 'b' * 127 + '2', batches: [{header_signature: 'b-2' ...}] ...}
            {header_signature: 'b' * 127 + '1', batches: [{header_signature: 'b-1' ...}] ...}
            {header_signature: 'b' * 127 + '0', batches: [{header_signature: 'b-0' ...}] ...}

        Expects to find:
            - a status of OK
            - a head_id of 'b' * 127 + '2', the latest
            - a paging response showing all 3 resources returned
            - a list of batches with 3 items
            - the items are instances of Batch
            - the first item has a header_signature of 'b-0'
            - the last item has a header_signature of 'b-2'
        """
        controls = self.make_sort_controls('header_signature')
        response = self.make_request(sorting=controls)

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('b' * 127 + '2', response.head_id)
        self.assert_valid_paging(response)
        self.assertEqual(3, len(response.batches))
        self.assert_all_instances(response.batches, Batch)
        self.assertEqual('b-0', response.batches[0].header_signature)
        self.assertEqual('b-2', response.batches[2].header_signature)

    def test_batch_list_sorted_by_bad_key(self):
        """Verifies batch list requests break properly sorted by a bad key.

        Queries the default mock block store with three blocks:
            {header_signature: 'b' * 127 + '2', batches: [{header_signature: 'b-2' ...}] ...}
            {header_signature: 'b' * 127 + '1', batches: [{header_signature: 'b-1' ...}] ...}
            {header_signature: 'b' * 127 + '0', batches: [{header_signature: 'b-0' ...}] ...}

        Expects to find:
            - a status of INVALID_SORT
            - that head_id, paging, and batches are missing
        """
        controls = self.make_sort_controls('bad')
        response = self.make_request(sorting=controls)

        self.assertEqual(self.status.INVALID_SORT, response.status)
        self.assertFalse(response.head_id)
        self.assertFalse(response.paging.SerializeToString())
        self.assertFalse(response.batches)

    def test_batch_list_sorted_by_nested_key(self):
        """Verifies batch list requests work sorted by header.signer_public_key.

        Queries the default mock block store with three blocks:
            {header_signature: 'b' * 127 + '2', batches: [{header_signature: 'b-2' ...}] ...}
            {header_signature: 'b' * 127 + '1', batches: [{header_signature: 'b-1' ...}] ...}
            {header_signature: 'b' * 127 + '0', batches: [{header_signature: 'b-0' ...}] ...}

        Expects to find:
            - a status of OK
            - a head_id of 'b' * 127 + '2', the latest
            - a paging response showing all 3 resources returned
            - a list of batches with 3 items
            - the items are instances of Batch
            - the first item has a header_signature of 'b-0'
            - the last item has a header_signature of 'b-2'
        """
        controls = self.make_sort_controls('header', 'signer_public_key')
        response = self.make_request(sorting=controls)

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('b' * 127 + '2', response.head_id)
        self.assert_valid_paging(response)
        self.assertEqual(3, len(response.batches))
        self.assert_all_instances(response.batches, Batch)
        self.assertEqual('b-0', response.batches[0].header_signature)
        self.assertEqual('b-2', response.batches[2].header_signature)

    def test_batch_list_sorted_by_implied_header(self):
        """Verifies batch list requests work sorted by an implicit header key.

        Queries the default mock block store with three blocks:
            {header_signature: 'b' * 127 + '2', batches: [{header_signature: 'b-2' ...}] ...}
            {header_signature: 'b' * 127 + '1', batches: [{header_signature: 'b-1' ...}] ...}
            {header_signature: 'b' * 127 + '0', batches: [{header_signature: 'b-0' ...}] ...}

        Expects to find:
            - a status of OK
            - a head_id of 'b' * 127 + '2', the latest
            - a paging response showing all 3 resources returned
            - a list of batches with 3 items
            - the items are instances of Batch
            - the first item has a header_signature of 'b-0'
            - the last item has a header_signature of 'b-2'
        """
        controls = self.make_sort_controls('signer_public_key')
        response = self.make_request(sorting=controls)

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('b' * 127 + '2', response.head_id)
        self.assert_valid_paging(response)
        self.assertEqual(3, len(response.batches))
        self.assert_all_instances(response.batches, Batch)
        self.assertEqual('b-0', response.batches[0].header_signature)
        self.assertEqual('b-2', response.batches[2].header_signature)

    def test_batch_list_sorted_in_reverse(self):
        """Verifies batch list requests work sorted by a key in reverse.

        Queries the default mock block store with three blocks:
            {header_signature: 'b' * 127 + '2', batches: [{header_signature: 'b-2' ...}] ...}
            {header_signature: 'b' * 127 + '1', batches: [{header_signature: 'b-1' ...}] ...}
            {header_signature: 'b' * 127 + '0', batches: [{header_signature: 'b-0' ...}] ...}

        Expects to find:
            - a status of OK
            - a head_id of 'b' * 127 + '2', the latest
            - a paging response showing all 3 resources returned
            - a list of batches with 3 items
            - the items are instances of Batch
            - the first item has a header_signature of 'b-2'
            - the last item has a header_signature of 'b-0'
        """
        controls = self.make_sort_controls('header_signature', reverse=True)
        response = self.make_request(sorting=controls)

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('b' * 127 + '2', response.head_id)
        self.assert_valid_paging(response)
        self.assertEqual(3, len(response.batches))
        self.assert_all_instances(response.batches, Batch)
        self.assertEqual('b-2', response.batches[0].header_signature)
        self.assertEqual('b-0', response.batches[2].header_signature)

    def test_batch_list_sorted_by_length(self):
        """Verifies batch list requests work sorted by a property's length.

        Queries the default mock block store with two added blocks:
            {header_signature: 'b' * 127 + 'long', batches: [{header_signature: 'b-long' ...}] ...}
            {header_signature: 'b' * 127 + 'longest', batches: [{header_signature: 'b-longest' ...}] ...}
            {header_signature: 'b' * 127 + '2', batches: [{header_signature: 'b-2' ...}] ...}
            {header_signature: 'b' * 127 + '1', batches: [{header_signature: 'b-1' ...}] ...}
            {header_signature: 'b' * 127 + '0', batches: [{header_signature: 'b-0' ...}] ...}

        Expects to find:
            - a status of OK
            - a head_id of 'b' * 127 + 'long', the latest
            - a paging response showing all 5 resources returned
            - a list of batches with 5 items
            - the items are instances of Batch
            - the second to last item has a header_signature of 'b' * 127 + 'long'
            - the last item has a header_signature of 'b' * 127 + 'longest'
        """
        self.add_blocks('longest', 'long')
        controls = self.make_sort_controls(
            'header_signature', compare_length=True)
        response = self.make_request(sorting=controls)

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('b' * 124 + 'long', response.head_id)
        self.assert_valid_paging(response, total=5)
        self.assertEqual(5, len(response.batches))
        self.assert_all_instances(response.batches, Batch)
        self.assertEqual('b-long', response.batches[3].header_signature)
        self.assertEqual('b-longest', response.batches[4].header_signature)


class TestBatchGetRequests(ClientHandlerTestCase):
    def setUp(self):
        store = MockBlockStore()
        self.initialize(
            handlers.BatchGetRequest(store),
            client_batch_pb2.ClientBatchGetRequest,
            client_batch_pb2.ClientBatchGetResponse)

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
            - a status of NO_RESOURCE
            - that the Batch returned, when serialized, is actually empty
        """
        response = self.make_request(batch_id='b' * 127 + '1')

        self.assertEqual(self.status.NO_RESOURCE, response.status)
        self.assertFalse(response.batch.SerializeToString())

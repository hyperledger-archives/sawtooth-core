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
from sawtooth_validator.protobuf import client_state_pb2
from test_client_request_handlers.base_case import ClientHandlerTestCase
from test_client_request_handlers.mocks import make_db_and_store


class TestStateCurrentRequests(ClientHandlerTestCase):
    def setUp(self):
        def mock_current_root():
            return '123'

        self.initialize(
            handlers.StateCurrentRequest(mock_current_root),
            client_state_pb2.ClientStateCurrentRequest,
            client_state_pb2.ClientStateCurrentResponse)

    def test_state_current_request(self):
        """Verifies requests for the current merkle root work properly.
        Should respond with a hard-coded mock merkle_root of '123'.
        """
        response = self.make_request()

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('123', response.merkle_root)


class TestStateListRequests(ClientHandlerTestCase):
    def _find_value(self, entries, address):
        """The ordering of entries is fairly arbitrary, so some tests
        need to filter for the matching address.
        """
        return [l for l in entries if l.address == address][0].data

    def setUp(self):
        db, store, roots = make_db_and_store()
        self.initialize(
            handlers.StateListRequest(db, store),
            client_state_pb2.ClientStateListRequest,
            client_state_pb2.ClientStateListResponse,
            store=store,
            roots=roots)

    def test_state_list_request(self):
        """Verifies requests for data lists without parameters work properly.

        Queries the latest state in the default mock db:
            state: {'a': b'3', 'b': b'5', 'c': b'7'}

        the tests expect to find:
            - a status of OK
            - a head_id of 'B-2' (the latest)
            - the default paging response, showing all 3 resources returned
            - a list of entries with 3 items
            - that the list contains instances of ClientStateListResponse.Entry
            - that there is a leaf with an address of 'a' and data of b'3'
        """
        response = self.make_request()

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('B-2', response.head_id)
        self.assert_valid_paging(response)
        self.assertEqual(3, len(response.entries))
        self.assert_all_instances(response.entries,
                                  client_state_pb2.ClientStateListResponse.Entry)
        self.assertEqual(b'3', self._find_value(response.entries, 'a'))

    def test_state_list_bad_request(self):
        """Verifies requests for lists of data break with bad protobufs.

        Expects to find:
            - a status of INTERNAL_ERROR
            - that head_id, paging, and entries are missing
        """
        response = self.make_bad_request(head_id='B-1')

        self.assertEqual(self.status.INTERNAL_ERROR, response.status)
        self.assertFalse(response.head_id)
        self.assertFalse(response.paging.SerializeToString())
        self.assertFalse(response.entries)

    def test_state_list_no_genesis(self):
        """Verifies requests for lists of data break properly with no genesis.

        Expects to find:
            - a status of NOT_READY
            - that head_id, paging, and entries are missing
        """
        self.break_genesis()
        response = self.make_request()

        self.assertEqual(self.status.NOT_READY, response.status)
        self.assertFalse(response.head_id)
        self.assertFalse(response.paging.SerializeToString())
        self.assertFalse(response.entries)

    def test_state_list_with_root(self):
        """Verifies requests for data lists work properly with a merkle root.

        Queries the first state in the default mock db:
            {'a': b'1'}

        Expects to find:
            - a status of OK
            - that head_id is missing (queried by root)
            - a paging response showing all 1 resources returned
            - a list of entries with 1 item
            - that the list contains instances of ClientStateListResponse.Entry
            - that ClientStateListResponse.Entry has an address of 'a' and data
            of b'1'
        """
        response = self.make_request(merkle_root=self.roots[0])

        self.assertEqual(self.status.OK, response.status)
        self.assertFalse(response.head_id)
        self.assert_valid_paging(response, total=1)
        self.assertEqual(1, len(response.entries))

        self.assert_all_instances(response.entries,
                                  client_state_pb2.ClientStateListResponse.Entry)
        self.assertEqual('a', response.entries[0].address)
        self.assertEqual(b'1', response.entries[0].data)

    def test_state_list_with_bad_root(self):
        """Verifies requests for lists of data break properly with a bad root.

        Expects to find:
            - a status of NO_ROOT
            - that head_id, paging, and entries are missing
        """
        response = self.make_request(merkle_root='bad')

        self.assertEqual(self.status.NO_ROOT, response.status)
        self.assertFalse(response.head_id)
        self.assertFalse(response.paging.SerializeToString())
        self.assertFalse(response.entries)

    def test_state_list_with_head(self):
        """Verifies requests for lists of data work properly with a head_id.

        Queries the second state in the default mock db:
            {'a': b'2', 'b': b'4'}

        Expects to find:
            - a status of OK
            - a head_id of 'B-1'
            - a paging response showing all 2 resources returned
            - a list of entries with 2 items
            - that the list contains instances of ClientStateListResponse.Entry
            - that there is a leaf with an address of 'a' and data of b'1'
        """
        response = self.make_request(head_id='B-1')

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('B-1', response.head_id)
        self.assert_valid_paging(response, total=2)
        self.assertEqual(2, len(response.entries))

        self.assert_all_instances(response.entries,
                                  client_state_pb2.ClientStateListResponse.Entry)
        self.assertEqual(b'2', self._find_value(response.entries, 'a'))

    def test_state_list_with_bad_head(self):
        """Verifies requests for lists of data break with a bad head_id.

        Expects to find:
            - a status of NO_ROOT
            - that head_id, paging, and entries are missing
        """
        response = self.make_request(head_id='bad')

        self.assertEqual(self.status.NO_ROOT, response.status)
        self.assertFalse(response.head_id)
        self.assertFalse(response.paging.SerializeToString())
        self.assertFalse(response.entries)

    def test_state_list_with_address(self):
        """Verifies requests for data lists filtered by address work properly.

        Queries the latest state in the default mock db:
            {'a': b'3', 'b': b'5', 'c': b'7'}

        Expects to find:
            - a status of OK
            - a head_id of 'B-2' (the latest)
            - a paging response showing all 1 resources returned
            - a list of entries with 1 item
            - that the list contains instances of ClientStateListResponse.Entry
            - that ClientStateListResponse.Entry matches the address of 'c' and
            has data of b'7'
        """
        response = self.make_request(address='c')

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('B-2', response.head_id)
        self.assert_valid_paging(response, total=1)
        self.assertEqual(1, len(response.entries))

        self.assert_all_instances(response.entries,
                                  client_state_pb2.ClientStateListResponse.Entry)
        self.assertEqual('c', response.entries[0].address)
        self.assertEqual(b'7', response.entries[0].data)

    def test_state_list_with_bad_address(self):
        """Verifies requests for data filtered by a bad address break properly.

        Expects to find:
            - a status of NO_RESOURCE
            - a head_id of 'B-2' (the latest chain head id)
            - that paging and entries are missing
        """
        response = self.make_request(address='bad')

        self.assertEqual(self.status.NO_RESOURCE, response.status)
        self.assertEqual('B-2', response.head_id)
        self.assertFalse(response.paging.SerializeToString())
        self.assertFalse(response.entries)

    def test_state_list_with_head_and_address(self):
        """Verifies requests for data work with a head and address filter.

        Queries the second state in the default mock db:
            {'a': b'2', 'b': b'4'}

        Expects to find:
            - a status of OK
            - a head_id of 'B-1'
            - a paging response showing all 1 resources returned
            - a list of entries with 1 item
            - that the list contains instances of ClientStateListResponse.Entry
            - that ClientStateListResponse.Entry matches the address of 'b',
            and has data of b'4'
        """
        response = self.make_request(head_id='B-1', address='b')

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('B-1', response.head_id)
        self.assert_valid_paging(response, total=1)
        self.assertEqual(1, len(response.entries))

        self.assert_all_instances(response.entries,
                                  client_state_pb2.ClientStateListResponse.Entry)
        self.assertEqual('b', response.entries[0].address)
        self.assertEqual(b'4', response.entries[0].data)

    def test_state_list_with_early_state(self):
        """Verifies requests for data break when the state predates an address.

        Attempts to query the second state in the default mock db:
            {'a': b'2', 'b': b'4'}

        Expects to find:
            - a status of NO_RESOURCE
            - a head_id of 'B-1'
            - that paging and entries are missing
        """
        response = self.make_request(address='c', head_id='B-1')

        self.assertEqual(self.status.NO_RESOURCE, response.status)
        self.assertEqual('B-1', response.head_id)
        self.assertFalse(response.paging.SerializeToString())
        self.assertFalse(response.entries)

    def test_state_list_paginated(self):
        """Verifies requests for data lists work when paginated just by count.

        Queries the latest state in the default mock db:
            {'a': b'3', 'b': b'5', 'c': b'7'}

        Expects to find:
            - a status of OK
            - a head_id of 'B-2', the latest
            - a paging response with a next_id of 'c'
            - a list of entries with 2 items
            - those items are instances of ClientStateListResponse.Entry
        """
        response = self.make_paged_request(count=2)

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('B-2', response.head_id)
        self.assert_valid_paging(response, next_id='c')
        self.assertEqual(2, len(response.entries))
        self.assert_all_instances(response.entries,
                                  client_state_pb2.ClientStateListResponse.Entry)

    def test_state_list_paginated_by_start_id(self):
        """Verifies data list requests work paginated by count and start_id.

        Queries the latest state in the default mock db:
            {'a': b'3', 'b': b'5', 'c': b'7'}

        Expects to find:
            - a status of OK
            - a head_id of 'B-2', the latest
            - a paging response with:
                * a next_id of 'c'
                * a previous_id of 'a'
                * a start_index of 1
                * the default total resource count of 3
            - a list of entries with 1 item
            - that item is an instance of ClientStateListResponse.Entry
            - that ClientStateListResponse.Entry has an address of 'b' and data
            of b'5'
        """
        response = self.make_paged_request(count=1, start_id='b')

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('B-2', response.head_id)
        self.assert_valid_paging(response, 'c', 'a', 1)
        self.assertEqual(1, len(response.entries))
        self.assert_all_instances(response.entries,
                                  client_state_pb2.ClientStateListResponse.Entry)
        self.assertEqual('b', response.entries[0].address)
        self.assertEqual(b'5', response.entries[0].data)

    def test_state_list_paginated_by_end_id(self):
        """Verifies data list requests work paginated by count and end_id.

        Queries the latest state in the default mock db:
            {'a': b'3', 'b': b'5', 'c': b'7'}

        Expects to find:
            - a status of OK
            - a head_id of 'B-2', the latest
            - a paging response with:
                * the default empty next_id
                * a previous_id of 'a'
                * a start_index of 1
                * the default total resource count of 3
            - a list of entries with 2 items
            - those items are instances of ClientStateListResponse.Entry
            - the last leaf has an address of 'c' and data of b'7'
        """
        response = self.make_paged_request(count=2, end_id='c')

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('B-2', response.head_id)
        self.assert_valid_paging(response, previous_id='a', start_index=1)
        self.assertEqual(2, len(response.entries))
        self.assert_all_instances(response.entries,
                                  client_state_pb2.ClientStateListResponse.Entry)
        self.assertEqual('c', response.entries[1].address)
        self.assertEqual(b'7', response.entries[1].data)

    def test_state_list_paginated_by_index(self):
        """Verifies data list requests work paginated by count and min_index.

        Queries the latest state in the default mock db:
            {'a': b'3', 'b': b'5', 'c': b'7'}

        Expects to find:
            - a status of OK
            - a head_id of 'B-2', the latest
            - a paging response with a next_id of 'b'
            - a list of entries with 1 item
            - that item is an instance of ClientStateListResponse.Entry
            - that ClientStateListResponse.Entry has an address of 'a' and data
            of b'3'
        """
        response = self.make_paged_request(count=1, start_index=0)

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('B-2', response.head_id)
        self.assert_valid_paging(response, next_id='b')
        self.assertEqual(1, len(response.entries))
        self.assert_all_instances(response.entries,
                                  client_state_pb2.ClientStateListResponse.Entry)
        self.assertEqual('a', response.entries[0].address)
        self.assertEqual(b'3', response.entries[0].data)

    def test_state_list_with_bad_pagination(self):
        """Verifies data requests break when paging specifies missing entries.

        Queries the latest state in the default mock db:
            {'a': b'3', 'b': b'5', 'c': b'7'}

        Expects to find:
            - a status of INVALID_PAGING
            - that head_id, paging, and entries are missing
        """
        response = self.make_paged_request(count=3, start_index=7)

        self.assertEqual(self.status.INVALID_PAGING, response.status)
        self.assertFalse(response.head_id)
        self.assertFalse(response.paging.SerializeToString())
        self.assertFalse(response.entries)

    def test_state_list_paginated_with_head(self):
        """Verifies data list requests work with both paging and a head id.

        Queries the second state in the default mock db:
            {'a': b'2', 'b': b'4'}

        Expects to find:
            - a status of OK
            - a head_id of 'B-1'
            - a paging response with:
                * an empty next_id
                * a previous_id of 'a'
                * a start_index of 1
                * a total resource count of 2
            - a list of entries with 1 item
            - that item is an instance of ClientStateListResponse.Entry
            - that ClientStateListResponse.Entry has an address of 'b' and data
            of b'4'
        """
        response = self.make_paged_request(
            count=1, start_index=1, head_id='B-1')

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('B-1', response.head_id)
        self.assert_valid_paging(response, '', 'a', 1, 2)
        self.assertEqual(1, len(response.entries))
        self.assert_all_instances(response.entries,
                                  client_state_pb2.ClientStateListResponse.Entry)
        self.assertEqual('b', response.entries[0].address)
        self.assertEqual(b'4', response.entries[0].data)

    def test_state_list_paginated_with_address(self):
        """Verifies data list requests work with both paging and an address.

        Queries the latest state in the default mock db:
            {'a': b'3', 'b': b'5', 'c': b'7'}

        Expects to find:
            - a status of OK
            - a head_id of 'B-2', the latest
            - a paging response with a total resource count of 1
            - a list of entries with 1 item
            - that item is an instance of ClientStateListResponse.Entry
            - that ClientStateListResponse.Entry has an address of 'b' and data
            of b'5'
        """
        response = self.make_paged_request(count=1, start_index=0, address='b')

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('B-2', response.head_id)
        self.assert_valid_paging(response, total=1)
        self.assertEqual(1, len(response.entries))
        self.assert_all_instances(response.entries,
                                  client_state_pb2.ClientStateListResponse.Entry)
        self.assertEqual('b', response.entries[0].address)
        self.assertEqual(b'5', response.entries[0].data)

    def test_state_list_sorted_by_key(self):
        """Verifies data list requests work sorted by header_signature.

        Queries the latest state in the default mock db:
            {'a': b'3', 'b': b'5', 'c': b'7'}

        Expects to find:
            - a status of OK
            - a head_id of 'B-2', the latest
            - a paging response showing all 3 resources returned
            - a list of entries with 3 items
            - the items are instances of ClientStateListResponse.Entry
            - the first ClientStateListResponse.Entry has an address of 'a' and
            data of b'3'
            - the last ClientStateListResponse.Entry has an address of 'c' and
            data of b'7'
        """
        controls = self.make_sort_controls('address')
        response = self.make_request(sorting=controls)

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('B-2', response.head_id)
        self.assert_valid_paging(response)
        self.assertEqual(3, len(response.entries))
        self.assert_all_instances(response.entries,
                                  client_state_pb2.ClientStateListResponse.Entry)

        self.assertEqual('a', response.entries[0].address)
        self.assertEqual(b'3', response.entries[0].data)
        self.assertEqual('c', response.entries[2].address)
        self.assertEqual(b'7', response.entries[2].data)

    def test_state_list_sorted_by_bad_key(self):
        """Verifies data list requests break properly sorted by a bad key.

        Queries the latest state in the default mock db:
            {'a': b'3', 'b': b'5', 'c': b'7'}

        Expects to find:
            - a status of INVALID_SORT
            - that head_id, paging, and entries are missing
        """
        controls = self.make_sort_controls('bad')
        response = self.make_request(sorting=controls)

        self.assertEqual(self.status.INVALID_SORT, response.status)
        self.assertFalse(response.head_id)
        self.assertFalse(response.paging.SerializeToString())
        self.assertFalse(response.entries)

    def test_state_list_sorted_in_reverse(self):
        """Verifies data list requests work sorted by a key in reverse.

        Queries the latest state in the default mock db:
            {'a': b'3', 'b': b'5', 'c': b'7'}

        Expects to find:
            - a status of OK
            - a head_id of 'B-2', the latest
            - a paging response showing all 3 resources returned
            - a list of entries with 3 items
            - the items are instances of ClientStateListResponse.Entry
            - the first ClientStateListResponse.Entry has an address of 'c' and
            data of b'7'
            - the last ClientStateListResponse.Entry has an address of 'a' and
            data of b'3'
        """
        controls = self.make_sort_controls('data', reverse=True)
        response = self.make_request(sorting=controls)

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('B-2', response.head_id)
        self.assert_valid_paging(response)
        self.assertEqual(3, len(response.entries))
        self.assert_all_instances(response.entries,
                                  client_state_pb2.ClientStateListResponse.Entry)
        self.assertEqual('c', response.entries[0].address)
        self.assertEqual(b'7', response.entries[0].data)
        self.assertEqual('a', response.entries[2].address)
        self.assertEqual(b'3', response.entries[2].data)


class TestStateGetRequests(ClientHandlerTestCase):
    def setUp(self):
        db, store, roots = make_db_and_store()
        self.initialize(
            handlers.StateGetRequest(db, store),
            client_state_pb2.ClientStateGetRequest,
            client_state_pb2.ClientStateGetResponse,
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

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

import shutil
import tempfile

import sawtooth_validator.state.client_handlers as handlers
from sawtooth_validator.protobuf import client_state_pb2
from test_client_request_handlers.base_case import ClientHandlerTestCase
from test_client_request_handlers.mocks import make_db_and_store


class TestStateListRequests(ClientHandlerTestCase):
    def _find_value(self, entries, address):
        """The ordering of entries is fairly arbitrary, so some tests
        need to filter for the matching address.
        """
        return [e for e in entries if e.address == address][0].data

    def setUp(self):
        self._temp_dir = tempfile.mkdtemp()
        db, store, roots = make_db_and_store(self._temp_dir)
        self.initialize(
            handlers.StateListRequest(db, store),
            client_state_pb2.ClientStateListRequest,
            client_state_pb2.ClientStateListResponse,
            store=store,
            roots=roots)

    def tearDown(self):
        shutil.rmtree(self._temp_dir)

    def test_state_list_request(self):
        """Verifies requests for data lists without parameters work properly.

        Queries the latest state in the default mock db:
            state: {'00...1': b'3', '00...2': b'5', '00...3': b'7'}

        the tests expect to find:
            - a status of OK
            - the latest state_root
            - a paging response with start of b'3' and limit 100
            - a list of entries with 3 items
            - that the list contains instances of ClientStateListResponse.Entry
            - that there is a leaf with an address of '00..1' and data of b'3'
        """
        response = self.make_request()

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(self.roots[2], response.state_root)
        self.assert_valid_paging(response, "0" * 69 + '1', 100)
        self.assertEqual(3, len(response.entries))
        self.assert_all_instances(
            response.entries,
            client_state_pb2.ClientStateListResponse.Entry)
        self.assertEqual(
            b'3', self._find_value(response.entries, '0' * 69 + '1'))

    def test_state_list_bad_request(self):
        """Verifies requests for lists of data break with bad protobufs.

        Expects to find:
            - a status of INTERNAL_ERROR
            - that state_root, paging, and entries are missing
        """
        response = self.make_bad_request(state_root='bad')

        self.assertEqual(self.status.INTERNAL_ERROR, response.status)
        self.assertFalse(response.state_root)
        self.assertFalse(response.paging.SerializeToString())
        self.assertFalse(response.entries)

    def test_state_list_no_genesis(self):
        """Verifies requests for lists of data break properly with no genesis.

        Expects to find:
            - a status of NOT_READY
            - that state_root, paging, and entries are missing
        """
        self.break_genesis()
        response = self.make_request()

        self.assertEqual(self.status.NOT_READY, response.status)
        self.assertFalse(response.state_root)
        self.assertFalse(response.paging.SerializeToString())
        self.assertFalse(response.entries)

    def test_state_list_with_root(self):
        """Verifies requests for data lists work properly with a merkle root.

        Queries the first state in the default mock db:
            {'00..1': b'1'}

        Expects to find:
            - a status of OK
            - that state_root is missing (queried by root)
            - a paging response with start of b'1' and limit 100
            - a list of entries with 1 item
            - that the list contains instances of ClientStateListResponse.Entry
            - that ClientStateListResponse.Entry has an address of '00..1' and
              data of b'1'
        """
        response = self.make_request(state_root=self.roots[0])

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(self.roots[0], response.state_root)
        self.assert_valid_paging(response, '0' * 69 + '1', 100)
        self.assertEqual(1, len(response.entries))

        self.assert_all_instances(
            response.entries,
            client_state_pb2.ClientStateListResponse.Entry)
        self.assertEqual('0' * 69 + '1', response.entries[0].address)
        self.assertEqual(b'1', response.entries[0].data)

    def test_state_list_with_invalid_root(self):
        """Verifies requests for lists of data break properly with an invalid
        root.

        Expects to find:
            - a status of INVALID_ROOT
            - that state_root, paging, and entries are missing
        """
        response = self.make_request(state_root='nope')

        self.assertEqual(self.status.INVALID_ROOT, response.status)
        self.assertFalse(response.state_root)
        self.assertFalse(response.paging.SerializeToString())
        self.assertFalse(response.entries)

    def test_state_list_with_missing_root(self):
        """Verifies requests for lists of data break properly with a missing
        root.

        Expects to find:
            - a status of NO_ROOT
            - that state_root, paging, and entries are missing
        """
        # Since it is hard to predict what the state root will be
        # ahead of time, just search for one we know is missing.
        i = 0
        missing_root = format(i, 'x').zfill(64)
        while missing_root in self.roots:
            missing_root = format(i, 'x').zfill(64)

        response = self.make_request(state_root=missing_root)

        self.assertEqual(self.status.NO_ROOT, response.status)
        self.assertFalse(response.state_root)
        self.assertFalse(response.paging.SerializeToString())
        self.assertFalse(response.entries)

    def test_state_list_with_address(self):
        """Verifies requests for data lists filtered by address work properly.

        Queries the latest state in the default mock db:
            {'00...1': b'3', '00...2': b'5', '00...3': b'7'}

        Expects to find:
            - a status of OK
            - the latest state_root
            - a paging response with start of b'7' and limit 100
            - a list of entries with 1 item
            - that the list contains instances of ClientStateListResponse.Entry
            - that ClientStateListResponse.Entry matches the address of '00..3'
              and has data of b'7'
        """
        response = self.make_request(address='0' * 69 + '3')

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(self.roots[2], response.state_root)
        self.assert_valid_paging(response, '0' * 69 + '3', 100)
        self.assertEqual(1, len(response.entries))

        self.assert_all_instances(
            response.entries,
            client_state_pb2.ClientStateListResponse.Entry)
        self.assertEqual('0' * 69 + '3', response.entries[0].address)
        self.assertEqual(b'7', response.entries[0].data)

    def test_state_list_with_missing_address(self):
        """Verifies requests for data filtered by a bad address break properly.

        Expects to find:
            - a status of NO_RESOURCE
            - the latest state_root
            - that paging and entries are missing
        """
        response = self.make_request(address='0' * 68 + 'ff')

        self.assertEqual(self.status.NO_RESOURCE, response.status)
        self.assertEqual(self.roots[2], response.state_root)
        self.assertFalse(response.paging.SerializeToString())
        self.assertFalse(response.entries)

    def test_state_list_with_invalid_address(self):
        """Verifies requests for data filtered by an invalid address break
        properly.

        Expects to find:
            - a status of INVALID_ADDRESS
            - the latest state_root
            - that paging and entries are missing
        """
        response = self.make_request(address='nope')

        self.assertEqual(self.status.INVALID_ADDRESS, response.status)
        self.assertFalse(response.paging.SerializeToString())
        self.assertFalse(response.entries)

    def test_state_list_with_head_and_address(self):
        """Verifies requests for data work with a head and address filter.

        Queries the second state in the default mock db:
            {'00..1': b'2', '00..2': b'4'}

        Expects to find:
            - a status of OK
            - the state_root from block 'bbb...1'
            - a paging response with start of b'4' and limit 100
            - a list of entries with 1 item
            - that the list contains instances of
              ClientStateListResponse.Entry
            - that ClientStateListResponse.Entry matches the address
              of '00..2', and has data of b'4'

        """
        response = self.make_request(
            state_root=self.roots[1], address='0' * 69 + '2')

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(self.roots[1], response.state_root)
        self.assert_valid_paging(response, '0' * 69 + '2', 100)
        self.assertEqual(1, len(response.entries))

        self.assert_all_instances(
            response.entries,
            client_state_pb2.ClientStateListResponse.Entry)
        self.assertEqual('0' * 69 + '2', response.entries[0].address)
        self.assertEqual(b'4', response.entries[0].data)

    def test_state_list_with_early_state(self):
        """Verifies requests for data break when the state predates an address.

        Attempts to query the second state in the default mock db:
            {'00..1': b'2', '00..2': b'4'}

        Expects to find:
            - a status of NO_RESOURCE
            - the state_root from block 'bbb...1'
            - that paging and entries are missing
        """
        response = self.make_request(
            address='0' * 69 + '3', state_root=self.roots[1])

        self.assertEqual(self.status.NO_RESOURCE, response.status)
        self.assertEqual(self.roots[1], response.state_root)
        self.assertFalse(response.paging.SerializeToString())
        self.assertFalse(response.entries)

    def test_state_list_paginated(self):
        """Verifies requests for data lists work when paginated just by limit.

        Queries the latest state in the default mock db:
            {'00...1': b'3', '00...2': b'5', '00...3': b'7'}

        Expects to find:
            - a status of OK
            - the latest state_root
            - a paging response with a next_id of '00..3', start '00..1', and
              limit '2'
            - a list of entries with 2 items
            - those items are instances of ClientStateListResponse.Entry
        """
        response = self.make_paged_request(limit=2)

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(self.roots[2], response.state_root)
        self.assert_valid_paging(
            response, '0' * 69 + '1', 2, next_id='0' * 69 + '3')
        self.assertEqual(2, len(response.entries))
        self.assert_all_instances(
            response.entries,
            client_state_pb2.ClientStateListResponse.Entry)

    def test_state_list_paginated_by_start_id(self):
        """Verifies data list requests work paginated by limit and start_id.

        Queries the latest state in the default mock db:
            {'00...1': b'3', '00...2': b'5', '00...3': b'7'}

        Expects to find:
            - a status of OK
            - the latest state_root
            - a paging response with:
                * limit 1
                * start of '00..2'
                * a next_id of '00..3'
            - a list of entries with 1 item
            - that item is an instance of ClientStateListResponse.Entry
            - that ClientStateListResponse.Entry has an address of '00..2' and
              data of b'5'
        """
        response = self.make_paged_request(limit=1, start='0' * 69 + '2')

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(self.roots[2], response.state_root)
        self.assert_valid_paging(response, '0' * 69 + '2', 1, '0' * 69 + '3')
        self.assertEqual(1, len(response.entries))
        self.assert_all_instances(
            response.entries,
            client_state_pb2.ClientStateListResponse.Entry)
        self.assertEqual('0' * 69 + '2', response.entries[0].address)
        self.assertEqual(b'5', response.entries[0].data)

    def test_state_list_with_bad_pagination(self):
        """Verifies data requests break when paging specifies missing entries.

        Queries the latest state in the default mock db:
            {'00...1': b'3', '00...2': b'5', '00...3': b'7'}

        Expects to find:
            - a status of INVALID_PAGING
            - that state_root, paging, and entries are missing
        """
        response = self.make_paged_request(limit=3, start="bad")

        self.assertEqual(self.status.INVALID_PAGING, response.status)
        self.assertFalse(response.state_root)
        self.assertFalse(response.paging.SerializeToString())
        self.assertFalse(response.entries)

    def test_state_list_paginated_with_state_root(self):
        """Verifies data list requests work with both paging and a head id.

        Queries the second state in the default mock db:
            {'00..1': b'2', '00..2': b'4'}

        Expects to find:
            - a status of OK
            - the state_root of block 'bbb...1'
            - a paging response with a next_id of '00..1', start '00..2', and
              limit '2'
            - a list of entries with 1 item
            - that item is an instance of ClientStateListResponse.Entry
            - that ClientStateListResponse.Entry has an address of '00..2' and
              data of b'4'
        """
        response = self.make_paged_request(
            limit=1, start="0" * 69 + '2', state_root=self.roots[1])

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(self.roots[1], response.state_root)
        self.assert_valid_paging(response, '0' * 69 + '2', 1)
        self.assertEqual(1, len(response.entries))
        self.assert_all_instances(
            response.entries,
            client_state_pb2.ClientStateListResponse.Entry)
        self.assertEqual('0' * 69 + '2', response.entries[0].address)
        self.assertEqual(b'4', response.entries[0].data)

    def test_state_list_paginated_with_address(self):
        """Verifies data list requests work with both paging and an address.

        Queries the latest state in the default mock db:
            {'00...1': b'3', '00...2': b'5', '00...3': b'7'}

        Expects to find:
            - a status of OK
            - the latest state_root
        - the default empty paging response
            - a list of entries with 1 item
            - that item is an instance of ClientStateListResponse.Entry
            - that ClientStateListResponse.Entry has an address of '00..2' and
              data of b'5'
        """
        response = self.make_paged_request(limit=1, address='0' * 69 + '2')

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(self.roots[2], response.state_root)
        self.assert_valid_paging(response, '0' * 69 + '2', 1)
        self.assertEqual(1, len(response.entries))
        self.assert_all_instances(
            response.entries,
            client_state_pb2.ClientStateListResponse.Entry)
        self.assertEqual('0' * 69 + '2', response.entries[0].address)
        self.assertEqual(b'5', response.entries[0].data)

    def test_state_list_sorted_in_reverse(self):
        """Verifies data list requests work sorted by a key in reverse.

        Queries the latest state in the default mock db:
            {'00...1': b'3', '00...2': b'5', '00...3': b'7'}

        Expects to find:
            - a status of OK
            - the latest state_root
            - a paging response with a next_id of '00..3' and a limit of 100
            - a list of entries with 3 items
            - the items are instances of ClientStateListResponse.Entry
            - the first ClientStateListResponse.Entry has an address of '00..3'
              and data of b'7'
            - the last ClientStateListResponse.Entry has an address of '00..1'
              and data of b'3'
        """
        controls = self.make_sort_controls('default', reverse=True)
        response = self.make_request(sorting=controls)

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(self.roots[2], response.state_root)
        self.assert_valid_paging(response, '0' * 69 + '3', 100)
        self.assertEqual(3, len(response.entries))
        self.assert_all_instances(
            response.entries,
            client_state_pb2.ClientStateListResponse.Entry)
        self.assertEqual('0' * 69 + '3', response.entries[0].address)
        self.assertEqual(b'7', response.entries[0].data)
        self.assertEqual('0' * 69 + '1', response.entries[2].address)
        self.assertEqual(b'3', response.entries[2].data)


class TestStateGetRequests(ClientHandlerTestCase):
    def setUp(self):
        self._temp_dir = tempfile.mkdtemp()
        db, store, roots = make_db_and_store(self._temp_dir)
        self.initialize(
            handlers.StateGetRequest(db, store),
            client_state_pb2.ClientStateGetRequest,
            client_state_pb2.ClientStateGetResponse,
            store=store,
            roots=roots)

    def tearDown(self):
        shutil.rmtree(self._temp_dir)

    def test_state_get_request(self):
        """Verifies requests for specific data by address work properly.

        Queries the latest state in the default mock db:
            {'00...1': b'3', '00...2': b'5', '00...3': b'7'}

        Expects to find:
            - a status of OK
            - the latest state_root
            - a value of b'5'
        """
        response = self.make_request(address='0' * 69 + '2')

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(self.roots[2], response.state_root)
        self.assertEqual(b'5', response.value)

    def test_state_get_bad_request(self):
        """Verifies requests for specfic data break with bad protobufs.

        Expects to find:
            - a status of INTERNAL_ERROR
            - that value and state_root are missing
        """
        response = self.make_bad_request(address='0' * 69 + '2')

        self.assertEqual(self.status.INTERNAL_ERROR, response.status)
        self.assertFalse(response.state_root)
        self.assertFalse(response.value)

    def test_state_get_no_genesis(self):
        """Verifies requests for specfic data with break properly no genesis.

        Expects to find:
            - a status of NOT_READY
            - that value and state_root are missing
        """
        self.break_genesis()
        response = self.make_request(address='0' * 69 + '2')

        self.assertEqual(self.status.NOT_READY, response.status)
        self.assertFalse(response.state_root)
        self.assertFalse(response.value)

    def test_state_get_with_invalid_address(self):
        """Verifies requests for specific data break properly by an invalid
        address.

        Expects to find:
            - a status of INVALID_ADDRESS
            - that value and state_root are missing
        """
        response = self.make_request(address='nope')

        self.assertEqual(self.status.INVALID_ADDRESS, response.status)
        self.assertFalse(response.state_root)
        self.assertFalse(response.value)

    def test_state_get_with_missing_address(self):
        """Verifies requests for specific data break properly by a bad address.

        Expects to find:
            - a status of NO_RESOURCE
            - that value and state_root are missing
        """
        response = self.make_request(address='0' * 68 + 'ff')

        self.assertEqual(self.status.NO_RESOURCE, response.status)
        self.assertFalse(response.state_root)
        self.assertFalse(response.value)

    def test_state_get_with_root(self):
        """Verifies requests for specific data work with a merkle root.

        Queries the second state in the default mock db:
            {'00..1': b'2', '00..2': b'4'}

        Expects to find:
            - a status of OK
            - that state_root is missing (queried by root)
            - a value of b'4'
        """
        response = self.make_request(
            address='0' * 69 + '2', state_root=self.roots[1])

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(self.roots[1], response.state_root)
        self.assertEqual(b'4', response.value)

    def test_state_get_with_invalid_root(self):
        """Verifies requests for specific data break properly with a bad root.

        Expects to find:
            - a status of NO_ROOT
            - that value and state_root are missing
        """
        response = self.make_request(address='0' * 69 + '2', state_root='nope')

        self.assertEqual(self.status.INVALID_ROOT, response.status)
        self.assertFalse(response.value)
        self.assertFalse(response.value)

    def test_state_get_with_missing_root(self):
        """Verifies requests for specific data break properly with a bad root.

        Expects to find:
            - a status of NO_ROOT
            - that value and state_root are missing
        """
        # Since it is hard to predict what the state root will be
        # ahead of time, just search for one we know is missing.
        i = 0
        missing_root = format(i, 'x').zfill(64)
        while missing_root in self.roots:
            missing_root = format(i, 'x').zfill(64)
        response = self.make_request(
            address='0' * 69 + '2', state_root=missing_root)

        self.assertEqual(self.status.NO_ROOT, response.status)
        self.assertFalse(response.value)
        self.assertFalse(response.value)

    def test_state_get_with_early_state(self):
        """Verifies requests for a datum break when state predates the address.

        Attempts to query the second state in the default mock db:
            {'00..1': b'2', '00..2': b'4'}

        Expects to find:
            - a status of NO_RESOURCE
            - that value and state_root are missing
        """
        response = self.make_request(
            address='0' * 69 + '3', state_root=self.roots[1])

        self.assertEqual(self.status.NO_RESOURCE, response.status)
        self.assertFalse(response.state_root)
        self.assertFalse(response.value)

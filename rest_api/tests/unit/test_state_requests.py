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

from base64 import b64decode
from aiohttp.test_utils import unittest_run_loop
from components import Mocks, BaseApiTest
from sawtooth_rest_api.protobuf.validator_pb2 import Message
from sawtooth_rest_api.protobuf import client_pb2


class StateListTests(BaseApiTest):

    async def get_application(self, loop):
        self.set_status_and_connection(
            Message.CLIENT_STATE_LIST_REQUEST,
            client_pb2.ClientStateListRequest,
            client_pb2.ClientStateListResponse)

        handlers = self.build_handlers(loop, self.connection)
        return self.build_app(loop, '/state', handlers.list_state)

    @unittest_run_loop
    async def test_state_list(self):
        """Verifies a GET /state without parameters works properly.

        It will receive a Protobuf response with:
            - a head id of '2'
            - a paging response with a start of 0, and 3 total resources
            - three entries with addresses/data of:
                * 'a': b'3'
                * 'b': b'5'
                * 'c': b'7'

        It should send a Protobuf request with:
            - empty paging controls

        It should send back a JSON response with:
            - a response status of 200
            - a head property of '2'
            - a link property that ends in '/state?head=2&min=0&count=3'
            - a paging property that matches the paging response
            - a data property that is a list of 3 leaf dicts
            - three entries that match those in Protobuf response
        """
        paging = Mocks.make_paging_response(0, 3)
        entries = Mocks.make_entries(a=b'3', b=b'5', c=b'7')
        self.connection.preset_response(head_id='2', paging=paging,
                                        entries=entries)

        response = await self.get_assert_200('/state')
        controls = Mocks.make_paging_controls()
        self.connection.assert_valid_request_sent(paging=controls)

        self.assert_has_valid_head(response, '2')
        self.assert_has_valid_link(response, '/state?head=2')
        self.assert_has_valid_paging(response, paging)
        self.assert_has_valid_data_list(response, 3)
        self.assert_entries_match(entries, response['data'])

    @unittest_run_loop
    async def test_state_list_with_validator_error(self):
        """Verifies a GET /state with a validator error breaks properly.

        It will receive a Protobuf response with:
            - a status of INTERNAL_ERROR

        It should send back a JSON response with:
            - a status of 500
            - an error property with a code of 10
        """
        self.connection.preset_response(self.status.INTERNAL_ERROR)
        response = await self.get_assert_status('/state', 500)

        self.assert_has_valid_error(response, 10)

    @unittest_run_loop
    async def test_state_list_with_no_genesis(self):
        """Verifies a GET /state with validator not ready breaks properly.

        It will receive a Protobuf response with:
            - a status of NOT_READY

        It should send back a JSON response with:
            - a status of 503
            - an error property with a code of 15
        """
        self.connection.preset_response(self.status.NOT_READY)
        response = await self.get_assert_status('/state', 503)

        self.assert_has_valid_error(response, 15)

    @unittest_run_loop
    async def test_state_list_with_head(self):
        """Verifies a GET /state works properly with head specified.

        It will receive a Protobuf response with:
            - a head id of '1'
            - a paging response with a start of 0, and 2 total resources
            - two entries with addresses/data of:
                * 'a': b'2'
                * 'b': b'4'

        It should send a Protobuf request with:
            - a head_id property of '1'
            - empty paging controls

        It should send back a JSON response with:
            - a response status of 200
            - a head property of '1'
            - a link property that ends in '/state?head=1&min=0&count=2'
            - a paging property that matches the paging response
            - a data property that is a list of 2 leaf dicts
            - three entries that match those in Protobuf response
        """
        paging = Mocks.make_paging_response(0, 2)
        entries = Mocks.make_entries(a=b'2', b=b'4')
        self.connection.preset_response(head_id='1', paging=paging,
                                        entries=entries)

        response = await self.get_assert_200('/state?head=1')
        controls = Mocks.make_paging_controls()
        self.connection.assert_valid_request_sent(head_id='1', paging=controls)

        self.assert_has_valid_head(response, '1')
        self.assert_has_valid_link(response, '/state?head=1')
        self.assert_has_valid_paging(response, paging)
        self.assert_has_valid_data_list(response, 2)
        self.assert_entries_match(entries, response['data'])

    @unittest_run_loop
    async def test_state_list_with_bad_head(self):
        """Verifies a GET /state breaks properly with a bad head specified.

        It will receive a Protobuf response with:
            - a status of NO_ROOT

        It should send back a JSON response with:
            - a response status of 404
            - an error property with a code of 50
        """
        self.connection.preset_response(self.status.NO_ROOT)
        response = await self.get_assert_status('/state?head=bad', 404)

        self.assert_has_valid_error(response, 50)

    @unittest_run_loop
    async def test_state_list_with_address(self):
        """Verifies a GET /state works properly filtered by address.

        It will receive a Protobuf response with:
            - a head id of '2'
            - a paging response with a start of 0, and 1 total resource
            - one leaf with addresses/data of: 'c': b'7'

        It should send a Protobuf request with:
            - an address property of 'c'
            - empty paging controls

        It should send back a JSON response with:
            - a response status of 200
            - a head property of '2'
            - a link property that ends in
            '/state?head=2&min=0&count=1&address=c'
            - a paging property that matches the paging response
            - a data property that is a list of 1 leaf dict
            - one leaf that matches the Protobuf response
        """
        paging = Mocks.make_paging_response(0, 1)
        entries = Mocks.make_entries(c=b'7')
        self.connection.preset_response(head_id='2', paging=paging,
                                        entries=entries)

        response = await self.get_assert_200('/state?address=c')
        controls = Mocks.make_paging_controls()
        self.connection.assert_valid_request_sent(address='c', paging=controls)

        self.assert_has_valid_head(response, '2')
        self.assert_has_valid_link(response, '/state?head=2&address=c')
        self.assert_has_valid_paging(response, paging)
        self.assert_has_valid_data_list(response, 1)
        self.assert_entries_match(entries, response['data'])

    @unittest_run_loop
    async def test_state_list_with_bad_address(self):
        """Verifies a GET /state breaks properly filtered by a bad address.

        It will receive a Protobuf response with:
            - a status of NO_RESOURCE
            - a head id of '2'

        It should send back a JSON response with:
            - a response status of 200
            - a head property of '2'
            - a link property that ends in '/state?head=2&address=bad'
            - a paging property with only a total_count of 0
            - a data property that is an empty list
        """
        paging = Mocks.make_paging_response(None, 0)
        self.connection.preset_response(
            self.status.NO_RESOURCE,
            head_id='2',
            paging=paging)
        response = await self.get_assert_200('/state?address=bad')

        self.assert_has_valid_head(response, '2')
        self.assert_has_valid_link(response, '/state?head=2&address=bad')
        self.assert_has_valid_paging(response, paging)
        self.assert_has_valid_data_list(response, 0)

    @unittest_run_loop
    async def test_state_list_with_head_and_address(self):
        """Verifies GET /state works with a head and filtered by address.

        It will receive a Protobuf response with:
            - a head id of '1'
            - a paging response with a start of 0, and 1 total resource
            - one leaf with addresses/data of: 'a': b'2'

        It should send a Protobuf request with:
            - a head_id property of '1'
            - an address property of 'a'
            - empty paging controls

        It should send back a JSON response with:
            - a response status of 200
            - a head property of '1'
            - a link property that ends in
            '/state?head=1&min=0&count=1&address=a'
            - a paging property that matches the paging response
            - a data property that is a list of 1 leaf dict
            - one leaf that matches the Protobuf response
        """
        paging = Mocks.make_paging_response(0, 1)
        entries = Mocks.make_entries(a=b'2')
        self.connection.preset_response(head_id='1', paging=paging,
                                        entries=entries)

        response = await self.get_assert_200('/state?address=a&head=1')
        self.connection.assert_valid_request_sent(
            head_id='1',
            address='a',
            paging=Mocks.make_paging_controls())

        self.assert_has_valid_head(response, '1')
        self.assert_has_valid_link(response, '/state?head=1&address=a')
        self.assert_has_valid_paging(response, paging)
        self.assert_has_valid_data_list(response, 1)
        self.assert_entries_match(entries, response['data'])

    @unittest_run_loop
    async def test_state_list_paginated(self):
        """Verifies GET /state paginated by min id works properly.

        It will receive a Protobuf response with:
            - a head id of 'd'
            - a paging response with a start of 1, and 4 total resources
            - one leaf of {'c': b'3'}

        It should send a Protobuf request with:
            - a paging controls with a count of 1, and a start_index of 1

        It should send back a JSON response with:
            - a response status of 200
            - a head property of 'd'
            - a link property that ends in '/state?head=d&min=1&count=1'
            - paging that matches the response, with next and previous links
            - a data property that is a list of 1 dict
            - and that dict is a leaf that matches the one received
        """
        paging = Mocks.make_paging_response(1, 4)
        entries = Mocks.make_entries(c=b'3')
        self.connection.preset_response(head_id='d', paging=paging,
                                        entries=entries)

        response = await self.get_assert_200('/state?min=1&count=1')
        controls = Mocks.make_paging_controls(1, start_index=1)
        self.connection.assert_valid_request_sent(paging=controls)

        self.assert_has_valid_head(response, 'd')
        self.assert_has_valid_link(response, '/state?head=d&min=1&count=1')
        self.assert_has_valid_paging(response, paging,
                                     '/state?head=d&min=2&count=1',
                                     '/state?head=d&min=0&count=1')
        self.assert_has_valid_data_list(response, 1)
        self.assert_entries_match(entries, response['data'])

    @unittest_run_loop
    async def test_state_list_with_zero_count(self):
        """Verifies a GET /state with a count of zero breaks properly.

        It should send back a JSON response with:
            - a response status of 400
            - an error property with a code of 53
        """
        response = await self.get_assert_status('/state?min=2&count=0', 400)

        self.assert_has_valid_error(response, 53)

    @unittest_run_loop
    async def test_state_list_with_bad_paging(self):
        """Verifies a GET /state with a bad paging breaks properly.

        It will receive a Protobuf response with:
            - a status of INVALID_PAGING

        It should send back a JSON response with:
            - a response status of 400
            - an error property with a code of 54
        """
        self.connection.preset_response(self.status.INVALID_PAGING)
        response = await self.get_assert_status('/state?min=-1', 400)

        self.assert_has_valid_error(response, 54)

    @unittest_run_loop
    async def test_state_list_paginated_with_just_count(self):
        """Verifies GET /state paginated just by count works properly.

        It will receive a Protobuf response with:
            - a head id of 'd'
            - a paging response with a start of 0, and 4 total resources
            - two entries of {'d': b'4'}, and {'c': b'3'}

        It should send a Protobuf request with:
            - a paging controls with a count of 2

        It should send back a JSON response with:
            - a response status of 200
            - a head property of 'd'
            - a link property that ends in '/state?head=d&min=0&count=2'
            - paging that matches the response with a next link
            - a data property that is a list of 2 dicts
            - and those dicts are entries that match those received
        """
        paging = Mocks.make_paging_response(0, 4)
        entries = Mocks.make_entries(d=b'4', c=b'3')
        self.connection.preset_response(head_id='d', paging=paging,
                                        entries=entries)

        response = await self.get_assert_200('/state?count=2')
        controls = Mocks.make_paging_controls(2)
        self.connection.assert_valid_request_sent(paging=controls)

        self.assert_has_valid_head(response, 'd')
        self.assert_has_valid_link(response, '/state?head=d&count=2')
        self.assert_has_valid_paging(response, paging,
                                     '/state?head=d&min=2&count=2')
        self.assert_has_valid_data_list(response, 2)
        self.assert_entries_match(entries, response['data'])

    @unittest_run_loop
    async def test_state_list_paginated_without_count(self):
        """Verifies GET /state paginated without count works properly.

        It will receive a Protobuf response with:
            - a head id of 'd'
            - a paging response with a start of 2, and 4 total resources
            - two entries of {'b': b'2'} and {'a': b'1'}

        It should send a Protobuf request with:
            - a paging controls with a start_index of 2

        It should send back a JSON response with:
            - a response status of 200
            - a head property of 'd'
            - a link property that ends in '/state?head=d&min=2&count=2'
            - paging that matches the response, with a previous link
            - a data property that is a list of 2 dicts
            - and those dicts are entries that match those received
        """
        paging = Mocks.make_paging_response(2, 4)
        entries = Mocks.make_entries(b=b'2', a=b'1')
        self.connection.preset_response(head_id='d', paging=paging,
                                        entries=entries)

        response = await self.get_assert_200('/state?min=2')
        controls = Mocks.make_paging_controls(None, start_index=2)
        self.connection.assert_valid_request_sent(paging=controls)

        self.assert_has_valid_head(response, 'd')
        self.assert_has_valid_link(response, '/state?head=d&min=2')
        self.assert_has_valid_paging(response, paging,
                                     previous_link='/state?head=d&min=0&count=2')
        self.assert_has_valid_data_list(response, 2)
        self.assert_entries_match(entries, response['data'])

    @unittest_run_loop
    async def test_state_list_paginated_by_min_id(self):
        """Verifies GET /state paginated by a min id works properly.

        It will receive a Protobuf response with:
            - a head id of 'd'
            - a paging response with:
                * a start_index of 1
                * total_resources of 4
                * a previous_id of 'd'
            - three entries of {'c': b'3'}, {'b': b'2'}, and {'a': b'1'}

        It should send a Protobuf request with:
            - a paging controls with a start_id of 'c'

        It should send back a JSON response with:
            - a response status of 200
            - a head property of 'd'
            - a link property that ends in '/state?head=d&min=c&count=5'
            - paging that matches the response, with a previous link
            - a data property that is a list of 3 dicts
            - and those dicts are entries that match those received
        """
        paging = Mocks.make_paging_response(1, 4, previous_id='d')
        entries = Mocks.make_entries(c=b'3', b=b'2', a=b'1')
        self.connection.preset_response(head_id='d', paging=paging,
                                        entries=entries)

        response = await self.get_assert_200('/state?min=c&count=5')
        controls = Mocks.make_paging_controls(5, start_id='c')
        self.connection.assert_valid_request_sent(paging=controls)

        self.assert_has_valid_head(response, 'd')
        self.assert_has_valid_link(response, '/state?head=d&min=c&count=5')
        self.assert_has_valid_paging(response, paging,
                                     previous_link='/state?head=d&max=d&count=5')
        self.assert_has_valid_data_list(response, 3)
        self.assert_entries_match(entries, response['data'])

    @unittest_run_loop
    async def test_state_list_paginated_by_max_id(self):
        """Verifies GET /state paginated by a max id works properly.

        It will receive a Protobuf response with:
            - a head id of 'd'
            - a paging response with:
                * a start_index of 1
                * a total_resources of 4
                * a previous_id of 'd'
                * a next_id of 'a'
            - two entries of {'c': b'3'} and {'b': b'3'}

        It should send a Protobuf request with:
            - a paging controls with a count of 2 and an end_id of 'b'

        It should send back a JSON response with:
            - a response status of 200
            - a head property of 'd'
            - a link property that ends in '/state?head=d&max=b&count=2'
            - paging that matches the response, with next and previous links
            - a data property that is a list of 2 dicts
            - and those dicts are entries that match those received
        """
        paging = Mocks.make_paging_response(1, 4, previous_id='d', next_id='a')
        entries = Mocks.make_entries(c=b'3', b=b'2')
        self.connection.preset_response(head_id='d', paging=paging,
                                        entries=entries)

        response = await self.get_assert_200('/state?max=b&count=2')
        controls = Mocks.make_paging_controls(2, end_id='b')
        self.connection.assert_valid_request_sent(paging=controls)

        self.assert_has_valid_head(response, 'd')
        self.assert_has_valid_link(response, '/state?head=d&max=b&count=2')
        self.assert_has_valid_paging(response, paging,
                                     '/state?head=d&min=a&count=2',
                                     '/state?head=d&max=d&count=2')
        self.assert_has_valid_data_list(response, 2)
        self.assert_entries_match(entries, response['data'])

    @unittest_run_loop
    async def test_state_list_paginated_by_max_index(self):
        """Verifies GET /state paginated by a max index works properly.

        It will receive a Protobuf response with:
            - a head id of 'd'
            - a paging response with a start of 0, and 4 total resources
            - three entries with the ids {'d': b'4'}, {'c': b'3'} and {'b': b'2'}

        It should send a Protobuf request with:
            - a paging controls with a count of 2 and an start_index of 0

        It should send back a JSON response with:
            - a response status of 200
            - a head property of 'd'
            - a link property that ends in '/state?head=d&min=3&count=7'
            - paging that matches the response, with a next link
            - a data property that is a list of 2 dicts
            - and those dicts are entries that match those received
        """
        paging = Mocks.make_paging_response(0, 4)
        entries = Mocks.make_entries(d=b'4', c=b'3', b=b'2')
        self.connection.preset_response(head_id='d', paging=paging,
                                        entries=entries)

        response = await self.get_assert_200('/state?max=2&count=7')
        controls = Mocks.make_paging_controls(3, start_index=0)
        self.connection.assert_valid_request_sent(paging=controls)

        self.assert_has_valid_head(response, 'd')
        self.assert_has_valid_link(response, '/state?head=d&max=2&count=7')
        self.assert_has_valid_paging(response, paging,
                                     '/state?head=d&min=3&count=7')
        self.assert_has_valid_data_list(response, 3)
        self.assert_entries_match(entries, response['data'])

    @unittest_run_loop
    async def test_state_list_sorted(self):
        """Verifies GET /state can send proper sort controls.

        It will receive a Protobuf response with:
            - a head id of '2'
            - a paging response with a start of 0, and 3 total resources
            - three entries with addresses/data of:
                * 'a': b'3'
                * 'b': b'5'
                * 'c': b'7'

        It should send a Protobuf request with:
            - empty paging controls
            - sort controls with a key of 'address'

        It should send back a JSON response with:
            - a status of 200
            - a head property of '2'
            - a link property ending in '/state?head=2&sort=address'
            - a paging property that matches the paging response
            - a data property that is a list of 3 dicts
            - three entries that match those in Protobuf response
        """
        paging = Mocks.make_paging_response(0, 3)
        entries = Mocks.make_entries(a=b'3', b=b'5', c=b'7')
        self.connection.preset_response(head_id='2', paging=paging,
                                        entries=entries)

        response = await self.get_assert_200('/state?sort=address')
        page_controls = Mocks.make_paging_controls()
        sorting = Mocks.make_sort_controls('address')
        self.connection.assert_valid_request_sent(
            paging=page_controls,
            sorting=sorting)

        self.assert_has_valid_head(response, '2')
        self.assert_has_valid_link(response, '/state?head=2&sort=address')
        self.assert_has_valid_paging(response, paging)
        self.assert_has_valid_data_list(response, 3)
        self.assert_entries_match(entries, response['data'])

    @unittest_run_loop
    async def test_batch_list_with_bad_sort(self):
        """Verifies a GET /state with a bad sort breaks properly.

        It will receive a Protobuf response with:
            - a status of INVALID_PAGING

        It should send back a JSON response with:
            - a response status of 400
            - an error property with a code of 57
        """
        self.connection.preset_response(self.status.INVALID_SORT)
        response = await self.get_assert_status('/state?sort=bad', 400)

        self.assert_has_valid_error(response, 57)

    @unittest_run_loop
    async def test_state_list_sorted_in_reverse(self):
        """Verifies a GET /state can send proper sort parameters.

        It will receive a Protobuf response with:
            - a head id of '2'
            - a paging response with a start of 0, and 3 total resources
            - three entries with addresses/data of:
                * 'c': b'7'
                * 'b': b'5'
                * 'a': b'3'

        It should send a Protobuf request with:
            - empty paging controls
            - sort controls with a key of 'address' that is reversed

        It should send back a JSON response with:
            - a status of 200
            - a head property of '2'
            - a link property ending in '/state?head=2&sort=-address'
            - a paging property that matches the paging response
            - a data property that is a list of 3 dicts
            - three entries that match those in Protobuf response
        """
        paging = Mocks.make_paging_response(0, 3)
        entries = Mocks.make_entries(c=b'7', b=b'5', a=b'3')
        self.connection.preset_response(head_id='2', paging=paging,
                                        entries=entries)

        response = await self.get_assert_200('/state?sort=-address')
        page_controls = Mocks.make_paging_controls()
        sorting = Mocks.make_sort_controls('address', reverse=True)
        self.connection.assert_valid_request_sent(
            paging=page_controls,
            sorting=sorting)

        self.assert_has_valid_head(response, '2')
        self.assert_has_valid_link(response, '/state?head=2&sort=-address')
        self.assert_has_valid_paging(response, paging)
        self.assert_has_valid_data_list(response, 3)
        self.assert_entries_match(entries, response['data'])

    @unittest_run_loop
    async def test_state_list_sorted_by_length(self):
        """Verifies a GET /state can send proper sort parameters.

        It will receive a Protobuf response with:
            - a head id of '2'
            - a paging response with a start of 0, and 3 total resources
            - three entries with addresses/data of:
                * 'c': b'7'
                * 'b': b'45'
                * 'a': b'123'

        It should send a Protobuf request with:
            - empty paging controls
            - sort controls with a key of 'value' sorted by length

        It should send back a JSON response with:
            - a status of 200
            - a head property of '2'
            - a link property ending in '/state?head=2&sort=value.length'
            - a paging property that matches the paging response
            - a data property that is a list of 3 dicts
            - three entries that match those in Protobuf response
        """
        paging = Mocks.make_paging_response(0, 3)
        entries = Mocks.make_entries(c=b'7', b=b'45', a=b'123')
        self.connection.preset_response(head_id='2', paging=paging,
                                        entries=entries)

        response = await self.get_assert_200('/state?sort=value.length')
        page_controls = Mocks.make_paging_controls()
        sorting = Mocks.make_sort_controls('value', compare_length=True)
        self.connection.assert_valid_request_sent(
            paging=page_controls,
            sorting=sorting)

        self.assert_has_valid_head(response, '2')
        self.assert_has_valid_link(response, '/state?head=2&sort=value.length')
        self.assert_has_valid_paging(response, paging)
        self.assert_has_valid_data_list(response, 3)
        self.assert_entries_match(entries, response['data'])

    @unittest_run_loop
    async def test_state_list_sorted_by_many_keys(self):
        """Verifies a GET /state can send proper sort parameters.

        It will receive a Protobuf response with:
            - a head id of '2'
            - a paging response with a start of 0, and 3 total resources
            - three entries with addresses/data of:
                * 'c': b'7'
                * 'b': b'5'
                * 'a': b'3'

        It should send a Protobuf request with:
            - empty paging controls
            - multiple sort controls with:
                * a key of 'address' that is reversed
                * a key of 'value' that is sorted by length

        It should send back a JSON response with:
            - a status of 200
            - a head property of '2'
            - link with '/state?head=2&sort=-address,value.length'
            - a paging property that matches the paging response
            - a data property that is a list of 3 dicts
            - three entries that match those in Protobuf response
        """
        paging = Mocks.make_paging_response(0, 3)
        entries = Mocks.make_entries(c=b'7', b=b'5', a=b'3')
        self.connection.preset_response(head_id='2', paging=paging,
                                        entries=entries)

        response = await self.get_assert_200(
            '/state?sort=-address,value.length')
        page_controls = Mocks.make_paging_controls()
        sorting = (Mocks.make_sort_controls('address', reverse=True) +
                   Mocks.make_sort_controls('value', compare_length=True))
        self.connection.assert_valid_request_sent(
            paging=page_controls,
            sorting=sorting)

        self.assert_has_valid_head(response, '2')
        self.assert_has_valid_link(response,
            '/state?head=2&sort=-address,value.length')
        self.assert_has_valid_paging(response, paging)
        self.assert_has_valid_data_list(response, 3)
        self.assert_entries_match(entries, response['data'])


class StateGetTests(BaseApiTest):

    async def get_application(self, loop):
        self.set_status_and_connection(
            Message.CLIENT_STATE_GET_REQUEST,
            client_pb2.ClientStateGetRequest,
            client_pb2.ClientStateGetResponse)

        handlers = self.build_handlers(loop, self.connection)
        return self.build_app(loop, '/state/{address}', handlers.fetch_state)

    @unittest_run_loop
    async def test_state_get(self):
        """Verifies a GET /state/{address} without parameters works properly.

        It will receive a Protobuf response with:
            - a head id of '2'
            - a leaf with addresses/data of: 'a': b'3'

        It should send a Protobuf request with:
            - an address property of 'a'

        It should send back a JSON response with:
            - a response status of 200
            - a head property of '2'
            - a link property that ends in '/state/b?head=2'
            - a data property that b64decodes to b'3'
        """
        self.connection.preset_response(head_id='2', value=b'3')

        response = await self.get_assert_200('/state/a')
        self.connection.assert_valid_request_sent(address='a')

        self.assert_has_valid_head(response, '2')
        self.assert_has_valid_link(response, '/state/a?head=2')
        self.assertIn('data', response)

        data = response['data']
        self.assertIsInstance(data, str)
        self.assertEqual(b'3', b64decode(data))

    @unittest_run_loop
    async def test_state_get_with_validator_error(self):
        """Verifies a GET /state/{address} with a validator error breaks properly.

        It will receive a Protobuf response with:
            - a status of INTERNAL_ERROR

        It should send back a JSON response with:
            - a status of 500
            - an error property with a code of 10
        """
        self.connection.preset_response(self.status.INTERNAL_ERROR)
        response = await self.get_assert_status('/state/a', 500)

        self.assert_has_valid_error(response, 10)

    @unittest_run_loop
    async def test_state_get_with_no_genesis(self):
        """Verifies a GET /state/{address} with validator not ready breaks properly.

        It will receive a Protobuf response with:
            - a status of NOT_READY

        It should send back a JSON response with:
            - a status of 503
            - an error property with a code of 15
        """
        self.connection.preset_response(self.status.NOT_READY)
        response = await self.get_assert_status('/state/a', 503)

        self.assert_has_valid_error(response, 15)

    @unittest_run_loop
    async def test_state_get_with_bad_address(self):
        """Verifies a GET /state/{address} breaks with a bad address.

        It will receive a Protobuf response with:
            - a status of NO_RESOURCE

        It should send back a JSON response with:
            - a response status of 404
            - an error property with a code of 75
        """
        self.connection.preset_response(self.status.NO_RESOURCE)
        response = await self.get_assert_status('/state/bad', 404)

        self.assert_has_valid_error(response, 75)

    @unittest_run_loop
    async def test_state_get_with_head(self):
        """Verifies a GET /state/{address} works properly with head parameter.

        It will receive a Protobuf response with:
            - a head id of '1'
            - a leaf with addresses/data of: 'b': b'4'

        It should send a Protobuf request with:
            - a head_id property of '1'
            - an address property of 'b'

        It should send back a JSON response with:
            - a response status of 200
            - a head property of '2'
            - a link property that ends in '/state/b?head=2'
            - a data property that b64decodes to b'4'
        """
        self.connection.preset_response(head_id='1', value=b'4')

        response = await self.get_assert_200('/state/b?head=1')
        self.connection.assert_valid_request_sent(head_id='1', address='b')

        self.assert_has_valid_head(response, '1')
        self.assert_has_valid_link(response, '/state/b?head=1')
        self.assertIn('data', response)

        data = response['data']
        self.assertIsInstance(data, str)
        self.assertEqual(b'4', b64decode(data))

    @unittest_run_loop
    async def test_state_get_with_bad_head(self):
        """Verifies a GET /state/{address} breaks properly with a bad head.

        It will receive a Protobuf response with:
            - a status of NO_ROOT

        It should send back a JSON response with:
            - a response status of 404
            - an error property with a code of 50
        """
        self.connection.preset_response(self.status.NO_ROOT)
        response = await self.get_assert_status('/state/b?head=bad', 404)

        self.assert_has_valid_error(response, 50)

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
from sawtooth_rest_api.protobuf import client_state_pb2
from sawtooth_rest_api.protobuf import client_block_pb2
from sawtooth_rest_api.protobuf import block_pb2


ID_A = 'a' * 128
ID_B = 'b' * 128
ID_C = 'c' * 128
ID_D = 'd' * 128

DEFAULT_LIMIT = 100


class StateListTests(BaseApiTest):

    async def get_application(self):
        self.set_status_and_connection(
            Message.CLIENT_STATE_LIST_REQUEST,
            client_state_pb2.ClientStateListRequest,
            client_state_pb2.ClientStateListResponse)

        handlers = self.build_handlers(self.loop, self.connection)
        return self.build_app(self.loop, '/state', handlers.list_state)

    @unittest_run_loop
    async def test_state_list(self):
        """Verifies a GET /state without parameters works properly.

        It will receive a Protobuf response with:
            - a state root of ID_C
            - a paging response with start of "a" and a limit of 100
            - three entries with addresses/data of:
                * 'a': b'3'
                * 'b': b'5'
                * 'c': b'7'

        It should send a Protobuf request with:
            - empty paging controls

        It should send back a JSON response with:
            - a response status of 200
            - a head property of ID_C
            - a link property that ends in
                /state?head={}&start=a&limit=100'.format(ID_C)
            - a paging property that matches the paging response
            - a data property that is a list of 3 leaf dicts
            - three entries that match those in Protobuf response
        """
        paging = Mocks.make_paging_response("", "a", DEFAULT_LIMIT)
        entries = Mocks.make_entries(a=b'3', b=b'5', c=b'7')
        self.connection.preset_response(state_root='beef', paging=paging,
                                        entries=entries)
        self.connection.preset_response(
            proto=client_block_pb2.ClientBlockGetResponse,
            block=block_pb2.Block(
                header_signature=ID_C,
                header=block_pb2.BlockHeader(
                    state_root_hash='beef').SerializeToString()))

        response = await self.get_assert_200('/state')
        controls = Mocks.make_paging_controls()
        self.connection.assert_valid_request_sent(
            state_root='beef', paging=controls)

        self.assert_has_valid_head(response, ID_C)
        self.assert_has_valid_link(
            response, '/state?head={}&start=a&limit=100'.format(ID_C))
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
        self.connection.preset_response(
            proto=client_block_pb2.ClientBlockGetResponse,
            block=block_pb2.Block())

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
        self.connection.preset_response(
            proto=client_block_pb2.ClientBlockGetResponse,
            block=block_pb2.Block())

        response = await self.get_assert_status('/state', 503)

        self.assert_has_valid_error(response, 15)

    @unittest_run_loop
    async def test_state_list_with_head(self):
        """Verifies a GET /state works properly with head specified.

        It will receive a Protobuf response with:
            - a head id of ID_B
            - a paging response with start of a and limit of 100
            - two entries with addresses/data of:
                * 'a': b'2'
                * 'b': b'4'

        It should send a Protobuf request with:
            - a head_id property of ID_B
            - empty paging controls

        It should send back a JSON response with:
            - a response status of 200
            - a head property of ID_B
            - a link property that ends in
                '/state?head={}&start=a&limit=100'.format(ID_B)
            - a paging property that matches the paging response
            - a data property that is a list of 2 leaf dicts
            - three entries that match those in Protobuf response
        """
        paging = Mocks.make_paging_response("", "a", DEFAULT_LIMIT)
        entries = Mocks.make_entries(a=b'2', b=b'4')
        self.connection.preset_response(state_root='beef', paging=paging,
                                        entries=entries)
        self.connection.preset_response(
            proto=client_block_pb2.ClientBlockGetResponse,
            block=block_pb2.Block(
                header_signature=ID_B,
                header=block_pb2.BlockHeader(
                    state_root_hash='beef').SerializeToString()))

        response = await self.get_assert_200('/state?head={}'.format(ID_B))
        controls = Mocks.make_paging_controls()
        self.connection.assert_valid_request_sent(
            state_root='beef', paging=controls)

        self.assert_has_valid_head(response, ID_B)
        self.assert_has_valid_link(
            response, '/state?head={}&start=a&limit=100'.format(ID_B))
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
        self.connection.preset_response(
            proto=client_block_pb2.ClientBlockGetResponse,
            block=block_pb2.Block())
        response = await self.get_assert_status('/state?head={}'.format(ID_D),
                                                404)

        self.assert_has_valid_error(response, 50)

    @unittest_run_loop
    async def test_state_list_with_address(self):
        """Verifies a GET /state works properly filtered by address.

        It will receive a Protobuf response with:
            - a head id of ID_C
            - an empty paging response
            - one leaf with addresses/data of: 'c': b'7'

        It should send a Protobuf request with:
            - an address property of 'c'
            - empty paging controls

        It should send back a JSON response with:
            - a response status of 200
            - a head property of ID_C
            - a link property that ends in
                '/state?head={}&start=c&limit=100&address=c'.format(ID_C)
            - a paging property that matches the paging response
            - a data property that is a list of 1 leaf dict
            - one leaf that matches the Protobuf response
        """
        paging = Mocks.make_paging_response("", "c", DEFAULT_LIMIT)
        entries = Mocks.make_entries(c=b'7')
        self.connection.preset_response(state_root='beef', paging=paging,
                                        entries=entries)
        self.connection.preset_response(
            proto=client_block_pb2.ClientBlockGetResponse,
            block=block_pb2.Block(
                header_signature=ID_C,
                header=block_pb2.BlockHeader(
                    state_root_hash='beef').SerializeToString()))

        response = await self.get_assert_200('/state?address=c')
        controls = Mocks.make_paging_controls()
        self.connection.assert_valid_request_sent(
            state_root='beef', address='c', paging=controls)

        self.assert_has_valid_head(response, ID_C)
        self.assert_has_valid_link(
            response,
            '/state?head={}&start=c&limit=100&address=c'.format(ID_C))
        self.assert_has_valid_paging(response, paging)
        self.assert_has_valid_data_list(response, 1)
        self.assert_entries_match(entries, response['data'])

    @unittest_run_loop
    async def test_state_list_with_bad_address(self):
        """Verifies a GET /state breaks properly filtered by a bad address.

        It will receive a Protobuf response with:
            - a status of NO_RESOURCE
            - a head id of ID_C

        It should send back a JSON response with:
            - a response status of 200
            - a head property of ID_C
            - a link property that ends in
                '/state?head={}&start=c&limit=100address=bad'.format(ID_C)
            - a paging property with only a total_count of 0
            - a data property that is an empty list
        """
        paging = Mocks.make_paging_response("", "c", DEFAULT_LIMIT)
        self.connection.preset_response(
            self.status.NO_RESOURCE,
            state_root='beef',
            paging=paging)
        self.connection.preset_response(
            proto=client_block_pb2.ClientBlockGetResponse,
            block=block_pb2.Block(
                header_signature=ID_C,
                header=block_pb2.BlockHeader(
                    state_root_hash='beef').SerializeToString()))
        response = await self.get_assert_200('/state?address=bad')

        self.assert_has_valid_head(response, ID_C)
        self.assert_has_valid_link(
            response,
            '/state?head={}&start=c&limit=100&address=bad'.format(ID_C))
        self.assert_has_valid_paging(response, paging)
        self.assert_has_valid_data_list(response, 0)

    @unittest_run_loop
    async def test_state_list_with_head_and_address(self):
        """Verifies GET /state works with a head and filtered by address.

        It will receive a Protobuf response with:
            - a head id of ID_B
            - a paging response with a start of a and a limit of 100
            - one leaf with addresses/data of: 'a': b'2'

        It should send a Protobuf request with:
            - a head_id property of ID_B
            - an address property of 'a'
            - empty paging controls

        It should send back a JSON response with:
            - a response status of 200
            - a head property of ID_B
            - a link property that ends in
                '/state?head={}&start=a&limit=100&address=a'.format(ID_B)
            - a paging property that matches the paging response
            - a data property that is a list of 1 leaf dict
            - one leaf that matches the Protobuf response
        """
        paging = Mocks.make_paging_response("", "a", DEFAULT_LIMIT)
        entries = Mocks.make_entries(a=b'2')
        self.connection.preset_response(state_root='beef', paging=paging,
                                        entries=entries)
        self.connection.preset_response(
            proto=client_block_pb2.ClientBlockGetResponse,
            block=block_pb2.Block(
                header_signature=ID_B,
                header=block_pb2.BlockHeader(
                    state_root_hash='beef').SerializeToString()))

        response = await self.get_assert_200(
            '/state?address=a&head={}'.format(ID_B))
        self.connection.assert_valid_request_sent(
            state_root='beef',
            address='a',
            paging=Mocks.make_paging_controls())

        self.assert_has_valid_head(response, ID_B)
        self.assert_has_valid_link(
            response,
            '/state?head={}&start=a&limit=100&address=a'.format(ID_B))
        self.assert_has_valid_paging(response, paging)
        self.assert_has_valid_data_list(response, 1)
        self.assert_entries_match(entries, response['data'])

    @unittest_run_loop
    async def test_state_list_paginated(self):
        """Verifies GET /state paginated by works properly.

        It will receive a Protobuf response with:
            - a head id of ID_D
            - a paging response with a start of 2
            - one leaf of {'c': b'3'}

        It should send a Protobuf request with:
            - a paging controls with a limit of 1, and a start of 1

        It should send back a JSON response with:
            - a response status of 200
            - a head property of ID_D
            - a link property that ends in
                '/state?head={}&start=c&limit=1'.format(ID_D)
            - paging that matches the response, with next and previous links
            - a data property that is a list of 1 dict
            - and that dict is a leaf that matches the one received
        """
        paging = Mocks.make_paging_response("b", "c", 1)
        entries = Mocks.make_entries(c=b'3')
        self.connection.preset_response(state_root='beef', paging=paging,
                                        entries=entries)
        self.connection.preset_response(
            proto=client_block_pb2.ClientBlockGetResponse,
            block=block_pb2.Block(
                header_signature=ID_D,
                header=block_pb2.BlockHeader(
                    state_root_hash='beef').SerializeToString()))

        response = await self.get_assert_200('/state?start=c&limit=1')
        controls = Mocks.make_paging_controls(1, start="c")
        self.connection.assert_valid_request_sent(
            state_root='beef', paging=controls)

        self.assert_has_valid_head(response, ID_D)
        self.assert_has_valid_link(
            response, '/state?head={}&start=c&limit=1'.format(ID_D))
        self.assert_has_valid_paging(
            response, paging, '/state?head={}&start=b&limit=1'.format(ID_D))
        self.assert_has_valid_data_list(response, 1)
        self.assert_entries_match(entries, response['data'])

    @unittest_run_loop
    async def test_state_list_with_zero_limit(self):
        """Verifies a GET /state with a limit of zero breaks properly.

        It should send back a JSON response with:
            - a response status of 400
            - an error property with a code of 53
        """
        response = await self.get_assert_status('/state?start=2&limit=0', 400)

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
        self.connection.preset_response(
            proto=client_block_pb2.ClientBlockGetResponse,
            block=block_pb2.Block())
        response = await self.get_assert_status('/state?start=-1', 400)

        self.assert_has_valid_error(response, 54)

    @unittest_run_loop
    async def test_state_list_paginated_with_just_limit(self):
        """Verifies GET /state paginated just by limit works properly.

        It will receive a Protobuf response with:
            - a head id of ID_D
            - a paging response with a start of d and limit of 2
            - two entries of {ID_D: b'4'}, and {'c': b'3'}

        It should send a Protobuf request with:
            - a paging controls with a limit of 2

        It should send back a JSON response with:
            - a response status of 200
            - a head property of ID_D
            - a link property that ends in
                '/state?head={}&start=d&limit=2'.format(ID_D)
            - paging that matches the response with a next link
            - a data property that is a list of 2 dicts
            - and those dicts are entries that match those received
        """
        paging = Mocks.make_paging_response("b", "d", 2)
        entries = Mocks.make_entries(d=b'4', c=b'3')
        self.connection.preset_response(state_root='beef', paging=paging,
                                        entries=entries)
        self.connection.preset_response(
            proto=client_block_pb2.ClientBlockGetResponse,
            block=block_pb2.Block(
                header_signature=ID_D,
                header=block_pb2.BlockHeader(
                    state_root_hash='beef').SerializeToString()))

        response = await self.get_assert_200('/state?limit=2')
        controls = Mocks.make_paging_controls(2)
        self.connection.assert_valid_request_sent(
            state_root='beef', paging=controls)

        self.assert_has_valid_head(response, ID_D)
        self.assert_has_valid_link(
            response, '/state?head={}&start=d&limit=2'.format(ID_D))
        self.assert_has_valid_paging(
            response, paging, '/state?head={}&start=b&limit=2'.format(ID_D))
        self.assert_has_valid_data_list(response, 2)
        self.assert_entries_match(entries, response['data'])

    @unittest_run_loop
    async def test_state_list_paginated_without_count(self):
        """Verifies GET /state paginated without count works properly.

        It will receive a Protobuf response with:
            - a head id of ID_D
            - a paging response start of "b" and limit of 100
            - two entries of {'b': b'2'} and {'a': b'1'}

        It should send a Protobuf request with:
            - a paging controls with a start of 2

        It should send back a JSON response with:
            - a response status of 200
            - a head property of ID_D
            - a link property that ends in
                '/state?head={}&start=b&limit=100'.format(ID_D))
            - paging that matches the response, with a previous link
            - a data property that is a list of 2 dicts
            - and those dicts are entries that match those received
        """
        paging = Mocks.make_paging_response("", "b", DEFAULT_LIMIT)
        entries = Mocks.make_entries(b=b'2', a=b'1')
        self.connection.preset_response(state_root='beef', paging=paging,
                                        entries=entries)
        self.connection.preset_response(
            proto=client_block_pb2.ClientBlockGetResponse,
            block=block_pb2.Block(
                header_signature=ID_D,
                header=block_pb2.BlockHeader(
                    state_root_hash='beef').SerializeToString()))

        response = await self.get_assert_200('/state?start=2')
        controls = Mocks.make_paging_controls(None, start="2")
        self.connection.assert_valid_request_sent(
            state_root='beef', paging=controls)

        self.assert_has_valid_head(response, ID_D)
        self.assert_has_valid_link(
            response, '/state?head={}&start=b&limit=100'.format(ID_D))
        self.assert_has_valid_paging(response, paging)
        self.assert_has_valid_data_list(response, 2)
        self.assert_entries_match(entries, response['data'])

    @unittest_run_loop
    async def test_state_list_paginated_by_start_id(self):
        """Verifies GET /state paginated by a start id works properly.

        It will receive a Protobuf response with:
            - a head id of ID_D
            - a paging response with a start of c and limit of 5
            - three entries of {'c': b'3'}, {'b': b'2'}, and {'a': b'1'}

        It should send a Protobuf request with:
            - a paging controls with a start_id of ID_C

        It should send back a JSON response with:
            - a response status of 200
            - a head property of ID_D
            - a link property that ends in
                '/state?head={}&start=c&limit=5'.format(ID_D, ID_C)
            - paging that matches the response, with a previous link
            - a data property that is a list of 3 dicts
            - and those dicts are entries that match those received
        """
        paging = Mocks.make_paging_response("", "c", 5)
        entries = Mocks.make_entries(c=b'3', b=b'2', a=b'1')
        self.connection.preset_response(state_root='beef', paging=paging,
                                        entries=entries)
        self.connection.preset_response(
            proto=client_block_pb2.ClientBlockGetResponse,
            block=block_pb2.Block(
                header_signature=ID_D,
                header=block_pb2.BlockHeader(
                    state_root_hash='beef').SerializeToString()))

        response = await self.get_assert_200('/state?start=c&limit=5')
        controls = Mocks.make_paging_controls(5, "c")
        self.connection.assert_valid_request_sent(
            state_root='beef', paging=controls)

        self.assert_has_valid_head(response, ID_D)
        self.assert_has_valid_link(
            response, '/state?head={}&start=c&limit=5'.format(ID_D))
        self.assert_has_valid_paging(response, paging)
        self.assert_has_valid_data_list(response, 3)
        self.assert_entries_match(entries, response['data'])

    @unittest_run_loop
    async def test_state_list_sorted_in_reverse(self):
        """Verifies a GET /state can send proper sort parameters.

        It will receive a Protobuf response with:
            - a head id of ID_C
            - a paging response with a start of c and  limit of 100
            - three entries with addresses/data of:
                * 'c': b'7'
                * 'b': b'5'
                * 'a': b'3'

        It should send a Protobuf request with:
            - empty paging controls
            - sort controls with a key of 'address' that is reversed

        It should send back a JSON response with:
            - a status of 200
            - a head property of ID_C
            - a link property ending in
                '/state?head={}&start=c&limit=100&reverse'.format(ID_C)
            - a paging property that matches the paging response
            - a data property that is a list of 3 dicts
            - three entries that match those in Protobuf response
        """
        paging = Mocks.make_paging_response("", "c", DEFAULT_LIMIT)
        entries = Mocks.make_entries(c=b'7', b=b'5', a=b'3')
        self.connection.preset_response(state_root='beef', paging=paging,
                                        entries=entries)
        self.connection.preset_response(
            proto=client_block_pb2.ClientBlockGetResponse,
            block=block_pb2.Block(
                header_signature=ID_C,
                header=block_pb2.BlockHeader(
                    state_root_hash='beef').SerializeToString()))

        response = await self.get_assert_200('/state?reverse')
        page_controls = Mocks.make_paging_controls()
        sorting = Mocks.make_sort_controls('default', reverse=True)
        self.connection.assert_valid_request_sent(
            state_root='beef',
            paging=page_controls,
            sorting=sorting)

        self.assert_has_valid_head(response, ID_C)
        self.assert_has_valid_link(
            response, '/state?head={}&start=c&limit=100&reverse'.format(ID_C))
        self.assert_has_valid_paging(response, paging)
        self.assert_has_valid_data_list(response, 3)
        self.assert_entries_match(entries, response['data'])


class StateGetTests(BaseApiTest):

    async def get_application(self):
        self.set_status_and_connection(
            Message.CLIENT_STATE_GET_REQUEST,
            client_state_pb2.ClientStateGetRequest,
            client_state_pb2.ClientStateGetResponse)

        handlers = self.build_handlers(self.loop, self.connection)
        return self.build_app(
            self.loop, '/state/{address}', handlers.fetch_state)

    @unittest_run_loop
    async def test_state_get(self):
        """Verifies a GET /state/{address} without parameters works properly.

        It will receive a Protobuf response with:
            - a head id of ID_C
            - a leaf with addresses/data of: 'a': b'3'

        It should send a Protobuf request with:
            - an address property of 'a'

        It should send back a JSON response with:
            - a response status of 200
            - a head property of ID_C
            - a link property that ends in '/state/b?head={}'.format(ID_C)
            - a data property that b64decodes to b'3'
        """
        self.connection.preset_response(state_root='beef', value=b'3')
        self.connection.preset_response(
            proto=client_block_pb2.ClientBlockGetResponse,
            block=block_pb2.Block(
                header_signature=ID_C,
                header=block_pb2.BlockHeader(
                    state_root_hash='beef').SerializeToString()))

        response = await self.get_assert_200('/state/a')
        self.connection.assert_valid_request_sent(
            state_root='beef', address='a')

        self.assert_has_valid_head(response, ID_C)
        self.assert_has_valid_link(response, '/state/a?head={}'.format(ID_C))
        self.assertIn('data', response)

        data = response['data']
        self.assertIsInstance(data, str)
        self.assertEqual(b'3', b64decode(data))

    @unittest_run_loop
    async def test_state_get_with_validator_error(self):
        """Verifies a GET /state/{address} with a validator error breaks
        properly.

        It will receive a Protobuf response with:
            - a status of INTERNAL_ERROR

        It should send back a JSON response with:
            - a status of 500
            - an error property with a code of 10
        """
        self.connection.preset_response(self.status.INTERNAL_ERROR)
        self.connection.preset_response(
            proto=client_block_pb2.ClientBlockGetResponse,
            block=block_pb2.Block())
        response = await self.get_assert_status('/state/a', 500)

        self.assert_has_valid_error(response, 10)

    @unittest_run_loop
    async def test_state_get_with_no_genesis(self):
        """Verifies a GET /state/{address} with validator not ready breaks
        properly.

        It will receive a Protobuf response with:
            - a status of NOT_READY

        It should send back a JSON response with:
            - a status of 503
            - an error property with a code of 15
        """
        self.connection.preset_response(self.status.NOT_READY)
        self.connection.preset_response(
            proto=client_block_pb2.ClientBlockGetResponse,
            block=block_pb2.Block())
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
        self.connection.preset_response(
            proto=client_block_pb2.ClientBlockGetResponse,
            block=block_pb2.Block())
        response = await self.get_assert_status('/state/bad', 404)

        self.assert_has_valid_error(response, 75)

    @unittest_run_loop
    async def test_state_get_with_head(self):
        """Verifies a GET /state/{address} works properly with head parameter.

        It will receive a Protobuf response with:
            - a head id of ID_B
            - a leaf with addresses/data of: 'b': b'4'

        It should send a Protobuf request with:
            - a head_id property of ID_B
            - an address property of 'b'

        It should send back a JSON response with:
            - a response status of 200
            - a head property of ID_C
            - a link property that ends in '/state/b?head={}'.format(ID_C)
            - a data property that b64decodes to b'4'
        """
        self.connection.preset_response(state_root='beef', value=b'4')
        self.connection.preset_response(
            proto=client_block_pb2.ClientBlockGetResponse,
            block=block_pb2.Block(
                header_signature=ID_B,
                header=block_pb2.BlockHeader(
                    state_root_hash='beef').SerializeToString()))

        response = await self.get_assert_200('/state/b?head={}'.format(ID_B))
        self.connection.assert_valid_request_sent(
            state_root='beef', address='b')

        self.assert_has_valid_head(response, ID_B)
        self.assert_has_valid_link(response, '/state/b?head={}'.format(ID_B))
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
        self.connection.preset_response(
            proto=client_block_pb2.ClientBlockGetResponse,
            block=block_pb2.Block())
        response = await self.get_assert_status(
            '/state/b?head={}'.format(ID_D), 404)

        self.assert_has_valid_error(response, 50)

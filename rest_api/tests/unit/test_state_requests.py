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

from unittest import mock
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
            - a paging response with a start of 0, and 3 total resources
            - three entries with addresses/data of:
                * 'a': b'3'
                * 'b': b'5'
                * 'c': b'7'

        It should send a Protobuf request with:
            - empty paging controls

        It should send back a JSON response with:
            - a response status of 200
            - a head property of ID_C
            - a link property that ends in '/state?head={}&min=0&count=3'.format(ID_C)
            - a paging property that matches the paging response
            - a data property that is a list of 3 leaf dicts
            - three entries that match those in Protobuf response
        """
        paging = Mocks.make_paging_response(0, 3)
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
        self.assert_has_valid_link(response, '/state?head={}'.format(ID_C))
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
            - a paging response with a start of 0, and 2 total resources
            - two entries with addresses/data of:
                * 'a': b'2'
                * 'b': b'4'

        It should send a Protobuf request with:
            - a head_id property of ID_B
            - empty paging controls

        It should send back a JSON response with:
            - a response status of 200
            - a head property of ID_B
            - a link property that ends in '/state?head={}&min=0&count=2'.format(ID_B)
            - a paging property that matches the paging response
            - a data property that is a list of 2 leaf dicts
            - three entries that match those in Protobuf response
        """
        paging = Mocks.make_paging_response(0, 2)
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
        self.assert_has_valid_link(response, '/state?head={}'.format(ID_B))
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
        response = await self.get_assert_status('/state?head={}'.format(ID_D), 404)

        self.assert_has_valid_error(response, 50)

    @unittest_run_loop
    async def test_state_list_with_address(self):
        """Verifies a GET /state works properly filtered by address.

        It will receive a Protobuf response with:
            - a head id of ID_C
            - a paging response with a start of 0, and 1 total resource
            - one leaf with addresses/data of: 'c': b'7'

        It should send a Protobuf request with:
            - an address property of 'c'
            - empty paging controls

        It should send back a JSON response with:
            - a response status of 200
            - a head property of ID_C
            - a link property that ends in
            '/state?head={}&min=0&count=1&address=c'.format(ID_C)
            - a paging property that matches the paging response
            - a data property that is a list of 1 leaf dict
            - one leaf that matches the Protobuf response
        """
        paging = Mocks.make_paging_response(0, 1)
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
        self.assert_has_valid_link(response, '/state?head={}&address=c'.format(ID_C))
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
            - a link property that ends in '/state?head={}&address=bad'.format(ID_C)
            - a paging property with only a total_count of 0
            - a data property that is an empty list
        """
        paging = Mocks.make_paging_response(None, 0)
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
        self.assert_has_valid_link(response, '/state?head={}&address=bad'.format(ID_C))
        self.assert_has_valid_paging(response, paging)
        self.assert_has_valid_data_list(response, 0)

    @unittest_run_loop
    async def test_state_list_with_head_and_address(self):
        """Verifies GET /state works with a head and filtered by address.

        It will receive a Protobuf response with:
            - a head id of ID_B
            - a paging response with a start of 0, and 1 total resource
            - one leaf with addresses/data of: 'a': b'2'

        It should send a Protobuf request with:
            - a head_id property of ID_B
            - an address property of 'a'
            - empty paging controls

        It should send back a JSON response with:
            - a response status of 200
            - a head property of ID_B
            - a link property that ends in
            '/state?head={}&min=0&count=1&address=a'.format(ID_B)
            - a paging property that matches the paging response
            - a data property that is a list of 1 leaf dict
            - one leaf that matches the Protobuf response
        """
        paging = Mocks.make_paging_response(0, 1)
        entries = Mocks.make_entries(a=b'2')
        self.connection.preset_response(state_root='beef', paging=paging,
                                        entries=entries)
        self.connection.preset_response(
            proto=client_block_pb2.ClientBlockGetResponse,
            block=block_pb2.Block(
                header_signature=ID_B,
                header=block_pb2.BlockHeader(
                    state_root_hash='beef').SerializeToString()))

        response = await self.get_assert_200('/state?address=a&head={}'.format(ID_B))
        self.connection.assert_valid_request_sent(
            state_root='beef',
            address='a',
            paging=Mocks.make_paging_controls())

        self.assert_has_valid_head(response, ID_B)
        self.assert_has_valid_link(response, '/state?head={}&address=a'.format(ID_B))
        self.assert_has_valid_paging(response, paging)
        self.assert_has_valid_data_list(response, 1)
        self.assert_entries_match(entries, response['data'])

    @unittest_run_loop
    async def test_state_list_paginated(self):
        """Verifies GET /state paginated by min id works properly.

        It will receive a Protobuf response with:
            - a head id of ID_D
            - a paging response with a start of 1, and 4 total resources
            - one leaf of {'c': b'3'}

        It should send a Protobuf request with:
            - a paging controls with a count of 1, and a start_index of 1

        It should send back a JSON response with:
            - a response status of 200
            - a head property of ID_D
            - a link property that ends in '/state?head={}&min=1&count=1'.format(ID_D)
            - paging that matches the response, with next and previous links
            - a data property that is a list of 1 dict
            - and that dict is a leaf that matches the one received
        """
        paging = Mocks.make_paging_response(1, 4)
        entries = Mocks.make_entries(c=b'3')
        self.connection.preset_response(state_root='beef', paging=paging,
                                        entries=entries)
        self.connection.preset_response(
            proto=client_block_pb2.ClientBlockGetResponse,
            block=block_pb2.Block(
                header_signature=ID_D,
                header=block_pb2.BlockHeader(
                    state_root_hash='beef').SerializeToString()))

        response = await self.get_assert_200('/state?min=1&count=1')
        controls = Mocks.make_paging_controls(1, start_index=1)
        self.connection.assert_valid_request_sent(
            state_root='beef', paging=controls)

        self.assert_has_valid_head(response, ID_D)
        self.assert_has_valid_link(response, '/state?head={}&min=1&count=1'.format(ID_D))
        self.assert_has_valid_paging(response, paging,
                                     '/state?head={}&min=2&count=1'.format(ID_D),
                                     '/state?head={}&min=0&count=1'.format(ID_D))
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
        self.connection.preset_response(
            proto=client_block_pb2.ClientBlockGetResponse,
            block=block_pb2.Block())
        response = await self.get_assert_status('/state?min=-1', 400)

        self.assert_has_valid_error(response, 54)

    @unittest_run_loop
    async def test_state_list_paginated_with_just_count(self):
        """Verifies GET /state paginated just by count works properly.

        It will receive a Protobuf response with:
            - a head id of ID_D
            - a paging response with a start of 0, and 4 total resources
            - two entries of {ID_D: b'4'}, and {'c': b'3'}

        It should send a Protobuf request with:
            - a paging controls with a count of 2

        It should send back a JSON response with:
            - a response status of 200
            - a head property of ID_D
            - a link property that ends in '/state?head={}&min=0&count=2'.format(ID_D)
            - paging that matches the response with a next link
            - a data property that is a list of 2 dicts
            - and those dicts are entries that match those received
        """
        paging = Mocks.make_paging_response(0, 4)
        entries = Mocks.make_entries(d=b'4', c=b'3')
        self.connection.preset_response(state_root='beef', paging=paging,
                                        entries=entries)
        self.connection.preset_response(
            proto=client_block_pb2.ClientBlockGetResponse,
            block=block_pb2.Block(
                header_signature=ID_D,
                header=block_pb2.BlockHeader(
                    state_root_hash='beef').SerializeToString()))

        response = await self.get_assert_200('/state?count=2')
        controls = Mocks.make_paging_controls(2)
        self.connection.assert_valid_request_sent(
            state_root='beef', paging=controls)

        self.assert_has_valid_head(response, ID_D)
        self.assert_has_valid_link(response, '/state?head={}&count=2'.format(ID_D))
        self.assert_has_valid_paging(response, paging,
                                     '/state?head={}&min=2&count=2'.format(ID_D))
        self.assert_has_valid_data_list(response, 2)
        self.assert_entries_match(entries, response['data'])

    @unittest_run_loop
    async def test_state_list_paginated_without_count(self):
        """Verifies GET /state paginated without count works properly.

        It will receive a Protobuf response with:
            - a head id of ID_D
            - a paging response with a start of 2, and 4 total resources
            - two entries of {'b': b'2'} and {'a': b'1'}

        It should send a Protobuf request with:
            - a paging controls with a start_index of 2

        It should send back a JSON response with:
            - a response status of 200
            - a head property of ID_D
            - a link property that ends in '/state?head={}&min=2&count=2'.format(ID_D)
            - paging that matches the response, with a previous link
            - a data property that is a list of 2 dicts
            - and those dicts are entries that match those received
        """
        paging = Mocks.make_paging_response(2, 4)
        entries = Mocks.make_entries(b=b'2', a=b'1')
        self.connection.preset_response(state_root='beef', paging=paging,
                                        entries=entries)
        self.connection.preset_response(
            proto=client_block_pb2.ClientBlockGetResponse,
            block=block_pb2.Block(
                header_signature=ID_D,
                header=block_pb2.BlockHeader(
                    state_root_hash='beef').SerializeToString()))

        response = await self.get_assert_200('/state?min=2')
        controls = Mocks.make_paging_controls(None, start_index=2)
        self.connection.assert_valid_request_sent(
            state_root='beef', paging=controls)

        self.assert_has_valid_head(response, ID_D)
        self.assert_has_valid_link(response, '/state?head={}&min=2'.format(ID_D))
        self.assert_has_valid_paging(response, paging,
                                     previous_link='/state?head={}&min=0&count=2'.format(ID_D))
        self.assert_has_valid_data_list(response, 2)
        self.assert_entries_match(entries, response['data'])

    @unittest_run_loop
    async def test_state_list_paginated_by_min_id(self):
        """Verifies GET /state paginated by a min id works properly.

        It will receive a Protobuf response with:
            - a head id of ID_D
            - a paging response with:
                * a start_index of 1
                * total_resources of 4
                * a previous_id of ID_D
            - three entries of {'c': b'3'}, {'b': b'2'}, and {'a': b'1'}

        It should send a Protobuf request with:
            - a paging controls with a start_id of ID_C

        It should send back a JSON response with:
            - a response status of 200
            - a head property of ID_D
            - a link property that ends in '/state?head={}&min={}&count=5'.format(ID_D, ID_C)
            - paging that matches the response, with a previous link
            - a data property that is a list of 3 dicts
            - and those dicts are entries that match those received
        """
        paging = Mocks.make_paging_response(1, 4, previous_id=ID_D)
        entries = Mocks.make_entries(c=b'3', b=b'2', a=b'1')
        self.connection.preset_response(state_root='beef', paging=paging,
                                        entries=entries)
        self.connection.preset_response(
            proto=client_block_pb2.ClientBlockGetResponse,
            block=block_pb2.Block(
                header_signature=ID_D,
                header=block_pb2.BlockHeader(
                    state_root_hash='beef').SerializeToString()))

        response = await self.get_assert_200('/state?min={}&count=5'.format(ID_C))
        controls = Mocks.make_paging_controls(5, start_id=ID_C)
        self.connection.assert_valid_request_sent(
            state_root='beef', paging=controls)

        self.assert_has_valid_head(response, ID_D)
        self.assert_has_valid_link(response, '/state?head={}&min={}&count=5'.format(ID_D, ID_C))
        self.assert_has_valid_paging(response, paging,
                                     previous_link='/state?head={}&max={}&count=5'.format(ID_D, ID_D))
        self.assert_has_valid_data_list(response, 3)
        self.assert_entries_match(entries, response['data'])

    @unittest_run_loop
    async def test_state_list_paginated_by_max_id(self):
        """Verifies GET /state paginated by a max id works properly.

        It will receive a Protobuf response with:
            - a head id of ID_D
            - a paging response with:
                * a start_index of 1
                * a total_resources of 4
                * a previous_id of ID_D
                * a next_id of ID_A
            - two entries of {'c': b'3'} and {'b': b'3'}

        It should send a Protobuf request with:
            - a paging controls with a count of 2 and an end_id of ID_B

        It should send back a JSON response with:
            - a response status of 200
            - a head property of ID_D
            - a link property that ends in '/state?head={}&max={}&count=2'.format(ID_D, ID_B)
            - paging that matches the response, with next and previous links
            - a data property that is a list of 2 dicts
            - and those dicts are entries that match those received
        """
        paging = Mocks.make_paging_response(1, 4, previous_id=ID_D, next_id=ID_A)
        entries = Mocks.make_entries(c=b'3', b=b'2')
        self.connection.preset_response(state_root='beef', paging=paging,
                                        entries=entries)
        self.connection.preset_response(
            proto=client_block_pb2.ClientBlockGetResponse,
            block=block_pb2.Block(
                header_signature=ID_D,
                header=block_pb2.BlockHeader(
                    state_root_hash='beef').SerializeToString()))

        response = await self.get_assert_200('/state?max={}&count=2'.format(ID_B))
        controls = Mocks.make_paging_controls(2, end_id=ID_B)
        self.connection.assert_valid_request_sent(
            state_root='beef', paging=controls)

        self.assert_has_valid_head(response, ID_D)
        self.assert_has_valid_link(response, '/state?head={}&max={}&count=2'.format(ID_D, ID_B))
        self.assert_has_valid_paging(response, paging,
                                     '/state?head={}&min={}&count=2'.format(ID_D, ID_A),
                                     '/state?head={}&max={}&count=2'.format(ID_D, ID_D))
        self.assert_has_valid_data_list(response, 2)
        self.assert_entries_match(entries, response['data'])

    @unittest_run_loop
    async def test_state_list_paginated_by_max_index(self):
        """Verifies GET /state paginated by a max index works properly.

        It will receive a Protobuf response with:
            - a head id of ID_D
            - a paging response with a start of 0, and 4 total resources
            - three entries with the ids {ID_D: b'4'}, {'c': b'3'} and {'b': b'2'}

        It should send a Protobuf request with:
            - a paging controls with a count of 2 and an start_index of 0

        It should send back a JSON response with:
            - a response status of 200
            - a head property of ID_D
            - a link property that ends in '/state?head={}&min=3&count=7'.format(ID_D)
            - paging that matches the response, with a next link
            - a data property that is a list of 2 dicts
            - and those dicts are entries that match those received
        """
        paging = Mocks.make_paging_response(0, 4)
        entries = Mocks.make_entries(d=b'4', c=b'3', b=b'2')
        self.connection.preset_response(state_root='beef', paging=paging,
                                        entries=entries)
        self.connection.preset_response(
            proto=client_block_pb2.ClientBlockGetResponse,
            block=block_pb2.Block(
                header_signature=ID_D,
                header=block_pb2.BlockHeader(
                    state_root_hash='beef').SerializeToString()))

        response = await self.get_assert_200('/state?max=2&count=7')
        controls = Mocks.make_paging_controls(3, start_index=0)
        self.connection.assert_valid_request_sent(
            state_root='beef', paging=controls)

        self.assert_has_valid_head(response, ID_D)
        self.assert_has_valid_link(response, '/state?head={}&max=2&count=7'.format(ID_D))
        self.assert_has_valid_paging(response, paging,
                                     '/state?head={}&min=3&count=7'.format(ID_D))
        self.assert_has_valid_data_list(response, 3)
        self.assert_entries_match(entries, response['data'])

    @unittest_run_loop
    async def test_state_list_sorted(self):
        """Verifies GET /state can send proper sort controls.

        It will receive a Protobuf response with:
            - a head id of ID_C
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
            - a head property of ID_C
            - a link property ending in '/state?head={}&sort=address'.format(ID_C)
            - a paging property that matches the paging response
            - a data property that is a list of 3 dicts
            - three entries that match those in Protobuf response
        """
        paging = Mocks.make_paging_response(0, 3)
        entries = Mocks.make_entries(a=b'3', b=b'5', c=b'7')
        self.connection.preset_response(state_root='beef', paging=paging,
                                        entries=entries)
        self.connection.preset_response(
            proto=client_block_pb2.ClientBlockGetResponse,
            block=block_pb2.Block(
                header_signature=ID_C,
                header=block_pb2.BlockHeader(
                    state_root_hash='beef').SerializeToString()))

        response = await self.get_assert_200('/state?sort=address')
        page_controls = Mocks.make_paging_controls()
        sorting = Mocks.make_sort_controls('address')
        self.connection.assert_valid_request_sent(
            state_root='beef',
            paging=page_controls,
            sorting=sorting)

        self.assert_has_valid_head(response, ID_C)
        self.assert_has_valid_link(response, '/state?head={}&sort=address'.format(ID_C))
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
        self.connection.preset_response(
            proto=client_block_pb2.ClientBlockGetResponse,
            block=block_pb2.Block())
        response = await self.get_assert_status('/state?sort=bad', 400)

        self.assert_has_valid_error(response, 57)

    @unittest_run_loop
    async def test_state_list_sorted_in_reverse(self):
        """Verifies a GET /state can send proper sort parameters.

        It will receive a Protobuf response with:
            - a head id of ID_C
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
            - a head property of ID_C
            - a link property ending in '/state?head={}&sort=-address'.format(ID_C)
            - a paging property that matches the paging response
            - a data property that is a list of 3 dicts
            - three entries that match those in Protobuf response
        """
        paging = Mocks.make_paging_response(0, 3)
        entries = Mocks.make_entries(c=b'7', b=b'5', a=b'3')
        self.connection.preset_response(state_root='beef', paging=paging,
                                        entries=entries)
        self.connection.preset_response(
            proto=client_block_pb2.ClientBlockGetResponse,
            block=block_pb2.Block(
                header_signature=ID_C,
                header=block_pb2.BlockHeader(
                    state_root_hash='beef').SerializeToString()))

        response = await self.get_assert_200('/state?sort=-address')
        page_controls = Mocks.make_paging_controls()
        sorting = Mocks.make_sort_controls('address', reverse=True)
        self.connection.assert_valid_request_sent(
            state_root='beef',
            paging=page_controls,
            sorting=sorting)

        self.assert_has_valid_head(response, ID_C)
        self.assert_has_valid_link(response, '/state?head={}&sort=-address'.format(ID_C))
        self.assert_has_valid_paging(response, paging)
        self.assert_has_valid_data_list(response, 3)
        self.assert_entries_match(entries, response['data'])

    @unittest_run_loop
    async def test_state_list_sorted_by_length(self):
        """Verifies a GET /state can send proper sort parameters.

        It will receive a Protobuf response with:
            - a head id of ID_C
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
            - a head property of ID_C
            - a link property ending in '/state?head={}&sort=value.length'.format(ID_C)
            - a paging property that matches the paging response
            - a data property that is a list of 3 dicts
            - three entries that match those in Protobuf response
        """
        paging = Mocks.make_paging_response(0, 3)
        entries = Mocks.make_entries(c=b'7', b=b'45', a=b'123')
        self.connection.preset_response(state_root='beef', paging=paging,
                                        entries=entries)
        self.connection.preset_response(
            proto=client_block_pb2.ClientBlockGetResponse,
            block=block_pb2.Block(
                header_signature=ID_C,
                header=block_pb2.BlockHeader(
                    state_root_hash='beef').SerializeToString()))

        response = await self.get_assert_200('/state?sort=value.length')
        page_controls = Mocks.make_paging_controls()
        sorting = Mocks.make_sort_controls('value', compare_length=True)
        self.connection.assert_valid_request_sent(
            state_root='beef',
            paging=page_controls,
            sorting=sorting)

        self.assert_has_valid_head(response, ID_C)
        self.assert_has_valid_link(response, '/state?head={}&sort=value.length'.format(ID_C))
        self.assert_has_valid_paging(response, paging)
        self.assert_has_valid_data_list(response, 3)
        self.assert_entries_match(entries, response['data'])

    @unittest_run_loop
    async def test_state_list_sorted_by_many_keys(self):
        """Verifies a GET /state can send proper sort parameters.

        It will receive a Protobuf response with:
            - a head id of ID_C
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
            - a head property of ID_C
            - link with '/state?head={}&sort=-address,value.length'.format(ID_C)
            - a paging property that matches the paging response
            - a data property that is a list of 3 dicts
            - three entries that match those in Protobuf response
        """
        paging = Mocks.make_paging_response(0, 3)
        entries = Mocks.make_entries(c=b'7', b=b'5', a=b'3')
        self.connection.preset_response(state_root='beef', paging=paging,
                                        entries=entries)
        self.connection.preset_response(
            proto=client_block_pb2.ClientBlockGetResponse,
            block=block_pb2.Block(
                header_signature=ID_C,
                header=block_pb2.BlockHeader(
                    state_root_hash='beef').SerializeToString()))

        response = await self.get_assert_200(
            '/state?sort=-address,value.length')
        page_controls = Mocks.make_paging_controls()
        sorting = (Mocks.make_sort_controls('address', reverse=True) +
                   Mocks.make_sort_controls('value', compare_length=True))
        self.connection.assert_valid_request_sent(
            state_root='beef',
            paging=page_controls,
            sorting=sorting)

        self.assert_has_valid_head(response, ID_C)
        self.assert_has_valid_link(response,
            '/state?head={}&sort=-address,value.length'.format(ID_C))
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
        return self.build_app(self.loop, '/state/{address}', handlers.fetch_state)

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
        """Verifies a GET /state/{address} with a validator error breaks properly.

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
        """Verifies a GET /state/{address} with validator not ready breaks properly.

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
        response = await self.get_assert_status('/state/b?head={}'.format(ID_D), 404)

        self.assert_has_valid_error(response, 50)

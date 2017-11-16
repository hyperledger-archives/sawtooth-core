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

from aiohttp.test_utils import unittest_run_loop
from components import Mocks, BaseApiTest
from sawtooth_rest_api.protobuf.validator_pb2 import Message
from sawtooth_rest_api.protobuf import client_pb2


class BlockListTests(BaseApiTest):

    async def get_application(self):
        self.set_status_and_connection(
            Message.CLIENT_BLOCK_LIST_REQUEST,
            client_pb2.ClientBlockListRequest,
            client_pb2.ClientBlockListResponse)

        handlers = self.build_handlers(self.loop, self.connection)
        return self.build_app(self.loop, '/blocks', handlers.list_blocks)

    @unittest_run_loop
    async def test_block_list(self):
        """Verifies a GET /blocks without parameters works properly.

        It will receive a Protobuf response with:
            - a head id of '2'
            - a paging response with a start of 0, and 3 total resources
            - three blocks with ids '2', '1', and '0'

        It should send a Protobuf request with:
            - empty paging controls

        It should send back a JSON response with:
            - a status of 200
            - a head property of '2'
            - a link property that ends in '/blocks?head=2'
            - a paging property that matches the paging response
            - a data property that is a list of 3 dicts
            - and those dicts are full blocks with ids '2', '1', and '0'
        """
        paging = Mocks.make_paging_response(0, 3)
        blocks = Mocks.make_blocks('2', '1', '0')
        self.connection.preset_response(head_id='2', paging=paging, blocks=blocks)

        response = await self.get_assert_200('/blocks')
        controls = Mocks.make_paging_controls()
        self.connection.assert_valid_request_sent(paging=controls)

        self.assert_has_valid_head(response, '2')
        self.assert_has_valid_link(response, '/blocks?head=2')
        self.assert_has_valid_paging(response, paging)
        self.assert_has_valid_data_list(response, 3)
        self.assert_blocks_well_formed(response['data'], '2', '1', '0')

    @unittest_run_loop
    async def test_block_list_with_validator_error(self):
        """Verifies a GET /blocks with a validator error breaks properly.

        It will receive a Protobuf response with:
            - a status of INTERNAL_ERROR

        It should send back a JSON response with:
            - a status of 500
            - an error property with a code of 10
        """
        self.connection.preset_response(self.status.INTERNAL_ERROR)
        response = await self.get_assert_status('/blocks', 500)

        self.assert_has_valid_error(response, 10)

    @unittest_run_loop
    async def test_block_list_with_no_genesis(self):
        """Verifies a GET /blocks with validator not ready breaks properly.

        It will receive a Protobuf response with:
            - a status of NOT_READY

        It should send back a JSON response with:
            - a status of 503
            - an error property with a code of 15
        """
        self.connection.preset_response(self.status.NOT_READY)
        response = await self.get_assert_status('/blocks', 503)

        self.assert_has_valid_error(response, 15)

    @unittest_run_loop
    async def test_block_list_with_head(self):
        """Verifies a GET /blocks with a head parameter works properly.

        It will receive a Protobuf response with:
            - a head id of '2'
            - a paging response with a start of 0, and 2 total resources
            - three blocks with ids '1' and '0'

        It should send a Protobuf request with:
            - a head_id property of '1'
            - empty paging controls

        It should send back a JSON response with:
            - a status of 200
            - a head property of '1'
            - a link property that ends in '/blocks?head=1'
            - a paging property that matches the paging response
            - a data property that is a list of 2 dicts
            - and those dicts are full blocks with ids '1' and '0'
        """
        paging = Mocks.make_paging_response(0, 2)
        blocks = Mocks.make_blocks('1', '0')
        self.connection.preset_response(head_id='1', paging=paging, blocks=blocks)

        response = await self.get_assert_200('/blocks?head=1')
        controls = Mocks.make_paging_controls()
        self.connection.assert_valid_request_sent(head_id='1', paging=controls)

        self.assert_has_valid_head(response, '1')
        self.assert_has_valid_link(response, '/blocks?head=1')
        self.assert_has_valid_paging(response, paging)
        self.assert_has_valid_data_list(response, 2)
        self.assert_blocks_well_formed(response['data'], '1', '0')

    @unittest_run_loop
    async def test_block_list_with_bad_head(self):
        """Verifies a GET /blocks with a bad head breaks properly.

        It will receive a Protobuf response with:
            - a status of NO_ROOT

        It should send back a JSON response with:
            - a status of 404
            - an error property with a code of 50
        """
        self.connection.preset_response(self.status.NO_ROOT)
        response = await self.get_assert_status('/blocks?head=bad', 404)

        self.assert_has_valid_error(response, 50)

    @unittest_run_loop
    async def test_block_list_with_ids(self):
        """Verifies GET /blocks with an id filter works properly.

        It will receive a Protobuf response with:
            - a head id of '2'
            - a paging response with a start of 0, and 2 total resources
            - two blocks with ids '0' and '2'

        It should send a Protobuf request with:
            - a block_ids property of ['0', '2']
            - empty paging controls

        It should send back a JSON response with:
            - a response status of 200
            - a head property of '2', the latest
            - a link property that ends in '/blocks?head=2&id=0,2'
            - a paging property that matches the paging response
            - a data property that is a list of 2 dicts
            - and those dicts are full blocks with ids '0' and '2'
        """
        paging = Mocks.make_paging_response(0, 2)
        blocks = Mocks.make_blocks('0', '2')
        self.connection.preset_response(head_id='2', paging=paging, blocks=blocks)

        response = await self.get_assert_200('/blocks?id=0,2')
        controls = Mocks.make_paging_controls()
        self.connection.assert_valid_request_sent(block_ids=['0', '2'], paging=controls)

        self.assert_has_valid_head(response, '2')
        self.assert_has_valid_link(response, '/blocks?head=2&id=0,2')
        self.assert_has_valid_paging(response, paging)
        self.assert_has_valid_data_list(response, 2)
        self.assert_blocks_well_formed(response['data'], '0', '2')

    @unittest_run_loop
    async def test_block_list_with_bad_ids(self):
        """Verifies GET /blocks with a bad id filter breaks properly.

        It will receive a Protobuf response with:
            - a status of NO_RESOURCE
            - a head property of '2'

        It should send back a JSON response with:
            - a response status of 200
            - a head property of '2', the latest
            - a link property that ends in '/blocks?head=2&id=bad,notgood'
            - a paging property with only a total_count of 0
            - a data property that is an empty list
        """
        paging = Mocks.make_paging_response(None, 0)
        self.connection.preset_response(
            self.status.NO_RESOURCE,
            head_id='2',
            paging=paging)
        response = await self.get_assert_200('/blocks?id=bad,notgood')

        self.assert_has_valid_head(response, '2')
        self.assert_has_valid_link(response, '/blocks?head=2&id=bad,notgood')
        self.assert_has_valid_paging(response, paging)
        self.assert_has_valid_data_list(response, 0)

    @unittest_run_loop
    async def test_block_list_with_head_and_ids(self):
        """Verifies GET /blocks with head and id parameters work properly.

        It will receive a Protobuf response with:
            - a head id of '1'
            - a paging response with a start of 0, and 1 total resource
            - one block with an id of '0'

        It should send a Protobuf request with:
            - a head_id property of '1'
            - a block_ids property of ['0']
            - empty paging controls

        It should send back a JSON response with:
            - a response status of 200
            - a head property of '1'
            - a link property that ends in '/blocks?head=1&id=0'
            - a paging property that matches the paging response
            - a data property that is a list of 1 dict
            - and that dict is a full block with an id of '0'
        """
        paging = Mocks.make_paging_response(0, 1)
        blocks = Mocks.make_blocks('0')
        self.connection.preset_response(head_id='1', paging=paging, blocks=blocks)

        response = await self.get_assert_200('/blocks?id=0&head=1')
        self.connection.assert_valid_request_sent(
            head_id='1',
            block_ids=['0'],
            paging=Mocks.make_paging_controls())

        self.assert_has_valid_head(response, '1')
        self.assert_has_valid_link(response, '/blocks?head=1&id=0')
        self.assert_has_valid_paging(response, paging)
        self.assert_has_valid_data_list(response, 1)
        self.assert_blocks_well_formed(response['data'], '0')

    @unittest_run_loop
    async def test_block_list_paginated(self):
        """Verifies GET /blocks paginated by min id works properly.

        It will receive a Protobuf response with:
            - a head id of 'd'
            - a paging response with a start of 1, and 4 total resources
            - one block with the id 'c'

        It should send a Protobuf request with:
            - paging controls with a count of 1, and a start_index of 1

        It should send back a JSON response with:
            - a response status of 200
            - a head property of 'd'
            - a link property that ends in '/blocks?head=d&min=1&count=1'
            - paging that matches the response, with next and previous links
            - a data property that is a list of 1 dict
            - and that dict is a full block with the id 'c'
        """
        paging = Mocks.make_paging_response(1, 4)
        blocks = Mocks.make_blocks('c')
        self.connection.preset_response(head_id='d', paging=paging, blocks=blocks)

        response = await self.get_assert_200('/blocks?min=1&count=1')
        controls = Mocks.make_paging_controls(1, start_index=1)
        self.connection.assert_valid_request_sent(paging=controls)

        self.assert_has_valid_head(response, 'd')
        self.assert_has_valid_link(response, '/blocks?head=d&min=1&count=1')
        self.assert_has_valid_paging(response, paging,
                                     '/blocks?head=d&min=2&count=1',
                                     '/blocks?head=d&min=0&count=1')
        self.assert_has_valid_data_list(response, 1)
        self.assert_blocks_well_formed(response['data'], 'c')

    @unittest_run_loop
    async def test_block_list_with_zero_count(self):
        """Verifies a GET /blocks with a count of zero breaks properly.

        It should send back a JSON response with:
            - a response status of 400
            - an error property with a code of 53
        """
        response = await self.get_assert_status('/blocks?min=2&count=0', 400)

        self.assert_has_valid_error(response, 53)

    @unittest_run_loop
    async def test_block_list_with_bad_paging(self):
        """Verifies a GET /blocks with a bad paging breaks properly.

        It will receive a Protobuf response with:
            - a status of INVALID_PAGING

        It should send back a JSON response with:
            - a response status of 400
            - an error property with a code of 54
        """
        self.connection.preset_response(self.status.INVALID_PAGING)
        response = await self.get_assert_status('/blocks?min=-1', 400)

        self.assert_has_valid_error(response, 54)


    @unittest_run_loop
    async def test_block_list_paginated_with_just_count(self):
        """Verifies GET /blocks paginated just by count works properly.

        It will receive a Protobuf response with:
            - a head id of 'd'
            - a paging response with a start of 0, and 4 total resources
            - two blocks with the ids 'd' and 'c'

        It should send a Protobuf request with:
            - paging controls with a count of 2

        It should send back a JSON response with:
            - a response status of 200
            - a head property of 'd'
            - a link property that ends in '/blocks?head=d'
            - paging that matches the response with a next link
            - a data property that is a list of 2 dicts
            - and those dicts are full blocks with ids 'd' and 'c'
        """
        paging = Mocks.make_paging_response(0, 4)
        blocks = Mocks.make_blocks('d', 'c')
        self.connection.preset_response(head_id='d', paging=paging, blocks=blocks)

        response = await self.get_assert_200('/blocks?count=2')
        controls = Mocks.make_paging_controls(2)
        self.connection.assert_valid_request_sent(paging=controls)

        self.assert_has_valid_head(response, 'd')
        self.assert_has_valid_link(response, '/blocks?head=d&count=2')
        self.assert_has_valid_paging(response, paging,
                                     '/blocks?head=d&min=2&count=2')
        self.assert_has_valid_data_list(response, 2)
        self.assert_blocks_well_formed(response['data'], 'd', 'c')

    @unittest_run_loop
    async def test_block_list_paginated_without_count(self):
        """Verifies GET /blocks paginated without count works properly.

        It will receive a Protobuf response with:
            - a head id of 'd'
            - a paging response with a start of 2, and 4 total resources
            - two blocks with the ids 'b' and 'a'

        It should send a Protobuf request with:
            - paging controls with a start_index of 2

        It should send back a JSON response with:
            - a response status of 200
            - a head property of 'd'
            - a link property that ends in '/blocks?head=d&min=2&count=2'
            - paging that matches the response, with a previous link
            - a data property that is a list of 2 dicts
            - and those dicts are full blocks with ids 'd' and 'c'
        """
        paging = Mocks.make_paging_response(2, 4)
        blocks = Mocks.make_blocks('b', 'a')
        self.connection.preset_response(head_id='d', paging=paging, blocks=blocks)

        response = await self.get_assert_200('/blocks?min=2')
        controls = Mocks.make_paging_controls(None, start_index=2)
        self.connection.assert_valid_request_sent(paging=controls)

        self.assert_has_valid_head(response, 'd')
        self.assert_has_valid_link(response, '/blocks?head=d&min=2')
        self.assert_has_valid_paging(response, paging,
                                     previous_link='/blocks?head=d&min=0&count=2')
        self.assert_has_valid_data_list(response, 2)
        self.assert_blocks_well_formed(response['data'], 'b', 'a')

    @unittest_run_loop
    async def test_block_list_paginated_by_min_id(self):
        """Verifies GET /blocks paginated by a min id works properly.

        It will receive a Protobuf response with:
            - a head id of 'd'
            - a paging response with:
                * a start_index of 1
                * total_resources of 4
                * a previous_id of 'd'
            - three blocks with the ids 'c', 'b' and 'a'

        It should send a Protobuf request with:
            - paging controls with a count of 5, and a start_id of 'c'

        It should send back a JSON response with:
            - a response status of 200
            - a head property of 'd'
            - a link property that ends in '/blocks?head=d&min=c&count=5'
            - paging that matches the response, with a previous link
            - a data property that is a list of 3 dicts
            - and those dicts are full blocks with ids 'c', 'b', and 'a'
        """
        paging = Mocks.make_paging_response(1, 4, previous_id='d')
        blocks = Mocks.make_blocks('c', 'b', 'a')
        self.connection.preset_response(head_id='d', paging=paging, blocks=blocks)

        response = await self.get_assert_200('/blocks?min=c&count=5')
        controls = Mocks.make_paging_controls(5, start_id='c')
        self.connection.assert_valid_request_sent(paging=controls)

        self.assert_has_valid_head(response, 'd')
        self.assert_has_valid_link(response, '/blocks?head=d&min=c&count=5')
        self.assert_has_valid_paging(response, paging,
                                     previous_link='/blocks?head=d&max=d&count=5')
        self.assert_has_valid_data_list(response, 3)
        self.assert_blocks_well_formed(response['data'], 'c', 'b', 'a')

    @unittest_run_loop
    async def test_block_list_paginated_by_max_id(self):
        """Verifies GET /blocks paginated by a max id works properly.

        It will receive a Protobuf response with:
            - a head id of 'd'
            - a paging response with:
                * a start_index of 1
                * a total_resources of 4
                * a previous_id of 'd'
                * a next_id of 'a'
            - two blocks with the ids 'c' and 'b'

        It should send a Protobuf request with:
            - paging controls with a count of 2, and an end_id of 'b'

        It should send back a JSON response with:
            - a response status of 200
            - a head property of 'd'
            - a link property that ends in '/blocks?head=d&max=b&count=2'
            - paging that matches the response, with next and previous links
            - a data property that is a list of 2 dicts
            - and those dicts are full blocks with ids 'c' and 'b'
        """
        paging = Mocks.make_paging_response(1, 4, previous_id='d', next_id='a')
        blocks = Mocks.make_blocks('c', 'b')
        self.connection.preset_response(head_id='d', paging=paging, blocks=blocks)

        response = await self.get_assert_200('/blocks?max=b&count=2')
        controls = Mocks.make_paging_controls(2, end_id='b')
        self.connection.assert_valid_request_sent(paging=controls)

        self.assert_has_valid_head(response, 'd')
        self.assert_has_valid_link(response, '/blocks?head=d&max=b&count=2')
        self.assert_has_valid_paging(response, paging,
                                     '/blocks?head=d&min=a&count=2',
                                     '/blocks?head=d&max=d&count=2')
        self.assert_has_valid_data_list(response, 2)
        self.assert_blocks_well_formed(response['data'], 'c', 'b')

    @unittest_run_loop
    async def test_block_list_paginated_by_max_index(self):
        """Verifies GET /blocks paginated by a max index works properly.

        It will receive a Protobuf response with:
            - a head id of 'd'
            - a paging response with a start of 0, and 4 total resources
            - three blocks with the ids 'd', 'c' and 'b'

        It should send a Protobuf request with:
            - paging controls with a count of 3, and an start_index of 0

        It should send back a JSON response with:
            - a response status of 200
            - a head property of 'd'
            - a link property that ends in '/blocks?head=d&min=3&count=7'
            - paging that matches the response, with a next link
            - a data property that is a list of 2 dicts
            - and those dicts are full blocks with ids 'd', 'c', and 'b'
        """
        paging = Mocks.make_paging_response(0, 4)
        blocks = Mocks.make_blocks('d', 'c', 'b')
        self.connection.preset_response(head_id='d', paging=paging, blocks=blocks)

        response = await self.get_assert_200('/blocks?max=2&count=7')
        controls = Mocks.make_paging_controls(3, start_index=0)
        self.connection.assert_valid_request_sent(paging=controls)

        self.assert_has_valid_head(response, 'd')
        self.assert_has_valid_link(response, '/blocks?head=d&max=2&count=7')
        self.assert_has_valid_paging(response, paging,
                                     '/blocks?head=d&min=3&count=7')
        self.assert_has_valid_data_list(response, 3)
        self.assert_blocks_well_formed(response['data'], 'd', 'c', 'b')

    @unittest_run_loop
    async def test_block_list_sorted(self):
        """Verifies GET /blocks can send proper sort controls.

        It will receive a Protobuf response with:
            - a head id of '2'
            - a paging response with a start of 0, and 3 total resources
            - three blocks with ids '0', '1', and '2'

        It should send a Protobuf request with:
            - empty paging controls
            - sort controls with a key of 'header_signature'

        It should send back a JSON response with:
            - a status of 200
            - a head property of '2'
            - a link property ending in '/blocks?head=2&sort=header_signature'
            - a paging property that matches the paging response
            - a data property that is a list of 3 dicts
            - and those dicts are full blocks with ids '0', '1', and '2'
        """
        paging = Mocks.make_paging_response(0, 3)
        blocks = Mocks.make_blocks('0', '1', '2')
        self.connection.preset_response(head_id='2', paging=paging, blocks=blocks)

        response = await self.get_assert_200('/blocks?sort=header_signature')
        page_controls = Mocks.make_paging_controls()
        sorting = Mocks.make_sort_controls('header_signature')
        self.connection.assert_valid_request_sent(
            paging=page_controls,
            sorting=sorting)

        self.assert_has_valid_head(response, '2')
        self.assert_has_valid_link(response,
            '/blocks?head=2&sort=header_signature')
        self.assert_has_valid_paging(response, paging)
        self.assert_has_valid_data_list(response, 3)
        self.assert_blocks_well_formed(response['data'], '0', '1', '2')

    @unittest_run_loop
    async def test_batch_list_with_bad_sort(self):
        """Verifies a GET /blocks with a bad sort breaks properly.

        It will receive a Protobuf response with:
            - a status of INVALID_PAGING

        It should send back a JSON response with:
            - a response status of 400
            - an error property with a code of 57
        """
        self.connection.preset_response(self.status.INVALID_SORT)
        response = await self.get_assert_status('/blocks?sort=bad', 400)

        self.assert_has_valid_error(response, 57)

    @unittest_run_loop
    async def test_block_list_sorted_with_nested_keys(self):
        """Verifies GET /blocks can send proper sort controls with nested keys.

        It will receive a Protobuf response with:
            - a head id of '2'
            - a paging response with a start of 0, and 3 total resources
            - three blocks with ids '0', '1', and '2'

        It should send a Protobuf request with:
            - empty paging controls
            - sort controls with keys of 'header' and 'signer_pubkey'

        It should send back a JSON response with:
            - a status of 200
            - a head property of '2'
            - a link ending in '/blocks?head=2&sort=header.signer_pubkey'
            - a paging property that matches the paging response
            - a data property that is a list of 3 dicts
            - and those dicts are full blocks with ids '0', '1', and '2'
        """
        paging = Mocks.make_paging_response(0, 3)
        blocks = Mocks.make_blocks('0', '1', '2')
        self.connection.preset_response(head_id='2', paging=paging, blocks=blocks)

        response = await self.get_assert_200(
            '/blocks?sort=header.signer_pubkey')
        page_controls = Mocks.make_paging_controls()
        sorting = Mocks.make_sort_controls('header', 'signer_pubkey')
        self.connection.assert_valid_request_sent(
            paging=page_controls,
            sorting=sorting)

        self.assert_has_valid_head(response, '2')
        self.assert_has_valid_link(response,
            '/blocks?head=2&sort=header.signer_pubkey')
        self.assert_has_valid_paging(response, paging)
        self.assert_has_valid_data_list(response, 3)
        self.assert_blocks_well_formed(response['data'], '0', '1', '2')

    @unittest_run_loop
    async def test_block_list_sorted_in_reverse(self):
        """Verifies a GET /blocks can send proper sort parameters.

        It will receive a Protobuf response with:
            - a head id of '2'
            - a paging response with a start of 0, and 3 total resources
            - three blocks with ids '2', '1', and '0'

        It should send a Protobuf request with:
            - empty paging controls
            - sort controls with a key of 'header_signature' that is reversed

        It should send back a JSON response with:
            - a status of 200
            - a head property of '2'
            - a link property ending in '/blocks?head=2&sort=-header_signature'
            - a paging property that matches the paging response
            - a data property that is a list of 3 dicts
            - and those dicts are full blocks with ids '2', '1', and '0'
        """
        paging = Mocks.make_paging_response(0, 3)
        blocks = Mocks.make_blocks('2', '1', '0')
        self.connection.preset_response(head_id='2', paging=paging, blocks=blocks)

        response = await self.get_assert_200('/blocks?sort=-header_signature')
        page_controls = Mocks.make_paging_controls()
        sorting = Mocks.make_sort_controls(
            'header_signature', reverse=True)
        self.connection.assert_valid_request_sent(
            paging=page_controls,
            sorting=sorting)

        self.assert_has_valid_head(response, '2')
        self.assert_has_valid_link(response,
            '/blocks?head=2&sort=-header_signature')
        self.assert_has_valid_paging(response, paging)
        self.assert_has_valid_data_list(response, 3)
        self.assert_blocks_well_formed(response['data'], '2', '1', '0')

    @unittest_run_loop
    async def test_block_list_sorted_by_length(self):
        """Verifies a GET /blocks can send proper sort parameters.

        It will receive a Protobuf response with:
            - a head id of '2'
            - a paging response with a start of 0, and 3 total resources
            - three blocks with ids '0', '1', and '2'

        It should send a Protobuf request with:
            - empty paging controls
            - sort controls with a key of 'batches' sorted by length

        It should send back a JSON response with:
            - a status of 200
            - a head property of '2'
            - a link property ending in '/blocks?head=2&sort=batches.length'
            - a paging property that matches the paging response
            - a data property that is a list of 3 dicts
            - and those dicts are full blocks with ids '0', '1', and '2'
        """
        paging = Mocks.make_paging_response(0, 3)
        blocks = Mocks.make_blocks('0', '1', '2')
        self.connection.preset_response(head_id='2', paging=paging, blocks=blocks)

        response = await self.get_assert_200('/blocks?sort=batches.length')
        page_controls = Mocks.make_paging_controls()
        sorting = Mocks.make_sort_controls('batches', compare_length=True)
        self.connection.assert_valid_request_sent(
            paging=page_controls,
            sorting=sorting)

        self.assert_has_valid_head(response, '2')
        self.assert_has_valid_link(response,
            '/blocks?head=2&sort=batches.length')
        self.assert_has_valid_paging(response, paging)
        self.assert_has_valid_data_list(response, 3)
        self.assert_blocks_well_formed(response['data'], '0', '1', '2')

    @unittest_run_loop
    async def test_block_list_sorted_by_many_keys(self):
        """Verifies a GET /blocks can send proper sort parameters.

        It will receive a Protobuf response with:
            - a head id of '2'
            - a paging response with a start of 0, and 3 total resources
            - three blocks with ids '2', '1', and '0'

        It should send a Protobuf request with:
            - empty paging controls
            - multiple sort controls with:
                * a key of 'header_signature' that is reversed
                * a key of 'batches' that is sorted by length

        It should send back a JSON response with:
            - a status of 200
            - a head property of '2'
            - link with '/blocks?head=2&sort=-header_signature,batches.length'
            - a paging property that matches the paging response
            - a data property that is a list of 3 dicts
            - and those dicts are full blocks with ids '2', '1', and '0'
        """
        paging = Mocks.make_paging_response(0, 3)
        blocks = Mocks.make_blocks('2', '1', '0')
        self.connection.preset_response(head_id='2', paging=paging, blocks=blocks)

        response = await self.get_assert_200(
            '/blocks?sort=-header_signature,batches.length')
        page_controls = Mocks.make_paging_controls()
        sorting = (Mocks.make_sort_controls('header_signature', reverse=True) +
                   Mocks.make_sort_controls('batches', compare_length=True))
        self.connection.assert_valid_request_sent(
            paging=page_controls,
            sorting=sorting)

        self.assert_has_valid_head(response, '2')
        self.assert_has_valid_link(response,
            '/blocks?head=2&sort=-header_signature,batches.length')
        self.assert_has_valid_paging(response, paging)
        self.assert_has_valid_data_list(response, 3)
        self.assert_blocks_well_formed(response['data'], '2', '1', '0')


class BlockGetTests(BaseApiTest):

    async def get_application(self):
        self.set_status_and_connection(
            Message.CLIENT_BLOCK_GET_REQUEST,
            client_pb2.ClientBlockGetRequest,
            client_pb2.ClientBlockGetResponse)

        handlers = self.build_handlers(self.loop, self.connection)
        return self.build_app(self.loop, '/blocks/{block_id}', handlers.fetch_block)

    @unittest_run_loop
    async def test_block_get(self):
        """Verifies a GET /blocks/{block_id} works properly.

        It should send a Protobuf request with:
            - a block_id property of '1'

        It will receive a Protobuf response with:
            - a block with an id of '1'

        It should send back a JSON response with:
            - a response status of 200
            - no head property
            - a link property that ends in '/blocks/1'
            - a data property that is a full block with an id of '0'
        """
        self.connection.preset_response(block=Mocks.make_blocks('1')[0])

        response = await self.get_assert_200('/blocks/1')
        self.connection.assert_valid_request_sent(block_id='1')

        self.assertNotIn('head', response)
        self.assert_has_valid_link(response, '/blocks/1')
        self.assertIn('data', response)
        self.assert_blocks_well_formed(response['data'], '1')

    @unittest_run_loop
    async def test_block_get_with_validator_error(self):
        """Verifies GET /blocks/{block_id} w/ validator error breaks properly.

        It will receive a Protobuf response with:
            - a status of INTERNAL_ERROR

        It should send back a JSON response with:
            - a status of 500
            - an error property with a code of 10
        """
        self.connection.preset_response(self.status.INTERNAL_ERROR)
        response = await self.get_assert_status('/blocks/1', 500)

        self.assert_has_valid_error(response, 10)

    @unittest_run_loop
    async def test_block_get_with_bad_id(self):
        """Verifies a GET /blocks/{block_id} with unfound id breaks properly.

        It will receive a Protobuf response with:
            - a status of NO_RESOURCE

        It should send back a JSON response with:
            - a response status of 404
            - an error property with a code of 70
        """
        self.connection.preset_response(self.status.NO_RESOURCE)
        response = await self.get_assert_status('/blocks/bad', 404)

        self.assert_has_valid_error(response, 70)

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
from tests.unit.components import Mocks, BaseApiTest
from sawtooth_sdk.protobuf.validator_pb2 import Message
from sawtooth_rest_api.protobuf import client_pb2


class StateListTests(BaseApiTest):

    async def get_application(self, loop):
        self.set_status_and_stream(
            Message.CLIENT_STATE_LIST_REQUEST,
            client_pb2.ClientStateListRequest,
            client_pb2.ClientStateListResponse)

        handlers = self.build_handlers(self.stream)
        return self.build_app(loop, '/state', handlers.state_list)

    @unittest_run_loop
    async def test_state_list(self):
        """Verifies a GET /state without parameters works properly.

        It will receive a Protobuf response with:
            - a head id of '2'
            - three leaves with addresses/data of:
                * 'a': b'3'
                * 'b': b'5'
                * 'c': b'7'

        It should send an empty Protobuf request of the correct type

        It should send back a JSON response with:
            - a response status of 200
            - a head property of '2'
            - a link property that ends in '/state?head=2'
            - a data property that is a list of 3 leaf dicts
            - three leaves that match those in Protobuf response
        """
        leaves = Mocks.make_leaves(a=b'3', b=b'5', c=b'7')
        self.stream.preset_response(head_id='2', leaves=leaves)

        response = await self.get_json_assert_200('/state')
        self.stream.assert_valid_request_sent()

        self.assert_has_valid_head(response, '2')
        self.assert_has_valid_link(response, '/state?head=2')
        self.assert_has_valid_data_list(response, 3)
        self.assert_leaves_match(leaves, response['data'])

    @unittest_run_loop
    async def test_state_list_with_validator_error(self):
        """Verifies a GET /state with a validator error breaks properly.

        It will receive a Protobuf response with:
            - a status of INTERNAL_ERROR

        It should send back a JSON response with:
            - a status of 500
        """
        self.stream.preset_response(self.status.INTERNAL_ERROR)
        await self.assert_500('/state')

    @unittest_run_loop
    async def test_state_list_with_no_genesis(self):
        """Verifies a GET /state with validator not ready breaks properly.

        It will receive a Protobuf response with:
            - a status of NOT_READY

        It should send back a JSON response with:
            - a status of 503
        """
        self.stream.preset_response(self.status.NOT_READY)
        await self.assert_503('/state')

    @unittest_run_loop
    async def test_state_list_with_head(self):
        """Verifies a GET /state works properly with head specified.

        It will receive a Protobuf response with:
            - a head id of '1'
            - two leaves with addresses/data of:
                * 'a': b'2'
                * 'b': b'4'

        It should send a Protobuf request with:
            - a head_id property of '1'

        It should send back a JSON response with:
            - a response status of 200
            - a head property of '1'
            - a link property that ends in '/state?head=1'
            - a data property that is a list of 2 leaf dicts
            - three leaves that match those in Protobuf response
        """
        leaves = Mocks.make_leaves(a=b'2', b=b'4')
        self.stream.preset_response(head_id='1', leaves=leaves)

        response = await self.get_json_assert_200('/state?head=1')
        self.stream.assert_valid_request_sent(head_id='1')

        self.assert_has_valid_head(response, '1')
        self.assert_has_valid_link(response, '/state?head=1')
        self.assert_has_valid_data_list(response, 2)
        self.assert_leaves_match(leaves, response['data'])

    @unittest_run_loop
    async def test_state_list_with_bad_head(self):
        """Verifies a GET /state breaks properly with a bad head specified.

        It will receive a Protobuf response with:
            - a status of NO_ROOT

        It should send back a JSON response with:
            - a response status of 404
        """
        self.stream.preset_response(self.status.NO_ROOT)
        await self.assert_404('/state?head=bad')

    @unittest_run_loop
    async def test_state_list_with_address(self):
        """Verifies a GET /state works properly filtered by address.

        It will receive a Protobuf response with:
            - a head id of '2'
            - one leaf with addresses/data of: 'c': b'7'

        It should send a Protobuf request with:
            - an address property of 'c'

        It should send back a JSON response with:
            - a response status of 200
            - a head property of '2'
            - a link property that ends in '/state?head=2&address=c'
            - a data property that is a list of 1 leaf dict
            - one leaf that matches the Protobuf response
        """
        leaves = Mocks.make_leaves(c=b'7')
        self.stream.preset_response(head_id='2', leaves=leaves)

        response = await self.get_json_assert_200('/state?address=c')
        self.stream.assert_valid_request_sent(address='c')

        self.assert_has_valid_head(response, '2')
        self.assert_has_valid_link(response, '/state?head=2&address=c')
        self.assert_has_valid_data_list(response, 1)
        self.assert_leaves_match(leaves, response['data'])

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
            - a data property that is an empty list
        """
        self.stream.preset_response(self.status.NO_RESOURCE, head_id='2')
        response = await self.get_json_assert_200('/state?address=bad')

        self.assert_has_valid_head(response, '2')
        self.assert_has_valid_link(response, '/state?head=2&address=bad')
        self.assert_has_valid_data_list(response, 0)

    @unittest_run_loop
    async def test_state_list_with_head_and_address(self):
        """Verifies GET /state works with a head and filtered by address.

        It will receive a Protobuf response with:
            - a head id of '1'
            - one leaf with addresses/data of: 'a': b'2'

        It should send a Protobuf request with:
            - a head_id property of '1'
            - an address property of 'a'

        It should send back a JSON response with:
            - a response status of 200
            - a head property of '1'
            - a link property that ends in '/state?head=1&address=a'
            - a data property that is a list of 1 leaf dict
            - one leaf that matches the Protobuf response
        """
        leaves = Mocks.make_leaves(a=b'2')
        self.stream.preset_response(head_id='1', leaves=leaves)

        response = await self.get_json_assert_200('/state?address=a&head=1')
        self.stream.assert_valid_request_sent(head_id='1', address='a')

        self.assert_has_valid_head(response, '1')
        self.assert_has_valid_link(response, '/state?head=1&address=a')
        self.assert_has_valid_data_list(response, 1)
        self.assert_leaves_match(leaves, response['data'])


class StateGetTests(BaseApiTest):

    async def get_application(self, loop):
        self.set_status_and_stream(
            Message.CLIENT_STATE_GET_REQUEST,
            client_pb2.ClientStateGetRequest,
            client_pb2.ClientStateGetResponse)

        handlers = self.build_handlers(self.stream)
        return self.build_app(loop, '/state/{address}', handlers.state_get)

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
        self.stream.preset_response(head_id='2', value=b'3')

        response = await self.get_json_assert_200('/state/a')
        self.stream.assert_valid_request_sent(address='a')

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
        """
        self.stream.preset_response(self.status.INTERNAL_ERROR)
        await self.assert_500('/state/a')

    @unittest_run_loop
    async def test_state_get_with_no_genesis(self):
        """Verifies a GET /state/{address} with validator not ready breaks properly.

        It will receive a Protobuf response with:
            - a status of NOT_READY

        It should send back a JSON response with:
            - a status of 503
        """
        self.stream.preset_response(self.status.NOT_READY)
        await self.assert_503('/state/a')

    @unittest_run_loop
    async def test_state_get_with_bad_address(self):
        """Verifies a GET /state/{address} breaks with a bad address.

        It will receive a Protobuf response with:
            - a status of NO_RESOURCE

        It should send back a JSON response with:
            - a response status of 404
        """
        self.stream.preset_response(self.status.NO_RESOURCE)
        await self.assert_404('/state/bad')

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
        self.stream.preset_response(head_id='1', value=b'4')

        response = await self.get_json_assert_200('/state/b?head=1')
        self.stream.assert_valid_request_sent(head_id='1', address='b')

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
        """
        self.stream.preset_response(self.status.NO_ROOT)
        await self.assert_404('/state/c?head=bad')

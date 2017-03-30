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
from tests.unit.components import Mocks, BaseApiTest
from sawtooth_sdk.protobuf.validator_pb2 import Message
from sawtooth_rest_api.protobuf import client_pb2


class BatchListTests(BaseApiTest):

    async def get_application(self, loop):
        self.set_status_and_stream(
            Message.CLIENT_BATCH_LIST_REQUEST,
            client_pb2.ClientBatchListRequest,
            client_pb2.ClientBatchListResponse)

        handlers = self.build_handlers(self.stream)
        return self.build_app(loop, '/batches', handlers.batch_list)

    @unittest_run_loop
    async def test_batch_list(self):
        """Verifies a GET /batches without parameters works properly.

        It will receive a Protobuf response with:
            - a head id of '2'
            - three batches with ids of '2', '1', and '0'

        It should send an empty Protobuf request of the correct type

        It should send back a JSON response with:
            - a response status of 200
            - a head property of '2'
            - a link property that ends in '/batches?head=2'
            - a data property that is a list of 3 dicts
            - and those dicts are full batches with ids '2', '1', and '0'
        """
        batches = Mocks.make_batches('2', '1', '0')
        self.stream.preset_response(head_id='2', batches=batches)

        response = await self.get_json_assert_200('/batches')
        self.stream.assert_valid_request_sent()

        self.assert_has_valid_head(response, '2')
        self.assert_has_valid_link(response, '/batches?head=2')
        self.assert_has_valid_data_list(response, 3)
        self.assert_batches_well_formed(response['data'], '2', '1', '0')

    @unittest_run_loop
    async def test_batch_list_with_validator_error(self):
        """Verifies a GET /batches with a validator error breaks properly.

        It will receive a Protobuf response with:
            - a status of INTERNAL_ERROR

        It should send back a JSON response with:
            - a status of 500
        """
        self.stream.preset_response(self.status.INTERNAL_ERROR)
        await self.assert_500('/batches')

    @unittest_run_loop
    async def test_batch_list_with_no_genesis(self):
        """Verifies a GET /batches with validator not ready breaks properly.

        It will receive a Protobuf response with:
            - a status of NOT_READY

        It should send back a JSON response with:
            - a status of 503
        """
        self.stream.preset_response(self.status.NOT_READY)
        await self.assert_503('/batches')

    @unittest_run_loop
    async def test_batch_list_with_head(self):
        """Verifies a GET /batches with a head parameter works properly.

        It will receive a Protobuf response with:
            - a head id of '1'
            - two batches with ids of 1' and '0'

        It should send a Protobuf request with:
            - a head_id property of '1'

        It should send back a JSON response with:
            - a response status of 200
            - a head property of '1'
            - a link property that ends in '/batches?head=1'
            - a data property that is a list of 2 dicts
            - and those dicts are full batches with ids '1' and '0'
        """
        batches = Mocks.make_batches('1', '0')
        self.stream.preset_response(head_id='1', batches=batches)

        response = await self.get_json_assert_200('/batches?head=1')
        self.stream.assert_valid_request_sent(head_id='1')

        self.assert_has_valid_head(response, '1')
        self.assert_has_valid_link(response, '/batches?head=1')
        self.assert_has_valid_data_list(response, 2)
        self.assert_batches_well_formed(response['data'], '1', '0')

    @unittest_run_loop
    async def test_batch_list_with_bad_head(self):
        """Verifies a GET /batches with a bad head breaks properly.

        It will receive a Protobuf response with:
            - a status of NO_ROOT

        It should send back a JSON response with:
            - a response status of 404
        """
        self.stream.preset_response(self.status.NO_ROOT)
        await self.assert_404('/batches?head=bad')

    @unittest_run_loop
    async def test_batch_list_with_ids(self):
        """Verifies GET /batches with the id parameter works properly.

        It will receive a Protobuf response with:
            - a head id of '2'
            - two batches with ids of '0' and '2'

        It should send a Protobuf request with:
            - a batch_ids property of ['0', '2']

        It should send back a JSON response with:
            - a response status of 200
            - a head property of '2', the latest
            - a link property that ends in '/batches?head=2&id=0,2'
            - a data property that is a list of 2 dicts
            - and those dicts are full batches with ids '0' and '2'
        """
        batches = Mocks.make_batches('0', '2')
        self.stream.preset_response(head_id='2', batches=batches)

        response = await self.get_json_assert_200('/batches?id=0,2')
        self.stream.assert_valid_request_sent(batch_ids=['0', '2'])

        self.assert_has_valid_head(response, '2')
        self.assert_has_valid_link(response, '/batches?head=2&id=0,2')
        self.assert_has_valid_data_list(response, 2)
        self.assert_batches_well_formed(response['data'], '0', '2')

    @unittest_run_loop
    async def test_batch_list_with_bad_ids(self):
        """Verifies GET /batches with a bad id parameter breaks properly.

        It will receive a Protobuf response with:
            - a status of NO_RESOURCE
            - a head id of '2'

        It should send back a JSON response with:
            - a response status of 200
            - a head property of '2', the latest
            - a link property that ends in '/batches?head=2&id=bad,notgood'
            - a data property that is an empty list
        """
        self.stream.preset_response(self.status.NO_RESOURCE, head_id='2')
        response = await self.get_json_assert_200('/batches?id=bad,notgood')

        self.assert_has_valid_head(response, '2')
        self.assert_has_valid_link(response, '/batches?head=2&id=bad,notgood')
        self.assert_has_valid_data_list(response, 0)

    @unittest_run_loop
    async def test_batch_list_with_head_and_ids(self):
        """Verifies GET /batches with head and id parameters works properly.

        It should send a Protobuf request with:
            - a head_id property of '1'
            - a batch_ids property of ['0']

        It will receive a Protobuf response with:
            - a head id of '1'
            - one batch with an id of '0'

        It should send back a JSON response with:
            - a response status of 200
            - a head property of '1'
            - a link property that ends in '/batches?head=1&id=0'
            - a data property that is a list of 1 dict
            - and that dict is a full batch with an id of '0'
        """
        batches = Mocks.make_batches('0')
        self.stream.preset_response(head_id='1', batches=batches)

        response = await self.get_json_assert_200('/batches?id=0&head=1')
        self.stream.assert_valid_request_sent(head_id='1', batch_ids=['0'])

        self.assert_has_valid_head(response, '1')
        self.assert_has_valid_link(response, '/batches?head=1&id=0')
        self.assert_has_valid_data_list(response, 1)
        self.assert_batches_well_formed(response['data'], '0')


class BatchGetTests(BaseApiTest):

    async def get_application(self, loop):
        self.set_status_and_stream(
            Message.CLIENT_BATCH_GET_REQUEST,
            client_pb2.ClientBatchGetRequest,
            client_pb2.ClientBatchGetResponse)

        handlers = self.build_handlers(self.stream)
        return self.build_app(loop, '/batches/{batch_id}', handlers.batch_get)

    @unittest_run_loop
    async def test_batch_get(self):
        """Verifies a GET /batches/{batch_id} works properly.

        It should send a Protobuf request with:
            - a head_id property of '1'
            - a block_ids property of ['0']

        It will receive a Protobuf response with:
            - a head id of '1'
            - three batches with ids of '2', '1', and '0'

        It should send back a JSON response with:
            - a response status of 200
            - no head property
            - a link property that ends in '/batches/1'
            - a data property that is a full batch with an id of '1'
        """
        self.stream.preset_response(batch=Mocks.make_batches('1')[0])

        response = await self.get_json_assert_200('/batches/1')
        self.stream.assert_valid_request_sent(batch_id='1')

        self.assertNotIn('head', response)
        self.assert_has_valid_link(response, '/batches/1')
        self.assertIn('data', response)
        self.assert_batches_well_formed(response['data'], '1')

    @unittest_run_loop
    async def test_batch_get_with_validator_error(self):
        """Verifies GET /batches/{batch_id} w/ validator error breaks properly.

        It will receive a Protobuf response with:
            - a status of INTERNAL_ERROR

        It should send back a JSON response with:
            - a status of 500
        """
        self.stream.preset_response(self.status.INTERNAL_ERROR)
        await self.assert_500('/batches/1')

    @unittest_run_loop
    async def test_batch_get_with_bad_id(self):
        """Verifies a GET /batches/{batch_id} with invalid id breaks properly.

        It will receive a Protobuf response with:
            - a status of INVALID_ID

        It should send back a JSON response with:
            - a response status of 400
        """
        self.stream.preset_response(self.status.INVALID_ID)
        await self.assert_400('/batches/bad')

    @unittest_run_loop
    async def test_batch_get_with_missing_id(self):
        """Verifies a GET /batches/{batch_id} with unfound id breaks properly.

        It will receive a Protobuf response with:
            - a status of NO_RESOURCE

        It should send back a JSON response with:
            - a response status of 404
        """
        self.stream.preset_response(self.status.NO_RESOURCE)
        await self.assert_404('/batches/missing')
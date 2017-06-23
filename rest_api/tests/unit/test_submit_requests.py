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

import json
from aiohttp.test_utils import unittest_run_loop
from tests.unit.components import Mocks, BaseApiTest
from sawtooth_sdk.protobuf.validator_pb2 import Message
from sawtooth_rest_api.protobuf import client_pb2
from sawtooth_rest_api.protobuf.client_pb2 import BatchStatus


class PostBatchTests(BaseApiTest):

    async def get_application(self, loop):
        self.set_status_and_stream(
            Message.CLIENT_BATCH_SUBMIT_REQUEST,
            client_pb2.ClientBatchSubmitRequest,
            client_pb2.ClientBatchSubmitResponse)

        handlers = self.build_handlers(loop, self.stream)
        return self.build_app(loop, '/batches', handlers.submit_batches)

    @unittest_run_loop
    async def test_post_batch(self):
        """Verifies a POST /batches with one id works properly.

        It will receive a Protobuf response with:
            - the default status of OK

        It should send a Protobuf request with:
            - a batches property that matches the batches sent

        It should send back a JSON response with:
            - a response status of 202
            - no data property
            - a link property that ends in '/batch_status?id=a'
        """
        batches = Mocks.make_batches('a')
        self.stream.preset_response()

        request = await self.post_batches(batches)
        self.stream.assert_valid_request_sent(batches=batches)
        self.assertEqual(202, request.status)

        response = await request.json()
        self.assertNotIn('data', response)
        self.assert_has_valid_link(response, '/batch_status?id=a')

    @unittest_run_loop
    async def test_post_batch_with_validator_error(self):
        """Verifies a POST /batches with a validator error breaks properly.

        It will receive a Protobuf response with:
            - a status of INTERNAL_ERROR

        It should send back a JSON response with:
            - a status of 500
            - an error property with a code of 10
        """
        batches = Mocks.make_batches('a')
        self.stream.preset_response(self.status.INTERNAL_ERROR)

        request = await self.post_batches(batches)
        self.assertEqual(500, request.status)

        response = await request.json()
        self.assert_has_valid_error(response, 10)

    @unittest_run_loop
    async def test_post_json_batch(self):
        """Verifies a POST /batches with a JSON request body breaks properly.

        It should send back a JSON response with:
            - a response status of 400
            - an error property with a code of 42
        """
        request = await self.client.post(
            '/batches',
            data='{"bad": "data"}',
            headers={'content-type': 'application/json'})
        self.assertEqual(400, request.status)

        response = await request.json()
        self.assert_has_valid_error(response, 42)

    @unittest_run_loop
    async def test_post_invalid_batch(self):
        """Verifies a POST /batches with an invalid batch breaks properly.

        It will receive a Protobuf response with:
            - a status of INVALID_BATCH

        It should send back a JSON response with:
            - a response status of 400
            - an error property with a code of 30
        """
        batches = Mocks.make_batches('bad')
        self.stream.preset_response(self.status.INVALID_BATCH)

        request = await self.post_batches(batches)
        self.assertEqual(400, request.status)

        response = await request.json()
        self.assert_has_valid_error(response, 30)

    @unittest_run_loop
    async def test_post_many_batches(self):
        """Verifies a POST /batches with many ids works properly.

        It will receive a Protobuf response with:
            - the default status of OK

        It should send a Protobuf request with:
            - a batches property that matches the batches sent

        It should send back a JSON response with:
            - a response status of 202
            - no data property
            - a link property that ends in '/batch_status?id=a,b,c'
        """
        batches = Mocks.make_batches('a', 'b', 'c')
        self.stream.preset_response()

        request = await self.post_batches(batches)
        self.stream.assert_valid_request_sent(batches=batches)
        self.assertEqual(202, request.status)

        response = await request.json()
        self.assertNotIn('data', response)
        self.assert_has_valid_link(response, '/batch_status?id=a,b,c')

    @unittest_run_loop
    async def test_post_no_batches(self):
        """Verifies a POST /batches with no batches breaks properly.

        It should send back a JSON response with:
            - a response status of 400
            - an error property with a code of 34
        """
        request = await self.post_batches([])
        self.assertEqual(400, request.status)

        response = await request.json()
        self.assert_has_valid_error(response, 34)

    @unittest_run_loop
    async def test_post_batch_with_wait(self):
        """Verifies a POST /batches can wait for commit properly.

        It will receive a Protobuf response with:
            - batch statuses of {'a': COMMITTED}

        It should send a Protobuf request with:
            - a batches property that matches the batches sent
            - a wait_for_commit property that is True
            - a timeout property of 4 (Rest Api default)

        It should send back a JSON response with:
            - a response status of 201
            - no data property
            - a link property that ends in '/batches?id=a'
        """
        batches = Mocks.make_batches('a')
        statuses = [BatchStatus(batch_id='a', status=BatchStatus.COMMITTED)]
        self.stream.preset_response(batch_statuses=statuses)

        request = await self.post_batches(batches, wait=True)
        self.stream.assert_valid_request_sent(
            batches=batches,
            wait_for_commit=True,
            timeout=4)
        self.assertEqual(201, request.status)

        response = await request.json()
        self.assert_has_valid_link(response, '/batches?id=a')
        self.assertNotIn('data', response)

    @unittest_run_loop
    async def test_post_batch_with_timeout(self):
        """Verifies a POST /batches works when timed out while waiting.

        It will receive a Protobuf response with:
            - batch statuses of {'pending': PENDING}

        It should send a Protobuf request with:
            - a batches property that matches the batches sent
            - a wait_for_commit property that is True
            - a timeout property of 4 (Rest Api default)

        It should send back a JSON response with:
            - a response status of 200
            - a link property that ends in '/batch_status?id=pending'
            - a data property matching the batch statuses received
        """
        batches = Mocks.make_batches('pending')
        statuses = [BatchStatus(batch_id='pending', status=BatchStatus.PENDING)]
        self.stream.preset_response(batch_statuses=statuses)

        request = await self.post_batches(batches, wait=True)
        self.stream.assert_valid_request_sent(
            batches=batches,
            wait_for_commit=True,
            timeout=4)
        self.assertEqual(202, request.status)

        response = await request.json()
        self.assert_has_valid_link(response, '/batch_status?id=pending&wait')
        self.assert_statuses_match(statuses, response['data'])


class BatchStatusTests(BaseApiTest):

    async def get_application(self, loop):
        self.set_status_and_stream(
            Message.CLIENT_BATCH_STATUS_REQUEST,
            client_pb2.ClientBatchStatusRequest,
            client_pb2.ClientBatchStatusResponse)

        handlers = self.build_handlers(loop, self.stream)
        return self.build_app(loop, '/batch_status', handlers.list_statuses)

    @unittest_run_loop
    async def test_batch_status_with_one_id(self):
        """Verifies a GET /batch_status with one id works properly.

        It will receive a Protobuf response with:
            - batch statuses of {batch_id: 'pending',  status: PENDING}

        It should send a Protobuf request with:
            - a batch_ids property of ['pending']

        It should send back a JSON response with:
            - a response status of 200
            - a link property that ends in '/batch_status?id=pending'
            - a data property matching the batch statuses received
        """
        statuses = [BatchStatus(batch_id='pending', status=BatchStatus.PENDING)]
        self.stream.preset_response(batch_statuses=statuses)

        response = await self.get_assert_200('/batch_status?id=pending')
        self.stream.assert_valid_request_sent(batch_ids=['pending'])

        self.assert_has_valid_link(response, '/batch_status?id=pending')
        self.assert_statuses_match(statuses, response['data'])

    @unittest_run_loop
    async def test_batch_status_with_invalid_data(self):
        """Verifies a GET /batch_status with fetched invalid data works.

        It will receive a Protobuf response with:
            - batch_id: 'bad-batch'
            - status: INVALID
            - invalid_transaction: 'bad-transaction'
            - message: 'error message'
            - extended_data: b'error data'

        It should send a Protobuf request with:
            - a batch_ids property of ['bad']

        It should send back a JSON response with:
            - a response status of 200
            - a link property that ends in '/batch_status?id=bad'
            - a data property matching the batch statuses received
        """
        statuses = [BatchStatus(
            batch_id='bad-batch',
            status=BatchStatus.INVALID,
            invalid_transactions=[BatchStatus.InvalidTransaction(
                transaction_id='bad-transaction',
                message='error message',
                extended_data=b'error data')])]
        self.stream.preset_response(batch_statuses=statuses)

        response = await self.get_assert_200('/batch_status?id=bad')
        self.stream.assert_valid_request_sent(batch_ids=['bad'])

        self.assert_has_valid_link(response, '/batch_status?id=bad')
        self.assert_statuses_match(statuses, response['data'])

    @unittest_run_loop
    async def test_batch_status_with_validator_error(self):
        """Verifies a GET /batch_status with a validator error breaks properly.

        It will receive a Protobuf response with:
            - a status of INTERNAL_ERROR

        It should send back a JSON response with:
            - a status of 500
            - an error property with a code of 10
        """
        self.stream.preset_response(self.status.INTERNAL_ERROR)
        response = await self.get_assert_status('/batch_status?id=pending', 500)

        self.assert_has_valid_error(response, 10)

    @unittest_run_loop
    async def test_batch_status_with_missing_statuses(self):
        """Verifies a GET /batch_status with no statuses breaks properly.

        It will receive a Protobuf response with:
            - a status of NO_RESOURCE

        It should send back a JSON response with:
            - a status of 500
            - an error property with a code of 27
        """
        self.stream.preset_response(self.status.NO_RESOURCE)
        response = await self.get_assert_status('/batch_status?id=pending', 500)

        self.assert_has_valid_error(response, 27)

    @unittest_run_loop
    async def test_batch_status_with_wait(self):
        """Verifies a GET /batch_status with a wait set works properly.

        It will receive a Protobuf response with:
            - batch statuses of {batch_id: 'pending', status: COMMITTED}

        It should send a Protobuf request with:
            - a batch_ids property of ['pending']
            - a wait_for_commit property that is True
            - a timeout property of 4 (Rest Api default)

        It should send back a JSON response with:
            - a response status of 200
            - a link property that ends in '/batch_status?id=pending&wait'
            - a data property matching the batch statuses received
        """
        statuses = [BatchStatus(batch_id='pending', status=BatchStatus.COMMITTED)]
        self.stream.preset_response(batch_statuses=statuses)

        response = await self.get_assert_200('/batch_status?id=pending&wait')
        self.stream.assert_valid_request_sent(
            batch_ids=['pending'],
            wait_for_commit=True,
            timeout=4)

        self.assert_has_valid_link(response, '/batch_status?id=pending&wait')
        self.assert_statuses_match(statuses, response['data'])

    @unittest_run_loop
    async def test_batch_status_with_many_ids(self):
        """Verifies a GET /batch_status with many ids works properly.

        It will receive a Protobuf response with:
            - batch statuses of:
                * 'committed': COMMITTED
                * 'unknown': UNKNOWN
                * 'bad': UNKNOWN

        It should send a Protobuf request with:
            - a batch_ids property of ['committed', 'unknown', 'bad']

        It should send back a JSON response with:
            - a response status of 200
            - link property ending in '/batch_status?id=committed,unknown,bad'
            - a data property matching the batch statuses received
        """
        statuses = [
            BatchStatus(batch_id='committed', status=BatchStatus.COMMITTED),
            BatchStatus(batch_id='unknown', status=BatchStatus.UNKNOWN),
            BatchStatus(batch_id='bad', status=BatchStatus.UNKNOWN)]
        self.stream.preset_response(batch_statuses=statuses)

        response = await self.get_assert_200(
            '/batch_status?id=committed,unknown,bad')
        self.stream.assert_valid_request_sent(
            batch_ids=['committed', 'unknown', 'bad'])

        self.assert_has_valid_link(
            response,
            '/batch_status?id=committed,unknown,bad')
        self.assert_statuses_match(statuses, response['data'])

    @unittest_run_loop
    async def test_batch_status_with_no_id(self):
        """Verifies a GET /batch_status with no id breaks properly.

        It should send back a JSON response with:
            - a response status of 400
            - an error property with a code of 66
        """
        response = await self.get_assert_status('/batch_status', 400)

        self.assert_has_valid_error(response, 66)

    @unittest_run_loop
    async def test_batch_status_as_post(self):
        """Verifies a POST to /batch_status works properly.

        It will receive a Protobuf response with:
            - batch statuses of:
                * 'committed': COMMITTED
                * 'pending': PENDING
                * 'bad': UNKNOWN

        It should send a Protobuf request with:
            - a batch_ids property of ['committed', 'pending', 'bad']

        It should send back a JSON response with:
            - a response status of 200
            - an empty link property
            - a data property matching the batch statuses received
        """
        statuses = [
            BatchStatus(batch_id='committed', status=BatchStatus.COMMITTED),
            BatchStatus(batch_id='pending', status=BatchStatus.PENDING),
            BatchStatus(batch_id='bad', status=BatchStatus.UNKNOWN)]
        self.stream.preset_response(batch_statuses=statuses)

        request = await self.client.post(
            '/batch_status',
            data=json.dumps(['committed', 'pending', 'bad']).encode(),
            headers={'content-type': 'application/json'})
        self.stream.assert_valid_request_sent(
            batch_ids=['committed', 'pending', 'bad'])
        self.assertEqual(200, request.status)

        response = await request.json()
        self.assertNotIn('link', response)
        self.assert_statuses_match(statuses, response['data'])

    @unittest_run_loop
    async def test_batch_status_wrong_post_type(self):
        """Verifies a bad POST to /batch_status breaks properly.

        It should send back a JSON response with:
            - a response status of 400
            - an error property with a code of 43
        """
        request = await self.client.post(
            '/batch_status',
            data=json.dumps(['a', 'b', 'c']).encode(),
            headers={'content-type': 'application/octet-stream'})
        self.assertEqual(400, request.status)

        response = await request.json()
        self.assert_has_valid_error(response, 43)

    @unittest_run_loop
    async def test_batch_status_as_bad_post(self):
        """Verifies an empty POST to /batch_status breaks properly.

        It should send back a JSON response with:
            - a response status of 400
            - an error property with a code of 46
        """
        request = await self.client.post(
            '/batch_status',
            data=json.dumps('bad body').encode(),
            headers={'content-type': 'application/json'})
        self.assertEqual(400, request.status)

        response = await request.json()
        self.assert_has_valid_error(response, 46)

    @unittest_run_loop
    async def test_batch_status_as_empty_post(self):
        """Verifies an empty POST to /batch_status breaks properly.

        It should send back a JSON response with:
            - a response status of 400
            - an error property with a code of 46
        """
        request = await self.client.post(
            '/batch_status',
            data=json.dumps([]).encode(),
            headers={'content-type': 'application/json'})
        self.assertEqual(400, request.status)

        response = await request.json()
        self.assert_has_valid_error(response, 46)

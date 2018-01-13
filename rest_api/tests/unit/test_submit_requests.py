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

from components import Mocks, BaseApiTest
from sawtooth_rest_api.protobuf.validator_pb2 import Message
from sawtooth_rest_api.protobuf import client_batch_submit_pb2
from sawtooth_rest_api.protobuf.client_batch_submit_pb2 \
    import ClientBatchStatus


ID_A = 'a' * 128
ID_B = 'b' * 128
ID_C = 'c' * 128
ID_D = 'd' * 128


class PostBatchTests(BaseApiTest):
    async def get_application(self):
        self.set_status_and_connection(
            Message.CLIENT_BATCH_SUBMIT_REQUEST,
            client_batch_submit_pb2.ClientBatchSubmitRequest,
            client_batch_submit_pb2.ClientBatchSubmitResponse)

        handlers = self.build_handlers(self.loop, self.connection)
        return self.build_app(self.loop, '/batches', handlers.submit_batches)

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
            - a link property that ends in '/batch_statuses?id={}'.format(ID_A)
        """
        batches = Mocks.make_batches(ID_A)
        self.connection.preset_response()

        request = await self.post_batches(batches)
        self.connection.assert_valid_request_sent(batches=batches)
        self.assertEqual(202, request.status)

        response = await request.json()
        self.assertNotIn('data', response)
        self.assert_has_valid_link(
            response, '/batch_statuses?id={}'.format(ID_A))

    @unittest_run_loop
    async def test_post_batch_with_validator_error(self):
        """Verifies a POST /batches with a validator error breaks properly.

        It will receive a Protobuf response with:
            - a status of INTERNAL_ERROR

        It should send back a JSON response with:
            - a status of 500
            - an error property with a code of 10
        """
        batches = Mocks.make_batches(ID_A)
        self.connection.preset_response(self.status.INTERNAL_ERROR)

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
        self.connection.preset_response(self.status.INVALID_BATCH)

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
            - a link property that ends in
            '/batch_statuses?id={},{},{}'.format(ID_A, ID_B, ID_C)
        """
        batches = Mocks.make_batches(ID_A, ID_B, ID_C)
        self.connection.preset_response()

        request = await self.post_batches(batches)
        self.connection.assert_valid_request_sent(batches=batches)
        self.assertEqual(202, request.status)

        response = await request.json()
        self.assertNotIn('data', response)
        self.assert_has_valid_link(
            response, '/batch_statuses?id={},{},{}'.format(ID_A, ID_B, ID_C))

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
    async def test_post_rejected_due_to_full_queue(self):
        """Verifies a POST /batches when the validator reports QUEUE_FULL
        breaks properly.

        It will receive a Protobuf response with:
            - a status of QUEUE_FULL

        It should send back a JSON response with:
            - a response status of 429
            - an error property with a code of 31
        """
        batches = Mocks.make_batches(ID_A)
        self.connection.preset_response(self.status.QUEUE_FULL)

        request = await self.post_batches(batches)
        self.assertEqual(429, request.status)
        response = await request.json()
        self.assert_has_valid_error(response, 31)


class ClientBatchStatusTests(BaseApiTest):

    async def get_application(self):
        self.set_status_and_connection(
            Message.CLIENT_BATCH_STATUS_REQUEST,
            client_batch_submit_pb2.ClientBatchStatusRequest,
            client_batch_submit_pb2.ClientBatchStatusResponse)

        handlers = self.build_handlers(self.loop, self.connection)
        return self.build_app(self.loop, '/batch_statuses',
                              handlers.list_statuses)

    @unittest_run_loop
    async def test_batch_statuses_with_one_id(self):
        """Verifies a GET /batch_statuses with one id works properly.

        It will receive a Protobuf response with:
            - batch statuses of {batch_id: ID_D,  status: PENDING}

        It should send a Protobuf request with:
            - a batch_ids property of [ID_D]

        It should send back a JSON response with:
            - a response status of 200
            - a link property that ends in '/batch_statuses?id={}'.format(ID_D)
            - a data property matching the batch statuses received
        """
        statuses = [ClientBatchStatus(
            batch_id=ID_D, status=ClientBatchStatus.PENDING)]
        self.connection.preset_response(batch_statuses=statuses)

        response = await self.get_assert_200(
            '/batch_statuses?id={}'.format(ID_D))
        self.connection.assert_valid_request_sent(batch_ids=[ID_D])

        self.assert_has_valid_link(
            response, '/batch_statuses?id={}'.format(ID_D))
        self.assert_statuses_match(statuses, response['data'])

    @unittest_run_loop
    async def test_batch_statuses_with_invalid_data(self):
        """Verifies a GET /batch_statuses with fetched invalid data works.

        It will receive a Protobuf response with:
            - batch_id: ID_D
            - status: INVALID
            - invalid_transaction: ID_D
            - message: 'error message'
            - extended_data: b'error data'

        It should send a Protobuf request with:
            - a batch_ids property of [ID_D]

        It should send back a JSON response with:
            - a response status of 200
            - a link property that ends in '/batch_statuses?id={}'.format(ID_D)
            - a data property matching the batch statuses received
        """
        statuses = [
            ClientBatchStatus(
                batch_id='bad-batch',
                status=ClientBatchStatus.INVALID,
                invalid_transactions=[
                    ClientBatchStatus.InvalidTransaction(
                        transaction_id=ID_D,
                        message='error message',
                        extended_data=b'error data')
                ])
        ]
        self.connection.preset_response(batch_statuses=statuses)

        response = await self.get_assert_200(
            '/batch_statuses?id={}'.format(ID_D))
        self.connection.assert_valid_request_sent(batch_ids=[ID_D])

        self.assert_has_valid_link(
            response, '/batch_statuses?id={}'.format(ID_D))
        self.assert_statuses_match(statuses, response['data'])

    @unittest_run_loop
    async def test_batch_statuses_with_validator_error(self):
        """Verifies a GET /batch_statuses with a validator error breaks
        properly.

        It will receive a Protobuf response with:
            - a status of INTERNAL_ERROR

        It should send back a JSON response with:
            - a status of 500
            - an error property with a code of 10
        """
        self.connection.preset_response(self.status.INTERNAL_ERROR)
        response = await self.get_assert_status(
            '/batch_statuses?id={}'.format(ID_D), 500)

        self.assert_has_valid_error(response, 10)

    @unittest_run_loop
    async def test_batch_statuses_with_missing_statuses(self):
        """Verifies a GET /batch_statuses with no statuses breaks properly.

        It will receive a Protobuf response with:
            - a status of NO_RESOURCE

        It should send back a JSON response with:
            - a status of 500
            - an error property with a code of 27
        """
        self.connection.preset_response(self.status.NO_RESOURCE)
        response = await self.get_assert_status(
            '/batch_statuses?id={}'.format(ID_D), 500)

        self.assert_has_valid_error(response, 27)

    @unittest_run_loop
    async def test_batch_statuses_with_wait(self):
        """Verifies a GET /batch_statuses with a wait set works properly.

        It will receive a Protobuf response with:
            - batch statuses of {batch_id: ID_D, status: COMMITTED}

        It should send a Protobuf request with:
            - a batch_ids property of [ID_D]
            - a wait property that is True
            - a timeout property of 4 (Rest Api default)

        It should send back a JSON response with:
            - a response status of 200
            - a link property that ends in
              '/batch_statuses?id={}&{}'.format(ID_C, ID_D)
            - a data property matching the batch statuses received
        """
        statuses = [
            ClientBatchStatus(
                batch_id=ID_D, status=ClientBatchStatus.COMMITTED)
        ]
        self.connection.preset_response(batch_statuses=statuses)

        response = await self.get_assert_200(
            '/batch_statuses?id={}&wait'.format(ID_D))
        self.connection.assert_valid_request_sent(
            batch_ids=[ID_D],
            wait=True,
            timeout=4)

        self.assert_has_valid_link(
            response, '/batch_statuses?id={}&wait'.format(ID_D))
        self.assert_statuses_match(statuses, response['data'])

    @unittest_run_loop
    async def test_batch_statuses_with_many_ids(self):
        """Verifies a GET /batch_statuses with many ids works properly.

        It will receive a Protobuf response with:
            - batch statuses of:
                * ID_A: COMMITTED
                * ID_B: UNKNOWN
                * ID_C: UNKNOWN

        It should send a Protobuf request with:
            - a batch_ids property of [ID_A, ID_B, ID_C]

        It should send back a JSON response with:
            - a response status of 200
            - link property ending in
              '/batch_statuses?id={},{},{}'.format(ID_A, ID_B, ID_C)
            - a data property matching the batch statuses received
        """
        statuses = [
            ClientBatchStatus(
                batch_id=ID_A, status=ClientBatchStatus.COMMITTED),
            ClientBatchStatus(
                batch_id=ID_B, status=ClientBatchStatus.UNKNOWN),
            ClientBatchStatus(
                batch_id=ID_C, status=ClientBatchStatus.UNKNOWN)]
        self.connection.preset_response(batch_statuses=statuses)

        response = await self.get_assert_200(
            '/batch_statuses?id={},{},{}'.format(ID_A, ID_B, ID_C))
        self.connection.assert_valid_request_sent(
            batch_ids=[ID_A, ID_B, ID_C])

        self.assert_has_valid_link(
            response,
            '/batch_statuses?id={},{},{}'.format(ID_A, ID_B, ID_C))
        self.assert_statuses_match(statuses, response['data'])

    @unittest_run_loop
    async def test_batch_statuses_with_no_id(self):
        """Verifies a GET /batch_statuses with no id breaks properly.

        It should send back a JSON response with:
            - a response status of 400
            - an error property with a code of 66
        """
        response = await self.get_assert_status('/batch_statuses', 400)

        self.assert_has_valid_error(response, 66)

    @unittest_run_loop
    async def test_batch_statuses_as_post(self):
        """Verifies a POST to /batch_statuses works properly.

        It will receive a Protobuf response with:
            - batch statuses of:
                * ID_A: COMMITTED
                * ID_B: PENDING
                * ID_C: UNKNOWN

        It should send a Protobuf request with:
            - a batch_ids property of [ID_A, ID_B, ID_C]

        It should send back a JSON response with:
            - a response status of 200
            - an empty link property
            - a data property matching the batch statuses received
        """
        statuses = [
            ClientBatchStatus(
                batch_id=ID_A, status=ClientBatchStatus.COMMITTED),
            ClientBatchStatus(
                batch_id=ID_B, status=ClientBatchStatus.PENDING),
            ClientBatchStatus(
                batch_id=ID_C, status=ClientBatchStatus.UNKNOWN)]
        self.connection.preset_response(batch_statuses=statuses)

        request = await self.client.post(
            '/batch_statuses',
            data=json.dumps([ID_A, ID_B, ID_C]).encode(),
            headers={'content-type': 'application/json'})
        self.connection.assert_valid_request_sent(
            batch_ids=[ID_A, ID_B, ID_C])
        self.assertEqual(200, request.status)

        response = await request.json()
        self.assertNotIn('link', response)
        self.assert_statuses_match(statuses, response['data'])

    @unittest_run_loop
    async def test_batch_statuses_wrong_post_type(self):
        """Verifies a bad POST to /batch_statuses breaks properly.

        It should send back a JSON response with:
            - a response status of 400
            - an error property with a code of 43
        """
        request = await self.client.post(
            '/batch_statuses',
            data=json.dumps([ID_A, ID_B, ID_C]).encode(),
            headers={'content-type': 'application/octet-stream'})
        self.assertEqual(400, request.status)

        response = await request.json()
        self.assert_has_valid_error(response, 43)

    @unittest_run_loop
    async def test_batch_statuses_as_bad_post(self):
        """Verifies an empty POST to /batch_statuses breaks properly.

        It should send back a JSON response with:
            - a response status of 400
            - an error property with a code of 46
        """
        request = await self.client.post(
            '/batch_statuses',
            data=json.dumps('bad body').encode(),
            headers={'content-type': 'application/json'})
        self.assertEqual(400, request.status)

        response = await request.json()
        self.assert_has_valid_error(response, 46)

    @unittest_run_loop
    async def test_batch_statuses_as_empty_post(self):
        """Verifies an empty POST to /batch_statuses breaks properly.

        It should send back a JSON response with:
            - a response status of 400
            - an error property with a code of 46
        """
        request = await self.client.post(
            '/batch_statuses',
            data=json.dumps([]).encode(),
            headers={'content-type': 'application/json'})
        self.assertEqual(400, request.status)

        response = await request.json()
        self.assert_has_valid_error(response, 46)

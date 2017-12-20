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

from components import BaseApiTest
from sawtooth_rest_api.protobuf.validator_pb2 import Message
from sawtooth_rest_api.protobuf import client_receipt_pb2
from sawtooth_rest_api.protobuf.transaction_receipt_pb2 import  \
    TransactionReceipt


ID_A = 'a' * 128
ID_B = 'b' * 128
ID_C = 'c' * 128
ID_D = 'd' * 128


class ReceiptGetRequestTests(BaseApiTest):
    async def get_application(self):
        self.set_status_and_connection(
            Message.CLIENT_RECEIPT_GET_REQUEST,
            client_receipt_pb2.ClientReceiptGetRequest,
            client_receipt_pb2.ClientReceiptGetResponse)

        handlers = self.build_handlers(self.loop, self.connection)
        return self.build_app(self.loop, '/receipts', handlers.list_receipts)

    def assert_receipts_match(self, proto_receipts, json_receipts):
        """Asserts that JSON statuses match the original enum statuses dict
        """
        self.assertEqual(len(proto_receipts), len(json_receipts))
        for pb_receipt, js_receipt in zip(proto_receipts, json_receipts):
            self.assertEqual(pb_receipt.transaction_id, js_receipt['id'])

    @unittest_run_loop
    async def test_receipts_with_one_id(self):
        """Verifies a GET /receipts with one id works properly.

        It will receive a Protobuf response with:
            - a transaction receipt with matching id

        It should send a Protobuf request with:
            - a transaction_ids property of [ID_B]

        It should send back a JSON response with:
            - a response status of 200
            - a link property that ends in '/receipts?id={}'.format(ID_B)
            - a data property matching the receipts received
        """
        receipts = [TransactionReceipt(transaction_id=ID_B)]
        self.connection.preset_response(
            receipts=receipts,
            status=self.status.OK)

        response = await self.get_assert_200('/receipts?id={}'.format(ID_B))
        self.connection.assert_valid_request_sent(transaction_ids=[ID_B])

        self.assert_has_valid_link(response, '/receipts?id={}'.format(ID_B))
        self.assert_receipts_match(receipts, response['data'])

    @unittest_run_loop
    async def test_receipts_with_missing_id(self):
        """Verifies a GET /receipts with fetched invalid data works.

        It will receive a Protobuf response with:
            - status: NO_RESOURCE

        It should send a Protobuf request with:
            - a transaction_ids property of ['missing']

        It should send back a JSON response with:
            - a response status of 404
            - a link property that ends in '/receipts?id={}'.format(ID_D)
            - a data property matching the receipts statuses received
        """
        receipts = []
        self.connection.preset_response(
            receipts=receipts,
            status=self.status.NO_RESOURCE)

        response = await self.get_assert_status('/receipts?id={}'.format(ID_D),
                                                404)
        self.connection.assert_valid_request_sent(transaction_ids=[ID_D])

        self.assert_has_valid_error(response, 80)

    @unittest_run_loop
    async def test_receipts_with_many_ids(self):
        """Verifies a GET /receipts with many ids works properly.

        It will receive a Protobuf response with receipts with ids:
            - ID_B
            - ID_C
            - ID_D

        It should send a Protobuf request with:
            - a transaction_ids property of [ID_B, ID_C, ID_D]

        It should send back a JSON response with:
            - a response status of 200
            - link property ending in
                '/receipts?id={},{},{}' .format(ID_B, ID_C, ID_D)
            - a data property matching the batch statuses received
        """
        receipts = [
            TransactionReceipt(transaction_id=t_id)
            for t_id in (ID_B, ID_C, ID_D)
        ]
        self.connection.preset_response(
            status=self.status.OK,
            receipts=receipts)

        response = await self.get_assert_200(
            '/receipts?id={},{},{}'.format(ID_B, ID_C, ID_D))
        self.connection.assert_valid_request_sent(
            transaction_ids=[ID_B, ID_C, ID_D])

        self.assert_has_valid_link(
            response,
            '/receipts?id={},{},{}'.format(ID_B, ID_C, ID_D))
        self.assert_receipts_match(receipts, response['data'])

    @unittest_run_loop
    async def test_batch_statuses_as_post(self):
        """Verifies a POST to /receipts with many ids works properly.

        It will receive a Protobuf response with receipts with ids:
            - ID_B
            - ID_C
            - ID_D

        It should send a Protobuf request with:
            - a transaction_ids property of [ID_B, ID_C, ID_D]

        It should send back a JSON response with:
            - a response status of 200
            - link property ending in
                '/receipts?id={},{},{}'.format(ID_B, ID_C, ID_D)
            - a data property matching the batch statuses received
        """
        receipts = [
            TransactionReceipt(transaction_id=t_id)
            for t_id in (ID_B, ID_C, ID_D)
        ]
        self.connection.preset_response(
            status=self.status.OK,
            receipts=receipts)

        request = await self.client.post(
            '/receipts',
            data=json.dumps([ID_B, ID_C, ID_D]).encode(),
            headers={'content-type': 'application/json'})
        self.connection.assert_valid_request_sent(
            transaction_ids=[ID_B, ID_C, ID_D])
        self.assertEqual(200, request.status)

        response = await request.json()
        self.assertNotIn('link', response)
        self.assert_receipts_match(receipts, response['data'])

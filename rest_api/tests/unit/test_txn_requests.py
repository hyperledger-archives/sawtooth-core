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
from sawtooth_rest_api.protobuf import client_transaction_pb2


ID_A = 'a' * 128
ID_B = 'b' * 128
ID_C = 'c' * 128
ID_D = 'd' * 128

DEFAULT_LIMIT = 100


class TransactionListTests(BaseApiTest):
    async def get_application(self):
        self.set_status_and_connection(
            Message.CLIENT_TRANSACTION_LIST_REQUEST,
            client_transaction_pb2.ClientTransactionListRequest,
            client_transaction_pb2.ClientTransactionListResponse)

        handlers = self.build_handlers(self.loop, self.connection)
        app = self.build_app(self.loop, '/transactions',
                             handlers.list_transactions)
        return app

    @unittest_run_loop
    async def test_txn_list(self):
        """Verifies a GET /transactions without parameters works properly.

        It will receive a Protobuf response with:
            - a head id of ID_C
            - a paging response with a start of ID_C and limit of 100
            - three transactions with ids of ID_C, ID_B, and ID_A

        It should send a Protobuf request with:
            - empty paging controls

        It should send back a JSON response with:
            - a response status of 200
            - a head property of ID_C
            - a link property that ends in
                '/transactions?head={}&start={}&limit=100'.format(ID_C, ID_C)
            - a paging property that matches the paging response
            - a data property that is a list of 3 dicts
            - those dicts are full transactions with ids ID_C, ID_B, and ID_A
        """
        paging = Mocks.make_paging_response("", ID_C, DEFAULT_LIMIT)
        self.connection.preset_response(
            head_id=ID_C,
            paging=paging,
            transactions=Mocks.make_txns(ID_C, ID_B, ID_A))

        response = await self.get_assert_200('/transactions')
        controls = Mocks.make_paging_controls()
        self.connection.assert_valid_request_sent(paging=controls)

        self.assert_has_valid_head(response, ID_C)
        self.assert_has_valid_link(
            response,
            '/transactions?head={ID_C}&start={ID_C}&limit=100'.format(
                ID_C=ID_C))
        self.assert_has_valid_paging(response, paging)
        self.assert_has_valid_data_list(response, 3)
        self.assert_txns_well_formed(response['data'], ID_C, ID_B, ID_A)

    @unittest_run_loop
    async def test_txn_list_with_validator_error(self):
        """Verifies a GET /transactions with a validator error breaks properly.

        It will receive a Protobuf response with:
            - a status of INTERNAL_ERROR

        It should send back a JSON response with:
            - a status of 500
            - an error property with a code of 10
        """
        self.connection.preset_response(self.status.INTERNAL_ERROR)
        response = await self.get_assert_status('/transactions', 500)

        self.assert_has_valid_error(response, 10)

    @unittest_run_loop
    async def test_txn_list_with_no_genesis(self):
        """Verifies GET /transactions with validator not ready breaks properly.

        It will receive a Protobuf response with:
            - a status of NOT_READY

        It should send back a JSON response with:
            - a status of 503
            - an error property with a code of 15
        """
        self.connection.preset_response(self.status.NOT_READY)
        response = await self.get_assert_status('/transactions', 503)

        self.assert_has_valid_error(response, 15)

    @unittest_run_loop
    async def test_txn_list_with_head(self):
        """Verifies a GET /transactions with a head parameter works properly.

        It will receive a Protobuf response with:
            - a head id of ID_B
            - a paging response with a start of ID_B and limit of 100
            - two transactions with ids of 1' and ID_A

        It should send a Protobuf request with:
            - a head_id property of ID_B
            - empty paging controls

        It should send back a JSON response with:
            - a response status of 200
            - a head property of ID_B
            - a link property that ends in
                '/transactions?head={}&start={}&limit=100'.format(ID_B, ID_B))
            - a paging property that matches the paging response
            - a data property that is a list of 2 dicts
            - those dicts are full transactions with ids ID_B and ID_A
        """
        paging = Mocks.make_paging_response("", ID_B, DEFAULT_LIMIT)
        self.connection.preset_response(
            head_id=ID_B,
            paging=paging,
            transactions=Mocks.make_txns(ID_B, ID_A))

        response = await self.get_assert_200(
            '/transactions?head={}'.format(ID_B))
        controls = Mocks.make_paging_controls()
        self.connection.assert_valid_request_sent(
            head_id=ID_B, paging=controls)
        self.assert_has_valid_head(response, ID_B)
        self.assert_has_valid_link(
            response,
            '/transactions?head={ID_B}&start={ID_B}&limit=100'.format(
                ID_B=ID_B))
        self.assert_has_valid_paging(response, paging)
        self.assert_has_valid_data_list(response, 2)
        self.assert_txns_well_formed(response['data'], ID_B, ID_A)

    @unittest_run_loop
    async def test_txn_list_with_bad_head(self):
        """Verifies a GET /transactions with a bad head id breaks properly.

        It will receive a Protobuf response with:
            - a status of NO_ROOT

        It should send back a JSON response with:
            - a response status of 404
            - an error property with a code of 50
        """
        self.connection.preset_response(self.status.NO_ROOT)
        response = await self.get_assert_status(
            '/transactions?head={}'.format(ID_D), 404)

        self.assert_has_valid_error(response, 50)

    @unittest_run_loop
    async def test_txn_list_with_ids(self):
        """Verifies GET /transactions with an id filter works properly.

        It will receive a Protobuf response with:
            - a head id of ID_C
            - a paging response with a start of ID_C and limit of 100
            - two transactions with ids of ID_A and ID_C

        It should send a Protobuf request with:
            - a transaction_ids property of [ID_A, ID_C]
            - empty paging controls

        It should send back a JSON response with:
            - a response status of 200
            - a head property of ID_C, the latest
            - a link property that ends in
                '/transactions?head={}&start={}&limit=100&id={},{}'
                    .format(ID_C, ID_C, ID_A, ID_C))
            - a paging property that matches the paging response
            - a data property that is a list of 2 dicts
            - those dicts are full transactions with ids ID_A and ID_C
        """
        paging = Mocks.make_paging_response("", ID_C, DEFAULT_LIMIT)
        transactions = Mocks.make_txns(ID_A, ID_C)
        self.connection.preset_response(
            head_id=ID_C, paging=paging, transactions=transactions)

        response = await self.get_assert_200('/transactions?id={},{}'.format(
            ID_A, ID_C))
        controls = Mocks.make_paging_controls()
        self.connection.assert_valid_request_sent(
            transaction_ids=[ID_A, ID_C], paging=controls)

        self.assert_has_valid_head(response, ID_C)
        link =\
            '/transactions?head={ID_C}&start={ID_C}&limit=100&id={ID_A},{ID_C}'

        self.assert_has_valid_link(
            response,
            link.format(ID_C=ID_C, ID_A=ID_A))
        self.assert_has_valid_paging(response, paging)
        self.assert_has_valid_data_list(response, 2)
        self.assert_txns_well_formed(response['data'], ID_A, ID_C)

    @unittest_run_loop
    async def test_txn_list_with_bad_ids(self):
        """Verifies GET /transactions with a bad id filter breaks properly.

        It will receive a Protobuf response with:
            - a status of NO_RESOURCE
            - a head id of ID_C

        It should send back a JSON response with:
            - a response status of 200
            - a head property of ID_C, the latest
            - a link property that ends in
                '/transactions?head={}&start={}&limit=100&id={},{}'
                    .format(ID_C, ID_C, ID_B, ID_D))
            - a paging property with only a total_count of 0
            - a data property that is an empty list
        """
        paging = Mocks.make_paging_response("", ID_C, DEFAULT_LIMIT)
        self.connection.preset_response(
            self.status.NO_RESOURCE, head_id=ID_C, paging=paging)
        response = await self.get_assert_200('/transactions?id={},{}'.format(
            ID_B, ID_D))

        self.assert_has_valid_head(response, ID_C)
        link =\
            '/transactions?head={ID_C}&start={ID_C}&limit=100&id={ID_B},{ID_D}'

        self.assert_has_valid_link(
            response,
            link.format(ID_C=ID_C, ID_B=ID_B, ID_D=ID_D))
        self.assert_has_valid_paging(response, paging)
        self.assert_has_valid_data_list(response, 0)

    @unittest_run_loop
    async def test_txn_list_with_head_and_ids(self):
        """Verifies GET /transactions with head and id parameters work
        properly.

        It should send a Protobuf request with:
            - a head_id property of ID_B
            - a paging response with a start of ID_B and limit of 100
            - a transaction_ids property of [ID_A]

        It will receive a Protobuf response with:
            - a head id of ID_B
            - one transaction with an id of ID_A
            - empty paging controls

        It should send back a JSON response with:
            - a response status of 200
            - a head property of ID_B
            - a link property that ends in
                '/transactions?head={}&start={}&limit=100&id={}'
                    .format(ID_B, ID_B, ID_A))
            - a paging property that matches the paging response
            - a data property that is a list of 1 dict
            - that dict is a full transaction with an id of ID_A
        """
        paging = Mocks.make_paging_response("", ID_B, DEFAULT_LIMIT)
        self.connection.preset_response(
            head_id=ID_B, paging=paging, transactions=Mocks.make_txns(ID_A))

        response = await self.get_assert_200(
            '/transactions?id={}&head={}'.format(ID_A, ID_B))
        controls = Mocks.make_paging_controls()
        self.connection.assert_valid_request_sent(
            head_id=ID_B, transaction_ids=[ID_A], paging=controls)

        self.assert_has_valid_head(response, ID_B)
        link = '/transactions?head={ID_B}&start={ID_B}&limit=100&id={ID_A}'
        self.assert_has_valid_link(
            response,
            link.format(ID_B=ID_B, ID_A=ID_A))
        self.assert_has_valid_paging(response, paging)
        self.assert_has_valid_data_list(response, 1)
        self.assert_txns_well_formed(response['data'], ID_A)

    @unittest_run_loop
    async def test_txn_list_with_zero_count(self):
        """Verifies a GET /transactions with a count of zero breaks properly.

        It should send back a JSON response with:
            - a response status of 400
            - an error property with a code of 53
        """
        response = await self.get_assert_status('/transactions?limit=0', 400)

        self.assert_has_valid_error(response, 53)

    @unittest_run_loop
    async def test_txn_list_with_bad_paging(self):
        """Verifies a GET /transactions with a bad paging breaks properly.

        It will receive a Protobuf response with:
            - a status of INVALID_PAGING

        It should send back a JSON response with:
            - a response status of 400
            - an error property with a code of 54
        """
        self.connection.preset_response(self.status.INVALID_PAGING)
        response = await self.get_assert_status('/transactions?min=-1', 400)

        self.assert_has_valid_error(response, 54)

    @unittest_run_loop
    async def test_txn_list_paginated_with_just_limit(self):
        """Verifies GET /transactions paginated just by limit works properly.

        It will receive a Protobuf response with:
            - a head id of ID_D
            - a paging response with a start of ID_D, next of ID_B and
              limit of 2
            - two transactions with the ids ID_D and ID_C

        It should send a Protobuf request with:
            - paging controls with a limit of 2

        It should send back a JSON response with:
            - a response status of 200
            - a head property of ID_D
            - a link property that ends in
                '/transactions?head={}&start={}&limit=2'.format(ID_D, ID_D))
            - paging that matches the response with a next link
            - a data property that is a list of 2 dicts
            - those dicts are full transactions with ids ID_D and ID_C
        """
        paging = Mocks.make_paging_response(ID_B, ID_D, 2)
        self.connection.preset_response(
            head_id=ID_D,
            paging=paging,
            transactions=Mocks.make_txns(ID_D, ID_C))

        response = await self.get_assert_200('/transactions?limit=2')
        controls = Mocks.make_paging_controls(2)
        self.connection.assert_valid_request_sent(paging=controls)

        self.assert_has_valid_head(response, ID_D)
        self.assert_has_valid_link(
            response, '/transactions?head={ID_D}&start={ID_D}&limit=2'.format(
                ID_D=ID_D))
        self.assert_has_valid_paging(
            response, paging, '/transactions?head={}&start={}&limit=2'.format(
                ID_D, ID_B))
        self.assert_has_valid_data_list(response, 2)
        self.assert_txns_well_formed(response['data'], ID_D, ID_C)

    @unittest_run_loop
    async def test_txn_list_paginated_without_count(self):
        """Verifies GET /transactions paginated without count works properly.

        It will receive a Protobuf response with:
            - a head id of ID_D
            - a paging response with a start of ID_D and a limit of 100
            - two transactions with the ids ID_B and ID_A

        It should send a Protobuf request with:
            - paging controls with a start of 2

        It should send back a JSON response with:
            - a response status of 200
            - a head property of ID_D
            - a link property that ends in
                '/transactions?head={}&start={}&limit=100'.format(ID_D, ID_D))
            - paging that matches the response, with a previous link
            - a data property that is a list of 2 dicts
            - those dicts are full transactions with ids ID_D and ID_C
        """
        paging = Mocks.make_paging_response("", ID_D, DEFAULT_LIMIT)
        self.connection.preset_response(
            head_id=ID_D,
            paging=paging,
            transactions=Mocks.make_txns(ID_B, ID_A))

        response = await self.get_assert_200('/transactions?start=2')
        controls = Mocks.make_paging_controls(None, start="2")
        self.connection.assert_valid_request_sent(paging=controls)

        self.assert_has_valid_head(response, ID_D)
        self.assert_has_valid_link(
            response,
            '/transactions?head={ID_D}&start={ID_D}&limit=100'.format(
                ID_D=ID_D))
        self.assert_has_valid_paging(response, paging)
        self.assert_has_valid_data_list(response, 2)
        self.assert_txns_well_formed(response['data'], ID_B, ID_A)

    @unittest_run_loop
    async def test_txn_list_paginated_by_start_id(self):
        """Verifies GET /transactions paginated by a start id works properly.

        It will receive a Protobuf response with:
            - a head id of ID_D
            - a paging response with start of ID_C and limit of 5
            - three transactions with the ids ID_C, ID_B and ID_A

        It should send a Protobuf request with:
            - paging controls with a count of 5, and a start_id of ID_C

        It should send back a JSON response with:
            - a response status of 200
            - a head property of ID_D
            - a link property that ends in
                '/transactions?head={}&start={}&limit=5'.format(ID_D, ID_C))
            - paging that matches the response, with a previous link
            - a data property that is a list of 3 dicts
            - those dicts are full transactions with ids ID_C, ID_B, and ID_A
        """
        paging = Mocks.make_paging_response("", ID_C, 5)
        self.connection.preset_response(
            head_id=ID_D,
            paging=paging,
            transactions=Mocks.make_txns(ID_C, ID_B, ID_A))

        response = await self.get_assert_200(
            '/transactions?start={}&limit=5'.format(ID_C))
        controls = Mocks.make_paging_controls(5, start=ID_C)
        self.connection.assert_valid_request_sent(paging=controls)

        self.assert_has_valid_head(response, ID_D)
        self.assert_has_valid_link(
            response, '/transactions?head={}&start={}&limit=5'.format(
                ID_D, ID_C))
        self.assert_has_valid_paging(response, paging)
        self.assert_has_valid_data_list(response, 3)
        self.assert_txns_well_formed(response['data'], ID_C, ID_B, ID_A)

    @unittest_run_loop
    async def test_txn_list_sorted_in_reverse(self):
        """Verifies a GET /transactions can send proper sort parameters.

        It will receive a Protobuf response with:
            - a head id of ID_C
            - a paging response with start of ID_C and limit of 100
            - three transactions with ids ID_C, ID_B, and ID_A

        It should send a Protobuf request with:
            - empty paging controls
            - sort controls with a key of 'header_signature' that is reversed

        It should send back a JSON response with:
            - a status of 200
            - a head property of ID_C
            - a link property ending in
                '/transactions?head={}&start={}&limit=100&reverse'
                    .format(ID_C, ID_C))
            - a paging property that matches the paging response
            - a data property that is a list of 3 dicts
            - and those dicts are full transactions with ids ID_C,
              ID_B, and ID_A
        """
        paging = Mocks.make_paging_response("", ID_C, DEFAULT_LIMIT)
        transactions = Mocks.make_txns(ID_C, ID_B, ID_A)
        self.connection.preset_response(
            head_id=ID_C, paging=paging, transactions=transactions)
        response = await self.get_assert_200('/transactions?reverse')
        page_controls = Mocks.make_paging_controls()
        sorting = Mocks.make_sort_controls("default", reverse=True)
        self.connection.assert_valid_request_sent(
            paging=page_controls,
            sorting=sorting)

        self.assert_has_valid_head(response, ID_C)
        self.assert_has_valid_link(
            response,
            '/transactions?head={ID_C}&start={ID_C}&limit=100&reverse'.format(
                ID_C=ID_C))
        self.assert_has_valid_paging(response, paging)
        self.assert_has_valid_data_list(response, 3)
        self.assert_txns_well_formed(response['data'], ID_C, ID_B, ID_A)


class TransactionGetTests(BaseApiTest):
    async def get_application(self):
        self.set_status_and_connection(
            Message.CLIENT_TRANSACTION_GET_REQUEST,
            client_transaction_pb2.ClientTransactionGetRequest,
            client_transaction_pb2.ClientTransactionGetResponse)

        handlers = self.build_handlers(self.loop, self.connection)
        return self.build_app(
            self.loop,
            '/transactions/{transaction_id}',
            handlers.fetch_transaction)

    @unittest_run_loop
    async def test_txn_get(self):
        """Verifies a GET /transactions/{transaction_id} works properly.

        It should send a Protobuf request with:
            - a transaction_id property of ID_B

        It will receive a Protobuf response with:
            - a transaction with an id of ID_B

        It should send back a JSON response with:
            - a response status of 200
            - no head property
            - a link property that ends in '/transactions/{}'.format(ID_B)
            - a data property that is a full batch with an id of ID_B
        """
        self.connection.preset_response(transaction=Mocks.make_txns(ID_B)[0])

        response = await self.get_assert_200('/transactions/{}'.format(ID_B))
        self.connection.assert_valid_request_sent(transaction_id=ID_B)

        self.assertNotIn('head', response)
        self.assert_has_valid_link(response, '/transactions/{}'.format(ID_B))
        self.assertIn('data', response)
        self.assert_txns_well_formed(response['data'], ID_B)

    @unittest_run_loop
    async def test_txn_get_with_validator_error(self):
        """Verifies GET /transactions/{transaction_id} w/ validator error
        breaks.

        It will receive a Protobuf response with:
            - a status of INTERNAL_ERROR

        It should send back a JSON response with:
            - a status of 500
            - an error property with a code of 10
        """
        self.connection.preset_response(self.status.INTERNAL_ERROR)
        response = await self.get_assert_status(
            '/transactions/{}'.format(ID_B), 500)

        self.assert_has_valid_error(response, 10)

    @unittest_run_loop
    async def test_txn_get_with_bad_id(self):
        """Verifies a GET /transactions/{transaction_id} with unfound id
        breaks.

        It will receive a Protobuf response with:
            - a status of NO_RESOURCE

        It should send back a JSON response with:
            - a response status of 404
            - an error property with a code of 72
        """
        self.connection.preset_response(self.status.NO_RESOURCE)
        response = await self.get_assert_status(
            '/transactions/{}'.format(ID_D), 404)

        self.assert_has_valid_error(response, 72)

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


class TransactionListTests(BaseApiTest):

    async def get_application(self, loop):
        self.set_status_and_connection(
            Message.CLIENT_TRANSACTION_LIST_REQUEST,
            client_pb2.ClientTransactionListRequest,
            client_pb2.ClientTransactionListResponse)

        handlers = self.build_handlers(loop, self.connection)
        app = self.build_app(loop, '/transactions', handlers.list_transactions)
        return app

    @unittest_run_loop
    async def test_txn_list(self):
        """Verifies a GET /transactions without parameters works properly.

        It will receive a Protobuf response with:
            - a head id of '2'
            - a paging response with a start of 0, and 3 total resources
            - three transactions with ids of '2', '1', and '0'

        It should send a Protobuf request with:
            - empty paging controls

        It should send back a JSON response with:
            - a response status of 200
            - a head property of '2'
            - a link property that ends in '/transactions?head=2'
            - a paging property that matches the paging response
            - a data property that is a list of 3 dicts
            - those dicts are full transactions with ids '2', '1', and '0'
        """
        paging = Mocks.make_paging_response(0, 3)
        self.connection.preset_response(
            head_id='2',
            paging=paging,
            transactions=Mocks.make_txns('2', '1', '0'))

        response = await self.get_assert_200('/transactions')
        controls = Mocks.make_paging_controls()
        self.connection.assert_valid_request_sent(paging=controls)

        self.assert_has_valid_head(response, '2')
        self.assert_has_valid_link(response, '/transactions?head=2')
        self.assert_has_valid_paging(response, paging)
        self.assert_has_valid_data_list(response, 3)
        self.assert_txns_well_formed(response['data'], '2', '1', '0')

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
            - a head id of '1'
            - a paging response with a start of 0, and 2 total resources
            - two transactions with ids of 1' and '0'

        It should send a Protobuf request with:
            - a head_id property of '1'
            - empty paging controls

        It should send back a JSON response with:
            - a response status of 200
            - a head property of '1'
            - a link property that ends in '/transactions?head=1'
            - a paging property that matches the paging response
            - a data property that is a list of 2 dicts
            - those dicts are full transactions with ids '1' and '0'
        """
        paging = Mocks.make_paging_response(0, 2)
        self.connection.preset_response(
            head_id='1',
            paging=paging,
            transactions=Mocks.make_txns('1', '0'))

        response = await self.get_assert_200('/transactions?head=1')
        controls = Mocks.make_paging_controls()
        self.connection.assert_valid_request_sent(head_id='1', paging=controls)

        self.assert_has_valid_head(response, '1')
        self.assert_has_valid_link(response, '/transactions?head=1')
        self.assert_has_valid_paging(response, paging)
        self.assert_has_valid_data_list(response, 2)
        self.assert_txns_well_formed(response['data'], '1', '0')

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
        response = await self.get_assert_status('/transactions?head=bad', 404)

        self.assert_has_valid_error(response, 50)

    @unittest_run_loop
    async def test_txn_list_with_ids(self):
        """Verifies GET /transactions with an id filter works properly.

        It will receive a Protobuf response with:
            - a head id of '2'
            - a paging response with a start of 0, and 2 total resources
            - two transactions with ids of '0' and '2'

        It should send a Protobuf request with:
            - a transaction_ids property of ['0', '2']
            - empty paging controls

        It should send back a JSON response with:
            - a response status of 200
            - a head property of '2', the latest
            - a link property that ends in '/transactions?head=2&id=0,2'
            - a paging property that matches the paging response
            - a data property that is a list of 2 dicts
            - those dicts are full transactions with ids '0' and '2'
        """
        paging = Mocks.make_paging_response(0, 2)
        transactions = Mocks.make_txns('0', '2')
        self.connection.preset_response(head_id='2', paging=paging, transactions=transactions)

        response = await self.get_assert_200('/transactions?id=0,2')
        controls = Mocks.make_paging_controls()
        self.connection.assert_valid_request_sent(transaction_ids=['0', '2'], paging=controls)

        self.assert_has_valid_head(response, '2')
        self.assert_has_valid_link(response, '/transactions?head=2&id=0,2')
        self.assert_has_valid_paging(response, paging)
        self.assert_has_valid_data_list(response, 2)
        self.assert_txns_well_formed(response['data'], '0', '2')

    @unittest_run_loop
    async def test_txn_list_with_bad_ids(self):
        """Verifies GET /transactions with a bad id filter breaks properly.

        It will receive a Protobuf response with:
            - a status of NO_RESOURCE
            - a head id of '2'

        It should send back a JSON response with:
            - a response status of 200
            - a head property of '2', the latest
            - a link property that ends in '/transactions?head=2&id=bad,notgood'
            - a paging property with only a total_count of 0
            - a data property that is an empty list
        """
        paging = Mocks.make_paging_response(None, 0)
        self.connection.preset_response(
            self.status.NO_RESOURCE,
            head_id='2',
            paging=paging)
        response = await self.get_assert_200('/transactions?id=bad,notgood')

        self.assert_has_valid_head(response, '2')
        self.assert_has_valid_link(response, '/transactions?head=2&id=bad,notgood')
        self.assert_has_valid_paging(response, paging)
        self.assert_has_valid_data_list(response, 0)

    @unittest_run_loop
    async def test_txn_list_with_head_and_ids(self):
        """Verifies GET /transactions with head and id parameters work properly.

        It should send a Protobuf request with:
            - a head_id property of '1'
            - a paging response with a start of 0, and 1 total resource
            - a transaction_ids property of ['0']

        It will receive a Protobuf response with:
            - a head id of '1'
            - one transaction with an id of '0'
            - empty paging controls

        It should send back a JSON response with:
            - a response status of 200
            - a head property of '1'
            - a link property that ends in '/transactions?head=1&id=0'
            - a paging property that matches the paging response
            - a data property that is a list of 1 dict
            - that dict is a full transaction with an id of '0'
        """
        paging = Mocks.make_paging_response(0, 1)
        self.connection.preset_response(
            head_id='1',
            paging=paging,
            transactions=Mocks.make_txns('0'))

        response = await self.get_assert_200('/transactions?id=0&head=1')
        controls = Mocks.make_paging_controls()
        self.connection.assert_valid_request_sent(
            head_id='1',
            transaction_ids=['0'],
            paging=controls)

        self.assert_has_valid_head(response, '1')
        self.assert_has_valid_link(response, '/transactions?head=1&id=0')
        self.assert_has_valid_paging(response, paging)
        self.assert_has_valid_data_list(response, 1)
        self.assert_txns_well_formed(response['data'], '0')

    @unittest_run_loop
    async def test_txn_list_paginated(self):
        """Verifies GET /transactions paginated by min id works properly.

        It will receive a Protobuf response with:
            - a head id of 'd'
            - a paging response with a start of 1, and 4 total resources
            - one transaction with the id 'c'

        It should send a Protobuf request with:
            - paging controls with a count of 1, and a start_index of 1

        It should send back a JSON response with:
            - a response status of 200
            - a head property of 'd'
            - a link property that ends in '/transactions?head=d&min=1&count=1'
            - paging that matches the response, with next and previous links
            - a data property that is a list of 1 dict
            - that dict is a full transaction with the id 'c'
        """
        paging = Mocks.make_paging_response(1, 4)
        self.connection.preset_response(
            head_id='d',
            paging=paging,
            transactions=Mocks.make_txns('c'))

        response = await self.get_assert_200('/transactions?min=1&count=1')
        controls = Mocks.make_paging_controls(1, start_index=1)
        self.connection.assert_valid_request_sent(paging=controls)

        self.assert_has_valid_head(response, 'd')
        self.assert_has_valid_link(response, '/transactions?head=d&min=1&count=1')
        self.assert_has_valid_paging(response, paging,
                                     '/transactions?head=d&min=2&count=1',
                                     '/transactions?head=d&min=0&count=1')
        self.assert_has_valid_data_list(response, 1)
        self.assert_txns_well_formed(response['data'], 'c')

    @unittest_run_loop
    async def test_txn_list_with_zero_count(self):
        """Verifies a GET /transactions with a count of zero breaks properly.

        It should send back a JSON response with:
            - a response status of 400
            - an error property with a code of 53
        """
        response = await self.get_assert_status('/transactions?count=0', 400)

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
    async def test_txn_list_paginated_with_just_count(self):
        """Verifies GET /transactions paginated just by count works properly.

        It will receive a Protobuf response with:
            - a head id of 'd'
            - a paging response with a start of 0, and 4 total resources
            - two transactions with the ids 'd' and 'c'

        It should send a Protobuf request with:
            - paging controls with a count of 2

        It should send back a JSON response with:
            - a response status of 200
            - a head property of 'd'
            - a link property that ends in '/transactions?head=d&count=2'
            - paging that matches the response with a next link
            - a data property that is a list of 2 dicts
            - those dicts are full transactions with ids 'd' and 'c'
        """
        paging = Mocks.make_paging_response(0, 4)
        self.connection.preset_response(
            head_id='d',
            paging=paging,
            transactions=Mocks.make_txns('d', 'c'))

        response = await self.get_assert_200('/transactions?count=2')
        controls = Mocks.make_paging_controls(2)
        self.connection.assert_valid_request_sent(paging=controls)

        self.assert_has_valid_head(response, 'd')
        self.assert_has_valid_link(response, '/transactions?head=d&count=2')
        self.assert_has_valid_paging(response, paging,
                                     '/transactions?head=d&min=2&count=2')
        self.assert_has_valid_data_list(response, 2)
        self.assert_txns_well_formed(response['data'], 'd', 'c')

    @unittest_run_loop
    async def test_txn_list_paginated_without_count(self):
        """Verifies GET /transactions paginated without count works properly.

        It will receive a Protobuf response with:
            - a head id of 'd'
            - a paging response with a start of 2, and 4 total resources
            - two transactions with the ids 'b' and 'a'

        It should send a Protobuf request with:
            - paging controls with a start_index of 2

        It should send back a JSON response with:
            - a response status of 200
            - a head property of 'd'
            - a link property that ends in '/transactions?head=d&min=2'
            - paging that matches the response, with a previous link
            - a data property that is a list of 2 dicts
            - those dicts are full transactions with ids 'd' and 'c'
        """
        paging = Mocks.make_paging_response(2, 4)
        self.connection.preset_response(
            head_id='d',
            paging=paging,
            transactions=Mocks.make_txns('b', 'a'))

        response = await self.get_assert_200('/transactions?min=2')
        controls = Mocks.make_paging_controls(None, start_index=2)
        self.connection.assert_valid_request_sent(paging=controls)

        self.assert_has_valid_head(response, 'd')
        self.assert_has_valid_link(response, '/transactions?head=d&min=2')
        self.assert_has_valid_paging(response, paging,
                                     previous_link='/transactions?head=d&min=0&count=2')
        self.assert_has_valid_data_list(response, 2)
        self.assert_txns_well_formed(response['data'], 'b', 'a')

    @unittest_run_loop
    async def test_txn_list_paginated_by_min_id(self):
        """Verifies GET /transactions paginated by a min id works properly.

        It will receive a Protobuf response with:
            - a head id of 'd'
            - a paging response with:
                * a start_index of 1
                * total_resources of 4
                * a previous_id of 'd'
            - three transactions with the ids 'c', 'b' and 'a'

        It should send a Protobuf request with:
            - paging controls with a count of 5, and a start_id of 'c'

        It should send back a JSON response with:
            - a response status of 200
            - a head property of 'd'
            - a link property that ends in '/transactions?head=d&min=c&count=5'
            - paging that matches the response, with a previous link
            - a data property that is a list of 3 dicts
            - those dicts are full transactions with ids 'c', 'b', and 'a'
        """
        paging = Mocks.make_paging_response(1, 4, previous_id='d')
        self.connection.preset_response(
            head_id='d',
            paging=paging,
            transactions=Mocks.make_txns('c', 'b', 'a'))

        response = await self.get_assert_200('/transactions?min=c&count=5')
        controls = Mocks.make_paging_controls(5, start_id='c')
        self.connection.assert_valid_request_sent(paging=controls)

        self.assert_has_valid_head(response, 'd')
        self.assert_has_valid_link(response, '/transactions?head=d&min=c&count=5')
        self.assert_has_valid_paging(response, paging,
                                     previous_link='/transactions?head=d&max=d&count=5')
        self.assert_has_valid_data_list(response, 3)
        self.assert_txns_well_formed(response['data'], 'c', 'b', 'a')

    @unittest_run_loop
    async def test_txn_list_paginated_by_max_id(self):
        """Verifies GET /transactions paginated by a max id works properly.

        It will receive a Protobuf response with:
            - a head id of 'd'
            - a paging response with:
                * a start_index of 1
                * a total_resources of 4
                * a previous_id of 'd'
                * a next_id of 'a'
            - two transactions with the ids 'c' and 'b'

        It should send a Protobuf request with:
            - paging controls with a count of 2, and an end_id of 'b'

        It should send back a JSON response with:
            - a response status of 200
            - a head property of 'd'
            - a link property that ends in '/transactions?head=d&max=b&count=2'
            - paging that matches the response, with next and previous links
            - a data property that is a list of 2 dicts
            - those dicts are full transactions with ids 'c' and 'b'
        """
        paging = Mocks.make_paging_response(1, 4, previous_id='d', next_id='a')
        self.connection.preset_response(
            head_id='d',
            paging=paging,
            transactions=Mocks.make_txns('c', 'b'))

        response = await self.get_assert_200('/transactions?max=b&count=2')
        controls = Mocks.make_paging_controls(2, end_id='b')
        self.connection.assert_valid_request_sent(paging=controls)

        self.assert_has_valid_head(response, 'd')
        self.assert_has_valid_link(response, '/transactions?head=d&max=b&count=2')
        self.assert_has_valid_paging(response, paging,
                                     '/transactions?head=d&min=a&count=2',
                                     '/transactions?head=d&max=d&count=2')
        self.assert_has_valid_data_list(response, 2)
        self.assert_txns_well_formed(response['data'], 'c', 'b')

    @unittest_run_loop
    async def test_txn_list_paginated_by_max_index(self):
        """Verifies GET /transactions paginated by a max index works properly.

        It will receive a Protobuf response with:
            - a head id of 'd'
            - a paging response with a start of 0, and 4 total resources
            - three transactions with the ids 'd', 'c' and 'b'

        It should send a Protobuf request with:
            - paging controls with a count of 3, and an start_index of 0

        It should send back a JSON response with:
            - a response status of 200
            - a head property of 'd'
            - a link property that ends in '/transactions?head=d&min=3&count=7'
            - paging that matches the response, with a next link
            - a data property that is a list of 2 dicts
            - those dicts are full transactions with ids 'd', 'c', and 'b'
        """
        paging = Mocks.make_paging_response(0, 4)
        self.connection.preset_response(
            head_id='d',
            paging=paging,
            transactions=Mocks.make_txns('d', 'c', 'b'))

        response = await self.get_assert_200('/transactions?max=2&count=7')
        controls = Mocks.make_paging_controls(3, start_index=0)
        self.connection.assert_valid_request_sent(paging=controls)

        self.assert_has_valid_head(response, 'd')
        self.assert_has_valid_link(response, '/transactions?head=d&max=2&count=7')
        self.assert_has_valid_paging(response, paging,
                                     '/transactions?head=d&min=3&count=7')
        self.assert_has_valid_data_list(response, 3)
        self.assert_txns_well_formed(response['data'], 'd', 'c', 'b')

    @unittest_run_loop
    async def test_txn_list_sorted(self):
        """Verifies GET /transactions can send proper sort controls.

        It will receive a Protobuf response with:
            - a head id of '2'
            - a paging response with a start of 0, and 3 total resources
            - three transactions with ids '0', '1', and '2'

        It should send a Protobuf request with:
            - empty paging controls
            - sort controls with a key of 'header_signature'

        It should send back a JSON response with:
            - a status of 200
            - a head property of '2'
            - a link property ending in '/transactions?head=2&sort=header_signature'
            - a paging property that matches the paging response
            - a data property that is a list of 3 dicts
            - and those dicts are full transactions with ids '0', '1', and '2'
        """
        paging = Mocks.make_paging_response(0, 3)
        transactions = Mocks.make_txns('0', '1', '2')
        self.connection.preset_response(head_id='2', paging=paging, transactions=transactions)

        response = await self.get_assert_200('/transactions?sort=header_signature')
        page_controls = Mocks.make_paging_controls()
        sorting = Mocks.make_sort_controls('header_signature')
        self.connection.assert_valid_request_sent(
            paging=page_controls,
            sorting=sorting)

        self.assert_has_valid_head(response, '2')
        self.assert_has_valid_link(response,
            '/transactions?head=2&sort=header_signature')
        self.assert_has_valid_paging(response, paging)
        self.assert_has_valid_data_list(response, 3)
        self.assert_txns_well_formed(response['data'], '0', '1', '2')

    @unittest_run_loop
    async def test_batch_list_with_bad_sort(self):
        """Verifies a GET /transactions with a bad sort breaks properly.

        It will receive a Protobuf response with:
            - a status of INVALID_PAGING

        It should send back a JSON response with:
            - a response status of 400
            - an error property with a code of 57
        """
        self.connection.preset_response(self.status.INVALID_SORT)
        response = await self.get_assert_status('/transactions?sort=bad', 400)

        self.assert_has_valid_error(response, 57)

    @unittest_run_loop
    async def test_txn_list_sorted_with_nested_keys(self):
        """Verifies GET /transactions can send proper sort controls with nested keys.

        It will receive a Protobuf response with:
            - a head id of '2'
            - a paging response with a start of 0, and 3 total resources
            - three transactions with ids '0', '1', and '2'

        It should send a Protobuf request with:
            - empty paging controls
            - sort controls with keys of 'header' and 'signer_pubkey'

        It should send back a JSON response with:
            - a status of 200
            - a head property of '2'
            - a link ending in '/transactions?head=2&sort=header.signer_pubkey'
            - a paging property that matches the paging response
            - a data property that is a list of 3 dicts
            - and those dicts are full transactions with ids '0', '1', and '2'
        """
        paging = Mocks.make_paging_response(0, 3)
        transactions = Mocks.make_txns('0', '1', '2')
        self.connection.preset_response(head_id='2', paging=paging, transactions=transactions)

        response = await self.get_assert_200(
            '/transactions?sort=header.signer_pubkey')
        page_controls = Mocks.make_paging_controls()
        sorting = Mocks.make_sort_controls('header', 'signer_pubkey')
        self.connection.assert_valid_request_sent(
            paging=page_controls,
            sorting=sorting)

        self.assert_has_valid_head(response, '2')
        self.assert_has_valid_link(response,
            '/transactions?head=2&sort=header.signer_pubkey')
        self.assert_has_valid_paging(response, paging)
        self.assert_has_valid_data_list(response, 3)
        self.assert_txns_well_formed(response['data'], '0', '1', '2')

    @unittest_run_loop
    async def test_txn_list_sorted_in_reverse(self):
        """Verifies a GET /transactions can send proper sort parameters.

        It will receive a Protobuf response with:
            - a head id of '2'
            - a paging response with a start of 0, and 3 total resources
            - three transactions with ids '2', '1', and '0'

        It should send a Protobuf request with:
            - empty paging controls
            - sort controls with a key of 'header_signature' that is reversed

        It should send back a JSON response with:
            - a status of 200
            - a head property of '2'
            - a link property ending in '/transactions?head=2&sort=-header_signature'
            - a paging property that matches the paging response
            - a data property that is a list of 3 dicts
            - and those dicts are full transactions with ids '2', '1', and '0'
        """
        paging = Mocks.make_paging_response(0, 3)
        transactions = Mocks.make_txns('2', '1', '0')
        self.connection.preset_response(head_id='2', paging=paging, transactions=transactions)

        response = await self.get_assert_200('/transactions?sort=-header_signature')
        page_controls = Mocks.make_paging_controls()
        sorting = Mocks.make_sort_controls(
            'header_signature', reverse=True)
        self.connection.assert_valid_request_sent(
            paging=page_controls,
            sorting=sorting)

        self.assert_has_valid_head(response, '2')
        self.assert_has_valid_link(response,
            '/transactions?head=2&sort=-header_signature')
        self.assert_has_valid_paging(response, paging)
        self.assert_has_valid_data_list(response, 3)
        self.assert_txns_well_formed(response['data'], '2', '1', '0')

    @unittest_run_loop
    async def test_txn_list_sorted_by_length(self):
        """Verifies a GET /transactions can send proper sort parameters.

        It will receive a Protobuf response with:
            - a head id of '2'
            - a paging response with a start of 0, and 3 total resources
            - three transactions with ids '0', '1', and '2'

        It should send a Protobuf request with:
            - empty paging controls
            - sort controls with a key of 'payload' sorted by length

        It should send back a JSON response with:
            - a status of 200
            - a head property of '2'
            - a link property ending in '/transactions?head=2&sort=payload.length'
            - a paging property that matches the paging response
            - a data property that is a list of 3 dicts
            - and those dicts are full transactions with ids '0', '1', and '2'
        """
        paging = Mocks.make_paging_response(0, 3)
        transactions = Mocks.make_txns('0', '1', '2')
        self.connection.preset_response(head_id='2', paging=paging, transactions=transactions)

        response = await self.get_assert_200('/transactions?sort=payload.length')
        page_controls = Mocks.make_paging_controls()
        sorting = Mocks.make_sort_controls('payload', compare_length=True)
        self.connection.assert_valid_request_sent(
            paging=page_controls,
            sorting=sorting)

        self.assert_has_valid_head(response, '2')
        self.assert_has_valid_link(response,
            '/transactions?head=2&sort=payload.length')
        self.assert_has_valid_paging(response, paging)
        self.assert_has_valid_data_list(response, 3)
        self.assert_txns_well_formed(response['data'], '0', '1', '2')

    @unittest_run_loop
    async def test_txn_list_sorted_by_many_keys(self):
        """Verifies a GET /transactions can send proper sort parameters.

        It will receive a Protobuf response with:
            - a head id of '2'
            - a paging response with a start of 0, and 3 total resources
            - three transactions with ids '2', '1', and '0'

        It should send a Protobuf request with:
            - empty paging controls
            - multiple sort controls with:
                * a key of 'header_signature' that is reversed
                * a key of 'payload' that is sorted by length

        It should send back a JSON response with:
            - a status of 200
            - a head property of '2'
            - link with '/transactions?head=2&sort=-header_signature,payload.length'
            - a paging property that matches the paging response
            - a data property that is a list of 3 dicts
            - and those dicts are full transactions with ids '2', '1', and '0'
        """
        paging = Mocks.make_paging_response(0, 3)
        transactions = Mocks.make_txns('2', '1', '0')
        self.connection.preset_response(head_id='2', paging=paging, transactions=transactions)

        response = await self.get_assert_200(
            '/transactions?sort=-header_signature,payload.length')
        page_controls = Mocks.make_paging_controls()
        sorting = (Mocks.make_sort_controls('header_signature', reverse=True) +
                   Mocks.make_sort_controls('payload', compare_length=True))
        self.connection.assert_valid_request_sent(
            paging=page_controls,
            sorting=sorting)

        self.assert_has_valid_head(response, '2')
        self.assert_has_valid_link(response,
            '/transactions?head=2&sort=-header_signature,payload.length')
        self.assert_has_valid_paging(response, paging)
        self.assert_has_valid_data_list(response, 3)
        self.assert_txns_well_formed(response['data'], '2', '1', '0')


class TransactionGetTests(BaseApiTest):

    async def get_application(self, loop):
        self.set_status_and_connection(
            Message.CLIENT_TRANSACTION_GET_REQUEST,
            client_pb2.ClientTransactionGetRequest,
            client_pb2.ClientTransactionGetResponse)

        handlers = self.build_handlers(loop, self.connection)
        return self.build_app(
            loop,
            '/transactions/{transaction_id}',
            handlers.fetch_transaction)

    @unittest_run_loop
    async def test_txn_get(self):
        """Verifies a GET /transactions/{transaction_id} works properly.

        It should send a Protobuf request with:
            - a transaction_id property of '1'

        It will receive a Protobuf response with:
            - a transaction with an id of '1'

        It should send back a JSON response with:
            - a response status of 200
            - no head property
            - a link property that ends in '/transactions/1'
            - a data property that is a full batch with an id of '1'
        """
        self.connection.preset_response(transaction=Mocks.make_txns('1')[0])

        response = await self.get_assert_200('/transactions/1')
        self.connection.assert_valid_request_sent(transaction_id='1')

        self.assertNotIn('head', response)
        self.assert_has_valid_link(response, '/transactions/1')
        self.assertIn('data', response)
        self.assert_txns_well_formed(response['data'], '1')

    @unittest_run_loop
    async def test_txn_get_with_validator_error(self):
        """Verifies GET /transactions/{transaction_id} w/ validator error breaks.

        It will receive a Protobuf response with:
            - a status of INTERNAL_ERROR

        It should send back a JSON response with:
            - a status of 500
            - an error property with a code of 10
        """
        self.connection.preset_response(self.status.INTERNAL_ERROR)
        response = await self.get_assert_status('/transactions/1', 500)

        self.assert_has_valid_error(response, 10)

    @unittest_run_loop
    async def test_txn_get_with_bad_id(self):
        """Verifies a GET /transactions/{transaction_id} with unfound id breaks.

        It will receive a Protobuf response with:
            - a status of NO_RESOURCE

        It should send back a JSON response with:
            - a response status of 404
            - an error property with a code of 72
        """
        self.connection.preset_response(self.status.NO_RESOURCE)
        response = await self.get_assert_status('/transactions/bad', 404)

        self.assert_has_valid_error(response, 72)

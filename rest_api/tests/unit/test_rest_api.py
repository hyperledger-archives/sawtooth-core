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
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from sawtooth_rest_api.protobuf import batch_pb2
from sawtooth_rest_api.routes import RouteHandler
from tests.unit.mock_stream import MockStream

class ApiTest(AioHTTPTestCase):

    async def get_application(self, loop):
        # Create handler and replace stream with mock
        handlers = RouteHandler('tcp://0.0.0.0:40404', 5)
        handlers._stream = MockStream()

        # Add handlers
        app = web.Application(loop=loop)
        app.router.add_post('/batches', handlers.batches_post)
        app.router.add_get('/batch_status', handlers.status_list)
        app.router.add_get('/state', handlers.state_list)
        app.router.add_get('/state/{address}', handlers.state_get)
        app.router.add_get('/blocks', handlers.block_list)
        app.router.add_get('/blocks/{block_id}', handlers.block_get)
        app.router.add_get('/batches', handlers.batch_list)
        app.router.add_get('/batches/{batch_id}', handlers.batch_get)
        return app

    @unittest_run_loop
    async def test_post_batch(self):
        """Verifies a POST /batches with one id works properly.

        Expects to find:
            - a response status of 202
            - no data property
            - a link property that ends in '/batches?id=a'
        """
        request = await self.post_batch_ids('a')
        self.assertEqual(202, request.status)

        response = await request.json()
        self.assertNotIn('data', response)
        self.assert_has_valid_link(response, '/batch_status?id=a')

    @unittest_run_loop
    async def test_post_json_batch(self):
        """Verifies a POST /batches with a JSON request body breaks properly.

        Expects to find:
            - a response status of 400
        """
        request = await self.client.post(
            '/batches',
            data='{"bad": "data"}',
            headers={'content-type': 'application/json'})
        self.assertEqual(400, request.status)

    @unittest_run_loop
    async def test_post_invalid_batch(self):
        """Verifies a POST /batches with an invalid batch breaks properly.

        *Note: the mock submit handler marks ids of 'bad' as invalid

        Expects to find:
            - a response status of 400
        """
        request = await self.post_batch_ids('bad')
        self.assertEqual(400, request.status)

    @unittest_run_loop
    async def test_post_many_batches(self):
        """Verifies a POST /batches with many ids works properly.

        Expects to find:
            - a response status of 202
            - no data property
            - a link property that ends in '/batch_status?id=a,b,c'
        """
        request = await self.post_batch_ids('a', 'b', 'c')
        self.assertEqual(202, request.status)

        response = await request.json()
        self.assertNotIn('data', response)
        self.assert_has_valid_link(response, '/batch_status?id=a,b,c')

    @unittest_run_loop
    async def test_post_no_batches(self):
        """Verifies a POST /batches with no batches breaks properly.

        Expects to find:
            - a response status of 400
        """
        request = await self.post_batch_ids()
        self.assertEqual(400, request.status)

    @unittest_run_loop
    async def test_post_batch_with_wait(self):
        """Verifies a POST /batches can wait for commit properly.

        Expects to find:
            - a response status of 201
            - no data property
        """
        request = await self.post_batch_ids('a', wait=True)
        self.assertEqual(201, request.status)

        response = await request.json()
        self.assert_has_valid_link(response, '/batches?id=a')
        self.assertNotIn('data', response)

    @unittest_run_loop
    async def test_post_batch_with_timeout(self):
        """Verifies a POST /batches works when timed out while waiting.

        *Note: the mock submit handler marks ids of 'pending' as PENDING

        Expects to find:
            - a response status of 200
            - a link property that ends in '/batch_status?id=pending'
            - a data property that is a dict with the key/value pair:
                * 'pending': 'PENDING'
        """
        request = await self.post_batch_ids('pending', wait=True)
        self.assertEqual(200, request.status)

        response = await request.json()
        self.assert_has_valid_link(response, '/batch_status?id=pending')
        self.assert_has_valid_data_dict(response, {'pending': 'PENDING'})

    @unittest_run_loop
    async def test_batch_status_with_one_id(self):
        """Verifies a GET /batch_status with one id works properly.

        Fetches from the following preseeded id/status pairs:
            'committed': COMMITTED
            'pending': PENDING
             *: UNKNOWN

        Expects to find:
            - a response status of 200
            - a link property that ends in '/batch_status?id=pending'
            - a data property that is a dict with the key/value pair:
                * 'pending': 'PENDING'
        """
        response = await self.get_json_assert_200('/batch_status?id=pending')

        self.assert_has_valid_link(response, '/batch_status?id=pending')
        self.assert_has_valid_data_dict(response, {'pending': 'PENDING'})

    @unittest_run_loop
    async def test_batch_status_with_wait(self):
        """Verifies a GET /batch_status with a wait set works properly.

        Fetches from preseeded id/status pairs that look like this with a wait:
            'committed': COMMITTED
            'pending': COMMITTED
             *: UNKNOWN

        Expects to find:
            - a response status of 200
            - a link property that ends in '/batch_status?id=pending&wait'
            - a data property that is a dict with the key/value pair:
                * 'pending': 'COMMITTED'
        """
        response = await self.get_json_assert_200('/batch_status?id=pending&wait')

        self.assert_has_valid_link(response, '/batch_status?id=pending&wait')
        self.assert_has_valid_data_dict(response, {'pending': 'COMMITTED'})

    @unittest_run_loop
    async def test_batch_status_with_many_ids(self):
        """Verifies a GET /batch_status with many ids works properly.

        Fetches from the following preseeded id/status pairs:
            'committed': COMMITTED
            'pending': PENDING
             *: UNKNOWN

        Expects to find:
            - a response status of 200
            - link property ending in '/batch_status?id=committed,unknown,bad'
            - a data property that is a dict with the key/value pairs:
                * 'committed': 'COMMITTED'
                * 'unknown': 'UNKNOWN'
                * 'bad': 'UNKNOWN'
        """
        response = await self.get_json_assert_200(
            '/batch_status?id=committed,unknown,bad')

        self.assert_has_valid_link(
            response,
            '/batch_status?id=committed,unknown,bad')
        self.assert_has_valid_data_dict(response, {
            'committed': 'COMMITTED',
            'unknown': 'UNKNOWN',
            'bad': 'UNKNOWN'})

    @unittest_run_loop
    async def test_batch_status_with_no_id(self):
        """Verifies a GET /batch_status with no id breaks properly.

        Expects to find:
            - a response status of 400
        """
        response = await self.get_and_assert_status('/batch_status', 400)

    @unittest_run_loop
    async def test_state_list(self):
        """Verifies a GET /state without parameters works properly.

        Fetches latest state from mock state data:
            '0': {'a': b'1'},
            '1': {'a': b'2', 'b': b'4'},
            '2': {'a': b'3', 'b': b'5', 'c': b'7'}

        Expects to find:
            - a response status of 200
            - a head property of '2'
            - a link property that ends in '/state?head=2'
            - a data property that is a list of 3 leaf dicts
            - and those leaves include the address/data pairs:
                * 'a': b'3'
                * 'b': b'5'
                * 'c': b'7'
        """
        response = await self.get_json_assert_200('/state')

        self.assert_has_valid_head(response, '2')
        self.assert_has_valid_link(response, '/state?head=2')
        self.assert_has_valid_data_list(response, 3)

        self.assert_leaves_contain(response['data'], 'a', b'3')
        self.assert_leaves_contain(response['data'], 'b', b'5')
        self.assert_leaves_contain(response['data'], 'c', b'7')

    @unittest_run_loop
    async def test_state_list_with_head(self):
        """Verifies a GET /state works properly with head specified.

        Fetches all state from '1' in mock state data:
            '0': {'a': b'1'},
            '1': {'a': b'2', 'b': b'4'},
            '2': {'a': b'3', 'b': b'5', 'c': b'7'}

        Expects to find:
            - a response status of 200
            - a head property of '1'
            - a link property that ends in '/state?head=1'
            - a data property that is a list of 2 leaf dicts
            - and those leaves include the address/data pairs:
                * 'a': b'2'
                * 'b': b'4'
        """
        response = await self.get_json_assert_200('/state?head=1')

        self.assert_has_valid_head(response, '1')
        self.assert_has_valid_link(response, '/state?head=1')
        self.assert_has_valid_data_list(response, 2)

        self.assert_leaves_contain(response['data'], 'a', b'2')
        self.assert_leaves_contain(response['data'], 'b', b'4')

    @unittest_run_loop
    async def test_state_list_with_bad_head(self):
        """Verifies a GET /state breaks properly with a bad head specified.

        Expects to find:
            - a response status of 404
        """
        await self.assert_404('/state?head=bad')

    @unittest_run_loop
    async def test_state_list_with_address(self):
        """Verifies a GET /state works properly filtered by address.

        Fetches latest state beginning with 'c' in data:
            '0': {'a': b'1'},
            '1': {'a': b'2', 'b': b'4'},
            '2': {'a': b'3', 'b': b'5', 'c': b'7'}

        Expects to find:
            - a response status of 200
            - a head property of '2'
            - a link property that ends in '/state?head=2&address=c'
            - a data property that is a list of 1 leaf dict
            - and that leaf include the address/data pairs: 'c': b'7'
        """
        response = await self.get_json_assert_200('/state?address=c')

        self.assert_has_valid_head(response, '2')
        self.assert_has_valid_link(response, '/state?head=2&address=c')
        self.assert_has_valid_data_list(response, 1)

        self.assert_leaves_contain(response['data'], 'c', b'7')

    @unittest_run_loop
    async def test_state_list_with_bad_address(self):
        """Verifies a GET /state breaks properly filtered by a bad address.

        Expects to find:
            - a response status of 200
            - a head property of '2'
            - a link property that ends in '/state?head=2&address=bad'
            - a data property that is an empty list
        """
        response = await self.get_json_assert_200('/state?address=bad')

        self.assert_has_valid_head(response, '2')
        self.assert_has_valid_link(response, '/state?head=2&address=bad')
        self.assert_has_valid_data_list(response, 0)

    @unittest_run_loop
    async def test_state_list_with_head_and_address(self):
        """Verifies GET /state works with a head and filtered by address.

        Fetches state from '1', beginning with 'a', in data:
            '0': {'a': b'1'},
            '1': {'a': b'2', 'b': b'4'},
            '2': {'a': b'3', 'b': b'5', 'c': b'7'}

        Expects to find:
            - a response status of 200
            - a head property of '1'
            - a link property that ends in '/state?head=1&address=a'
            - a data property that is a list of 1 leaf dict
            - and that leaf include the address/data pairs: 'c': b'7'
        """
        response = await self.get_json_assert_200('/state?address=a&head=1')

        self.assert_has_valid_head(response, '1')
        self.assert_has_valid_link(response, '/state?head=1&address=a')
        self.assert_has_valid_data_list(response, 1)

        self.assert_leaves_contain(response['data'], 'a', b'2')

    @unittest_run_loop
    async def test_state_list_with_head_too_early(self):
        """Verifies GET /state breaks with head earlier than address filter

        Tries to fetch state beginning with 'b', from '0', in data:
            '0': {'a': b'1'},
            '1': {'a': b'2', 'b': b'4'},
            '2': {'a': b'3', 'b': b'5', 'c': b'7'}

        Expects to find:
            - a response status of 200
            - a head property of '0'
            - a link property that ends in '/state?head=0&address=b'
            - a data property that is an empty list
        """
        response = await self.get_json_assert_200('/state?address=b&head=0')

        self.assert_has_valid_head(response, '0')
        self.assert_has_valid_link(response, '/state?head=0&address=b')
        self.assert_has_valid_data_list(response, 0)

    @unittest_run_loop
    async def test_state_get(self):
        """Verifies a GET /state/{address} without parameters works properly.

        Fetches latest state with address 'a' in mock state data:
            '0': {'a': b'1'},
            '1': {'a': b'2', 'b': b'4'},
            '2': {'a': b'3', 'b': b'5', 'c': b'7'}

        Expects to find:
            - a response status of 200
            - a head property of '2'
            - a link property that ends in '/state/b?head=2'
            - a data property that b64decodes to b'5'
        """
        response = await self.get_json_assert_200('/state/a')

        self.assert_has_valid_head(response, '2')
        self.assert_has_valid_link(response, '/state/a?head=2')
        self.assertIn('data', response)

        data = response['data']
        self.assertIsInstance(data, str)
        self.assertEqual(b'3', b64decode(data))

    @unittest_run_loop
    async def test_state_bad_get(self):
        """Verifies a GET /state/{address} breaks with a bad address.

        Expects to find:
            - a response status of 404
        """
        await self.assert_404('/state/bad')

    @unittest_run_loop
    async def test_state_get_with_head(self):
        """Verifies a GET /state/{address} works properly with head parameter.

        Fetches state with address 'a', from '1', in data:
            '0': {'a': b'1'},
            '1': {'a': b'2', 'b': b'4'},
            '2': {'a': b'3', 'b': b'5', 'c': b'7'}

        Expects to find:
            - a response status of 200
            - a head property of '2'
            - a link property that ends in '/state/b?head=2'
            - a data property that b64decodes to b'5'
        """
        response = await self.get_json_assert_200('/state/b?head=1')

        self.assert_has_valid_head(response, '1')
        self.assert_has_valid_link(response, '/state/b?head=1')
        self.assertIn('data', response)

        data = response['data']
        self.assertIsInstance(data, str)
        self.assertEqual(b'4', b64decode(data))

    @unittest_run_loop
    async def test_state_get_with_bad_head(self):
        """Verifies a GET /state/{address} breaks properly with a bad head.

        Expects to find:
            - a response status of 404
        """
        await self.assert_404('/state/c?head=bad')

    @unittest_run_loop
    async def test_state_get_with_early_head(self):
        """Verifies GET /state/{address} breaks with head earlier than address.

        Tries to get address 'c', from '0', in data:
            '0': {'a': b'1'},
            '1': {'a': b'2', 'b': b'4'},
            '2': {'a': b'3', 'b': b'5', 'c': b'7'}

        Expects to find:
            - a response status of 404
        """
        await self.assert_404('/state/c?head=0')

    @unittest_run_loop
    async def test_block_list(self):
        """Verifies a GET /blocks without parameters works properly.

        Fetches all blocks from default mock store:
            {
                header: {previous_block_id: '1', ...},
                header_signature: '2',
                batches: [{
                    header: {signer_pubkey: 'pubkey', ...},
                    header_signature: '2',
                    transactions: [{
                        header: {nonce: '2', ...},
                        header_signature: '2',
                        payload: b'payload'
                    }]
                }]
            },
            {header: {...}, header_signature: '1', batches: [{...}]},
            {header: {...}, header_signature: '0', batches: [{...}]}

        Expects to find:
            - a response status of 200
            - a head property of '2'
            - a link property that ends in '/blocks?head=2'
            - a data property that:
                * contains a list of 3 block dicts with a header and batches
                * batches with 1 batch with a header and transactions
                * transactions with 1 transaction with a header
        """
        response = await self.get_json_assert_200('/blocks')

        self.assert_has_valid_head(response, '2')
        self.assert_has_valid_link(response, '/blocks?head=2')
        self.assert_has_valid_data_list(response, 3)

        first_block = response['data'][0]
        self.assertEqual(response['head'], first_block['header_signature'])
        self.assert_block_well_formed(first_block, '2')

    @unittest_run_loop
    async def test_block_list_with_head(self):
        """Verifies a GET /blocks with a head parameter works properly.

        Fetches blocks from '1' and older from the store:
            {
                header: {previous_block_id: '1', ...},
                header_signature: '2',
                batches: [{
                    header: {signer_pubkey: 'pubkey', ...},
                    header_signature: '2',
                    transactions: [{
                        header: {nonce: '2', ...},
                        header_signature: '2',
                        payload: b'payload'
                    }]
                }]
            },
            {header: {...}, header_signature: '0', batches: [{...}]}

        Expects to find:
            - a response status of 200
            - a head property of '1'
            - a link property that ends in '/blocks?head=1'
            - a data property that:
                * contains a list of 2 block dicts with a header and batches
                * batches with 1 batch with a header and transactions
                * transactions with 1 transaction with a header
        """
        response = await self.get_json_assert_200('/blocks?head=1')

        self.assert_has_valid_head(response, '1')
        self.assert_has_valid_link(response, '/blocks?head=1')
        self.assert_has_valid_data_list(response, 2)

        first_block = response['data'][0]
        self.assertEqual(response['head'], first_block['header_signature'])
        self.assert_block_well_formed(first_block, '1')

    @unittest_run_loop
    async def test_block_list_with_bad_head(self):
        """Verifies a GET /blocks with a bad head breaks properly.

        Expects to find:
            - a response status of 404
        """
        await self.assert_404('/blocks?head=bad')

    @unittest_run_loop
    async def test_block_list_with_ids(self):
        """Verifies GET /blocks with the id parameter works properly.

        Fetches blocks from default mock store:
            {
                header: {previous_block_id: '1', ...},
                header_signature: '2',
                batches: [{
                    header: {signer_pubkey: 'pubkey', ...},
                    header_signature: '2',
                    transactions: [{
                        header: {nonce: '2', ...},
                        header_signature: '2',
                        payload: b'payload'
                    }]
                }]
            },
            {header: {...}, header_signature: '1', batches: [{...}]},
            {header: {...}, header_signature: '0', batches: [{...}]}

        Expects to find:
            - a response status of 200
            - a head property of '2', the latest
            - a link property that ends in '/blocks?head=2&id=0,2'
            - a data property that:
                * contains a list of 2 block dicts with a header and batches
                * batches with 1 batch with a header and transactions
                * transactions with 1 transaction with a header
        """
        response = await self.get_json_assert_200('/blocks?id=0,2')

        self.assert_has_valid_head(response, '2')
        self.assert_has_valid_link(response, '/blocks?head=2&id=0,2')
        self.assert_has_valid_data_list(response, 2)
        self.assert_block_well_formed(response['data'][0], '0')

    @unittest_run_loop
    async def test_block_list_with_bad_ids(self):
        """Verifies GET /blocks with a bad id parameter breaks properly.

        Expects to find:
            - a response status of 200
            - a head property of '2', the latest
            - a link property that ends in '/blocks?head=2&id=bad,notgood'
            - a data property that is an empty list
        """
        response = await self.get_json_assert_200('/blocks?id=bad,notgood')

        self.assert_has_valid_head(response, '2')
        self.assert_has_valid_link(response, '/blocks?head=2&id=bad,notgood')
        self.assert_has_valid_data_list(response, 0)

    @unittest_run_loop
    async def test_block_list_with_head_and_ids(self):
        """Verifies GET /blocks with head and id parameters works properly.

        Fetches blocks from default mock store:
            {
                header: {previous_block_id: '1', ...},
                header_signature: '2',
                batches: [{
                    header: {signer_pubkey: 'pubkey', ...},
                    header_signature: '2',
                    transactions: [{
                        header: {nonce: '2', ...},
                        header_signature: '2',
                        payload: b'payload'
                    }]
                }]
            },
            {header: {...}, header_signature: '1', batches: [{...}]},
            {header: {...}, header_signature: '0', batches: [{...}]}

        Expects to find:
            - a response status of 200
            - a head property of '1'
            - a link property that ends in '/blocks?head=1&id=0'
            - a data property that:
                * contains a list of 1 block dicts with a header and batches
                * batches with 1 batch with a header and transactions
                * transactions with 1 transaction with a header
        """
        response = await self.get_json_assert_200('/blocks?id=0&head=1')

        self.assert_has_valid_head(response, '1')
        self.assert_has_valid_link(response, '/blocks?head=1&id=0')
        self.assert_has_valid_data_list(response, 1)
        self.assert_block_well_formed(response['data'][0], '0')

    @unittest_run_loop
    async def test_block_list_with_id_head_mismatch(self):
        """Verifies GET /blocks with ids missing from a specified head work.

        Expects to find:
            - a response status of 200
            - a head property of '0'
            - a link property that ends in '/blocks?head=0&id=1,2'
            - a data property that is an empty list
        """
        response = await self.get_json_assert_200('/blocks?id=1,2&head=0')

        self.assert_has_valid_head(response, '0')
        self.assert_has_valid_link(response, '/blocks?head=0&id=1,2')
        self.assert_has_valid_data_list(response, 0)

    @unittest_run_loop
    async def test_block_get(self):
        """Verifies a GET /blocks/{block_id} works properly.

        Fetches block '1' from the default mock store:
            {
                header: {previous_block_id: '0', ...},
                header_signature: '1',
                batches: [{
                    header: {signer_pubkey: 'pubkey', ...},
                    header_signature: '1',
                    transactions: [{
                        header: {nonce: '1', ...},
                        header_signature: '1',
                        payload: b'payload'
                    }]
                }]
            }

        Expects to find:
            - a response status of 200
            - no head property
            - a link property that ends in '/blocks/1'
            - a data property that:
                * contains a single block dict with a header and batches
                * batches with 1 batch with a header and transactions
                * transactions with 1 transaction with a header
        """
        response = await self.get_json_assert_200('/blocks/1')

        self.assertNotIn('head', response)
        self.assert_has_valid_link(response, '/blocks/1')
        self.assertIn('data', response)
        self.assert_block_well_formed(response['data'], '1')

    @unittest_run_loop
    async def test_block_get_with_bad_id(self):
        """Verifies a GET /blocks/{block_id} with invalid id breaks properly.

        Expects to find:
            - a response status of 400
        """
        await self.assert_400('/blocks/bad')

    @unittest_run_loop
    async def test_block_get_with_missing_id(self):
        """Verifies a GET /blocks/{block_id} with not found id breaks properly.

        Expects to find:
            - a response status of 404
        """
        await self.assert_404('/blocks/missing')

    @unittest_run_loop
    async def test_batch_list(self):
        """Verifies a GET /batches without parameters works properly.

        Fetches all batches from default mock store:
            {
                header: {previous_block_id: '1', ...},
                header_signature: '2',
                batches: [{
                    header: {signer_pubkey: 'pubkey', ...},
                    header_signature: '2',
                    transactions: [{
                        header: {nonce: '2', ...},
                        header_signature: '2',
                        payload: b'payload'
                    }]
                }]
            },
            {header: {...}, header_signature: '1', batches: [{...}]},
            {header: {...}, header_signature: '0', batches: [{...}]}

        Expects to find:
            - a response status of 200
            - a head property of '2'
            - a link property that ends in '/batches?head=2'
            - a data property that:
                * is a list of 3 batch dicts with a header and transactions
                * transactions property has 1 transaction with a header
        """
        response = await self.get_json_assert_200('/batches')

        self.assert_has_valid_head(response, '2')
        self.assert_has_valid_link(response, '/batches?head=2')
        self.assert_has_valid_data_list(response, 3)
        self.assert_batch_well_formed(response['data'][0], '2')

    @unittest_run_loop
    async def test_batch_list_with_head(self):
        """Verifies a GET /batches with a head parameter works properly.

        Fetches batches from '1' and older from the store:
            {
                header: {previous_block_id: '1', ...},
                header_signature: '2',
                batches: [{
                    header: {signer_pubkey: 'pubkey', ...},
                    header_signature: '2',
                    transactions: [{
                        header: {nonce: '2', ...},
                        header_signature: '2',
                        payload: b'payload'
                    }]
                }]
            },
            {header: {...}, header_signature: '0', batches: [{...}]}

        Expects to find:
            - a response status of 200
            - a head property of '1'
            - a link property that ends in '/batches?head=1'
            - a data property that:
                * is a list of 2 batch dicts with a header and transactions
                * transactions properties with 1 transaction with a header
        """
        response = await self.get_json_assert_200('/batches?head=1')

        self.assert_has_valid_head(response, '1')
        self.assert_has_valid_link(response, '/batches?head=1')
        self.assert_has_valid_data_list(response, 2)
        self.assert_batch_well_formed(response['data'][0], '1')

    @unittest_run_loop
    async def test_batch_list_with_bad_head(self):
        """Verifies a GET /batches with a bad head breaks properly.

        Expects to find:
            - a response status of 404
        """
        await self.assert_404('/batches?head=bad')

    @unittest_run_loop
    async def test_batch_list_with_ids(self):
        """Verifies GET /batches with the id parameter works properly.

        Fetches batches from default mock store:
            {
                header: {previous_block_id: '1', ...},
                header_signature: '2',
                batches: [{
                    header: {signer_pubkey: 'pubkey', ...},
                    header_signature: '2',
                    transactions: [{
                        header: {nonce: '2', ...},
                        header_signature: '2',
                        payload: b'payload'
                    }]
                }]
            },
            {header: {...}, header_signature: '1', batches: [{...}]},
            {header: {...}, header_signature: '0', batches: [{...}]}

        Expects to find:
            - a response status of 200
            - a head property of '2', the latest
            - a link property that ends in '/batches?head=2&id=0,2'
            - a data property that:
                * contains a list of 2 batch dicts with a header and batches
                * batches with 1 batch with a header and transactions
                * transactions with 1 transaction with a header
        """
        response = await self.get_json_assert_200('/batches?id=0,2')

        self.assert_has_valid_head(response, '2')
        self.assert_has_valid_link(response, '/batches?head=2&id=0,2')
        self.assert_has_valid_data_list(response, 2)
        self.assert_batch_well_formed(response['data'][0], '0')

    @unittest_run_loop
    async def test_batch_list_with_bad_ids(self):
        """Verifies GET /batches with a bad id parameter breaks properly.

        Expects to find:
            - a response status of 200
            - a head property of '2', the latest
            - a link property that ends in '/batches?head=2&id=bad,notgood'
            - a data property that is an empty list
        """
        response = await self.get_json_assert_200('/batches?id=bad,notgood')

        self.assert_has_valid_head(response, '2')
        self.assert_has_valid_link(response, '/batches?head=2&id=bad,notgood')
        self.assert_has_valid_data_list(response, 0)

    @unittest_run_loop
    async def test_batch_list_with_head_and_ids(self):
        """Verifies GET /batches with head and id parameters works properly.

        Fetches batches from default mock store:
            {
                header: {previous_block_id: '1', ...},
                header_signature: '2',
                batches: [{
                    header: {signer_pubkey: 'pubkey', ...},
                    header_signature: '2',
                    transactions: [{
                        header: {nonce: '2', ...},
                        header_signature: '2',
                        payload: b'payload'
                    }]
                }]
            },
            {header: {...}, header_signature: '1', batches: [{...}]},
            {header: {...}, header_signature: '0', batches: [{...}]}

        Expects to find:
            - a response status of 200
            - a head property of '1'
            - a link property that ends in '/batches?head=1&id=0'
            - a data property that:
                * contains a list of 1 batch dicts with a header and batches
                * batches with 1 batch with a header and transactions
                * transactions with 1 transaction with a header
        """
        response = await self.get_json_assert_200('/batches?id=0&head=1')

        self.assert_has_valid_head(response, '1')
        self.assert_has_valid_link(response, '/batches?head=1&id=0')
        self.assert_has_valid_data_list(response, 1)
        self.assert_batch_well_formed(response['data'][0], '0')

    @unittest_run_loop
    async def test_batch_list_with_id_head_mismatch(self):
        """Verifies GET /batches with ids missing from a specified head work.

        Expects to find:
            - a response status of 200
            - a head property of '0'
            - a link property that ends in '/batches?head=0&id=1,2'
            - a data property that is an empty list
        """
        response = await self.get_json_assert_200('/batches?id=1,2&head=0')

        self.assert_has_valid_head(response, '0')
        self.assert_has_valid_link(response, '/batches?head=0&id=1,2')
        self.assert_has_valid_data_list(response, 0)

    @unittest_run_loop
    async def test_batch_get(self):
        """Verifies a GET /batches/{batch_id} works properly.

        Fetches batch '1' from the default mock store:
            {
                header: {signer_pubkey: 'pubkey', ...},
                header_signature: '1',
                transactions: [{
                    header: {nonce: '1', ...},
                    header_signature: '1',
                    payload: b'payload'
                }]
            }

        Expects to find:
            - a response status of 200
            - no head property
            - a link property that ends in '/batches/1'
            - a data property that:
                * is a single batch dict with a header and transactions
                * transactions property with 1 transaction with a header
        """
        response = await self.get_json_assert_200('/batches/1')

        self.assertNotIn('head', response)
        self.assert_has_valid_link(response, '/batches/1')
        self.assertIn('data', response)
        self.assert_batch_well_formed(response['data'], '1')

    @unittest_run_loop
    async def test_batch_get_with_bad_id(self):
        """Verifies a GET /batches/{batch_id} with invalid id breaks properly.

        Expects to find:
            - a response status of 400
        """
        await self.assert_400('/batches/bad')

    @unittest_run_loop
    async def test_batch_get_with_missing_id(self):
        """Verifies a GET /batches/{batch_id} with not found id breaks properly.

        Expects to find:
            - a response status of 404
        """
        await self.assert_404('/batches/missing')


    async def post_batch_ids(self, *batch_ids, wait=False):
        batches = [batch_pb2.Batch(
            header_signature=batch_id,
            header=b'header') for batch_id in batch_ids]
        batch_list = batch_pb2.BatchList(batches=batches)

        return await self.client.post(
            '/batches' + ('?wait' if wait else ''),
            data=batch_list.SerializeToString(),
            headers={'content-type': 'application/octet-stream'})

    async def get_and_assert_status(self, endpoint, status):
        request = await self.client.get(endpoint)
        self.assertEqual(status, request.status)
        return request

    async def get_json_assert_200(self, endpoint):
        request = await self.get_and_assert_status(endpoint, 200)
        return await request.json()

    async def assert_400(self, endpoint):
        await self.get_and_assert_status(endpoint, 400)

    async def assert_404(self, endpoint):
        await self.get_and_assert_status(endpoint, 404)

    def assert_all_instances(self, items, cls):
        """Asserts that all items in a collection are instances of a class
        """
        for item in items:
            self.assertIsInstance(item, cls)

    def assert_has_valid_head(self, response, expected):
        """Asserts a response has a head string with an expected value
        """
        self.assertIn('head', response)
        head = response['head']
        self.assertIsInstance(head, str)
        self.assertEqual(head, expected)

    def assert_has_valid_link(self, response, expected_ending):
        """Asserts a response has a link url string with an expected ending
        """
        self.assertIn('link', response)
        link = response['link']
        self.assertIsInstance(link, str)
        self.assertTrue(link.startswith('http'))
        self.assertTrue(link.endswith(expected_ending))

    def assert_has_valid_data_list(self, response, expected_length):
        """Asserts a response has a data list of dicts of an expected length.
        """
        self.assertIn('data', response)
        data = response['data']
        self.assertIsInstance(data, list)
        self.assert_all_instances(data, dict)
        self.assertEqual(expected_length, len(data))

    def assert_has_valid_data_dict(self, response, expected_value):
        """Asserts a response has a data dict with an expected value.
        """
        self.assertIn('data', response)
        data = response['data']
        self.assertIsInstance(data, dict)
        self.assertEqual(expected_value, data)

    def assert_leaves_contain(self, leaves, address, value):
        """Asserts that there is one leaf that matches an address,
        and that its data when b64decoded matches an expected value.
        """
        matches = [l for l in leaves if l['address'] == address]
        self.assertEqual(1, len(matches))
        self.assertEqual(value, b64decode(matches[0]['data']))

    def assert_block_well_formed(self, block, expected_id):
        """Tests a block dict is fully expanded and matches the expected id.
        Assumes the block contains one batch and txn which share the id.
        """
        self.assertIsInstance(block, dict)
        self.assertEqual(expected_id, block['header_signature'])
        self.assertIsInstance(block['header'], dict)
        self.assertEqual(b'consensus', b64decode(block['header']['consensus']))

        batches = block['batches']
        self.assertIsInstance(batches, list)
        self.assertEqual(1, len(batches))
        self.assert_all_instances(batches, dict)
        self.assert_batch_well_formed(batches[0], expected_id)

    def assert_batch_well_formed(self, batch, expected_id):
        self.assertEqual(expected_id, batch['header_signature'])
        self.assertIsInstance(batch['header'], dict)
        self.assertEqual('pubkey', batch['header']['signer_pubkey'])

        txns = batch['transactions']
        self.assertIsInstance(txns, list)
        self.assertEqual(1, len(txns))
        self.assert_all_instances(txns, dict)
        self.assert_txn_well_formed(txns[0], expected_id)

    def assert_txn_well_formed(self, txn, expected_id):
        self.assertEqual(expected_id, txn['header_signature'])
        self.assertEqual(b'payload', b64decode(txn['payload']))
        self.assertIsInstance(txn['header'], dict)
        self.assertEqual(expected_id, txn['header']['nonce'])

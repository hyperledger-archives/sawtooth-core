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
from sawtooth_rest_api.routes import RouteHandler
from tests.unit.mock_stream import MockStream

class ApiTest(AioHTTPTestCase):

    async def get_application(self, loop):
        # Create handler and replace stream with mock
        handlers = RouteHandler('tcp://0.0.0.0:40404', 5)
        handlers._stream = MockStream()

        # Add handlers
        app = web.Application(loop=loop)
        app.router.add_get('/state', handlers.state_list)
        app.router.add_get('/state/{address}', handlers.state_get)
        app.router.add_get('/blocks', handlers.block_list)
        app.router.add_get('/blocks/{block_id}', handlers.block_get)
        return app

    async def get_and_assert_status(self, endpoint, status):
        request = await self.client.request('GET', endpoint)
        self.assertEqual(status, request.status)
        return request

    async def get_json_assert_200(self, endpoint):
        request = await self.get_and_assert_status(endpoint, 200)
        return await request.json()

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
        """Asserts a response has a data list of dicts of an expected length,
        """
        self.assertIn('data', response)
        data = response['data']
        self.assertIsInstance(data, list)
        self.assert_all_instances(data, dict)
        self.assertEqual(expected_length, len(data))

    def assert_block_well_formed(self, block, expected_id):
        """Tests a block dict is fully expanded and matches the expected id.
        Assumes the block contains one batch and txn which share the id.
        """

        # Check block and its header
        self.assertIsInstance(block, dict)
        self.assertEqual(expected_id, block['header_signature'])
        self.assertIsInstance(block['header'], dict)
        self.assertEqual(b'consensus', b64decode(block['header']['consensus']))

        # Check batch and its header
        batches = block['batches']
        self.assertIsInstance(batches, list)
        self.assertEqual(1, len(batches))
        self.assert_all_instances(batches, dict)

        self.assertEqual(expected_id, batches[0]['header_signature'])
        self.assertIsInstance(batches[0]['header'], dict)
        self.assertEqual('pubkey', batches[0]['header']['signer_pubkey'])

        # Check transaction and its header
        txns = batches[0]['transactions']
        self.assertIsInstance(txns, list)
        self.assertEqual(1, len(txns))
        self.assert_all_instances(txns, dict)

        self.assertEqual(expected_id, txns[0]['header_signature'])
        self.assertEqual(b'payload', b64decode(txns[0]['payload']))
        self.assertIsInstance(txns[0]['header'], dict)
        self.assertEqual(expected_id, txns[0]['header']['nonce'])

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
            {header: {...}, header_signature: '1', batches: [{...}]},
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
        """Verifies a GET /blocks with a bad head breaks properly.

        Expects to find:
            - a response status of 404
        """
        await self.assert_404('/blocks/bad')

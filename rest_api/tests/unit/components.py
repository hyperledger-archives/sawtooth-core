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

import re
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase
from base64 import b64decode

from sawtooth_rest_api.route_handlers import RouteHandler
from sawtooth_rest_api.protobuf import client_pb2
from sawtooth_rest_api.protobuf.client_pb2 import Leaf
from sawtooth_rest_api.protobuf.client_pb2 import PagingControls
from sawtooth_rest_api.protobuf.client_pb2 import PagingResponse
from sawtooth_rest_api.protobuf.client_pb2 import SortControls
from sawtooth_rest_api.protobuf.block_pb2 import Block
from sawtooth_rest_api.protobuf.block_pb2 import BlockHeader
from sawtooth_rest_api.protobuf.batch_pb2 import BatchList
from sawtooth_rest_api.protobuf.batch_pb2 import Batch
from sawtooth_rest_api.protobuf.batch_pb2 import BatchHeader
from sawtooth_rest_api.protobuf.transaction_pb2 import Transaction
from sawtooth_rest_api.protobuf.transaction_pb2 import TransactionHeader


TEST_TIMEOUT = 5


class MockStream(object):
    """Replaces a route handler's stream to allow tests to preset the response
    to send back as well as run asserts on the protobufs sent to the stream.

    Methods can be accessed using `self.stream` within a test case. MockStream
    should not be initialized directly.
    """
    def __init__(self, test_case, request_type, request_proto, response_proto):
        self._tests = test_case
        self._request_type = request_type
        self._request_proto = request_proto
        self._response_proto = response_proto
        self._reset_sent_request()
        self._reset_response()

    def preset_response(self, status=None, **response_data):
        """Sets the response that will be returned by the next `send` call.
        Should be set once before every test call the Rest Api makes to stream.

        Args:
            status (int, optional): Enum of the response status, defaults to OK
            response_data (kwargs): Other data to add to the Protobuf response
        """
        if status is None:
            status = self._response_proto.OK
        self._response = self._response_proto(status=status, **response_data)

    def assert_valid_request_sent(self, **request_data):
        """Asserts that the last sent request matches the expected data.

        Args:
            request_data (kwargs): The data expected to be in the last request

        Raises:
            AssertionError: Raised if no new request was sent previous to call
        """
        if not self._sent_request_type or not self._sent_request:
            raise AssertionError('You must send a request before testing it!')

        self._tests.assertEqual(self._sent_request_type, self._request_type)

        expected_request = self._request_proto(**request_data)
        self._tests.assertEqual(self._sent_request, expected_request)

        self._reset_sent_request()

    def send(self, message_type, content):
        """Replaces send method on Stream. Should not be called directly.
        """
        request = self._request_proto()
        request.ParseFromString(content)

        self._sent_request_type = message_type
        self._sent_request = request

        try:
            response_bytes = self._response.SerializeToString()
        except AttributeError:
            raise AssertionError("Preset a response before sending a request!")

        self._reset_response()
        return self._MockFuture(response_bytes)

    def _reset_sent_request(self):
        self._sent_request_type = None
        self._sent_request = None

    def _reset_response(self):
        self._response = None

    class _MockFuture(object):
        class Response(object):
            def __init__(self, content):
                # message_type must be set, but is not important
                self.message_type = 0
                self.content = content

        def __init__(self, response_content):
            self._response = self.Response(response_content)

        def result(self, timeout):
            return self._response


class BaseApiTest(AioHTTPTestCase):
    """A parent class for Rest Api test cases, providing common functionality.
    """
    async def get_application(self, loop):
        """Each child must implement this method which similar to __init__
        sets up aiohttp's async test cases.

        Additionally, within this method each child should run the methods
        `set_status_and_steam`, `build_handlers`, and `build_app` as part of
        the setup process.

        Args:
            loop (object): Provided by aiohttp for acync operations,
                will be needed in order to `build_app`.

        Returns:
            web.Application: the individual app for this test case
        """
        raise NotImplementedError('Rest Api tests need get_application method')

    def set_status_and_stream(self, req_type, req_proto, resp_proto):
        """Sets the `status` and `stream` properties for the test case.

        Args:
            req_type (int): Expected enum of the type of Message sent to stream
            req_proto (class): Protobuf of requests that will be sent to stream
            resp_proto (class): Protobuf of responses to send back from stream
        """
        self.status = resp_proto
        self.stream = MockStream(self, req_type, req_proto, resp_proto)

    @staticmethod
    def build_handlers(loop, stream):
        """Returns Rest Api route handlers modified with some a mock stream.

        Args:
            stream (object): The MockStream set to `self.stream`

        Returns:
            RouteHandler: The route handlers to handle test queries
        """
        handlers = RouteHandler(loop, stream, TEST_TIMEOUT)
        return handlers

    @staticmethod
    def build_app(loop, endpoint, handler):
        """Returns the final app for `get_application`, with routes set up
        to be test queried.

        Args:
            loop (object): The loop provided to `get_application`
            endpoint (str): The path that will be queried by this test case
            handler (function): Rest Api handler for queries to the endpoint

        Returns:
            web.Application: the individual app for this test case
        """
        app = web.Application(loop=loop)
        app.router.add_get(endpoint, handler)
        app.router.add_post(endpoint, handler)
        return app

    async def post_batches(self, batches, wait=False):
        """POSTs batches to '/batches' with an optional wait parameter
        """
        batch_bytes = BatchList(batches=batches).SerializeToString()
        query_string = '?wait' if wait else ''
        wait_val = '=' + str(wait) if type(wait) == int else ''

        return await self.client.post(
            '/batches' + query_string + wait_val,
            data=batch_bytes,
            headers={'content-type': 'application/octet-stream'})

    async def get_assert_status(self, endpoint, status):
        """GETs from endpoint, asserts an HTTP status, returns parsed response
        """
        request = await self.client.get(endpoint)
        self.assertEqual(status, request.status)
        return await request.json()

    async def get_assert_200(self, endpoint):
        """GETs from endpoint, asserts a 200 status, returns a parsed response
        """
        return await self.get_assert_status(endpoint, 200)

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
        self.assert_valid_url(link, expected_ending)

    def assert_has_valid_paging(self, js_response, pb_paging,
                                next_link=None, previous_link=None):
        """Asserts a response has a paging dict with the expected values.
        The expected values for start_index and total_count are in pb_paging.
        """
        self.assertIn('paging', js_response)
        js_paging = js_response['paging']

        self.assertIn('total_count', js_paging)
        self.assertEqual(js_paging['total_count'], pb_paging.total_resources)

        # if total resources is zero, no start index should be sent
        if not pb_paging.total_resources:
            self.assertNotIn('start_index', js_paging)
        else:
            self.assertIn('start_index', js_paging)
            self.assertEqual(js_paging['start_index'], pb_paging.start_index)

        if next_link is not None:
            self.assertIn('next', js_paging)
            self.assert_valid_url(js_paging['next'], next_link)
        else:
            self.assertNotIn('next', js_paging)

        if previous_link is not None:
            self.assertIn('previous', js_paging)
            self.assert_valid_url(js_paging['previous'], previous_link)
        else:
            self.assertNotIn('previous', js_paging)

    def assert_has_valid_error(self, response, expected_code):
        """Asserts a response has only an error dict with an expected code
        """
        self.assertIn('error', response)
        self.assertEqual(1, len(response))

        error = response['error']
        self.assertIn('code', error)
        self.assertEqual(error['code'], expected_code)
        self.assertIn('title', error)
        self.assertIsInstance(error['title'], str)
        self.assertIn('message', error)
        self.assertIsInstance(error['message'], str)

    def assert_has_valid_data_list(self, response, expected_length):
        """Asserts a response has a data list of dicts of an expected length.
        """
        self.assertIn('data', response)
        data = response['data']
        self.assertIsInstance(data, list)
        self.assert_all_instances(data, dict)
        self.assertEqual(expected_length, len(data))

    def assert_valid_url(self, url, expected_ending=''):
        """Asserts a url is valid, and ends with the expected value
        """
        self.assertIsInstance(url, str)
        self.assertTrue(url.startswith('http'))
        try:
            self.assertTrue(url.endswith(expected_ending))
        except AssertionError:
            raise AssertionError(
                'Expected "{}" to end with "{}"'.format(url, expected_ending))

    def assert_leaves_match(self, proto_leaves, json_leaves):
        """Asserts that each JSON leaf matches the original Protobuf leaves
        """
        self.assertEqual(len(proto_leaves), len(json_leaves))
        for pb_leaf, js_leaf in zip(proto_leaves, json_leaves):
            self.assertIn('address', js_leaf)
            self.assertIn('data', js_leaf)
            self.assertEqual(pb_leaf.address, js_leaf['address'])
            self.assertEqual(pb_leaf.data, b64decode(js_leaf['data']))

    def assert_statuses_match(self, proto_statuses, json_statuses):
        """Asserts that JSON statuses match the original enum statuses dict
        """
        self.assertEqual(len(proto_statuses), len(json_statuses))
        for pb_status, js_status in zip(proto_statuses, json_statuses):
            self.assertEqual(pb_status.batch_id, js_status['id'])
            pb_enum_name = client_pb2.BatchStatus.Status.Name(pb_status.status)
            self.assertEqual(pb_enum_name, js_status['status'])

    def assert_blocks_well_formed(self, blocks, *expected_ids):
        """Asserts a block dict or list of block dicts have expanded headers
        and match the expected ids. Assumes each block contains one batch and
        transaction which share its id.
        """
        if not isinstance(blocks, list):
            blocks = [blocks]

        for block, expected_id in zip(blocks, expected_ids):
            self.assertIsInstance(block, dict)
            self.assertEqual(expected_id, block['header_signature'])
            self.assertIsInstance(block['header'], dict)
            self.assertEqual(b'consensus', b64decode(block['header']['consensus']))

            batches = block['batches']
            self.assertIsInstance(batches, list)
            self.assertEqual(1, len(batches))
            self.assert_all_instances(batches, dict)
            self.assert_batches_well_formed(batches, expected_id)

    def assert_batches_well_formed(self, batches, *expected_ids):
        """Asserts a batch dict or list of batch dicts have expanded headers
        and match the expected ids. Assumes each batch contains one transaction
        which shares its id.
        """
        if not isinstance(batches, list):
            batches = [batches]

        for batch, expected_id in zip(batches, expected_ids):
            self.assertEqual(expected_id, batch['header_signature'])
            self.assertIsInstance(batch['header'], dict)
            self.assertEqual('pubkey', batch['header']['signer_pubkey'])

            txns = batch['transactions']
            self.assertIsInstance(txns, list)
            self.assertEqual(1, len(txns))
            self.assert_all_instances(txns, dict)
            self.assert_txns_well_formed(txns, expected_id)

    def assert_txns_well_formed(self, txns, *expected_ids):
        """Asserts a transaction dict or list of transactions dicts have
        expanded headers and match the expected ids.
        """

        if not isinstance(txns, list):
            txns = [txns]

        for txn, expected_id in zip(txns, expected_ids):
            self.assertEqual(expected_id, txn['header_signature'])
            self.assertEqual(b'payload', b64decode(txn['payload']))
            self.assertIsInstance(txn['header'], dict)
            self.assertEqual(expected_id, txn['header']['nonce'])


class Mocks(object):
    """A static class with methods that return lists of mock Protobuf objects.
    """
    @staticmethod
    def make_paging_controls(count=None, start_id=None, end_id=None, start_index=None):
        """Returns a PagingControls Protobuf
        """
        return PagingControls(
            count=count,
            start_id=start_id,
            end_id=end_id,
            start_index=start_index)

    @staticmethod
    def make_paging_response(start, total, next_id=None, previous_id=None):
        """Returns a PagingResponse Protobuf
        """
        return PagingResponse(
            start_index=start,
            total_resources=total,
            next_id=next_id,
            previous_id=previous_id)

    @staticmethod
    def make_sort_controls(*keys, reverse=False, compare_length=False):
        """Returns a SortControls Protobuf in a list. Use concatenation to
        combine multiple sort controls.
        """
        return [SortControls(
            keys=keys,
            reverse=reverse,
            compare_length=compare_length)]

    @staticmethod
    def make_leaves(**leaf_data):
        """Returns Leaf objects with specfied kwargs turned into
        addresses and data
        """
        return [Leaf(address=a, data=d) for a, d in leaf_data.items()]

    @classmethod
    def make_blocks(cls, *block_ids):
        """Returns Block objects with the specified ids, and each with
        one Batch with one Transaction with matching ids.
        """
        blocks = []

        for block_id in block_ids:
            batches = cls.make_batches(block_id)

            blk_header = BlockHeader(
                block_num=len(blocks),
                previous_block_id=blocks[-1].header_signature if blocks else '',
                signer_pubkey='pubkey',
                batch_ids=[b.header_signature for b in batches],
                consensus=b'consensus',
                state_root_hash='root_hash')

            block = Block(
                header=blk_header.SerializeToString(),
                header_signature=block_id,
                batches=batches)

            blocks.append(block)

        return blocks

    @classmethod
    def make_batches(cls, *batch_ids):
        """Returns Batch objects with the specified ids, and each with
        one Transaction with matching ids.
        """
        batches = []

        for batch_id in batch_ids:
            txns = cls.make_txns(batch_id)

            batch_header = BatchHeader(
                signer_pubkey='pubkey',
                transaction_ids=[t.header_signature for t in txns])

            batch = Batch(
                header=batch_header.SerializeToString(),
                header_signature=batch_id,
                transactions=txns)

            batches.append(batch)

        return batches

    @staticmethod
    def make_txns(*txn_ids):
        """Returns Transaction objects with the specified ids and a header
        nonce that matches its id.
        """
        txns = []

        for txn_id in txn_ids:
            txn_header = TransactionHeader(
                batcher_pubkey='pubkey',
                family_name='family',
                family_version='0.0',
                nonce=txn_id,
                signer_pubkey='pubkey')

            txn = Transaction(
                header=txn_header.SerializeToString(),
                header_signature=txn_id,
                payload=b'payload')

            txns.append(txn)

        return txns

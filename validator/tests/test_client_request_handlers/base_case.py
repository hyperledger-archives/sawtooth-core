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

# pylint: disable=attribute-defined-outside-init

import unittest
from sawtooth_validator.protobuf import client_list_control_pb2


class ClientHandlerTestCase(unittest.TestCase):
    """Parent for Client Request Handler tests that simplifies making requests.
    Run initialize as part of setUp, and then call make_request in each test.
    """

    def initialize(self, handler, request_proto, response_proto,
                   store=None, roots=None, tracker=None):
        self._identity = '1234567'
        self._handler = handler
        self._request_proto = request_proto
        self._store = store
        self._tracker = tracker
        self.status = response_proto
        self.roots = roots

    def make_request(self, **kwargs):
        """Serializes kwargs with the protobuf request, sends it to handler
        """
        return self._handle(self._serialize(**kwargs))

    def make_paged_request(self, **kwargs):
        """Parses out paging kwargs and adds them into a ClientPagingControls
        object, before sending it all on to `make_request`
        """
        paging_keys = ['start', 'limit']
        paging_args = {k: kwargs.pop(k) for k in paging_keys if k in kwargs}
        paging_request = client_list_control_pb2.ClientPagingControls(
            **paging_args)
        return self.make_request(paging=paging_request, **kwargs)

    def make_sort_controls(self, *keys, reverse=False):
        """Creates a ClientSortControls object and returns it in a list. Use
        concatenation to combine multiple ClientSortControls.
        """
        return [client_list_control_pb2.ClientSortControls(
            keys=keys, reverse=reverse)]

    def _serialize(self, **kwargs):
        request = self._request_proto(**kwargs)
        return request.SerializeToString()

    def _handle(self, request):
        result = self._handler.handle(self._identity, request)
        return result.message_out

    def make_bad_request(self, **kwargs):
        """Truncates the protobuf request, which will break it as long as
        the protobuf is not empty.
        """
        return self._handle(self._serialize(**kwargs)[0:-1])

    def break_genesis(self):
        """Breaks the chain head causing certain "latest" requests to fail.
        Simulates what block store would look like if genesis had not been run.
        """
        self._store.clear()

    def add_blocks(self, *base_ids):
        """Adds new blocks to a test case's block store with specified
        base_ids.
        """
        for base_id in base_ids:
            self._store.add_block(base_id)

    def assert_all_instances(self, items, cls):
        """Checks that all items in a collection are instances of a class
        """
        for item in items:
            self.assertIsInstance(item, cls)

    def assert_valid_paging(self, response, start, limit, next_id=''):
        """Checks that a response's ClientPagingResponse is set properly.
        Defaults to expecting a single page with all mock resources.
        """
        self.assertIsInstance(
            response.paging, client_list_control_pb2.ClientPagingResponse)
        self.assertEqual(response.paging.start, start)
        self.assertEqual(response.paging.limit, limit)
        self.assertEqual(response.paging.next, next_id)

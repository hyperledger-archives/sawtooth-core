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

from threading import Thread
from time import time, sleep

import sawtooth_validator.state.client_handlers as handlers
from sawtooth_validator.protobuf import client_pb2
from test_client_request_handlers.base_case import ClientHandlerTestCase
from test_client_request_handlers.mocks import make_mock_batch
from test_client_request_handlers.mocks import make_store_and_cache


class TestBatchSubmitFinisher(ClientHandlerTestCase):
    def setUp(self):
        store, cache = make_store_and_cache()

        self.initialize(
            handlers.BatchSubmitFinisher(store, cache),
            client_pb2.ClientBatchSubmitRequest,
            client_pb2.ClientBatchSubmitResponse,
            store=store)

    def test_batch_submit_without_wait(self):
        """Verifies finisher simply returns OK when not set to wait.

        Expects to find:
            - a response status of OK
            - no batch_statusus
        """
        response = self.make_request(batches=[make_mock_batch('new')])

        self.assertEqual(self.status.OK, response.status)
        self.assertFalse(response.batch_statuses)

    def test_batch_submit_bad_request(self):
        """Verifies finisher breaks properly when sent a bad request.

        Expects to find:
            - a response status of INTERNAL_ERROR
        """
        response = self.make_bad_request(batches=[make_mock_batch('new')])

        self.assertEqual(self.status.INTERNAL_ERROR, response.status)

    def test_batch_submit_with_wait(self):
        """Verifies finisher works properly when waiting for commit.

        Queries the default mock block store which will have no block with
        the id 'new' until added by a separate thread.

        Expects to find:
            - less than 8 seconds to have passed (i.e. did not wait for timeout)
            - a response status of OK
            - a status of COMMITTED at key 'b-new' in batch_statuses
        """
        start_time = time()
        def delayed_add():
            sleep(2)
            self._store.add_block('new')
        Thread(target=delayed_add).start()

        response = self.make_request(
            batches=[make_mock_batch('new')],
            wait_for_commit=True,
            timeout=10)

        self.assertGreater(8, time() - start_time)
        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(response.batch_statuses['b-new'], client_pb2.COMMITTED)


class TestBatchStatusRequests(ClientHandlerTestCase):
    def setUp(self):
        store, cache = make_store_and_cache()

        self.initialize(
            handlers.BatchStatusRequest(store, cache),
            client_pb2.ClientBatchStatusRequest,
            client_pb2.ClientBatchStatusResponse,
            store=store)

    def test_batch_status_in_store(self):
        """Verifies requests for status of a batch in the block store work.

        Queries the default mock block store with three blocks/batches:
            {header: {batch_ids: ['b-2'] ...}, header_signature: 'B-2' ...},
            {header: {batch_ids: ['b-1'] ...}, header_signature: 'B-1' ...},
            {header: {batch_ids: ['b-0'] ...}, header_signature: 'B-0' ...}

        Expects to find:
            - a response status of OK
            - a status of COMMITTED at key '0' in batch_statuses
        """
        response = self.make_request(batch_ids=['b-0'])

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(response.batch_statuses['b-0'], client_pb2.COMMITTED)

    def test_batch_status_bad_request(self):
        """Verifies bad requests for status of a batch break properly.

        Expects to find:
            - a response status of INTERNAL_ERROR
        """
        response = self.make_bad_request(batch_ids=['b-0'])

        self.assertEqual(self.status.INTERNAL_ERROR, response.status)

    def test_batch_status_when_empty(self):
        """Verifies requests for batch statuses with no ids break properly.

        Expects to find:
            - a response status of NO_RESOURCE
            - that batch_statuses is empty
        """
        response = self.make_request(batch_ids=[])

        self.assertEqual(self.status.NO_RESOURCE, response.status)
        self.assertFalse(response.batch_statuses)

    def test_batch_status_in_cache(self):
        """Verifies requests for status of a batch in the batch cache work.

        Queries the default mock batch cache with two batches:
            {header_signature: 'b-3' ...},
            {header_signature: 'b-2' ...}

        Expects to find:
            - a response status of OK
            - a status of PENDING at key 'b-3' in batch_statuses
        """
        response = self.make_request(batch_ids=['b-3'])

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(response.batch_statuses['b-3'], client_pb2.PENDING)

    def test_batch_status_when_missing(self):
        """Verifies requests for status of a batch that is not found work.

        Expects to find:
            - a response status of OK
            - a status of UNKNOWN at key 'z' in batch_statuses
        """
        response = self.make_request(batch_ids=['z'])

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(response.batch_statuses['z'], client_pb2.UNKNOWN)

    def test_batch_status_in_store_and_cache(self):
        """Verifies requests for status of batch in both store and cache work.

        Queries the default mock block store with three blocks/batches:
            {header: {batch_ids: ['b-2'] ...}, header_signature: 'B-2' ...},
            {header: {batch_ids: ['b-1'] ...}, header_signature: 'B-1' ...},
            {header: {batch_ids: ['b-0'] ...}, header_signature: 'B-0' ...}

        ...and the default mock batch cache with two batches:
            {header_signature: 'B-3' ...},
            {header_signature: 'B-2' ...}

        Expects to find:
            - a response status of OK
            - a status of COMMITTED at key '2' in batch_statuses
        """
        response = self.make_request(batch_ids=['b-2'])

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(response.batch_statuses['b-2'], client_pb2.COMMITTED)

    def test_batch_status_for_many_batches(self):
        """Verifies requests for status of many batches work properly.

        Queries the default mock block store with three blocks/batches:
            {header: {batch_ids: ['b-2'] ...}, header_signature: 'B-2' ...},
            {header: {batch_ids: ['b-1'] ...}, header_signature: 'B-1' ...},
            {header: {batch_ids: ['b-0'] ...}, header_signature: 'B-0' ...}

        ...and the default mock batch cache with two batches:
            {header_signature: 'B-3' ...},
            {header_signature: 'B-2' ...}

        Expects to find:
            - a response status of OK
            - a status of COMMITTED at key '1' in batch_statuses
            - a status of COMMITTED at key '2' in batch_statuses
            - a status of PENDING at key '3' in batch_statuses
            - a status of UNKNOWN at key 'y' in batch_statuses
        """
        response = self.make_request(batch_ids=['b-1', 'b-2', 'b-3', 'y'])

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(response.batch_statuses['b-1'], client_pb2.COMMITTED)
        self.assertEqual(response.batch_statuses['b-2'], client_pb2.COMMITTED)
        self.assertEqual(response.batch_statuses['b-3'], client_pb2.PENDING)
        self.assertEqual(response.batch_statuses['y'], client_pb2.UNKNOWN)

    def test_batch_status_with_wait(self):
        """Verifies requests for status that wait for commit work properly.

        Queries the default mock block store which will have no block with
        the id 'awaited' until added by a separate thread.

        Expects to find:
            - less than 8 seconds to have passed (i.e. did not wait for timeout)
            - a response status of OK
            - a status of COMMITTED at key 'b-new' in batch_statuses
        """
        start_time = time()
        def delayed_add():
            sleep(2)
            self._store.add_block('new')
        Thread(target=delayed_add).start()

        response = self.make_request(
            batch_ids=['b-new'],
            wait_for_commit=True,
            timeout=10)

        self.assertGreater(8, time() - start_time)
        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(response.batch_statuses['b-new'], client_pb2.COMMITTED)

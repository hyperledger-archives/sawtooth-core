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
from sawtooth_validator.protobuf import client_batch_submit_pb2
from sawtooth_validator.protobuf.client_batch_submit_pb2 \
    import ClientBatchStatus
from test_client_request_handlers.base_case import ClientHandlerTestCase
from test_client_request_handlers.mocks import make_mock_batch
from test_client_request_handlers.mocks import make_store_and_tracker


A_0 = 'a' * 127 + '0'
A_1 = 'a' * 127 + '1'
A_2 = 'a' * 127 + '2'


class TestBatchSubmitPreprocessor(ClientHandlerTestCase):
    def test_batch_submit_bad_request(self):
        """Verifies preprocessor breaks properly when sent a bad request.

        Expects to find:
            - a response status of INTERNAL_ERROR
        """

        request = client_batch_submit_pb2.ClientBatchSubmitRequest(
            batches=[make_mock_batch('new')]
        ).SerializeToString()[0:-1]

        result = handlers.client_batch_submit_request_preprocessor(request)

        self.assertEqual(
            client_batch_submit_pb2.ClientBatchSubmitResponse.INTERNAL_ERROR,
            result.message_out.status)


class TestBatchSubmitFinisher(ClientHandlerTestCase):
    def setUp(self):
        store, tracker = make_store_and_tracker()

        self.initialize(
            handlers.BatchSubmitFinisher(tracker),
            client_batch_submit_pb2.ClientBatchSubmitRequest,
            client_batch_submit_pb2.ClientBatchSubmitResponse,
            store=store,
            tracker=tracker)

    def test_batch_submit_without_wait(self):
        """Verifies finisher simply returns OK when not set to wait.

        Expects to find:
            - a response status of OK
            - no batch_statuses
        """
        response = self._handle(
            client_batch_submit_pb2.ClientBatchSubmitRequest(
                batches=[make_mock_batch('new')]))

        self.assertEqual(self.status.OK, response.status)


class TestBatchStatusRequests(ClientHandlerTestCase):
    def setUp(self):
        store, tracker = make_store_and_tracker()

        self.initialize(
            handlers.BatchStatusRequest(tracker),
            client_batch_submit_pb2.ClientBatchStatusRequest,
            client_batch_submit_pb2.ClientBatchStatusResponse,
            store=store,
            tracker=tracker)

    def test_batch_statuses_in_store(self):
        """Verifies requests for status of a batch in the block store work.

        Queries the default mock block store with three blocks/batches:
            {
                header: {batch_ids: ['aaa...2'] ...},
                 header_signature: 'bbb...2' ...}
            ,
            {
                header: {batch_ids: ['aaa...1'] ...},
                 header_signature: 'bbb...1' ...}
            ,
            {
                header: {batch_ids: ['aaa...0'] ...},
                 header_signature: 'bbb...0' ...
            }

        Expects to find:
            - a response status of OK
            - a status of COMMITTED at key '0' in batch_statuses
        """
        response = self.make_request(batch_ids=[A_0])

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(response.batch_statuses[0].batch_id, A_0)
        self.assertEqual(response.batch_statuses[0].status,
                         ClientBatchStatus.COMMITTED)

    def test_batch_statuses_bad_request(self):
        """Verifies bad requests for status of a batch break properly.

        Expects to find:
            - a response status of INTERNAL_ERROR
        """
        response = self.make_bad_request(batch_ids=[A_0])

        self.assertEqual(self.status.INTERNAL_ERROR, response.status)

    def test_batch_statuses_when_empty(self):
        """Verifies requests for batch statuses with no ids break properly.

        Expects to find:
            - a response status of NO_RESOURCE
            - that batch_statuses is empty
        """
        response = self.make_request(batch_ids=[])

        self.assertEqual(self.status.NO_RESOURCE, response.status)
        self.assertFalse(response.batch_statuses)

    def test_invalid_batch_statuses(self):
        """Verifies batch status requests marked INVALID by the tracker work.

        Queries the default mock batch tracker with invalid batch ids of:
            - 'aaa...f'

        Expects to find:
            - a response status of OK
            - a status of INVALID at key 'aaa...f' in batch_statuses
            - an invalid_transaction with
                * an 'id' of 'ccc...f'
                * a message of 'error message'
                * extended_data of b'error data'
        """
        response = self.make_request(batch_ids=['a' * 127 + 'f'])

        self.assertEqual(self.status.OK, response.status)
        status = response.batch_statuses[0]
        self.assertEqual(status.batch_id, 'a' * 127 + 'f')
        self.assertEqual(status.status, ClientBatchStatus.INVALID)
        self.assertEqual(1, len(status.invalid_transactions))

        invalid_txn = status.invalid_transactions[0]
        self.assertEqual(invalid_txn.transaction_id, 'c' * 127 + 'f')
        self.assertEqual(invalid_txn.message, 'error message')
        self.assertEqual(invalid_txn.extended_data, b'error data')

    def test_pending_batch_statuses(self):
        """Verifies batch status requests marked PENDING by the tracker work.

        Queries the default mock batch tracker with pending batch ids of:
            - 'aaa...d'

        Expects to find:
            - a response status of OK
            - a status of PENDING at key 'aaa...d' in batch_statuses
        """
        response = self.make_request(batch_ids=['a' * 127 + 'd'])

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(response.batch_statuses[0].batch_id, 'a' * 127 + 'd')
        self.assertEqual(response.batch_statuses[0].status,
                         ClientBatchStatus.PENDING)

    def test_batch_statuses_when_missing(self):
        """Verifies requests for status of a batch that is not found work.

        Expects to find:
            - a response status of OK
            - a status of UNKNOWN at key 'fff...' in batch_statuses
        """
        response = self.make_request(batch_ids=['f' * 128])

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(response.batch_statuses[0].batch_id, 'f' * 128)
        self.assertEqual(response.batch_statuses[0].status,
                         ClientBatchStatus.UNKNOWN)

    def test_batch_statuses_when_invalid(self):
        """Verifies requests for status of a batch break with invalid ids.

        Expects to find:
            - a status of INVALID_ID
            - that the batch_statuses are missing
        """
        response = self.make_request(batch_ids=['not', 'valid'])

        self.assertEqual(self.status.INVALID_ID, response.status)
        self.assertFalse(response.batch_statuses)

    def test_batch_statuses_for_many_batches(self):
        """Verifies requests for status of many batches work properly.

        Queries the default mock block store with three blocks/batches:
            {
                header: {batch_ids: ['aaa...2'] ...},
                 header_signature: 'bbb...2' ...}
            ,
            {
                header: {batch_ids: ['aaa...1'] ...},
                 header_signature: 'bbb...1' ...}
            ,
            {
                header: {batch_ids: ['aaa...0'] ...},
                 header_signature: 'bbb...0' ...
            }

        ...and the default mock batch tracker with pending batch ids of:
            - 'aaa...d'

        Expects to find:
            - a response status of OK
            - a status of COMMITTED at key 'aaa...1' in batch_statuses
            - a status of COMMITTED at key 'aaa...2' in batch_statuses
            - a status of PENDING at key 'aaa...d' in batch_statuses
            - a status of UNKNOWN at key 'fff...f' in batch_statuses
        """
        response = self.make_request(
            batch_ids=[A_1, A_2, 'a' * 127 + 'd', 'f' * 128])

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(response.batch_statuses[0].status,
                         ClientBatchStatus.COMMITTED)
        self.assertEqual(response.batch_statuses[1].status,
                         ClientBatchStatus.COMMITTED)
        self.assertEqual(response.batch_statuses[2].status,
                         ClientBatchStatus.PENDING)
        self.assertEqual(response.batch_statuses[3].status,
                         ClientBatchStatus.UNKNOWN)

    def test_batch_statuses_with_wait(self):
        """Verifies requests for status that wait for commit work properly.

        Queries the default mock block store which will have no block with
        the id 'aaa...e' until added by a separate thread.

        Expects to find:
            - less than 8 seconds to have passed (i.e. did not wait for
            timeout)
            - a response status of OK
            - a status of COMMITTED at key 'aaa...e' in batch_statuses
        """
        self._tracker.notify_batch_pending(make_mock_batch('e'))
        start_time = time()

        def delayed_add():
            sleep(1)
            self._store.add_block('e')
            self._tracker.chain_update(None, [])

        Thread(target=delayed_add).start()

        response = self.make_request(
            batch_ids=['a' * 127 + 'e'],
            wait=True,
            timeout=10)

        self.assertGreater(8, time() - start_time)
        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(response.batch_statuses[0].status,
                         ClientBatchStatus.COMMITTED)

    def test_batch_statuses_with_committed_wait(self):
        """Verifies requests for status that wait for commit work properly,
        when the batch is already committed.

        Expects to find:
            - less than 8 seconds to have passed (i.e. did not wait for
            timeout)
            - a response status of OK
            - a status of COMMITTED at key 'aaa...0' in batch_statuses
        """
        start_time = time()
        response = self.make_request(
            batch_ids=[A_0],
            wait=True,
            timeout=10)

        self.assertGreater(8, time() - start_time)
        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(response.batch_statuses[0].status,
                         ClientBatchStatus.COMMITTED)

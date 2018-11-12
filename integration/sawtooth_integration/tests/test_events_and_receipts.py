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

import unittest
import logging
import json
import urllib.request
import urllib.error

import cbor

from sawtooth_integration.tests.integration_tools import wait_for_rest_apis
from sawtooth_intkey.intkey_message_factory import IntkeyMessageFactory
from sawtooth_intkey.processor.handler import INTKEY_ADDRESS_PREFIX
from sawtooth_intkey.processor.handler import make_intkey_address
from sawtooth_sdk.messaging.stream import Stream

from sawtooth_sdk.protobuf import events_pb2
from sawtooth_sdk.protobuf import client_event_pb2
from sawtooth_sdk.protobuf import validator_pb2
from sawtooth_sdk.protobuf import batch_pb2
from sawtooth_sdk.protobuf import client_receipt_pb2
from sawtooth_sdk.protobuf import transaction_receipt_pb2

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)
WAIT = 300
NULL_BLOCK_IDENTIFIER = "0000000000000000"


class TestEventsAndReceipts(unittest.TestCase):
    def test_subscribe_and_unsubscribe(self):
        """Tests that a client can subscribe and unsubscribe from events."""
        response = self._subscribe()
        self.assert_subscribe_response(response)

        response = self._unsubscribe()
        self.assert_unsubscribe_response(response)

    def test_subscribe_and_unsubscribe_with_catch_up(self):
        """Tests that a client can subscribe and unsubscribe from events."""
        response = self._subscribe(
            last_known_block_ids=[NULL_BLOCK_IDENTIFIER])
        self.assert_subscribe_response(response)

        # Ensure that it receives the genesis block
        msg = self.stream.receive().result()
        self.assertEqual(
            msg.message_type,
            validator_pb2.Message.CLIENT_EVENTS)
        event_list = events_pb2.EventList()
        event_list.ParseFromString(msg.content)
        events = event_list.events
        self.assertEqual(len(events), 2)
        self.assert_block_commit_event(events[0], 0)
        self.assert_state_event(events[1], '000000')

        response = self._unsubscribe()
        self.assert_unsubscribe_response(response)

    def test_block_commit_event_received(self):
        """Tests that block commit events are properly received on block
        boundaries."""
        self._subscribe()

        for i in range(1, 5):
            self.batch_submitter.submit_next_batch()
            msg = self.stream.receive().result()
            self.assertEqual(
                msg.message_type,
                validator_pb2.Message.CLIENT_EVENTS)
            event_list = events_pb2.EventList()
            event_list.ParseFromString(msg.content)
            events = event_list.events
            self.assertEqual(len(events), 2)
            self.assert_block_commit_event(events[0], i)
            self.assert_state_event(events[1], INTKEY_ADDRESS_PREFIX)

        self._unsubscribe()

    def test_get_events(self):
        """Tests that block commit events are properly received on block
        boundaries."""
        self._subscribe()

        self.batch_submitter.submit_next_batch()
        msg = self.stream.receive().result()
        self._unsubscribe()

        event_list = events_pb2.EventList()
        event_list.ParseFromString(msg.content)
        events = event_list.events
        block_commit_event = events[0]
        block_id = list(filter(
            lambda attr: attr.key == "block_id",
            block_commit_event.attributes))[0].value
        block_num = list(filter(
            lambda attr: attr.key == "block_num",
            block_commit_event.attributes))[0].value

        response = self._get_events(
            block_id,
            [events_pb2.EventSubscription(event_type="sawtooth/block-commit")])
        events = self.assert_events_get_response(response)
        self.assert_block_commit_event(events[0], block_num)

    def test_catchup(self):
        """Tests that a subscriber correctly receives catchup events."""
        self._subscribe()

        blocks = []
        for i in range(4):
            self.batch_submitter.submit_next_batch()
            msg = self.stream.receive().result()
            event_list = events_pb2.EventList()
            event_list.ParseFromString(msg.content)
            events = event_list.events
            block_commit_event = events[0]
            block_id = list(filter(
                lambda attr: attr.key == "block_id",
                block_commit_event.attributes))[0].value
            block_num = list(filter(
                lambda attr: attr.key == "block_num",
                block_commit_event.attributes))[0].value
            blocks.append((block_num, block_id))

        self._unsubscribe()

        self.assert_subscribe_response(
            self._subscribe(last_known_block_ids=[blocks[0][1]]))
        LOGGER.warning("Waiting for catchup events")
        for i in range(3):
            msg = self.stream.receive().result()
            LOGGER.warning("Got catchup events: ")
            event_list = events_pb2.EventList()
            event_list.ParseFromString(msg.content)
            events = event_list.events
            self.assertEqual(len(events), 2)
            block_commit_event = events[0]
            block_id = list(filter(
                lambda attr: attr.key == "block_id",
                block_commit_event.attributes))[0].value
            block_num = list(filter(
                lambda attr: attr.key == "block_num",
                block_commit_event.attributes))[0].value
            self.assertEqual((block_num, block_id), blocks[i + 1])

        self._unsubscribe()

    def test_receipt_stored(self):
        """Tests that receipts are stored successfully when a block is
        committed."""
        self._subscribe()
        n = self.batch_submitter.submit_next_batch()
        response = self._get_receipt(n)
        receipts = self.assert_receipt_get_response(response)
        state_change = receipts[0].state_changes[0]
        self.assertEqual(
            state_change.type,
            transaction_receipt_pb2.StateChange.SET)
        self.assertEqual(
            state_change.value,
            cbor.dumps({str(n): 0}))
        self.assertEqual(
            state_change.address,
            make_intkey_address(str(n)))
        self._unsubscribe()

    @classmethod
    def setUpClass(cls):
        wait_for_rest_apis(['rest-api:8008'])
        cls.batch_submitter = BatchSubmitter(WAIT)

    def setUp(self):
        self.url = "tcp://validator:4004"
        self.stream = Stream(self.url)

    def tearDown(self):
        if self.stream is not None:
            self.stream.close()

    def _get_receipt(self, num):
        txn_id = \
            self.batch_submitter.batches[num].transactions[0].header_signature
        request = client_receipt_pb2.ClientReceiptGetRequest(
            transaction_ids=[txn_id])
        response = self.stream.send(
            validator_pb2.Message.CLIENT_RECEIPT_GET_REQUEST,
            request.SerializeToString()).result()
        return response

    def _get_events(self, block_id, subscriptions):
        request = client_event_pb2.ClientEventsGetRequest(
            block_ids=[block_id],
            subscriptions=subscriptions)
        response = self.stream.send(
            validator_pb2.Message.CLIENT_EVENTS_GET_REQUEST,
            request.SerializeToString()).result()
        return response

    def _subscribe(self, subscriptions=None, last_known_block_ids=None):
        if subscriptions is None:
            subscriptions = [
                events_pb2.EventSubscription(
                    event_type="sawtooth/block-commit"),
                # Subscribe to the settings state events, to test genesis
                # catch-up.
                events_pb2.EventSubscription(
                    event_type="sawtooth/state-delta",
                    filters=[events_pb2.EventFilter(
                        key='address',
                        match_string='000000.*',
                        filter_type=events_pb2.EventFilter.REGEX_ANY)]),
                # Subscribe to the intkey state events, to test additional
                # events.
                events_pb2.EventSubscription(
                    event_type="sawtooth/state-delta",
                    filters=[events_pb2.EventFilter(
                        key='address',
                        match_string='{}.*'.format(INTKEY_ADDRESS_PREFIX),
                        filter_type=events_pb2.EventFilter.REGEX_ANY)]),
            ]
        if last_known_block_ids is None:
            last_known_block_ids = []
        request = client_event_pb2.ClientEventsSubscribeRequest(
            subscriptions=subscriptions,
            last_known_block_ids=last_known_block_ids)
        response = self.stream.send(
            validator_pb2.Message.CLIENT_EVENTS_SUBSCRIBE_REQUEST,
            request.SerializeToString()).result()
        return response

    def _unsubscribe(self):
        request = client_event_pb2.ClientEventsUnsubscribeRequest()
        response = self.stream.send(
            validator_pb2.Message.CLIENT_EVENTS_UNSUBSCRIBE_REQUEST,
            request.SerializeToString()).result()
        return response

    def assert_block_commit_event(self, event, block_num):
        self.assertEqual(event.event_type, "sawtooth/block-commit")
        self.assertTrue(
            all([
                any(attribute.key == "block_id"
                    for attribute in event.attributes),
                any(attribute.key == "block_num"
                    for attribute in event.attributes),
                any(attribute.key == "previous_block_id"
                    for attribute in event.attributes),
                any(attribute.key == "state_root_hash"
                    for attribute in event.attributes),
            ]))
        for attribute in event.attributes:
            if attribute.key == "block_num":
                self.assertEqual(attribute.value, str(block_num))

    def assert_receipt_get_response(self, msg):
        self.assertEqual(
            msg.message_type,
            validator_pb2.Message.CLIENT_RECEIPT_GET_RESPONSE)

        receipt_response = client_receipt_pb2.ClientReceiptGetResponse()
        receipt_response.ParseFromString(msg.content)

        self.assertEqual(
            receipt_response.status,
            client_receipt_pb2.ClientReceiptGetResponse.OK)

        return receipt_response.receipts

    def assert_state_event(self, event, address_prefix):
        self.assertEqual(event.event_type, "sawtooth/state-delta")
        state_change_list = transaction_receipt_pb2.StateChangeList()
        state_change_list.ParseFromString(event.data)
        for change in state_change_list.state_changes:
            self.assertTrue(change.address.startswith(address_prefix))

    def assert_events_get_response(self, msg):
        self.assertEqual(
            msg.message_type,
            validator_pb2.Message.CLIENT_EVENTS_GET_RESPONSE)

        events_response = client_event_pb2.ClientEventsGetResponse()
        events_response.ParseFromString(msg.content)

        self.assertEqual(
            events_response.status,
            client_event_pb2.ClientEventsGetResponse.OK)

        return events_response.events

    def assert_subscribe_response(self, msg):
        self.assertEqual(
            msg.message_type,
            validator_pb2.Message.CLIENT_EVENTS_SUBSCRIBE_RESPONSE)

        response = client_event_pb2.ClientEventsSubscribeResponse()
        response.ParseFromString(msg.content)

        self.assertEqual(
            response.status,
            client_event_pb2.ClientEventsSubscribeResponse.OK)

    def assert_unsubscribe_response(self, msg):
        self.assertEqual(
            msg.message_type,
            validator_pb2.Message.CLIENT_EVENTS_UNSUBSCRIBE_RESPONSE)

        response = client_event_pb2.ClientEventsUnsubscribeResponse()

        response.ParseFromString(msg.content)

        self.assertEqual(
            response.status,
            client_event_pb2.ClientEventsUnsubscribeResponse.OK)


class BatchSubmitter:
    def __init__(self, timeout):
        self.batches = []
        self.imf = IntkeyMessageFactory()
        self.timeout = timeout

    def _post_batch(self, batch):
        headers = {'Content-Type': 'application/octet-stream'}
        response = self._query_rest_api(
            '/batches',
            data=batch,
            headers=headers,
            expected_code=202)

        return self._submit_request('{}&wait={}'.format(
            response['link'], self.timeout))

    def _query_rest_api(self, suffix='', data=None, headers=None,
                        expected_code=200):
        if headers is None:
            headers = {}
        url = 'http://rest-api:8008' + suffix
        return self._submit_request(urllib.request.Request(url, data, headers),
                                    expected_code=expected_code)

    def _submit_request(self, request, expected_code=200):
        conn = urllib.request.urlopen(request)
        assert expected_code == conn.getcode()

        response = conn.read().decode('utf-8')
        return json.loads(response)

    def make_batch(self, num):
        return self.imf.create_batch([('set', str(num), 0)])

    def submit_next_batch(self):
        batch_list_bytes = self.make_batch(len(self.batches))
        batch_list = batch_pb2.BatchList()
        batch_list.ParseFromString(batch_list_bytes)
        self.batches.append(batch_list.batches[0])
        self._post_batch(batch_list_bytes)
        return len(self.batches) - 1

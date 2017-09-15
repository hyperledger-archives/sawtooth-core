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
import base64
import sys

import cbor

from sawtooth_intkey.intkey_message_factory import IntkeyMessageFactory
from sawtooth_intkey.processor.handler import make_intkey_address
from sawtooth_sdk.messaging.stream import Stream

from sawtooth_validator.protobuf import events_pb2
from sawtooth_validator.protobuf import validator_pb2
from sawtooth_validator.protobuf import batch_pb2
from sawtooth_validator.protobuf import txn_receipt_pb2
from sawtooth_validator.protobuf import state_delta_pb2

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)
WAIT = 300


class TestEventsAndReceipts(unittest.TestCase):
    def test_subscribe_and_unsubscribe(self):
        """Tests that a client can subscribe and unsubscribe from events."""
        response = self._subscribe()
        self.assert_subscribe_response(response)

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
            self.assertEqual(len(events), 1)
            self.assert_block_commit_event(events[0], i)

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
            state_delta_pb2.StateChange.SET)
        self.assertEqual(
            state_change.value,
            cbor.dumps({str(n): 0}))
        self.assertEqual(
            state_change.address,
            make_intkey_address(str(n)))
        self._unsubscribe()

    @classmethod
    def setUpClass(cls):
        cls.batch_submitter = BatchSubmitter(WAIT)

    def setUp(self):
        self.url = "tcp://validator:4004"
        self.stream = Stream(self.url)

    def tearDown(self):
        if self.stream is not None:
            self.stream.close()

    def _get_receipt(self, n):
        txn_id = \
            self.batch_submitter.batches[n].transactions[0].header_signature
        request = txn_receipt_pb2.ClientReceiptGetRequest(
            transaction_ids=[txn_id])
        response = self.stream.send(
            validator_pb2.Message.CLIENT_RECEIPT_GET_REQUEST,
            request.SerializeToString()).result()
        return response

    def _subscribe(self, subscriptions=None):
        if subscriptions is None:
            subscriptions = [
                events_pb2.EventSubscription(event_type="block_commit"),
            ]
        request = events_pb2.ClientEventsSubscribeRequest(
            subscriptions=subscriptions)
        response = self.stream.send(
            validator_pb2.Message.CLIENT_EVENTS_SUBSCRIBE_REQUEST,
            request.SerializeToString()).result()
        return response

    def _unsubscribe(self):
        request = events_pb2.ClientEventsUnsubscribeRequest()
        response = self.stream.send(
            validator_pb2.Message.CLIENT_EVENTS_UNSUBSCRIBE_REQUEST,
            request.SerializeToString()).result()
        return response

    def assert_block_commit_event(self, event, block_num):
        self.assertEqual(event.event_type, "block_commit")
        self.assertTrue(all([
            any(attribute.key == "block_id" for attribute in event.attributes),
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

        receipt_response = txn_receipt_pb2.ClientReceiptGetResponse()
        receipt_response.ParseFromString(msg.content)

        self.assertEqual(
            receipt_response.status,
            txn_receipt_pb2.ClientReceiptGetResponse.OK)

        return receipt_response.receipts

    def assert_subscribe_response(self, msg):
        self.assertEqual(
            msg.message_type,
            validator_pb2.Message.CLIENT_EVENTS_SUBSCRIBE_RESPONSE)

        subscription_response = events_pb2.ClientEventsSubscribeResponse()
        subscription_response.ParseFromString(msg.content)

        self.assertEqual(
            subscription_response.status,
            events_pb2.ClientEventsSubscribeResponse.OK)

    def assert_unsubscribe_response(self, msg):
        self.assertEqual(
            msg.message_type,
            validator_pb2.Message.CLIENT_EVENTS_UNSUBSCRIBE_RESPONSE)

        subscription_response = events_pb2.ClientEventsUnsubscribeResponse()
        subscription_response.ParseFromString(msg.content)

        self.assertEqual(
            subscription_response.status,
            events_pb2.ClientEventsUnsubscribeResponse.OK)

class BatchSubmitter:
    def __init__(self, timeout):
        self.batches = []
        self.imf = IntkeyMessageFactory()
        self.timeout = timeout

    def _post_batch(self, batch):
        headers = {'Content-Type': 'application/octet-stream'}
        response = self._query_rest_api(
            '/batches?wait={}'.format(self.timeout),
            data=batch,
            headers=headers)
        return response

    def _query_rest_api(self, suffix='', data=None, headers={}):
        url = 'http://rest-api:8080' + suffix
        request = urllib.request.Request(url, data, headers)
        response = urllib.request.urlopen(request).read().decode('utf-8')
        return json.loads(response)

    def make_batch(self, n):
        return self.imf.create_batch([('set', str(n), 0)])

    def submit_next_batch(self):
        batch_list_bytes = self.make_batch(len(self.batches))
        batch_list = batch_pb2.BatchList()
        batch_list.ParseFromString(batch_list_bytes)
        self.batches.append(batch_list.batches[0])
        self._post_batch(batch_list_bytes)
        return len(self.batches) - 1

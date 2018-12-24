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

# pylint: disable=protected-access

import unittest
from unittest.mock import Mock
from unittest.mock import MagicMock
from uuid import uuid4

from sawtooth_validator.database.dict_database import DictDatabase
from sawtooth_validator.journal.block_store import BlockStore
from sawtooth_validator.journal.block_wrapper import BlockWrapper
from sawtooth_validator.journal.event_extractors \
    import BlockEventExtractor
from sawtooth_validator.journal.receipt_store import TransactionReceiptStore
from sawtooth_validator.networking.dispatch import HandlerStatus

from sawtooth_validator.server.events.broadcaster import EventBroadcaster
from sawtooth_validator.server.events.handlers \
    import ClientEventsGetRequestHandler
from sawtooth_validator.server.events.handlers \
    import ClientEventsSubscribeValidationHandler
from sawtooth_validator.server.events.handlers \
    import ClientEventsSubscribeHandler
from sawtooth_validator.server.events.handlers \
    import ClientEventsUnsubscribeHandler

from sawtooth_validator.server.events.subscription import EventSubscription
from sawtooth_validator.server.events.subscription import EventFilterFactory

from sawtooth_validator.execution.tp_state_handlers import TpEventAddHandler

from sawtooth_validator.protobuf import events_pb2
from sawtooth_validator.protobuf import client_event_pb2
from sawtooth_validator.protobuf import block_pb2
from sawtooth_validator.protobuf import state_context_pb2
from sawtooth_validator.protobuf import transaction_receipt_pb2
from sawtooth_validator.protobuf import validator_pb2

from sawtooth_signing import create_context
from sawtooth_signing import CryptoFactory

from test_scheduler.yaml_scheduler_tester import create_batch
from test_scheduler.yaml_scheduler_tester import create_transaction


def create_block(block_num=85,
                 previous_block_id="0000000000000000",
                 block_id="abcdef1234567890",
                 batches=None):
    if batches is None:
        batches = []
    block_header = block_pb2.BlockHeader(
        block_num=block_num,
        state_root_hash="0987654321fedcba",
        previous_block_id=previous_block_id)
    block = BlockWrapper(
        block_pb2.Block(
            header_signature=block_id,
            header=block_header.SerializeToString(),
            batches=batches))
    return block


def create_chain(num=10):
    context = create_context('secp256k1')
    private_key = context.new_random_private_key()
    crypto_factory = CryptoFactory(context)
    signer = crypto_factory.new_signer(private_key)

    counter = 1
    previous_block_id = "0000000000000000"
    blocks = []
    while counter <= num:
        current_block_id = uuid4().hex
        txns = [
            t[0]
            for t in [
                create_transaction(
                    payload=uuid4().hex.encode(), signer=signer)
                for _ in range(20)
            ]
        ]

        txn_ids = [t.header_signature for t in txns]
        batch = create_batch(
            transactions=txns,
            signer=signer)

        blk_w = create_block(
            counter,
            previous_block_id,
            current_block_id,
            batches=[batch])
        blocks.append((current_block_id, blk_w, txn_ids))

        counter += 1
        previous_block_id = current_block_id

    return blocks


def create_receipt(txn_id, key_values):
    events = []
    for key, value in key_values:
        event = events_pb2.Event()
        event.event_type = "sawtooth/block-commit"
        attribute = event.attributes.add()
        attribute.key = key
        attribute.value = value
        events.append(event)

    receipt = transaction_receipt_pb2.TransactionReceipt(transaction_id=txn_id)
    receipt.events.extend(events)
    return receipt


def create_block_commit_subscription():
    return EventSubscription(event_type="sawtooth/block-commit")


FILTER_FACTORY = EventFilterFactory()


class EventSubscriptionTest(unittest.TestCase):
    def test_filter(self):
        """Test that a regex filter matches properly against an event."""
        self.assertIn(
            events_pb2.Event(attributes=[
                events_pb2.Event.Attribute(
                    key="address", value="000000" + "f" * 64)]),
            FILTER_FACTORY.create(
                key="address", match_string="000000.*",
                filter_type=events_pb2.EventFilter.REGEX_ANY))

        self.assertIn(
            events_pb2.Event(attributes=[
                events_pb2.Event.Attribute(key="abc", value="123")]),
            FILTER_FACTORY.create(key="abc", match_string="123"))

    def test_subscription(self):
        """Test that an event correctly matches against a subscription."""
        self.assertIn(
            events_pb2.Event(
                event_type="test", attributes=[
                    events_pb2.Event.Attribute(
                        key="test", value="test")]),
            EventSubscription(
                event_type="test", filters=[
                    FILTER_FACTORY.create(
                        key="test", match_string="test")]))


class ClientEventsSubscribeValidationHandlerTest(unittest.TestCase):
    def test_subscribe(self):
        """Test that a subscriber is successfully validated and added to the
        event broadcaster.
        """

        mock_event_broadcaster = Mock()
        mock_event_broadcaster.get_latest_known_block_id.return_value = \
            "0" * 128
        handler = \
            ClientEventsSubscribeValidationHandler(mock_event_broadcaster)
        request = client_event_pb2.ClientEventsSubscribeRequest(
            subscriptions=[
                events_pb2.EventSubscription(
                    event_type="test_event",
                    filters=[
                        events_pb2.EventFilter(
                            key="test",
                            match_string="test",
                            filter_type=events_pb2.EventFilter.SIMPLE_ANY)
                    ],
                )
            ],
            last_known_block_ids=["0" * 128]).SerializeToString()

        response = handler.handle("test_conn_id", request)

        mock_event_broadcaster.add_subscriber.assert_called_with(
            "test_conn_id",
            [EventSubscription(
                event_type="test_event",
                filters=[
                    FILTER_FACTORY.create(key="test", match_string="test")])],
            "0" * 128)
        self.assertEqual(HandlerStatus.RETURN_AND_PASS, response.status)
        self.assertEqual(client_event_pb2.ClientEventsSubscribeResponse.OK,
                         response.message_out.status)

    def test_subscribe_bad_filter(self):
        """Tests that the handler will respond with an INVALID_FILTER
        when a subscriber provides an invalid filter.
        """
        mock_event_broadcaster = Mock()
        handler = \
            ClientEventsSubscribeValidationHandler(mock_event_broadcaster)
        request = client_event_pb2.ClientEventsSubscribeRequest(
            subscriptions=[
                events_pb2.EventSubscription(
                    event_type="test_event",
                    filters=[
                        events_pb2.EventFilter(
                            key="test",
                            match_string="???",
                            filter_type=events_pb2.EventFilter.REGEX_ANY)
                    ],
                )
            ],
            last_known_block_ids=["0" * 128]).SerializeToString()

        response = handler.handle("test_conn_id", request)

        mock_event_broadcaster.add_subscriber.assert_not_called()
        self.assertEqual(HandlerStatus.RETURN, response.status)
        self.assertEqual(
            client_event_pb2.ClientEventsSubscribeResponse.INVALID_FILTER,
            response.message_out.status)


class ClientEventsSubscribeHandlersTest(unittest.TestCase):
    def test_subscribe(self):
        """Tests that the handler turns on the subscriber."""
        mock_event_broadcaster = Mock()
        handler = ClientEventsSubscribeHandler(mock_event_broadcaster)
        request = client_event_pb2.ClientEventsSubscribeRequest()

        response = handler.handle("test_conn_id", request)

        mock_event_broadcaster.enable_subscriber.assert_called_with(
            "test_conn_id")
        self.assertEqual(HandlerStatus.PASS, response.status)


class ClientEventsUnsubscribeHandlerTest(unittest.TestCase):
    def test_unsubscribe(self):
        """Test that a handler will unregister a subscriber via a requestor's
        connection id.
        """
        mock_event_broadcaster = Mock()
        handler = ClientEventsUnsubscribeHandler(mock_event_broadcaster)

        request = (
            client_event_pb2.ClientEventsUnsubscribeRequest()
            .SerializeToString()
        )

        response = handler.handle('test_conn_id', request)

        mock_event_broadcaster.disable_subscriber.assert_called_with(
            'test_conn_id')
        mock_event_broadcaster.remove_subscriber.assert_called_with(
            'test_conn_id')

        self.assertEqual(HandlerStatus.RETURN, response.status)
        self.assertEqual(client_event_pb2.ClientEventsUnsubscribeResponse.OK,
                         response.message_out.status)


class ClientEventsGetRequestHandlerTest(unittest.TestCase):
    def setUp(self):
        self.block_store = BlockStore(DictDatabase())
        self.receipt_store = TransactionReceiptStore(DictDatabase())
        self._txn_ids_by_block_id = {}
        for block_id, blk_w, txn_ids in create_chain():
            self.block_store[block_id] = blk_w
            self._txn_ids_by_block_id[block_id] = txn_ids
            for txn_id in txn_ids:
                receipt = create_receipt(txn_id=txn_id,
                                         key_values=[("address", block_id)])
                self.receipt_store.put(
                    txn_id=txn_id,
                    txn_receipt=receipt)

    def test_get_events_by_block_id(self):
        """Tests that the correct events are returned by the
        ClientEventsGetRequest handler for each block id.

        """

        event_broadcaster = EventBroadcaster(
            Mock(),
            block_store=self.block_store,
            receipt_store=self.receipt_store)
        for block_id, _ in self._txn_ids_by_block_id.items():
            request = client_event_pb2.ClientEventsGetRequest()
            request.block_ids.extend([block_id])
            subscription = request.subscriptions.add()
            subscription.event_type = "sawtooth/block-commit"
            event_filter = subscription.filters.add()
            event_filter.key = "address"
            event_filter.match_string = block_id
            event_filter.filter_type = event_filter.SIMPLE_ALL

            event_filter2 = subscription.filters.add()
            event_filter2.key = "block_id"
            event_filter2.match_string = block_id
            event_filter2.filter_type = event_filter2.SIMPLE_ALL

            handler = ClientEventsGetRequestHandler(event_broadcaster)
            handler_output = handler.handle(
                "dummy_conn_id",
                request.SerializeToString())

            self.assertEqual(handler_output.message_type,
                             validator_pb2.Message.CLIENT_EVENTS_GET_RESPONSE)

            self.assertEqual(handler_output.status, HandlerStatus.RETURN)
            self.assertTrue(
                all(any(a.value == block_id
                        for a in e.attributes)
                    for e in handler_output.message_out.events),
                "Each Event has at least one attribute value that is the"
                " block id for the block.")
            self.assertEqual(handler_output.message_out.status,
                             client_event_pb2.ClientEventsGetResponse.OK)
            self.assertTrue(len(handler_output.message_out.events) > 0)


class EventBroadcasterTest(unittest.TestCase):
    def test_add_remove_subscriber(self):
        """Test adding and removing a subscriber."""
        mock_service = Mock()
        mock_block_store = Mock()
        mock_receipt_store = Mock()
        event_broadcaster = EventBroadcaster(mock_service,
                                             mock_block_store,
                                             mock_receipt_store)
        subscriptions = [
            EventSubscription(
                event_type="test_event",
                filters=[
                    FILTER_FACTORY.create(key="test", match_string="test")
                ],
            )
        ]
        event_broadcaster.add_subscriber("test_conn_id", subscriptions, [])

        self.assertTrue(
            "test_conn_id" in event_broadcaster._subscribers.keys())
        self.assertEqual(
            event_broadcaster._subscribers["test_conn_id"].subscriptions,
            subscriptions)

        event_broadcaster.remove_subscriber("test_conn_id")

        self.assertTrue(
            "test_conn_id" not in event_broadcaster._subscribers.keys())

    def test_broadcast_events(self):
        """Test that broadcast_events works with a single subscriber to the
        sawtooth/block-commit event type and that the subscriber does
        not receive events until it is enabled.

        """
        mock_service = Mock()
        mock_block_store = Mock()
        mock_receipt_store = Mock()
        event_broadcaster = EventBroadcaster(mock_service,
                                             mock_block_store,
                                             mock_receipt_store)
        block = create_block()

        event_broadcaster.chain_update(block, [])
        mock_service.send.assert_not_called()

        event_broadcaster.add_subscriber(
            "test_conn_id", [create_block_commit_subscription()], [])

        event_broadcaster.chain_update(block, [])
        mock_service.send.assert_not_called()

        event_broadcaster.enable_subscriber("test_conn_id")
        event_broadcaster.chain_update(block, [])

        event_list = events_pb2.EventList(
            events=BlockEventExtractor(block).extract(
                [create_block_commit_subscription()])).SerializeToString()
        mock_service.send.assert_called_with(
            validator_pb2.Message.CLIENT_EVENTS,
            event_list, connection_id="test_conn_id", one_way=True)

    def test_catchup_subscriber(self):
        """Test that catch subscriber handles the case of:
        - no blocks (i.e. the genesis block has not been produced or received
        - a block that has some receipts exists and sends results
        """
        mock_service = Mock()
        mock_block_store = MagicMock()
        mock_block_store.chain_head = None
        mock_block_store.get_predecessor_iter.return_value = []
        mock_receipt_store = Mock()

        event_broadcaster = EventBroadcaster(mock_service,
                                             mock_block_store,
                                             mock_receipt_store)

        event_broadcaster.add_subscriber(
            "test_conn_id", [create_block_commit_subscription()], [])

        event_broadcaster.catchup_subscriber("test_conn_id")

        mock_service.send.assert_not_called()

        block = create_block()
        mock_block_store.chain_head = block
        mock_block_store.get_predecessor_iter.return_value = [block]
        mock_block_store.__getitem__.return_value = block

        event_broadcaster.catchup_subscriber("test_conn_id")
        event_list = events_pb2.EventList(
            events=BlockEventExtractor(block).extract(
                [create_block_commit_subscription()])).SerializeToString()
        mock_service.send.assert_called_with(
            validator_pb2.Message.CLIENT_EVENTS,
            event_list, connection_id="test_conn_id", one_way=True)


class TpEventAddHandlerTest(unittest.TestCase):
    def test_add_event(self):
        event = events_pb2.Event(event_type="add_event")
        mock_context_manager = Mock()
        handler = TpEventAddHandler(mock_context_manager)
        request = state_context_pb2.TpEventAddRequest(
            event=event).SerializeToString()

        response = handler.handle("test_conn_id", request)

        self.assertEqual(HandlerStatus.RETURN, response.status)

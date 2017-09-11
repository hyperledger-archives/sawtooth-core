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
from unittest.mock import Mock

from sawtooth_validator.database.dict_database import DictDatabase
from sawtooth_validator.networking.dispatch import Handler
from sawtooth_validator.networking.dispatch import HandlerResult
from sawtooth_validator.networking.dispatch import HandlerStatus

from sawtooth_validator.server.events.broadcaster import EventBroadcaster
from sawtooth_validator.server.events.handlers \
    import ClientEventsSubscribeValidationHandler
from sawtooth_validator.server.events.handlers \
    import ClientEventsSubscribeHandler
from sawtooth_validator.server.events.handlers \
    import ClientEventsUnsubscribeHandler
from sawtooth_validator.server.events.subscription import EventSubscription
from sawtooth_validator.server.events.subscription import EventFilterFactory
from sawtooth_validator.server.events.subscription import EventFilterType

from sawtooth_validator.protobuf import events_pb2
from sawtooth_validator.protobuf import block_pb2
from sawtooth_validator.protobuf import validator_pb2

from sawtooth_validator.journal.block_wrapper import BlockWrapper
from sawtooth_validator.journal.event_extractors \
    import BlockEventExtractor


def create_block():
    block_header = block_pb2.BlockHeader(
        block_num=85,
        state_root_hash="0987654321fedcba",
        previous_block_id="0000000000000000")
    block = BlockWrapper(block_pb2.Block(
        header_signature="abcdef1234567890",
        header=block_header.SerializeToString()))
    return block


def create_block_commit_subscription():
    return EventSubscription(event_type="block_commit")


FILTER_FACTORY = EventFilterFactory()


class EventSubscriptionTest(unittest.TestCase):
    def test_filter(self):
        """Test that a regex filter matches properly against an event."""
        self.assertIn(
            events_pb2.Event(attributes=[
                events_pb2.Event.Attribute(
                    key="address", value="000000" + "f" * 64)]),
            FILTER_FACTORY.create(key="address", match_string="000000.*",
                filter_type=EventFilterType.regex_any))

        self.assertIn(
            events_pb2.Event(attributes=[
                events_pb2.Event.Attribute(key="abc", value="123")]),
            FILTER_FACTORY.create(key="abc", match_string="123"))

    def test_subscription(self):
        """Test that an event correctly matches against a subscription."""
        self.assertIn(
            events_pb2.Event(event_type="test", attributes=[
                events_pb2.Event.Attribute(key="test", value="test")]),
            EventSubscription(
                event_type="test",
                filters=[FILTER_FACTORY.create(key="test", match_string="test")]))


class ClientEventsSubscribeValidationHandlerTest(unittest.TestCase):
    def test_subscribe(self):
        """Test that a subscriber is successfully validated and added to the
        event broadcaster.
        """

        mock_event_broadcaster = Mock()
        handler = \
            ClientEventsSubscribeValidationHandler(mock_event_broadcaster)
        request = events_pb2.ClientEventsSubscribeRequest(
            subscriptions=[events_pb2.EventSubscription(
                event_type="test_event",
                filters=[
                    events_pb2.EventFilter(key="test", match_string="test")],
            )],
            last_known_block_ids=["0" * 128]).SerializeToString()

        response = handler.handle("test_conn_id", request)

        mock_event_broadcaster.add_subscriber.assert_called_with(
            "test_conn_id",
            [EventSubscription(
                event_type="test_event",
                filters=[
                    FILTER_FACTORY.create(key="test", match_string="test")])],
            ["0" * 128])
        self.assertEqual(HandlerStatus.RETURN_AND_PASS, response.status)
        self.assertEqual(events_pb2.ClientEventsSubscribeResponse.OK,
                         response.message_out.status)

    def test_subscribe_bad_filter(self):
        """Tests that the handler will respond with an INVALID_FILTER
        when a subscriber provides an invalid filter.
        """
        mock_event_broadcaster = Mock()
        handler = \
            ClientEventsSubscribeValidationHandler(mock_event_broadcaster)
        request = events_pb2.ClientEventsSubscribeRequest(
            subscriptions=[events_pb2.EventSubscription(
                event_type="test_event",
                filters=[events_pb2.EventFilter(
                    key="test", match_string="???",
                    filter_type=events_pb2.EventFilter.REGEX_ANY)],
            )],
            last_known_block_ids=["0" * 128]).SerializeToString()

        response = handler.handle("test_conn_id", request)

        mock_event_broadcaster.add_subscriber.assert_not_called()
        self.assertEqual(HandlerStatus.RETURN, response.status)
        self.assertEqual(
            events_pb2.ClientEventsSubscribeResponse.INVALID_FILTER,
             response.message_out.status)


class ClientEventsSubscribeHandlersTest(unittest.TestCase):

    def test_subscribe(self):
        """Tests that the handler turns on the subscriber."""
        mock_event_broadcaster = Mock()
        handler = ClientEventsSubscribeHandler(mock_event_broadcaster)
        request = events_pb2.ClientEventsSubscribeRequest()

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

        request = \
            events_pb2.ClientEventsUnsubscribeRequest().SerializeToString()

        response = handler.handle('test_conn_id', request)

        mock_event_broadcaster.disable_subscriber.assert_called_with(
            'test_conn_id')
        mock_event_broadcaster.remove_subscriber.assert_called_with(
            'test_conn_id')

        self.assertEqual(HandlerStatus.RETURN, response.status)
        self.assertEqual(events_pb2.ClientEventsUnsubscribeResponse.OK,
                         response.message_out.status)


class EventBroadcasterTest(unittest.TestCase):
    def test_add_remove_subscriber(self):
        """Test adding and removing a subscriber."""
        mock_service = Mock()
        event_broadcaster = EventBroadcaster(mock_service)
        subscriptions = [EventSubscription(
            event_type="test_event",
            filters=[FILTER_FACTORY.create(key="test", match_string="test")],
        )]
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
        block_commit event type and that the subscriber does not receive events
        until it is enabled.
        """
        mock_service = Mock()
        event_broadcaster = EventBroadcaster(mock_service)
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
            event_list, connection_id="test_conn_id")

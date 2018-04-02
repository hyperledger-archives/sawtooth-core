# Copyright 2016, 2017 Intel Corporation
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

import asyncio
import logging
import json
import aiohttp
from aiohttp import web

from google.protobuf.json_format import MessageToDict

from sawtooth_rest_api.protobuf.validator_pb2 import Message

from sawtooth_rest_api.messaging import ConnectionEvent
from sawtooth_rest_api.messaging import DisconnectError
from sawtooth_rest_api.protobuf import client_list_control_pb2
from sawtooth_rest_api.protobuf import client_block_pb2
from sawtooth_rest_api.protobuf import client_event_pb2
from sawtooth_rest_api.protobuf import events_pb2
from sawtooth_rest_api.protobuf import transaction_receipt_pb2


LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30


class StateDeltaSubscriberHandler:
    """
    Handles websocket connections and negotiates their subscriptions for state
    deltas.

    This handler acts as a subscriber on behalf of all incoming websocket
    connections.  The handler subscribes to all state delta changes when the
    first websocket client requests a subscription, regardless of the client's
    own address prefix filters of interest. Subsequent websocket subscribers
    all are fed state deltas from the incoming complete stream, filtered by
    this handler according to their preferred filters.
    """

    def __init__(self, connection):
        """
        Constructs this handler on a given validator connection.

        Args:
            connection (messaging.Connection): the validator connection
        """
        self._connection = connection

        self._latest_state_delta_event = None
        self._subscribers = []
        self._subscriber_lock = asyncio.Lock()
        self._delta_task = None
        self._listening = False
        self._accepting = True

        self._connection.on_connection_state_change(
            ConnectionEvent.DISCONNECTED,
            self._handle_disconnect)
        self._connection.on_connection_state_change(
            ConnectionEvent.RECONNECTED,
            self._handle_reconnection)

    async def on_shutdown(self):
        """
        Cleans up any outstanding subscriptions.
        """
        await self._unregister_subscriptions()

        self._accepting = False

        for (ws, _) in self._subscribers:
            await ws.close(code=aiohttp.WSCloseCode.GOING_AWAY,
                           message='Server shutdown')

    async def subscriptions(self, request):
        """
        Handles requests for new subscription websockets.

        Args:
            request (aiohttp.Request): the incoming request

        Returns:
            aiohttp.web.WebSocketResponse: the websocket response, when the
                resulting websocket is closed
        """

        if not self._accepting:
            return web.Response(status=503)

        web_sock = web.WebSocketResponse()
        await web_sock.prepare(request)

        async for msg in web_sock:
            if msg.type == aiohttp.WSMsgType.TEXT:
                await self._handle_message(web_sock, msg.data)
            elif msg.type == aiohttp.WSMsgType.ERROR:
                LOGGER.warning(
                    'Web socket connection closed with exception %s',
                    web_sock.exception())
                await web_sock.close()

        await self._handle_unsubscribe(web_sock)

        return web_sock

    async def _handle_message(self, web_sock, message_content):
        try:
            incoming_message = json.loads(message_content)
        except json.decoder.JSONDecodeError:
            await web_sock.send_str(json.dumps({
                'error': 'Invalid input: "{}"'.format(message_content)
            }))
            return

        action = incoming_message.get('action', '')
        if action == 'subscribe':
            await self._handle_subscribe(web_sock, incoming_message)
        elif action == 'unsubscribe':
            await self._handle_unsubscribe(web_sock)
        elif action == 'get_block_deltas':
            await self._handle_get_block_deltas(web_sock, incoming_message)
        else:
            await web_sock.send_str(json.dumps({
                'error': 'Unknown action "{}"'.format(action)
            }))

    async def _handle_subscribe(self, web_sock, subscription_message):
        if not self._subscribers:
            await self._register_subscriptions()

        LOGGER.debug('Sending initial most recent event to new subscriber')

        addr_prefixes = subscription_message.get('address_prefixes', [])
        with await self._subscriber_lock:
            self._subscribers.append((web_sock, addr_prefixes))

        event = self._latest_state_delta_event
        if event is not None:
            await web_sock.send_str(json.dumps({
                'block_id': event.block_id,
                'block_num': event.block_num,
                'previous_block_id': event.previous_block_id,
                'state_changes': self._client_deltas(
                    event.state_changes, addr_prefixes)
            }))

    async def _handle_unsubscribe(self, web_sock):
        index = None

        with await self._subscriber_lock:
            for i, (subscriber_web_sock, _) in enumerate(self._subscribers):
                if subscriber_web_sock == web_sock:
                    index = i
                    break

            if index is not None:
                del self._subscribers[index]

            if not self._subscribers:
                asyncio.ensure_future(self._unregister_subscriptions())

    async def _handle_disconnect(self):
        LOGGER.debug('Validator disconnected')
        for (ws, _) in self._subscribers:
            await ws.send_str(json.dumps({
                'warning': 'Validator unavailable'
            }))

    async def _handle_reconnection(self):
        LOGGER.debug('Attempting to resubscribe...')
        # Send an unregister message (just in case it was a network hiccup,
        # not a validator restart)
        try:
            await self._unregister_subscriptions()
            if self._subscribers:
                await self._register_subscriptions()
        except DisconnectError:
            LOGGER.debug('Validator is not yet available')
            return

    async def _register_subscriptions(self):
        try:
            last_known_block_id = await self._get_latest_block_id()
            self._latest_state_delta_event = \
                await self._get_block_deltas(last_known_block_id)

            LOGGER.debug('Starting subscriber from %s',
                         last_known_block_id[:8])

            resp = await self._connection.send(
                Message.CLIENT_EVENTS_SUBSCRIBE_REQUEST,
                client_event_pb2.ClientEventsSubscribeRequest(
                    subscriptions=self._make_subscriptions(),
                    last_known_block_ids=[last_known_block_id],
                ).SerializeToString())

            subscription = \
                client_event_pb2. ClientEventsSubscribeResponse()
            subscription.ParseFromString(resp.content)

            if subscription.status != \
                    client_event_pb2.ClientEventsSubscribeResponse.OK:
                LOGGER.error('unable to subscribe!')

            self._listening = True
            self._delta_task = asyncio.ensure_future(self._listen_for_events())
        except asyncio.TimeoutError as e:
            LOGGER.error('Unable to subscribe to events: %s', str(e))
        except DisconnectError:
            LOGGER.debug(
                'Unable to register: validator connection is missing.')

    async def _unregister_subscriptions(self):
        with await self._subscriber_lock:
            if self._delta_task and not self._subscribers:
                self._listening = False
                self._delta_task.cancel()
                self._delta_task = None

                req = client_event_pb2.ClientEventsUnsubscribeRequest()
                try:
                    await self._connection.send(
                        Message.CLIENT_EVENTS_UNSUBSCRIBE_REQUEST,
                        req.SerializeToString(),
                        timeout=DEFAULT_TIMEOUT)
                    LOGGER.info('Unsubscribed to state delta events')
                except asyncio.TimeoutError as e:
                    LOGGER.error('Unable to unsubscribe from events: %s',
                                 str(e))

    async def _handle_get_block_deltas(self, web_sock, get_block_message):
        if 'block_id' not in get_block_message:
            await web_sock.send_str(json.dumps({
                'error': 'Must specify a block id'
            }))
            return

        block_id = get_block_message['block_id']
        addr_prefixes = get_block_message.get('address_prefixes', [])

        event = await self._get_block_deltas(block_id)
        await web_sock.send_str(json.dumps({
            'block_id': event.block_id,
            'block_num': event.block_num,
            'previous_block_id': event.previous_block_id,
            'state_changes': self._client_deltas(
                event.state_changes, addr_prefixes)
        }))

    async def _get_block_deltas(self, block_id):
        resp = await self._connection.send(
            Message.CLIENT_EVENTS_GET_REQUEST,
            client_event_pb2.ClientEventsGetRequest(
                subscriptions=self._make_subscriptions(),
                block_ids=[block_id]).SerializeToString(),
            timeout=DEFAULT_TIMEOUT)

        events_resp = client_event_pb2.ClientEventsGetResponse()
        events_resp.ParseFromString(resp.content)

        if events_resp.status == \
                client_event_pb2.ClientEventsGetResponse.OK:
            events = list(events_resp.events)
            try:
                return StateDeltaEvent(events)
            except KeyError as err:
                LOGGER.warning("Received unexpected event list: %s", err)

        return None

    async def _get_latest_block_id(self):
        resp = await self._connection.send(
            Message.CLIENT_BLOCK_LIST_REQUEST,
            client_block_pb2.ClientBlockListRequest(
                paging=client_list_control_pb2.ClientPagingControls(limit=1)
            ).SerializeToString())

        block_list_resp = client_block_pb2.ClientBlockListResponse()
        block_list_resp.ParseFromString(resp.content)

        if block_list_resp.status != \
           client_block_pb2.ClientBlockListResponse.OK:
            LOGGER.error('Unable to fetch latest block id')

        return block_list_resp.head_id

    async def _listen_for_events(self):
        LOGGER.debug('Subscribing to state delta events')
        while self._listening:
            try:
                msg = await self._connection.receive()
            except asyncio.CancelledError:
                return

            # Note: if there are other messages that the REST API will listen
            # for, a way of splitting the incoming messages will be needed.
            if msg.message_type == Message.CLIENT_EVENTS:
                event_list = events_pb2.EventList()
                event_list.ParseFromString(msg.content)
                events = list(event_list.events)
                try:
                    state_delta_event = StateDeltaEvent(events)
                except KeyError as err:
                    LOGGER.warning("Received unexpected event list: %s", err)

                LOGGER.debug('Received event %s: %s changes',
                             state_delta_event.block_id[:8],
                             len(state_delta_event.state_changes))

                base_event = {
                    'block_id': state_delta_event.block_id,
                    'block_num': state_delta_event.block_num,
                    'previous_block_id': state_delta_event.previous_block_id,
                }

                if self._latest_state_delta_event is not None and \
                        state_delta_event.block_num <= \
                        self._latest_state_delta_event.block_num:
                    base_event['fork_detected'] = True

                LOGGER.debug('Updating %s subscribers', len(self._subscribers))

                for (web_sock, addr_prefixes) in self._subscribers:
                    base_event['state_changes'] = self._client_deltas(
                        state_delta_event.state_changes, addr_prefixes)
                    try:
                        await web_sock.send_str(json.dumps(base_event))
                    except asyncio.CancelledError:
                        return

                self._latest_state_delta_event = state_delta_event

    @staticmethod
    def _client_deltas(state_changes, addr_prefixes):
        return [_message_to_dict(change)
                for change in state_changes
                if StateDeltaSubscriberHandler._matches_prefixes(
                    change, addr_prefixes)]

    @staticmethod
    def _matches_prefixes(state_change, addr_prefixes):
        if not addr_prefixes:
            return True

        for prefix in addr_prefixes:
            if state_change.address.startswith(prefix):
                return True

        return False

    @staticmethod
    def _make_subscriptions(address_prefixes=None):
        return [
            events_pb2.EventSubscription(event_type="sawtooth/state-delta"),
            events_pb2.EventSubscription(event_type="sawtooth/block-commit"),
        ]

    @staticmethod
    def _make_state_delta_event(event_list):
        """State deltas and block commits are separate now, this function
        merges them back together for compatibility.
        """


class StateDeltaEvent:
    def __init__(self, event_list):
        """
        Convert an event list into an object that is similar to the previous
        state delta event for compatibility.

        Raises
            KeyError
                An event was missing from the event list or an attribute was
                missing from an event.
        """
        block_commit = self._get_event("sawtooth/block-commit", event_list)
        self.block_id = self._get_attr(block_commit, "block_id")
        self.block_num = self._get_attr(block_commit, "block_num")
        self.previous_block_id = self._get_attr(
            block_commit, "previous_block_id")

        state_delta = self._get_event("sawtooth/state-delta", event_list)
        state_change_list = transaction_receipt_pb2.StateChangeList()
        state_change_list.ParseFromString(state_delta.data)
        self.state_changes = state_change_list.state_changes

    @staticmethod
    def _get_attr(event, key):
        attrs = list(filter(
            lambda attr: attr.key == key,
            event.attributes))
        if attrs:
            return attrs[0].value
        raise KeyError("Key '%s' not found in event attributes" % key)

    @staticmethod
    def _get_event(event_type, event_list):
        events = list(filter(
            lambda event: event.event_type == event_type,
            event_list,
        ))
        if events:
            return events[0]
        raise KeyError("Event type '%s' not found" % event_type)


def _message_to_dict(message):
    """Converts a Protobuf object to a python dict with desired settings.
    """
    return MessageToDict(
        message,
        including_default_value_fields=True,
        preserving_proto_field_name=True)

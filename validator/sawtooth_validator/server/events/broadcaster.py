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

import logging
from threading import Condition

from sawtooth_validator.protobuf.events_pb2 import EventList
from sawtooth_validator.protobuf import validator_pb2

from sawtooth_validator.journal.chain import ChainObserver
from sawtooth_validator.journal.event_extractors \
    import BlockEventExtractor
from sawtooth_validator.journal.event_extractors \
    import ReceiptEventExtractor

LOGGER = logging.getLogger(__name__)


class EventBroadcaster(ChainObserver):
    def __init__(self, service, block_store, receipt_store):
        self._subscribers = {}
        self._subscribers_cv = Condition()
        self._service = service
        self._block_store = block_store
        self._receipt_store = receipt_store

    def add_subscriber(self, connection_id, subscriptions,
                       last_known_block_ids):
        """Register the subscriber for the given event subscriptions.

        Raises an exception if:
        1. The subscription is unsuccessful.
        2. None of the block ids in last_known_block_ids are part of the
           current chain.
        """
        with self._subscribers_cv:
            self._subscribers[connection_id] = \
                EventSubscriber(
                    connection_id, subscriptions, last_known_block_ids)

    def enable_subscriber(self, connection_id):
        """Start sending events to the subscriber.

        If any of the block ids in last_known_block_ids are part of the current
        chain, the observer will be notified of all events that it would have
        received based on its subscriptions for each block in the chain since
        the most recent block in last_known_block_ids.
        """
        with self._subscribers_cv:
            self._subscribers[connection_id].start_listening()

    def disable_subscriber(self, connection_id):
        with self._subscribers_cv:
            self._subscribers[connection_id].stop_listening()

    def remove_subscriber(self, connection_id):
        with self._subscribers_cv:
            if connection_id in self._subscribers:
                del self._subscribers[connection_id]

    def get_events_for_block_ids(self, block_ids, subscriptions):
        """Get a list of events associated with all the block ids.

        Args:
            block_ids (list of str): The block ids to search for events that
                match each subscription.
            subscriptions (list of EventSubscriptions): EventFilter and
                event type to filter events.

        Returns (list of Events): The Events associated which each block id.

        Raises: KeyError A block id isn't found within the block store.

        """

        events = []

        extractors = []
        for block_id in block_ids:
            blk_w = self._block_store[block_id]
            extractors.append(BlockEventExtractor(blk_w))
            receipts = []
            for batch in blk_w.block.batches:
                for txn in batch.transactions:
                    try:
                        receipts.append(self._receipt_store.get(
                            txn.header_signature))
                    except KeyError:
                        LOGGER.warning(
                            "Transaction id %s not found in receipt store "
                            " while looking"
                            " up events for block id %s",
                            txn.header_signature[:10],
                            block_id[:10])
            extractors.append(ReceiptEventExtractor(receipts=receipts))

        for extractor in extractors:
            events.extend(extractor.extract(subscriptions))
        return events

    def chain_update(self, block, receipts):
        extractors = [
            BlockEventExtractor(block),
            ReceiptEventExtractor(receipts),
        ]

        subscriptions = []
        for subscriber in self._subscribers.values():
            for subscription in subscriber.subscriptions:
                if subscription not in subscriptions:
                    subscriptions.append(subscription)

        events = []
        for extractor in extractors:
            extracted_events = extractor.extract(subscriptions)
            if extracted_events:
                events.extend(extracted_events)

        if events:
            self.broadcast_events(events)

    def broadcast_events(self, events):
        LOGGER.debug("Broadcasting events: %s", events)
        if self._subscribers:
            for connection_id, subscriber in self._subscribers.items():
                if subscriber.is_listening():
                    subscriber_events = [event for event in events
                                         if subscriber.is_subscribed(event)]
                    event_list = EventList(events=subscriber_events)
                    self._send(connection_id, event_list.SerializeToString())

    def _send(self, connection_id, message_bytes):
        self._service.send(validator_pb2.Message.CLIENT_EVENTS,
                           message_bytes,
                           connection_id=connection_id)


class EventSubscriber:
    def __init__(self, connection_id, subscriptions, last_known_block_ids):
        self._connection_id = connection_id
        self._subscriptions = subscriptions
        self._listening = False
        self._last_known_block_ids = last_known_block_ids

    def start_listening(self):
        self._listening = True

    def stop_listening(self):
        self._listening = False

    def is_listening(self):
        return self._listening

    def is_subscribed(self, event):
        for sub in self._subscriptions:
            if event in sub:
                return True

        return False

    @property
    def subscriptions(self):
        return self._subscriptions.copy()

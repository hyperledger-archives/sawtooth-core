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
from sawtooth_validator.journal.block_wrapper import NULL_BLOCK_IDENTIFIER

LOGGER = logging.getLogger(__name__)


class NoKnownBlockError(Exception):
    pass


class EventBroadcaster(ChainObserver):
    def __init__(self, service, block_store, receipt_store):
        self._subscribers = {}
        self._subscribers_cv = Condition()
        self._service = service
        self._block_store = block_store
        self._receipt_store = receipt_store

    def add_subscriber(self, connection_id, subscriptions,
                       last_known_block_id):
        """Register the subscriber for the given event subscriptions.

        Raises:
            InvalidFilterError
                One of the filters in the subscriptions is invalid.
        """
        with self._subscribers_cv:
            self._subscribers[connection_id] = \
                EventSubscriber(
                    connection_id, subscriptions, last_known_block_id)

        LOGGER.debug(
            'Added Subscriber %s for %s', connection_id, subscriptions)

    def catchup_subscriber(self, connection_id):
        """Send an event list with all events that are in the given
        subscriptions from all blocks since that latest block in the current
        chain that is in the given last known block ids.

        Raises:
            PossibleForkDetectedError
                A possible fork was detected while building the event list
            NoKnownBlockError
                None of the last known blocks were in the current chain
            KeyError
                Unknown connection_id
        """
        with self._subscribers_cv:
            subscriber = self._subscribers[connection_id]
            last_known_block_id = subscriber.get_last_known_block_id()
            subscriptions = subscriber.subscriptions

        if last_known_block_id is not None:
            LOGGER.debug(
                'Catching up Subscriber %s from %s',
                connection_id, last_known_block_id)

            # Send catchup events one block at a time
            for block_id in self.get_catchup_block_ids(last_known_block_id):
                events = self.get_events_for_block_id(block_id, subscriptions)
                event_list = EventList(events=events)
                self._send(connection_id, event_list.SerializeToString())

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

    def get_catchup_block_ids(self, last_known_block_id):
        '''
        Raises:
            PossibleForkDetectedError
        '''
        # If latest known block is not the current chain head, catch up
        catchup_up_blocks = []
        chain_head = self._block_store.chain_head
        if chain_head and last_known_block_id != chain_head.identifier:
            # Start from the chain head and get blocks until we reach the
            # known block
            for block in self._block_store.get_predecessor_iter():
                # All the blocks if NULL_BLOCK_IDENTIFIER
                if last_known_block_id != NULL_BLOCK_IDENTIFIER:
                    if block.identifier == last_known_block_id:
                        break
                catchup_up_blocks.append(block.identifier)

        return list(reversed(catchup_up_blocks))

    def get_latest_known_block_id(self, last_known_block_ids):
        '''
        Raises:
            NoKnownBlockError
        '''
        # Filter known blocks to contain only blocks in the current chain
        blocks = []
        if last_known_block_ids:
            for block_id in last_known_block_ids:
                # If the subscriber wants all the blocks
                if block_id == NULL_BLOCK_IDENTIFIER:
                    blocks.append((-1, block_id))
                else:
                    try:
                        block = self._block_store[block_id]
                    except KeyError:
                        continue
                    block_num = block.block_num
                    blocks.append((block_num, block_id))

        # No known blocks in the current chain
        if not blocks:
            raise NoKnownBlockError()

        # Sort by block num and get the block id of the latest known block
        blocks.sort()
        block_id = blocks[-1][1]
        return block_id

    def get_events_for_block_ids(self, block_ids, subscriptions):
        """Get a list of events associated with all the block ids.

        Args:
            block_ids (list of str): The block ids to search for events that
                match each subscription.
            subscriptions (list of EventSubscriptions): EventFilter and
                event type to filter events.

        Returns (list of Events): The Events associated which each block id.

        Raises:
            KeyError
                A block id isn't found within the block store or a transaction
                is missing from the receipt store.
        """

        blocks = [self._block_store[block_id] for block_id in block_ids]
        return self.get_events_for_blocks(blocks, subscriptions)

    def get_events_for_block_id(self, block_id, subscriptions):
        block = self._block_store[block_id]
        return self.get_events_for_block(block, subscriptions)

    def get_events_for_blocks(self, blocks, subscriptions):
        """Get a list of events associated with all the blocks.

        Args:
            blocks (list of BlockWrapper): The blocks to search for events that
                match each subscription.
            subscriptions (list of EventSubscriptions): EventFilter and
                event type to filter events.

        Returns (list of Events): The Events associated which each block id.

        Raises:
            KeyError A receipt is missing from the receipt store.
        """

        events = []
        for blkw in blocks:
            events.extend(self.get_events_for_block(blkw, subscriptions))
        return events

    def get_events_for_block(self, blkw, subscriptions):
        receipts = []
        for batch in blkw.block.batches:
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
                        blkw.identifier[:10])

        block_event_extractor = BlockEventExtractor(blkw)
        receipt_event_extractor = ReceiptEventExtractor(receipts=receipts)

        events = []
        events.extend(block_event_extractor.extract(subscriptions))
        events.extend(receipt_event_extractor.extract(subscriptions))

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
        with self._subscribers_cv:
            # Copy the subscribers
            subscribers = {
                conn: sub.copy()
                for conn, sub in self._subscribers.items()
            }

        if subscribers:
            for connection_id, subscriber in subscribers.items():
                if subscriber.is_listening():
                    subscriber_events = [
                        event for event in events
                        if subscriber.is_subscribed(event)
                    ]
                    event_list = EventList(events=subscriber_events)
                    self._send(connection_id, event_list.SerializeToString())

    def _send(self, connection_id, message_bytes):
        self._service.send(
            validator_pb2.Message.CLIENT_EVENTS,
            message_bytes,
            connection_id=connection_id,
            one_way=True)


class EventSubscriber:
    def __init__(self, connection_id, subscriptions, last_known_block,
                 listening=False):
        self._connection_id = connection_id
        self._subscriptions = subscriptions
        self._listening = listening
        self._last_known_block = last_known_block

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

    def get_last_known_block_id(self):
        return self._last_known_block

    def set_last_known_block_id(self):
        return self._last_known_block

    def copy(self):
        return self.__class__(
            self._connection_id,
            self._subscriptions,
            self._last_known_block,
            self._listening)

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

from sawtooth_validator.exceptions import PossibleForkDetectedError
from sawtooth_validator.networking.dispatch import Handler
from sawtooth_validator.networking.dispatch import HandlerResult
from sawtooth_validator.networking.dispatch import HandlerStatus

from sawtooth_validator.protobuf import validator_pb2
from sawtooth_validator.protobuf.state_delta_pb2 import StateDeltaEvent
from sawtooth_validator.protobuf.state_delta_pb2 import \
    StateDeltaSubscribeRequest
from sawtooth_validator.protobuf.state_delta_pb2 import \
    StateDeltaSubscribeResponse
from sawtooth_validator.protobuf.state_delta_pb2 import \
    StateDeltaUnsubscribeRequest
from sawtooth_validator.protobuf.state_delta_pb2 import \
    StateDeltaUnsubscribeResponse
from sawtooth_validator.protobuf.state_delta_pb2 import \
    StateDeltaGetEventsRequest
from sawtooth_validator.protobuf.state_delta_pb2 import \
    StateDeltaGetEventsResponse

LOGGER = logging.getLogger(__name__)


class NoKnownBlockError(Exception):
    pass


class _DeltaSubscriber(object):
    """Small holder for subscriber to prefix filters
    """
    def __init__(self, connection_id, address_prefix_filters):
        self.connection_id = connection_id
        self.address_prefixes = address_prefix_filters

    def deltas_of_interest(self, deltas):
        return [delta for delta in deltas if self._match(delta.address)]

    def _match(self, address):
        # Match all if there are no prefixes
        if not self.address_prefixes:
            return True

        for prefix in self.address_prefixes:
            if address.startswith(prefix):
                return True

        return False


class StateDeltaProcessor(object):
    """The StateDeltaProcessor manages subscribers for state deltas.
    """

    def __init__(self, service, state_delta_store, block_store):
        """Constructs a new StateDeltaProcessor.

        Args:
            service (:obj:`Interconnect`): The zmq internal interface.
            state_delta_store (:obj:`StateDeltaStore`): The source of state
                delta values.
            block_store (:obj:`BlockStore`): A BlockStore instance.
        """
        self._service = service
        self._state_delta_store = state_delta_store
        self._block_store = block_store

        self._subscriber_cond = Condition()
        self._subscribers = {}

    @property
    def subscriber_ids(self):
        """Returns the connection ids of the current subscribers.
        """
        with self._subscriber_cond:
            return list(self._subscribers.keys())

    def is_valid_subscription(self, last_known_block_ids):
        try:
            self._match_known_block_id(last_known_block_ids)
            return True
        except NoKnownBlockError:
            return False

    def add_subscriber(
        self,
        connection_id,
        last_known_block_ids,
        address_prefix_filters
    ):
        """Add a subscriber for deltas over specific address_prefixes.

        Args:
            connection_id (str): a connection id
            last_known_block_ids (list of str): a list of block ids known to
                to the subscriber, expected in order of newest to oldest
            address_prefix_filters (list of str): a list of address prefixes
                to filter

        Raises:
            NoKnownBlockError: if the list of last_known_block_ids does not
                contain a block id contained in the block store.
        """
        with self._subscriber_cond:
            self._subscribers[connection_id] = _DeltaSubscriber(
                connection_id, address_prefix_filters)

        LOGGER.debug('Added Subscriber %s for %s',
                     connection_id, address_prefix_filters)

        known_block_id = self._match_known_block_id(last_known_block_ids)
        if known_block_id != self._block_store.chain_head.identifier:
            LOGGER.debug('Catching up Subscriber %s from %s to %s',
                         connection_id,
                         known_block_id,
                         self._block_store.chain_head.identifier[:8])
            catch_up_blocks = []

            try:
                for block in self._block_store.get_predecessor_iter():
                    if block.identifier == known_block_id:
                        break
                    catch_up_blocks.append(block)
            except PossibleForkDetectedError:
                LOGGER.debug(
                    'Possible fork while loading blocks for state deltas')

                # Given that the subscriber has been added to the collection
                # it will receive the events based on the current chain, which
                # will be resolved on client.
                return

            subscriber = self._subscribers[connection_id]
            for block in reversed(catch_up_blocks):
                self._send_changes(
                    block,
                    self._get_delta(block.header.state_root_hash),
                    subscriber)

    def _match_known_block_id(self, last_known_block_ids):
        if last_known_block_ids:
            for block_id in last_known_block_ids:
                if block_id in self._block_store:
                    return block_id

            # No matching block id
            raise NoKnownBlockError()

        return None

    def remove_subscriber(self, connection_id):
        """remove a subscriber with a given connection_id
        """
        with self._subscriber_cond:
            if connection_id in self._subscribers:
                subscriber = self._subscribers[connection_id]
                del self._subscribers[connection_id]
                LOGGER.debug('Removed Subscriber %s for %s',
                             connection_id, subscriber.address_prefixes)

    def publish_deltas(self, block):
        """Publish the state changes for a block.

        Args:
            block (:obj:`BlockWrapper`): The block whose state delta will
                be published.
        """
        LOGGER.debug('Publishing state delta from %s', block)
        state_root_hash = block.header.state_root_hash

        deltas = self._get_delta(state_root_hash)

        if self._subscribers:
            self._broadcast_changes(block, deltas)

    def _get_delta(self, state_root_hash):
        try:
            return self._state_delta_store.get_state_deltas(state_root_hash)
        except KeyError:
            return []

    def _broadcast_changes(self, block, deltas):
        state_change_evt = StateDeltaEvent(
            block_id=block.header_signature,
            block_num=block.header.block_num,
            state_root_hash=block.header.state_root_hash,
            previous_block_id=block.header.previous_block_id)

        for subscriber in self._subscribers.values():
            acceptable_changes = subscriber.deltas_of_interest(deltas)
            state_change_evt.ClearField('state_changes')

            if acceptable_changes:
                state_change_evt.state_changes.extend(acceptable_changes)

            LOGGER.debug('sending change event to %s',
                         subscriber.connection_id)
            self._send(subscriber.connection_id,
                       state_change_evt.SerializeToString())

    def _send_changes(self, block, deltas, subscriber):
        state_change_evt = StateDeltaEvent(
            block_id=block.header_signature,
            block_num=block.header.block_num,
            state_root_hash=block.header.state_root_hash,
            previous_block_id=block.header.previous_block_id,
            state_changes=subscriber.deltas_of_interest(deltas))

        LOGGER.debug('sending change event to %s', subscriber.connection_id)
        self._send(subscriber.connection_id,
                   state_change_evt.SerializeToString())

    def _send(self, connection_id, message_bytes):
        self._service.send(validator_pb2.Message.STATE_DELTA_EVENT,
                           message_bytes,
                           connection_id=connection_id)


class StateDeltaSubscriberValidationHandler(Handler):
    """Handles receiving messages for registering state delta subscribers.
    """

    _msg_type = validator_pb2.Message.STATE_DELTA_SUBSCRIBE_RESPONSE

    def __init__(self, delta_processor):
        self._delta_processor = delta_processor

    def handle(self, connection_id, message_content):
        request = StateDeltaSubscribeRequest()
        request.ParseFromString(message_content)

        ack = StateDeltaSubscribeResponse()
        if self._delta_processor.is_valid_subscription(
                request.last_known_block_ids):
            ack.status = ack.OK
            result = HandlerResult(
                HandlerStatus.RETURN_AND_PASS,
                message_out=ack,
                message_type=self._msg_type)
        else:
            ack.status = ack.UNKNOWN_BLOCK
            result = HandlerResult(
                HandlerStatus.RETURN,
                message_out=ack,
                message_type=self._msg_type)

        return result


class StateDeltaAddSubscriberHandler(Handler):

    def __init__(self, delta_processor):
        self._delta_processor = delta_processor

    def handle(self, connection_id, message_content):
        request = StateDeltaSubscribeRequest()
        request.ParseFromString(message_content)

        try:
            self._delta_processor.add_subscriber(
                connection_id,
                request.last_known_block_ids,
                request.address_prefixes)
        except NoKnownBlockError:
            LOGGER.debug('Subscriber %s added, but catch-up failed',
                         connection_id)
            return HandlerResult(HandlerStatus.DROP)

        return HandlerResult(HandlerStatus.PASS)


class StateDeltaUnsubscriberHandler(Handler):
    """Handles receiving messages for unregistering state delta subscribers.
    """

    _msg_type = validator_pb2.Message.STATE_DELTA_UNSUBSCRIBE_RESPONSE

    def __init__(self, delta_processor):
        self._delta_processor = delta_processor

    def handle(self, connection_id, message_content):
        request = StateDeltaUnsubscribeRequest()
        request.ParseFromString(message_content)

        ack = StateDeltaUnsubscribeResponse()
        self._delta_processor.remove_subscriber(connection_id)
        ack.status = ack.OK

        return HandlerResult(
            HandlerStatus.RETURN,
            message_out=ack,
            message_type=self._msg_type)


class StateDeltaGetEventsHandler(Handler):
    """Handles receiving messages for getting state delta events based on block
    ids.
    """
    _msg_type = validator_pb2.Message.STATE_DELTA_GET_EVENTS_RESPONSE

    def __init__(self, block_store, state_delta_store):
        self._block_store = block_store
        self._state_delta_store = state_delta_store

    def handle(self, connection_id, message_content):
        request = StateDeltaGetEventsRequest()
        request.ParseFromString(message_content)

        # Create a temporary subscriber for this response
        temp_subscriber = _DeltaSubscriber(connection_id,
                                           request.address_prefixes)
        events = []
        for block_id in request.block_ids:
            try:
                block = self._block_store[block_id]
            except KeyError:
                LOGGER.debug('Ignoring state delete event request for %s...',
                             block_id[:8])
                continue

            try:
                deltas = self._state_delta_store.get_state_deltas(
                    block.header.state_root_hash)
            except KeyError:
                deltas = []

            event = StateDeltaEvent(
                block_id=block_id,
                block_num=block.header.block_num,
                state_root_hash=block.header.state_root_hash,
                previous_block_id=block.header.previous_block_id,
                state_changes=temp_subscriber.deltas_of_interest(deltas))

            events.append(event)

        status = StateDeltaGetEventsResponse.OK if events else \
            StateDeltaGetEventsResponse.NO_VALID_BLOCKS_SPECIFIED

        ack = StateDeltaGetEventsResponse(status=status, events=events)

        return HandlerResult(
            HandlerStatus.RETURN,
            message_out=ack,
            message_type=self._msg_type)

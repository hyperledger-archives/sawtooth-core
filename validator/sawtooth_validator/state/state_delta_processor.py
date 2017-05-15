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

from sawtooth_validator.networking.dispatch import Handler
from sawtooth_validator.networking.dispatch import HandlerResult
from sawtooth_validator.networking.dispatch import HandlerStatus

from sawtooth_validator.protobuf import validator_pb2
from sawtooth_validator.protobuf.state_delta_pb2 import StateDeltaEvent
from sawtooth_validator.protobuf.state_delta_pb2 import \
    RegisterStateDeltaSubscriberRequest
from sawtooth_validator.protobuf.state_delta_pb2 import \
    RegisterStateDeltaSubscriberResponse
from sawtooth_validator.protobuf.state_delta_pb2 import \
    UnregisterStateDeltaSubscriberRequest
from sawtooth_validator.protobuf.state_delta_pb2 import \
    UnregisterStateDeltaSubscriberResponse

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

        if last_known_block_ids:
            known_block_id = None
            for block_id in last_known_block_ids:
                if block_id in self._block_store:
                    known_block_id = block_id
                    break

            if not known_block_id:
                raise NoKnownBlockError()

        with self._subscriber_cond:
            self._subscribers[connection_id] = _DeltaSubscriber(
                connection_id, address_prefix_filters)

        LOGGER.debug('Added Subscriber %s for %s',
                     connection_id, address_prefix_filters)

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
        LOGGER.debug('Publishing state delta fro %s', block)
        state_root_hash = block.header.state_root_hash

        deltas = self._get_delta(state_root_hash)

        if len(self._subscribers) > 0:
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
            state_root_hash=block.header.state_root_hash)

        for subscriber in self._subscribers.values():
            acceptable_changes = subscriber.deltas_of_interest(deltas)
            state_change_evt.ClearField('state_changes')

            if len(acceptable_changes) > 0:
                state_change_evt.state_changes.extend(acceptable_changes)

            LOGGER.debug('sending change event to %s',
                         subscriber.connection_id)
            self._send(subscriber.connection_id,
                       state_change_evt.SerializeToString())

    def _send(self, connection_id, message_bytes):
        self._service.send(validator_pb2.Message.STATE_DELTA_EVENT,
                           message_bytes,
                           connection_id=connection_id)


class StateDeltaSubscriberHandler(Handler):
    """Handles receiving messages for registering state delta subscribers.
    """

    _msg_type = validator_pb2.Message.STATE_DELTA_SUBSCRIBE_RESPONSE

    def __init__(self, delta_processor):
        self._delta_processor = delta_processor

    def handle(self, connection_id, message_content):
        request = RegisterStateDeltaSubscriberRequest()
        request.ParseFromString(message_content)

        ack = RegisterStateDeltaSubscriberResponse()
        try:
            self._delta_processor.add_subscriber(
                connection_id,
                request.last_known_block_ids,
                request.address_prefixes)
            ack.status = ack.OK
        except NoKnownBlockError:
            ack.status = ack.UNKNOWN_BLOCK

        return HandlerResult(
            HandlerStatus.RETURN,
            message_out=ack,
            message_type=self._msg_type)


class StateDeltaUnsubscriberHandler(Handler):
    """Handles receiving messages for unregistering state delta subscribers.
    """

    _msg_type = validator_pb2.Message.STATE_DELTA_UNSUBSCRIBE_RESPONSE

    def __init__(self, delta_processor):
        self._delta_processor = delta_processor

    def handle(self, connection_id, message_content):
        request = UnregisterStateDeltaSubscriberRequest()
        request.ParseFromString(message_content)

        ack = UnregisterStateDeltaSubscriberResponse()
        self._delta_processor.remove_subscriber(connection_id)
        ack.status = ack.OK

        return HandlerResult(
            HandlerStatus.RETURN,
            message_out=ack,
            message_type=self._msg_type)

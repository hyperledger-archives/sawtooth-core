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

from collections import namedtuple
from concurrent.futures import CancelledError
import logging
import time

import psycopg2

from google.protobuf.message import DecodeError

from sawtooth_sdk.messaging.exceptions import ValidatorConnectionError
from sawtooth_sdk.messaging.stream import RECONNECT_EVENT

from sawtooth_sdk.protobuf.state_delta_pb2 import \
    StateDeltaSubscribeRequest
from sawtooth_sdk.protobuf.state_delta_pb2 import \
    StateDeltaSubscribeResponse
from sawtooth_sdk.protobuf.state_delta_pb2 import \
    StateDeltaUnsubscribeRequest
from sawtooth_sdk.protobuf.state_delta_pb2 import StateDeltaEvent
from sawtooth_sdk.protobuf.state_delta_pb2 import StateChange
from sawtooth_sdk.protobuf.validator_pb2 import Message

from sawtooth_supplychain.common.addressing import Addressing

from sawtooth_supplychain.protobuf.agent_pb2 import AgentContainer
from sawtooth_supplychain.protobuf.application_pb2 import ApplicationContainer
from sawtooth_supplychain.protobuf.application_pb2 import Application
from sawtooth_supplychain.protobuf.record_pb2 import RecordContainer


LOGGER = logging.getLogger(__name__)


AGENT_NAMESPACE = Addressing.agent_namespace()
APPLICATION_NAMESPACE = Addressing.application_namespace()
RECORD_NAMESPACE = Addressing.record_namespace()


class Subscriber:
    """A State Delta Subscriber for supplychain.

    The Subscriber will send a StateDeltaSubscribeRequest, limited to the
    state values within the namespaces for the supplychain family.
    """
    def __init__(self, stream, db_connection):
        self._stream = stream
        self._db_connection = db_connection

        self._active = True

    def start(self):
        """Starts the subscriber.

        Sends a subscribe request and begins processing the received events.
        """
        self._do_start()

    def _do_start(self, is_resubscribing=False):
        current_block = self._get_current_block()

        last_known_blocks = None
        if current_block != _NIL_BLOCK:
            LOGGER.info('Subscribing with last known block %s',
                        current_block.block_id[:8])
            last_known_blocks = [current_block.block_id]
        else:
            LOGGER.info('Subscribing from genesis block')

        status = self._subscribe(last_known_blocks)

        if status == StateDeltaSubscribeResponse.OK:
            if not is_resubscribing:
                self._listen_for_events()
        elif status == StateDeltaSubscribeResponse.UNKNOWN_BLOCK:
            self._resolve_registration_fork()
            if not is_resubscribing:
                self._listen_for_events()
        else:
            LOGGER.error('Unable to subscribe due to validator error.')

    def shutdown(self):
        """Shuts down the subscriber.

        Sends an unsubscribe request to the validator and stops listening for
        events.
        """
        self._active = False
        try:
            LOGGER.debug('Unsubscribing from validator')
            fut = self._stream.send(
                Message.STATE_DELTA_UNSUBSCRIBE_REQUEST,
                StateDeltaUnsubscribeRequest().SerializeToString())

            fut.result(timeout=10)
        except ValidatorConnectionError:
            LOGGER.debug('Validator connection lost while unsubscribing')

    def _get_current_block(self, cur=None):
        close_on_return = False
        if not cur:
            close_on_return = True
            cur = self._db_connection.cursor()

        try:
            cur.execute('SELECT block_id, block_num, state_root_hash '
                        'FROM block ORDER BY block_num DESC LIMIT 1')
            result = cur.fetchone()
            if result:
                return _Block._make(result)

            return _NIL_BLOCK
        finally:
            if close_on_return and cur:
                cur.close()

    def _subscribe(self, last_known_block_ids):
        try:
            self._stream.wait_for_ready()

            future = self._stream.send(
                Message.STATE_DELTA_SUBSCRIBE_REQUEST,
                StateDeltaSubscribeRequest(
                    last_known_block_ids=last_known_block_ids,
                    address_prefixes=[
                        AGENT_NAMESPACE,
                        APPLICATION_NAMESPACE,
                        RECORD_NAMESPACE]
                ).SerializeToString())

            register_response = StateDeltaSubscribeResponse()
            register_response.ParseFromString(future.result().content)
            return register_response.status
        except ValidatorConnectionError:
            LOGGER.debug('Validator connection lost while subscribing')
            return None

    def _resolve_registration_fork(self):
        """Scans through the set of block ids and sends known blocks, in order
        to find a common block id to restart event handling.
        """
        status = None
        with self._db_connection.cursor() as cur:
            cur.execute('SELECT block_id '
                        'FROM block ORDER BY block_num DESC')
            while status != StateDeltaSubscribeResponse.OK:
                block_id_rows = cur.fetchmany(10)
                block_ids = [row[0] for row in block_id_rows]

                status = self._subscribe(block_ids)

                if status == StateDeltaSubscribeResponse.INTERNAL_ERROR:
                    LOGGER.error('Unable to subscribe due to validator error.')
                    return status

        return status

    def _listen_for_events(self):
        while self._active:
            future = self._stream.receive()

            incoming = None
            try:
                incoming = future.result()
            except CancelledError:
                time.sleep(2)
                continue

            if incoming == RECONNECT_EVENT:
                self._stream.wait_for_ready()
                LOGGER.debug('Resubscribing to validator')
                self._do_start(is_resubscribing=True)
            elif incoming.message_type == Message.STATE_DELTA_EVENT:
                state_delta_event = StateDeltaEvent()
                try:
                    state_delta_event.ParseFromString(incoming.content)
                except DecodeError:
                    LOGGER.exception('Unable to decode message %s', incoming)
                    continue

                self._handle_event(state_delta_event)
            else:
                LOGGER.debug('Received unknown event %s',
                             Message.Type.Name(incoming.message_type))

    def _handle_event(self, event):
        """Handles an incoming StateDeltaEvent.

        This function will update both the block table, identify forks and
        resolve them, as well as update the domain-specific tables. If all
        database operations are successful, the changes will be committed. In
        the case of an exception, the transaction will be rolled back.

        Args:
            event (:obj:`StateDeltaEvent`): the received event
        """
        try:
            with self._db_connection.cursor() as cur:
                cur.execute(
                    'SELECT block_id, block_num, state_root_hash '
                    'FROM block WHERE block_num = %s',
                    [event.block_num])

                LOGGER.debug(
                    'Received event for block %s of %s change(s)',
                    event.block_id[:8], len(event.state_changes))

                block_row = cur.fetchone()
                if block_row:
                    existing_block = _Block._make(block_row)

                    if existing_block.block_id != event.block_id:
                        LOGGER.info(
                            'Fork detected: replacing %s (%s) with %s (%s)',
                            existing_block.block_id[:8],
                            existing_block.block_num,
                            event.block_id[:8],
                            event.block_num)
                        # a fork occurred on the validator to which we are
                        # subscribed remove the changes from the previous fork
                        Subscriber._resolve_fork(cur, existing_block)
                    else:
                        # Repeated event
                        return

                cur.execute('INSERT INTO block VALUES (%s, %s, %s)',
                            [event.block_id,
                             event.block_num,
                             event.state_root_hash])

                for state_change in event.state_changes:
                    if state_change.address.startswith(AGENT_NAMESPACE):
                        Subscriber._apply_agent_change(
                            cur, event.block_num, state_change)
                    elif state_change.address.startswith(
                            APPLICATION_NAMESPACE):
                        Subscriber._apply_application_change(
                            cur, event.block_num, state_change)
                    elif state_change.address.startswith(RECORD_NAMESPACE):
                        Subscriber._apply_record_change(
                            cur, event.block_num, state_change)
                    else:
                        LOGGER.warning(
                            'Received state change from wrong namespace: %s',
                            state_change.address[:6])

                self._db_connection.commit()
        except psycopg2.DatabaseError:
            LOGGER.exception('Unable to handle event!')
        finally:
            self._db_connection.rollback()

    @staticmethod
    def _apply_agent_change(cur, block_num, agent_state_change):
        agent_container = AgentContainer()
        agent_container.ParseFromString(agent_state_change.value)

        for agent in agent_container.entries:
            cur.execute('UPDATE agent SET end_block_num = %s '
                        'WHERE end_block_num IS NULL AND identifier = %s',
                        [block_num, agent.identifier])

            if agent_state_change.type == StateChange.SET:
                cur.execute(
                    'INSERT INTO agent (start_block_num, identifier, name) '
                    'VALUES (%s, %s, %s)',
                    [block_num, agent.identifier, agent.name])

    @staticmethod
    def _apply_application_change(cur, block_num, application_state_change):
        application_container = ApplicationContainer()
        application_container.ParseFromString(application_state_change.value)

        # Since this contains all the applications for a given record, we must
        # mark all the existing ones for the record as the previous block
        if application_container.entries:
            cur.execute('UPDATE application SET end_block_num = %s '
                        'WHERE end_block_num IS NULL AND '
                        'record_identifier = %s',
                        [block_num,
                         application_container.entries[0].record_identifier])

        for application in application_container.entries:
            if application_state_change.type == StateChange.SET:
                cur.execute(
                    'INSERT INTO application '
                    '(start_block_num, record_identifier, applicant,'
                    ' creation_time, type, status, terms) '
                    'VALUES (%s, %s, %s, %s, %s, %s, %s)',
                    [block_num,
                     application.record_identifier,
                     application.applicant,
                     application.creation_time,
                     application.type,
                     application.status,
                     application.terms])

    @staticmethod
    def _apply_record_change(cur, block_num, record_state_change):
        record_container = RecordContainer()
        record_container.ParseFromString(record_state_change.value)

        for record in record_container.entries:
            cur.execute('UPDATE record SET end_block_num = %s '
                        'WHERE end_block_num IS NULL AND identifier = %s',
                        [block_num, record.identifier])

            if record_state_change.type == StateChange.SET:
                cur.execute(
                    'INSERT INTO record '
                    '(id, start_block_num,'
                    ' identifier, '
                    ' creation_time, '
                    ' finalize) '
                    'VALUES (DEFAULT, %s, %s, %s, %s) RETURNING id',
                    [block_num,
                     record.identifier,
                     record.creation_time,
                     record.final])

                (record_id,) = cur.fetchone()

                insert_record_agent_sql = \
                    """INSERT INTO record_agent
                    (record_id, agent_identifier, start_time, agent_type)
                    VALUES (%s, %s, %s, %s)
                    """
                for owner in record.owners:
                    cur.execute(
                        insert_record_agent_sql,
                        [record_id,
                         owner.agent_identifier,
                         owner.start_time,
                         Application.OWNER])
                for custodian in record.custodians:
                    cur.execute(
                        insert_record_agent_sql,
                        [record_id,
                         custodian.agent_identifier,
                         custodian.start_time,
                         Application.CUSTODIAN])

    @staticmethod
    def _resolve_fork(cur, block):
        LOGGER.debug('resolving fork of %s', block)
        # Remove agents from old fork:
        cur.execute('DELETE FROM agent WHERE start_block_num >= %s',
                    [block.block_num])
        cur.execute('UPDATE agent SET end_block_num = null '
                    'WHERE end_block_num >= %s',
                    [block.block_num])

        # Remove applications from old fork:
        cur.execute('DELETE FROM application WHERE start_block_num >= %s',
                    [block.block_num])
        cur.execute('UPDATE application SET end_block_num = null '
                    'WHERE end_block_num >= %s',
                    [block.block_num])

        # Remove records from old fork:
        cur.execute('DELETE FROM record_agent WHERE record_id = '
                    '(SELECT id FROM record WHERE start_block_num >= %s)',
                    [block.block_num])
        cur.execute('DELETE FROM record WHERE start_block_num >= %s',
                    [block.block_num])
        cur.execute('UPDATE record SET end_block_num = null '
                    'WHERE end_block_num >= %s',
                    [block.block_num])

        # Remove block history from old fork
        cur.execute('DELETE FROM block WHERE block_num >= %s',
                    [block.block_num])


_Block = namedtuple('_Block', ['block_id', 'block_num', 'state_root_hash'])

_NIL_BLOCK = _Block(None, None, None)

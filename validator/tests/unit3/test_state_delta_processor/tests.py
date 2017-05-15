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

from sawtooth_validator.state.state_delta_store import StateDeltaStore
from sawtooth_validator.state.state_delta_processor import \
    StateDeltaProcessor
from sawtooth_validator.state.state_delta_processor import \
    NoKnownBlockError
from sawtooth_validator.state.state_delta_processor import \
    StateDeltaSubscriberHandler
from sawtooth_validator.state.state_delta_processor import \
    StateDeltaUnsubscriberHandler

from sawtooth_validator.protobuf.state_delta_pb2 import StateChange
from sawtooth_validator.protobuf.state_delta_pb2 import StateDeltaEvent
from sawtooth_validator.protobuf.state_delta_pb2 import \
    RegisterStateDeltaSubscriberRequest
from sawtooth_validator.protobuf.state_delta_pb2 import \
    RegisterStateDeltaSubscriberResponse
from sawtooth_validator.protobuf.state_delta_pb2 import \
    UnregisterStateDeltaSubscriberRequest
from sawtooth_validator.protobuf.state_delta_pb2 import \
    UnregisterStateDeltaSubscriberResponse
from sawtooth_validator.protobuf import validator_pb2

from test_journal.block_tree_manager import BlockTreeManager


class StateDeltaProcessorHandlerTest(unittest.TestCase):

    def test_register_subscriber(self):
        """Tests that the handler will add a valid subscriber and return an OK
        response.
        """
        mock_block_store = {'a': Mock()}
        delta_processor = StateDeltaProcessor(
            service=Mock(),
            state_delta_store=Mock(),
            block_store=mock_block_store)

        handler = StateDeltaSubscriberHandler(delta_processor)

        request = RegisterStateDeltaSubscriberRequest(
            last_known_block_ids=['a'],
            address_prefixes=['000000']).SerializeToString()

        response = handler.handle('test_conn_id', request)

        self.assertEqual(HandlerStatus.RETURN, response.status)

        self.assertEqual(RegisterStateDeltaSubscriberResponse.OK,
                         response.message_out.status)

    def test_register_with_uknown_block_ids(self):
        """Tests that the handler will respond with an UNKNOWN_BLOCK
        when a subscriber does not supply a known block id in
        last_known_block_ids
        """
        mock_block_store = {}

        delta_processor = StateDeltaProcessor(
            service=Mock(),
            state_delta_store=Mock(),
            block_store=mock_block_store)

        handler = StateDeltaSubscriberHandler(delta_processor)

        request = RegisterStateDeltaSubscriberRequest(
            last_known_block_ids=['a'],
            address_prefixes=['000000']).SerializeToString()

        response = handler.handle('test_conn_id', request)

        self.assertEqual(HandlerStatus.RETURN, response.status)

        self.assertEqual(
            RegisterStateDeltaSubscriberResponse.UNKNOWN_BLOCK,
            response.message_out.status)


class StateDeltaUnregisterSubscriberHandlerTest(unittest.TestCase):
    def test_unregister_subscriber(self):
        """Test that a handler will unregister a subscriber via a the requestor's
        connection id.
        """
        mock_delta_processor = Mock()
        handler = StateDeltaUnsubscriberHandler(mock_delta_processor)

        request = UnregisterStateDeltaSubscriberRequest().SerializeToString()

        response = handler.handle('test_conn_id', request)

        mock_delta_processor.remove_subscriber.assert_called_with(
            'test_conn_id')

        self.assertEqual(HandlerStatus.RETURN, response.status)
        self.assertEqual(UnregisterStateDeltaSubscriberResponse.OK,
                         response.message_out.status)


class StateDeltaProcessorTest(unittest.TestCase):

    def test_add_subscriber(self):
        """Test adding a subscriber, who has no known blocks.

        This scenerio is valid for subscribers who have never connected and
        would need to receive all deltas since the genesis block.
        """
        mock_service = Mock()
        block_tree_manager = BlockTreeManager()

        delta_processor = StateDeltaProcessor(
            service=mock_service,
            state_delta_store=Mock(),
            block_store=block_tree_manager.block_store)

        delta_processor.add_subscriber(
            'test_conn_id',
            [],
            ['deadbeef'])

        self.assertEqual(['test_conn_id'], delta_processor.subscriber_ids)

    def test_add_subscrber_known_block_id(self):
        """Test adding a subscriber, whose known block id is the current
        chainhead.
        """

        mock_service = Mock()
        block_tree_manager = BlockTreeManager()

        delta_processor = StateDeltaProcessor(
            service=mock_service,
            state_delta_store=Mock(),
            block_store=block_tree_manager.block_store)

        delta_processor.add_subscriber(
            'test_conn_id',
            [block_tree_manager.chain_head.identifier],
            ['deadbeef'])

        self.assertEqual(['test_conn_id'], delta_processor.subscriber_ids)

        self.assertTrue(not mock_service.send.called)

    def test_add_subscriber_unknown_block_id(self):
        """Test adding a subscriber, whose known block id is not in the
        current chain.
        """
        block_tree_manager = BlockTreeManager()

        delta_processor = StateDeltaProcessor(
            service=Mock(),
            state_delta_store=Mock(),
            block_store=block_tree_manager.block_store)

        with self.assertRaises(NoKnownBlockError):
            delta_processor.add_subscriber(
                'test_conn_id',
                ['deadbeefb10c4'],
                ['deadbeef'])

    def test_remove_subscriber(self):
        """Test adding a subscriber, whose known block id is the current
        chainhead, followed by removing the subscriber.
        """
        mock_service = Mock()
        block_tree_manager = BlockTreeManager()

        delta_processor = StateDeltaProcessor(
            service=mock_service,
            state_delta_store=Mock(),
            block_store=block_tree_manager.block_store)

        delta_processor.add_subscriber(
            'test_conn_id',
            [block_tree_manager.chain_head.identifier],
            ['deadbeef' 'beefdead'])

        self.assertEqual(['test_conn_id'], delta_processor.subscriber_ids)

        delta_processor.remove_subscriber('test_conn_id')

        self.assertEqual([], delta_processor.subscriber_ids)

    def test_publish_deltas(self):
        """Tests that a subscriber filtering on an address prefix receives only
        the changes in an event that match.
        """
        mock_service = Mock()
        block_tree_manager = BlockTreeManager()

        database = DictDatabase()
        delta_store = StateDeltaStore(database)

        delta_processor = StateDeltaProcessor(
            service=mock_service,
            state_delta_store=delta_store,
            block_store=block_tree_manager.block_store)

        delta_processor.add_subscriber(
            'test_conn_id',
            [block_tree_manager.chain_head.identifier],
            ['deadbeef'])

        next_block = block_tree_manager.generate_block()
        # State added during context squash for our block
        delta_store.save_state_deltas(
            next_block.header.state_root_hash,
            [StateChange(address='deadbeef01',
                         value='my_state_Value'.encode(),
                         type=StateChange.SET),
             StateChange(address='a14ea01',
                         value='some other state value'.encode(),
                         type=StateChange.SET)])

        # call to publish deltas for that block to the subscribers
        delta_processor.publish_deltas(next_block)

        mock_service.send.assert_called_with(
            validator_pb2.Message.STATE_DELTA_EVENT,
            StateDeltaEvent(
                block_id=next_block.identifier,
                block_num=next_block.header.block_num,
                state_root_hash=next_block.header.state_root_hash,
                state_changes=[StateChange(address='deadbeef01',
                               value='my_state_Value'.encode(),
                               type=StateChange.SET)]
            ).SerializeToString(),
            connection_id='test_conn_id')

    def test_publish_deltas_subscriber_matches_no_addresses(self):
        """Given a subscriber whose prefix filters don't match any addresses
        in the current state delta, it should still receive an event with the
        block change information.
        """
        mock_service = Mock()
        block_tree_manager = BlockTreeManager()

        database = DictDatabase()
        delta_store = StateDeltaStore(database)

        delta_processor = StateDeltaProcessor(
            service=mock_service,
            state_delta_store=delta_store,
            block_store=block_tree_manager.block_store)

        delta_processor.add_subscriber(
            'settings_conn_id',
            [block_tree_manager.chain_head.identifier],
            ['000000'])

        next_block = block_tree_manager.generate_block()
        # State added during context squash for our block
        delta_store.save_state_deltas(
            next_block.header.state_root_hash,
            [StateChange(address='deadbeef01',
                         value='my_state_Value'.encode(),
                         type=StateChange.SET),
             StateChange(address='a14ea01',
                         value='some other state value'.encode(),
                         type=StateChange.SET)])

        # call to publish deltas for that block to the subscribers
        delta_processor.publish_deltas(next_block)

        mock_service.send.assert_called_with(
            validator_pb2.Message.STATE_DELTA_EVENT,
            StateDeltaEvent(
                block_id=next_block.identifier,
                block_num=next_block.header.block_num,
                state_root_hash=next_block.header.state_root_hash,
                state_changes=[]
            ).SerializeToString(),
            connection_id='settings_conn_id')

    def test_publish_deltas_no_state_changes(self):
        """Given a block transition, where no state changes happened (e.g. it
        only had transactions which did not change state), the
        StateDeltaProcessor should still publish an event with the block change
        information.
        """
        mock_service = Mock()
        block_tree_manager = BlockTreeManager()

        database = DictDatabase()
        delta_store = StateDeltaStore(database)

        delta_processor = StateDeltaProcessor(
            service=mock_service,
            state_delta_store=delta_store,
            block_store=block_tree_manager.block_store)

        delta_processor.add_subscriber(
            'subscriber_conn_id',
            [block_tree_manager.chain_head.identifier],
            ['000000'])

        next_block = block_tree_manager.generate_block()
        delta_processor.publish_deltas(next_block)

        mock_service.send.assert_called_with(
            validator_pb2.Message.STATE_DELTA_EVENT,
            StateDeltaEvent(
                block_id=next_block.identifier,
                block_num=next_block.header.block_num,
                state_root_hash=next_block.header.state_root_hash,
                state_changes=[]
            ).SerializeToString(),
            connection_id='subscriber_conn_id')

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
import json
import time

from sawtooth_sdk.protobuf.validator_pb2 import Message

from sawtooth_processor_test.transaction_processor_test_case \
    import TransactionProcessorTestCase

from sawtooth_supplychain_test.supplychain_message_factory \
    import SupplychainMessageFactory
import sawtooth_supplychain.common.addressing as addressing

LOGGER = logging.getLogger(__name__)


class TestSupplyChain(TransactionProcessorTestCase):

    @classmethod
    def setUpClass(cls):
        super(TestSupplyChain, cls).setUpClass()
        cls.validator.register_comparator(
            Message.TP_STATE_SET_REQUEST,
            compare_set_request)
        cls.factory = SupplychainMessageFactory()

    def test_record_create(self):
        """
        Test if the supplychain processor can create a record.
        """
        validator = self.validator
        factory = self.factory

        record_addr = addressing.create_record_id("a")
        agent_addr = addressing.get_agent_id(self.factory.public_key)
        addrs = [record_addr, agent_addr]
        time_stamp = time.time()

        # 1. -> Send a set transaction
        #    <- Expect a state get request
        validator.send(factory.create_tp_process_request(
            {
                'MessageType': 'Record',
                'Action': 'Create',
                'RecordId': record_addr,
                'Timestamp': time_stamp
            }, addrs, addrs))

        # test for record existance
        received = validator.expect(factory.create_get_request(record_addr))
        validator.respond(factory.create_get_response(
            record_addr, None), received)

        # add_record_owner
        self.expect_agent_value_update(agent_addr, 'OwnRecords',
                                       record_addr, True)

        # Test for agent record
        # add_record_holder
        self.expect_agent_value_update(agent_addr, 'HoldRecords',
                                       record_addr, 0)

        # Expect test for existance
        received = validator.expect(factory.create_set_request(
            record_addr, {
                'RecordInfo': {
                    'CurrentHolder': agent_addr,
                    'Owner': agent_addr,
                    'Custodians': [],
                    'Parents': None,
                    'Timestamp': time_stamp,
                    'Sensor': None,
                    'Final': False,
                    'ApplicationFrom': None,
                    'ApplicationType': None,
                    'ApplicationTerms': None,
                    'ApplicationStatus': None,
                    'EncryptedConsumerAcccessible': None,
                    'EncryptedOwnerAccessible': None
                },
                'StoredTelemetry': {},
                'DomainAttributes': {}
            }))
        validator.respond(factory.create_set_response(record_addr), received)

        self.expect_ok()

    def test_record_create_application(self):
        """
        Test if the supplychain processor can create a application.
        """
        validator = self.validator
        factory = self.factory

        record_addr = addressing.create_record_id("a")
        agent_addr = addressing.get_agent_id(self.factory.public_key)
        holder_addr = addressing.get_agent_id("holder")
        addrs = [record_addr, agent_addr, holder_addr]

        # 1. -> Send a set transaction
        #    <- Expect a state get request
        validator.send(factory.create_tp_process_request(
            {
                'MessageType': 'Record',
                'Action': 'CreateApplication',
                'RecordId': record_addr,
                'ApplicationType': 'test',
                'ApplicationTerms': 'terms',
            }, addrs, addrs))

        # test for record existance
        received = validator.expect(factory.create_get_request(record_addr))
        validator.respond(factory.create_get_response(
            record_addr, {
                'RecordInfo': {
                    'ApplicationFrom': None,
                    'ApplicationType': None,
                    'ApplicationTerms': None,
                    'ApplicationStatus': 'Open',
                    'CurrentHolder': holder_addr
                }}), received)

        # AgentHandler.update_record_tracking
        self.expect_agent_value_update(agent_addr, 'OpenApplications',
                                       record_addr, 1)
        # AgentHandler.update_record_tracking
        self.expect_agent_value_update(holder_addr, 'HoldRecords',
                                       record_addr, 1)

        received = validator.expect(factory.create_set_request(
            record_addr, {
                'RecordInfo': {
                    'ApplicationFrom': agent_addr,
                    'ApplicationType': 'test',
                    'ApplicationTerms': 'terms',
                    'ApplicationStatus': 'Open',
                    'CurrentHolder': holder_addr,
                }}))
        validator.respond(factory.create_set_response(record_addr), received)
        self.expect_ok()

    def test_record_accept_application(self):
        """
        Test if the supplychain processor can create a application.
        """
        validator = self.validator
        factory = self.factory

        record_addr = addressing.create_record_id("a")
        agent_addr = addressing.get_agent_id(self.factory.public_key)
        addrs = [record_addr, agent_addr]

        # 1. -> Send a set transaction
        #    <- Expect a state get request
        validator.send(factory.create_tp_process_request(
            {
                'MessageType': 'Record',
                'Action': 'AcceptApplication',
                'RecordId': record_addr,
            }, addrs, addrs))

        # test for record existance
        received = validator.expect(factory.create_get_request(record_addr))
        validator.respond(factory.create_get_response(
            record_addr, {
                'RecordInfo': {
                    'ApplicationFrom': agent_addr,
                    'ApplicationStatus': 'Open',
                    'CurrentHolder': agent_addr,
                    'Sensor': 'sensor'
                }
            }), received)

        # AgentHandler.remove_open_application
        LOGGER.debug("1")
        self.expect_agent_value_delete(agent_addr, 'OpenApplications',
                                       record_addr, 1)
        LOGGER.debug("2")
        self.expect_agent_value_update(agent_addr, 'HoldRecords',
                                       record_addr, 0)
        LOGGER.debug("3")
        # AgentHandler.add_accepted_application
        self.expect_agent_value_update(agent_addr, 'AcceptedApplications',
                                       record_addr, "sensor")
        LOGGER.debug("4")

        received = validator.expect(factory.create_set_request(
            record_addr, {
                'RecordInfo': {
                    'ApplicationStatus': 'Accepted',
                    'ApplicationFrom': agent_addr,
                    'CurrentHolder': agent_addr,
                    'Sensor': 'sensor'
                }}))
        validator.respond(factory.create_set_response(record_addr), received)
        self.expect_ok()

    def test_record_reject_application(self):
        """
        Test if the supplychain processor can reject an application.
        """
        validator = self.validator
        factory = self.factory

        record_addr = addressing.create_record_id("a")
        agent_addr = addressing.get_agent_id(self.factory.public_key)
        addrs = [record_addr, agent_addr]

        # 1. -> Send a set transaction
        #    <- Expect a state get request
        validator.send(factory.create_tp_process_request(
            {
                'MessageType': 'Record',
                'Action': 'RejectApplication',
                'RecordId': record_addr,
            }, addrs, addrs))

        # test for record existance
        received = validator.expect(factory.create_get_request(record_addr))
        validator.respond(factory.create_get_response(
            record_addr, {
                'RecordInfo': {
                    'ApplicationFrom': agent_addr,
                    'ApplicationStatus': 'Open',
                    'CurrentHolder': agent_addr
                }
            }), received)

        # AgentHandler.remove_open_application
        self.expect_agent_value_delete(agent_addr, 'OpenApplications',
                                       record_addr, 1)
        self.expect_agent_value_update(agent_addr, 'HoldRecords',
                                       record_addr, 0)

        received = validator.expect(factory.create_set_request(
            record_addr, {
                'RecordInfo': {
                    'ApplicationStatus': 'Rejected',
                    'ApplicationFrom': agent_addr,
                    'CurrentHolder': agent_addr
                }}))
        validator.respond(factory.create_set_response(record_addr), received)
        self.expect_ok()

    def test_record_cancel_application(self):
        """
        Test if the supplychain processor can cancel an application.
        """
        validator = self.validator
        factory = self.factory

        record_addr = addressing.create_record_id("a")
        agent_addr = addressing.get_agent_id(self.factory.public_key)
        addrs = [record_addr, agent_addr]

        # 1. -> Send a set transaction
        #    <- Expect a state get request
        validator.send(factory.create_tp_process_request(
            {
                'MessageType': 'Record',
                'Action': 'CancelApplication',
                'RecordId': record_addr,
            }, addrs, addrs))

        # test for record existance
        received = validator.expect(factory.create_get_request(record_addr))
        validator.respond(factory.create_get_response(
            record_addr, {
                'RecordInfo': {
                    'ApplicationFrom': agent_addr,
                    'ApplicationStatus': 'Open',
                    'CurrentHolder': agent_addr
                }
            }), received)

        # AgentHandler.remove_open_application
        self.expect_agent_value_delete(agent_addr, 'OpenApplications',
                                       record_addr, 1)
        self.expect_agent_value_update(agent_addr, 'HoldRecords',
                                       record_addr, 0)

        received = validator.expect(factory.create_set_request(
            record_addr, {
                'RecordInfo': {
                    'ApplicationStatus': 'Cancelled',
                    'ApplicationFrom': agent_addr,
                    'CurrentHolder': agent_addr
                }}))
        validator.respond(factory.create_set_response(record_addr), received)
        self.expect_ok()

    def test_record_finalize(self):
        """
        Test if the supplychain processor can cancel an application.
        """
        validator = self.validator
        factory = self.factory

        record_addr = addressing.create_record_id("a")
        agent_addr = addressing.get_agent_id(self.factory.public_key)
        addrs = [record_addr, agent_addr]

        # 1. -> Send a set transaction
        #    <- Expect a state get request
        validator.send(factory.create_tp_process_request(
            {
                'MessageType': 'Record',
                'Action': 'Finalize',
                'RecordId': record_addr
            }, addrs, addrs))

        # test for record existance
        received = validator.expect(factory.create_get_request(record_addr))
        validator.respond(factory.create_get_response(
            record_addr, {
                'RecordInfo': {
                    'Final': False,
                    'Owner': agent_addr,
                    'CurrentHolder': agent_addr
                }
            }), received)

        # AgentHandler.remove_record_owner
        self.expect_agent_value_delete(agent_addr, 'OwnRecords',
                                       record_addr, 1)

        # AgentHandler.remove_record_holder
        self.expect_agent_value_delete(agent_addr, 'HoldRecords',
                                       record_addr, 1)

        received = validator.expect(factory.create_set_request(
            record_addr, {
                'RecordInfo': {
                    'Final': True,
                    'Owner': agent_addr,
                    'CurrentHolder': agent_addr
                },
            }))
        validator.respond(factory.create_set_response(record_addr), received)
        self.expect_ok()

    def test_agent_create(self):
        """
        Test if the supplychain processor can create an agent.
        """
        validator = self.validator
        factory = self.factory

        agent_addr = addressing.get_agent_id(self.factory.public_key)

        # 1. -> Send a set transaction
        #    <- Expect a state get request
        validator.send(factory.create_tp_process_request(
            {
                'MessageType': 'Agent',
                'Action': 'Create',
                'Name': 'test'
            }))

        # Expect test for agent existance
        received = validator.expect(factory.create_get_request(agent_addr))
        validator.respond(factory.create_get_response(
            agent_addr, None), received)

        # Expect create the agent record
        received = validator.expect(factory.create_set_request(
            agent_addr, {
                'Name': 'test',
                'Type': None,
                'Url': None,
                'OwnRecords': {},
                'HoldRecords': {},
                'OpenApplications': {},
                'AcceptedApplications': {}
            }))
        validator.respond(factory.create_set_response(agent_addr), received)

        self.expect_ok()

    def expect_agent_value_update(self, agent_addr, field, record_addr, value,
                                  exists=False):
        validator = self.validator
        factory = self.factory

        initial_value = {field: {}} \
            if not exists else {field: {record_addr: 0}}
        received = validator.expect(factory.create_get_request(agent_addr))
        validator.respond(factory.create_get_response(
            agent_addr, initial_value), received)
        received = validator.expect(factory.create_set_request(
            agent_addr, {
                field: {record_addr: value}
            }))
        validator.respond(factory.create_set_response(agent_addr), received)

    def expect_agent_value_delete(self, agent_addr, field, record_addr, value):
        validator = self.validator
        factory = self.factory

        initial_value = {field: {record_addr: value}}
        received = validator.expect(factory.create_get_request(agent_addr))
        validator.respond(factory.create_get_response(
            agent_addr, initial_value), received)
        received = validator.expect(factory.create_set_request(
            agent_addr, {field: {}}))
        validator.respond(factory.create_set_response(agent_addr), received)

    def expect_ok(self):
        self.expect_tp_response('OK')

    def expect_invalid(self):
        self.expect_tp_response('INVALID_TRANSACTION')

    def expect_tp_response(self, response):
        self.validator.expect(
            self.factory.create_tp_response(
                response))


def compare_set_request(req1, req2):
    if len(req1.entries) != len(req2.entries):
        return False

    entries1 = [(e.address, json.loads(e.data.decode())) for e in req1.entries]
    entries2 = [(e.address, json.loads(e.data.decode())) for e in req2.entries]

    return entries1 == entries2

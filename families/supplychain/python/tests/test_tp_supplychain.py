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
import time

from sawtooth_sdk.protobuf.validator_pb2 import Message

from sawtooth_processor_test.transaction_processor_test_case \
    import TransactionProcessorTestCase

from sawtooth_supplychain_test.supplychain_message_factory \
    import SupplychainMessageFactory
from sawtooth_supplychain.common.addressing import Addressing


from sawtooth_supplychain.protobuf.application_pb2 import Application


LOGGER = logging.getLogger(__name__)


class TestSupplyChain(TransactionProcessorTestCase):
    @classmethod
    def setUpClass(cls):
        super(TestSupplyChain, cls).setUpClass()
        cls.validator.register_comparator(
            Message.TP_STATE_SET_REQUEST,
            compare_set_request)
        cls.factory = SupplychainMessageFactory()

    def test_agent_create(self):
        """
        Test if the supplychain processor can create an agent.
        """
        try:
            validator = self.validator
            factory = self.factory

            agent_pub_key = factory.public_key
            agent_addr = Addressing.agent_address(agent_pub_key)

            # 1. -> Send a set transaction
            #    <- Expect a state get request
            validator.send(factory.create_agent_tp_process_request("agent"))

            # Expect test for agent existance
            received = self.expect_get([agent_addr])
            self.respond_get(received, [(agent_addr, None)])

            # Expect create agent
            agent = factory.create_agent(agent_pub_key, "agent")
            received = self.expect_set([(agent_addr, agent)])
            self.respond_set(received, [agent_addr])

            self.expect_ok()
        except Exception:
            LOGGER.exception("test_agent_create exception")
            raise

    def test_record_create(self):
        """
        Test if the supplychain processor can create a record.
        """
        try:
            validator = self.validator
            factory = self.factory

            record_identifier = 'serial number'
            record_addr = Addressing.record_address(record_identifier)
            agent_pub_key = factory.public_key
            agent_addr = Addressing.agent_address(agent_pub_key)
            record_timestamp = int(time.time())

            # 1. -> Send a set transaction
            #    <- Expect a state get request
            validator.send(factory.create_record_tp_process_request(
                record_identifier, record_timestamp))

            # test for record existance
            received = self.expect_get([agent_addr, record_addr])
            agent = factory.create_agent(agent_pub_key)
            self.respond_get(received,
                             [(agent_addr, agent),
                              (record_addr, None)])

            # Expect create Record
            record = factory.create_record(record_identifier,
                                           record_timestamp)
            factory.add_agent_record(record.owners,
                                     agent_pub_key,
                                     record_timestamp)
            factory.add_agent_record(record.custodians,
                                     agent_pub_key,
                                     record_timestamp)
            received = self.expect_set([(record_addr, record)])
            self.respond_set(received, [record_addr])

            self.expect_ok()
        except Exception:
            LOGGER.exception("test_record_create exception")
            raise

    def test_create_application(self):
        """
        Test if the supplychain processor can create a application.
        """
        try:
            validator = self.validator
            factory = self.factory

            record_id = "serial number"
            record_addr = Addressing.record_address(record_id)
            agent_pub_key = factory.public_key
            agent_addr = Addressing.agent_address(agent_pub_key)
            application_addr = Addressing.application_address(record_id)
            timestamp = int(time.time())
            terms = "Please take this."

            # 1. -> Send a set transaction
            #    <- Expect a state get request
            validator.send(factory.create_application_tp_process_request(
                agent_pub_key,
                record_id,
                timestamp,
                Application.OWNER,
                terms))

            # test for record existance
            received = self.expect_get(
                [agent_addr, application_addr, record_addr])

            agent = factory.create_agent(agent_pub_key)
            record = factory.create_record(record_id)
            self.respond_get(received,
                             [(agent_addr, agent),
                              (application_addr, None),
                              (record_addr, record)])

            # Expect test for existance
            application = factory.create_application(
                record_id,
                agent_pub_key,
                Application.OWNER,
                Application.OPEN,
                timestamp,
                terms)
            received = self.expect_set([(application_addr, application)])
            self.respond_set(received, [application_addr])

            self.expect_ok()
        except Exception:
            LOGGER.exception("test_create_application exception")
            raise

    def test_application_accept(self):
        """
        Test if the supplychain processor can create a application.
        """
        try:
            validator = self.validator
            factory = self.factory

            applicant_id = "applicant pub key"

            record_id = "serial number"
            record_addr = Addressing.record_address(record_id)
            agent_pub_key = factory.public_key
            application_addr = Addressing.application_address(record_id)
            timestamp = int(time.time())

            # 1. -> Send a set transaction
            #    <- Expect a state get request
            validator.send(
                factory.create_application_accept_tp_process_request(
                    record_id,
                    applicant_id,
                    Application.OWNER,
                    timestamp))

            # test for application and record existance
            received = self.expect_get([application_addr, record_addr])
            application = factory.create_application(
                record_id,
                applicant_id,
                Application.OWNER,
                Application.OPEN)
            record = factory.create_record(record_id)
            factory.add_agent_record(record.owners, agent_pub_key)

            self.respond_get(received,
                             [(application_addr, application),
                              (record_addr, record)])

            # Update record and application
            application.status = Application.ACCEPTED
            factory.add_agent_record(record.owners, applicant_id, timestamp)
            received = self.expect_set(
                [(application_addr, application),
                 (record_addr, record)])
            self.respond_set(received,
                             [application_addr, record_addr])
            self.expect_ok()
        except Exception:
            LOGGER.exception("test_application_accept exception")
            raise

    def test_application_reject(self):
        """
        Test if the supplychain processor can reject an application.
        """
        try:
            validator = self.validator
            factory = self.factory

            applicant_id = "applicant pub key"
            record_id = "serial number"
            record_addr = Addressing.record_address(record_id)
            agent_pub_key = factory.public_key
            application_addr = Addressing.application_address(record_id)

            # 1. -> Send a set transaction
            #    <- Expect a state get request
            validator.send(
                factory.create_application_reject_tp_process_request(
                    record_id,
                    applicant_id,
                    Application.OWNER))

            # test for application and record existance
            received = self.expect_get([application_addr, record_addr])
            application = factory.create_application(
                record_id,
                applicant_id,
                Application.OWNER,
                Application.OPEN)
            record = factory.create_record(record_id)
            factory.add_agent_record(record.owners, agent_pub_key)
            self.respond_get(received,
                             [(application_addr, application),
                              (record_addr, record)])

            # Update record and application
            application.status = Application.REJECTED
            received = self.expect_set([(application_addr, application)])
            self.respond_set(received, [application_addr, record_addr])
            self.expect_ok()
        except Exception:
            LOGGER.exception("test_application_reject exception")
            raise

    def test_application_cancel(self):
        """
        Test if the supplychain processor can cancel an application.
        """
        try:
            validator = self.validator
            factory = self.factory

            record_id = "serial number"
            agent_pub_key = factory.public_key
            application_addr = Addressing.application_address(record_id)

            # 1. -> Send a set transaction
            #    <- Expect a state get request
            validator.send(
                factory.create_application_cancel_tp_process_request(
                    record_id,
                    agent_pub_key,
                    Application.OWNER))

            # test for application existance
            received = self.expect_get([application_addr])
            application = factory.create_application(
                record_id,
                agent_pub_key,
                Application.OWNER,
                Application.OPEN)
            self.respond_get(
                received,
                [(application_addr, application)])

            # Update application
            application.status = Application.CANCELED
            received = self.expect_set([(application_addr, application)])
            self.respond_set(received, [application_addr])

            self.expect_ok()
        except Exception:
            LOGGER.exception("test_application_cancel exception")
            raise

    def test_record_finalize(self):
        """
        Test if the supplychain processor can finalize a record.
        """
        try:
            validator = self.validator
            factory = self.factory

            record_id = "serial number"
            record_addr = Addressing.record_address(record_id)
            agent_pub_key = factory.public_key

            # 1. -> Send a set transaction
            #    <- Expect a state get request
            validator.send(
                factory.finalize_record_tp_process_request(
                    record_id))

            # test for record existance
            received = self.expect_get([record_addr])

            record = factory.create_record(record_id)
            factory.add_agent_record(record.owners, agent_pub_key)
            factory.add_agent_record(record.custodians, agent_pub_key)
            self.respond_get(received, [(record_addr, record)])

            # Update record
            record.final = True
            received = self.expect_set([(record_addr, record)])
            self.respond_set(received, [record_addr])

            self.expect_ok()
        except Exception:
            LOGGER.exception("test_record_finalize exception")
            raise

    def expect_get(self, addrs):
        return self.validator.expect(
            self.factory.create_get_request(addrs))

    def respond_get(self, received, values):
        self.validator.respond(
            self.factory.create_get_response(values),
            received)

    def expect_set(self, values):
        return self.validator.expect(
            self.factory.create_set_request(values))

    def respond_set(self, received, addrs):
        return self.validator.respond(
            self.factory.create_set_response(addrs), received)

    def expect_ok(self):
        self.expect_tp_response('OK')

    def expect_invalid(self):
        self.expect_tp_response('INVALID_TRANSACTION')

    def expect_tp_response(self, response):
        self.validator.expect(
            self.factory.create_tp_response(response))


def compare_set_request(req1, req2):
    if len(req1.entries) != len(req2.entries):
        return False

    entries1 = [(e.address, e.data) for e in req1.entries]
    entries2 = [(e.address, e.data) for e in req2.entries]

    return entries1 == entries2

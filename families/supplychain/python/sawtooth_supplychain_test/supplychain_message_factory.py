# Copyright 2016 Intel Corporation
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

from collections import OrderedDict

from sawtooth_processor_test.message_factory import MessageFactory
from sawtooth_supplychain.common.addressing import Addressing

from sawtooth_supplychain.processor.handler import SUPPLYCHAIN_VERSION
from sawtooth_supplychain.processor.handler import SUPPLYCHAIN_FAMILY_NAME

from sawtooth_supplychain.protobuf.agent_pb2 import AgentContainer
from sawtooth_supplychain.protobuf.agent_pb2 import Agent

from sawtooth_supplychain.protobuf.application_pb2 import ApplicationContainer
from sawtooth_supplychain.protobuf.application_pb2 import Application

from sawtooth_supplychain.protobuf.payload_pb2 import SupplyChainPayload
from sawtooth_supplychain.protobuf.payload_pb2 import AgentCreatePayload
from sawtooth_supplychain.protobuf.payload_pb2 import ApplicationCreatePayload
from sawtooth_supplychain.protobuf.payload_pb2 import ApplicationAcceptPayload
from sawtooth_supplychain.protobuf.payload_pb2 import ApplicationRejectPayload
from sawtooth_supplychain.protobuf.payload_pb2 import ApplicationCancelPayload
from sawtooth_supplychain.protobuf.payload_pb2 import RecordCreatePayload
from sawtooth_supplychain.protobuf.payload_pb2 import RecordFinalizePayload

from sawtooth_supplychain.protobuf.record_pb2 import RecordContainer
from sawtooth_supplychain.protobuf.record_pb2 import Record


class SupplychainMessageFactory(object):
    def __init__(self, private=None, public=None):
        self._factory = MessageFactory(
            encoding='application/protobuf',
            family_name=SUPPLYCHAIN_FAMILY_NAME,
            family_version=SUPPLYCHAIN_VERSION,
            namespace=[Addressing.agent_namespace(),
                       Addressing.application_namespace(),
                       Addressing.record_namespace()],
            private=private,
            public=public
        )

    @property
    def public_key(self):
        return self._factory.get_public_key()

    def _dumps(self, obj):
        if obj is not None:
            return obj.SerializeToString()
        return None

    def create_tp_register(self):
        return self._factory.create_tp_register()

    def create_tp_response(self, status):
        return self._factory.create_tp_response(status)

    def _create_txn(self, txn_function, txn, inputs=None, outputs=None):
        payload = self._dumps(txn)
        return txn_function(payload, inputs, outputs, [])

    def create_tp_process_request(self, action, data=None,
                                  inputs=None, outputs=None):
        payload = SupplyChainPayload(action=action, data=self._dumps(data))
        txn_function = self._factory.create_tp_process_request
        return self._create_txn(txn_function, payload, inputs, outputs)

    def create_get_request(self, addresses):
        return self._factory.create_get_request(addresses)

    def create_get_response(self, items):
        response = OrderedDict()
        for (addr, value) in items:
            data = None
            if value is not None:
                data = self._dumps(self._containerize(value))
            response[addr] = data
        return self._factory.create_get_response(response)

    def create_set_request(self, items):
        response = OrderedDict()
        for (addr, value) in items:
            data = None
            if value is not None:
                data = self._dumps(self._containerize(value))
            response[addr] = data
        return self._factory.create_set_request(response)

    def create_set_response(self, addresses):
        return self._factory.create_set_response(addresses)

    @staticmethod
    def _containerize(value):
        if isinstance(value, Agent):
            return AgentContainer(entries=[value])
        elif isinstance(value, Application):
            return ApplicationContainer(entries=[value])
        elif isinstance(value, Record):
            return RecordContainer(entries=[value])
        raise Exception("Unknown data type")

    def create_agent_tp_process_request(self, name):
        agent_pub_key = self.public_key
        agent_addr = Addressing.agent_address(agent_pub_key)
        inputs = [agent_addr]
        outputs = [agent_addr]

        return self.create_tp_process_request(
            SupplyChainPayload.AGENT_CREATE,
            AgentCreatePayload(name="agent"),
            inputs, outputs)

    def create_record_tp_process_request(self,
                                         identifier,
                                         timestamp):
        record_addr = Addressing.record_address(identifier)
        agent_pub_key = self.public_key
        agent_addr = Addressing.agent_address(agent_pub_key)
        inputs = [agent_addr, record_addr]
        outputs = [agent_addr, record_addr]

        return self.create_tp_process_request(
            SupplyChainPayload.RECORD_CREATE,
            RecordCreatePayload(identifier=identifier,
                                creation_time=timestamp),
            inputs, outputs)

    def finalize_record_tp_process_request(self,
                                           record_id):
        record_addr = Addressing.record_address(record_id)
        agent_pub_key = self.public_key
        agent_addr = Addressing.agent_address(agent_pub_key)
        inputs = [agent_addr, record_addr]
        outputs = [agent_addr, record_addr]

        return self.create_tp_process_request(
            SupplyChainPayload.RECORD_FINALIZE,
            RecordFinalizePayload(identifier=record_id),
            inputs, outputs)

    def create_application_tp_process_request(self,
                                              agent_pub_key,
                                              record_id,
                                              timestamp,
                                              application_type,
                                              terms=None):
        record_addr = Addressing.record_address(record_id)
        agent_pub_key = self.public_key
        agent_addr = Addressing.agent_address(agent_pub_key)
        inputs = [agent_addr, record_addr]
        outputs = [record_addr]

        return self.create_tp_process_request(
            SupplyChainPayload.APPLICATION_CREATE,
            ApplicationCreatePayload(record_identifier=record_id,
                                     creation_time=timestamp,
                                     type=application_type,
                                     terms=terms),
            inputs, outputs)

    def create_application_accept_tp_process_request(self,
                                                     record_id,
                                                     applicant_id,
                                                     application_type,
                                                     timestamp=0):
        record_addr = Addressing.record_address(record_id)
        agent_pub_key = self.public_key
        agent_addr = Addressing.agent_address(agent_pub_key)
        inputs = [agent_addr, record_addr]
        outputs = [record_addr]

        return self.create_tp_process_request(
            SupplyChainPayload.APPLICATION_ACCEPT,
            ApplicationAcceptPayload(record_identifier=record_id,
                                     applicant=applicant_id,
                                     type=application_type,
                                     timestamp=timestamp),
            inputs, outputs)

    def create_application_reject_tp_process_request(self,
                                                     record_id,
                                                     applicant_id,
                                                     application_type):
        record_addr = Addressing.record_address(record_id)
        agent_pub_key = self.public_key
        agent_addr = Addressing.agent_address(agent_pub_key)
        application_addr = Addressing.application_address(record_id)
        inputs = [agent_addr, application_addr, record_addr]
        outputs = [application_addr]

        return self.create_tp_process_request(
            SupplyChainPayload.APPLICATION_REJECT,
            ApplicationRejectPayload(record_identifier=record_id,
                                     applicant=applicant_id,
                                     type=application_type),
            inputs, outputs)

    def create_application_cancel_tp_process_request(self,
                                                     record_id,
                                                     applicant_id,
                                                     application_type):
        record_addr = Addressing.record_address(record_id)
        agent_pub_key = self.public_key
        agent_addr = Addressing.agent_address(agent_pub_key)
        application_addr = Addressing.application_address(record_id)
        inputs = [agent_addr, application_addr, record_addr]
        outputs = [application_addr]

        return self.create_tp_process_request(
            SupplyChainPayload.APPLICATION_CANCEL,
            ApplicationCancelPayload(record_identifier=record_id,
                                     applicant=applicant_id,
                                     type=application_type),
            inputs, outputs)

    def create_agent(self, identifier, name=None):
        agent = Agent(identifier=identifier)
        if name:
            agent.name = name
        return agent

    def create_record(self, identifier, timestamp=0,
                      owners=None, custodians=None, final=False):
        return Record(
            identifier=identifier,
            creation_time=timestamp,
            owners=owners or [],
            custodians=custodians or [],
            final=False)

    def add_agent_record(self, field, pub_key, timestamp=0):
        record = field.add()
        record.agent_identifier = pub_key
        record.start_time = timestamp

    def create_application(self, record_id, agent_pub_key, application_type,
                           status, timestamp=0, terms=None):
        return Application(
            record_identifier=record_id,
            applicant=agent_pub_key,
            creation_time=timestamp,
            type=application_type,
            status=status,
            terms=terms)

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

from sawtooth_sdk.processor.state import StateEntry
from sawtooth_sdk.processor.exceptions import InvalidTransaction
from sawtooth_sdk.processor.exceptions import InternalError
from sawtooth_sdk.protobuf.transaction_pb2 import TransactionHeader

from sawtooth_supplychain.common.addressing import Addressing

from sawtooth_supplychain.protobuf.payload_pb2 import SupplyChainPayload
from sawtooth_supplychain.protobuf.payload_pb2 import AgentCreatePayload
from sawtooth_supplychain.protobuf.payload_pb2 import ApplicationCreatePayload
from sawtooth_supplychain.protobuf.payload_pb2 import ApplicationAcceptPayload
from sawtooth_supplychain.protobuf.payload_pb2 import ApplicationRejectPayload
from sawtooth_supplychain.protobuf.payload_pb2 import ApplicationCancelPayload
from sawtooth_supplychain.protobuf.payload_pb2 import RecordCreatePayload
from sawtooth_supplychain.protobuf.payload_pb2 import RecordFinalizePayload

from sawtooth_supplychain.protobuf.agent_pb2 import AgentContainer

from sawtooth_supplychain.protobuf.application_pb2 import ApplicationContainer
from sawtooth_supplychain.protobuf.application_pb2 import Application

from sawtooth_supplychain.protobuf.record_pb2 import RecordContainer


LOGGER = logging.getLogger(__name__)

SUPPLYCHAIN_VERSION = '0.5'
SUPPLYCHAIN_FAMILY_NAME = 'sawtooth_supplychain'


class SupplyChainHandler(object):
    def __init__(self):
        pass

    @property
    def family_name(self):
        return SUPPLYCHAIN_FAMILY_NAME

    @property
    def family_versions(self):
        return [SUPPLYCHAIN_VERSION]

    @property
    def encodings(self):
        return ['application/protobuf']

    @property
    def namespaces(self):
        return [Addressing.agent_namespace(),
                Addressing.application_namespace(),
                Addressing.record_namespace()]

    def apply(self, transaction, state):
        try:
            txn_header = TransactionHeader()
            txn_header.ParseFromString(transaction.header)
            originator = txn_header.signer_pubkey
            payload = SupplyChainPayload()
            payload.ParseFromString(transaction.payload)

            LOGGER.debug("SupplyChainHandler.apply action: %s",
                         SupplyChainPayload.Action.Name(payload.action))

            if payload.action == SupplyChainPayload.AGENT_CREATE:
                self._agent_create(state, originator, payload.data)
            elif payload.action == SupplyChainPayload.APPLICATION_CREATE:
                self._application_create(state, originator, payload.data)
            elif payload.action == SupplyChainPayload.APPLICATION_ACCEPT:
                self._application_accept(state, originator, payload.data)
            elif payload.action == SupplyChainPayload.APPLICATION_REJECT:
                self._application_reject(state, originator, payload.data)
            elif payload.action == SupplyChainPayload.APPLICATION_CANCEL:
                self._application_cancel(state, originator, payload.data)
            elif payload.action == SupplyChainPayload.RECORD_CREATE:
                self._record_create(state, originator, payload.data)
            elif payload.action == SupplyChainPayload.RECORD_FINALIZE:
                self._record_finalize(state, originator, payload.data)
            else:
                raise InvalidTransaction('Invalid/Unknown Action')
        except Exception:
            LOGGER.exception("")
            raise

    def _agent_create(self, state, originator, data):
        txn_data = AgentCreatePayload()
        txn_data.ParseFromString(data)

        agent_addr = Addressing.agent_address(originator)
        LOGGER.debug("_agent_create: %s %s", originator, agent_addr)
        state_items = self._get(state, [agent_addr])
        agents = state_items.get(agent_addr, AgentContainer())

        # check that the agent does not exists
        agent = self._find_agent(agents, originator)
        if agent is not None:
            raise InvalidTransaction("Agent already exists.")

        # create the new agent
        agent = agents.entries.add()
        agent.identifier = originator
        agent.name = txn_data.name

        # send back the updated agents list
        self._set(state, [(agent_addr, agents)])

    def _record_create(self, state, originator, data):
        txn_data = RecordCreatePayload()
        txn_data.ParseFromString(data)

        agent_addr = Addressing.agent_address(originator)
        record_addr = Addressing.record_address(txn_data.identifier)

        state_items = self._get(state, [agent_addr, record_addr])

        agents = state_items.get(agent_addr, None)
        records = state_items.get(record_addr, RecordContainer())

        # check that the agent exists
        if self._find_agent(agents, originator) is None:
            raise InvalidTransaction("Agent is not registered.")

        # check that the record does not exists
        record = self._find_record(records, txn_data.identifier)
        if record is not None:
            raise InvalidTransaction("Record already exists.")

        # create the new record
        record = records.entries.add()
        record.identifier = txn_data.identifier
        record.creation_time = txn_data.creation_time
        owner = record.owners.add()
        owner.agent_identifier = originator
        owner.start_time = txn_data.creation_time
        custodian = record.custodians.add()
        custodian.agent_identifier = originator
        custodian.start_time = txn_data.creation_time
        record.final = False

        # send back the updated agents list
        self._set(state, [(record_addr, records)])

    def _record_finalize(self, state, originator, data):
        txn_data = RecordFinalizePayload()
        txn_data.ParseFromString(data)

        record_addr = Addressing.record_address(txn_data.identifier)

        state_items = self._get(state, [record_addr])

        records = state_items.get(record_addr, RecordContainer())

        # check that the record does not exists
        record = self._find_record(records, txn_data.identifier)
        if record is None:
            raise InvalidTransaction("Record does not exists.")

        owner = record.owners[len(record.owners) - 1]
        if owner.agent_identifier != originator:
            raise InvalidTransaction(
                "Record can only be finalized by owner.")

        custodian = record.custodians[len(record.custodians) - 1]
        if custodian.agent_identifier != originator:
            raise InvalidTransaction(
                "Application can only be finalized when the owner is the " +
                "custodian.")

        # Mark the record as final
        record.final = True

        # send back the updated agents list
        self._set(state, [(record_addr, records)])

    def _application_create(self, state, originator, data):
        txn_data = ApplicationCreatePayload()
        txn_data.ParseFromString(data)

        agent_addr = Addressing.agent_address(originator)
        record_addr = Addressing.record_address(txn_data.record_identifier)
        application_addr = Addressing.application_address(
            txn_data.record_identifier)
        state_items = self._get(state,
                                [agent_addr, application_addr, record_addr])

        # check that the agent and record exists
        agents = state_items.get(agent_addr, None)
        if self._find_agent(agents, originator) is None:
            raise InvalidTransaction("Agent is not registered.")

        records = state_items.get(record_addr, None)
        record = self._find_record(records, txn_data.record_identifier)
        if record is None:
            raise InvalidTransaction("Record does not exist.")

        if record.final:
            raise InvalidTransaction("Record is final, no updates can be " +
                                     "proposed.")

        # check that the application does not exists
        applications = state_items.get(application_addr,
                                       ApplicationContainer())
        application = self._find_application(
            applications, originator, txn_data.record_identifier,
            txn_data.type)
        if application is not None:
            raise InvalidTransaction("Application already exists.")

        # create the new application
        application = applications.entries.add()
        application.record_identifier = txn_data.record_identifier
        application.applicant = originator
        application.creation_time = txn_data.creation_time
        application.type = txn_data.type
        application.status = Application.OPEN
        application.terms = txn_data.terms

        # send back the updated application list
        self._set(state, [(application_addr, applications)])

    def _application_accept(self, state, originator, data):
        txn_data = ApplicationAcceptPayload()
        txn_data.ParseFromString(data)

        record_addr = Addressing.record_address(txn_data.record_identifier)
        application_addr = Addressing.application_address(
            txn_data.record_identifier)

        state_items = self._get(state, [application_addr, record_addr])

        # check that the application exists
        applications = state_items.get(application_addr, None)
        application = self._find_application(
            applications, txn_data.applicant, txn_data.record_identifier,
            txn_data.type)
        if application is None:
            raise InvalidTransaction("Application does not exists.")

        # check that the recorf exists
        records = state_items.get(record_addr, None)
        record = self._find_record(records, application.record_identifier)
        if record is None:
            raise InvalidTransaction("Record does not exists.")

        if record.final:
            raise InvalidTransaction("Record is final, no updates can be " +
                                     "made.")

        # verify the txn signer is qualified to accept the application
        if application.type == Application.OWNER:
            owner = record.owners[len(record.owners) - 1]
            if owner.agent_identifier != originator:
                raise InvalidTransaction(
                    "Application can only be accepted by owner.")
        elif application.type == Application.CUSTODIAN:
            custodian = record.custodians[len(record.custodians) - 1]
            if custodian.agent_identifier != originator:
                raise InvalidTransaction(
                    "Application can only be accepted by custodian.")
        else:
            raise InvalidTransaction("Invalid application type.")

        # update the application
        application.status = Application.ACCEPTED

        # update the record
        if application.type == Application.OWNER:
            agent_record = record.owners.add()
        elif application.type == Application.CUSTODIAN:
            agent_record = record.custodians.add()
        agent_record.agent_identifier = application.applicant
        agent_record.start_time = txn_data.timestamp

        # send back the updated application list
        self._set(state, [(application_addr, applications),
                          (record_addr, records)])

    def _application_cancel(self, state, originator, data):
        txn_data = ApplicationCancelPayload()
        txn_data.ParseFromString(data)

        application_addr = Addressing.application_address(
            txn_data.record_identifier)

        state_items = self._get(state, [application_addr])

        # check that the application exists
        applications = state_items.get(application_addr, None)
        application = self._find_application(
            applications, txn_data.applicant, txn_data.record_identifier,
            txn_data.type)
        if application is None:
            raise InvalidTransaction("Application does not exists.")

        # verify the txn signer is qualified to accept the application
        if application.applicant != originator:
            raise InvalidTransaction("Only Applicant can cancel Application.")

        # update the application
        application.status = Application.CANCELED

        # send back the updated application list
        self._set(state, [(application_addr, applications)])

    def _application_reject(self, state, originator, data):
        txn_data = ApplicationRejectPayload()
        txn_data.ParseFromString(data)

        record_addr = Addressing.record_address(txn_data.record_identifier)
        application_addr = Addressing.application_address(
            txn_data.record_identifier)

        state_items = self._get(state, [application_addr, record_addr])

        # check that the application exists
        applications = state_items.get(application_addr, None)
        application = self._find_application(
            applications, txn_data.applicant, txn_data.record_identifier,
            txn_data.type)
        if application is None:
            raise InvalidTransaction("Application does not exists.")

        # check that the recorf exists
        records = state_items.get(record_addr, None)
        record = self._find_record(records, application.record_identifier)
        if record is None:
            raise InvalidTransaction("Record does not exists.")

        # verify the txn signer is qualified to accept the application
        if application.type == Application.OWNER:
            owner = record.owners[len(record.owners) - 1]
            if owner.agent_identifier != originator:
                raise InvalidTransaction(
                    "Application can only be rejected by owner.")
        elif application.type == Application.CUSTODIAN:
            custodian = record.custodians[len(record.custodian) - 1]
            if custodian.agent_identifier != originator:
                raise InvalidTransaction(
                    "Application can only be rejected by custodian.")
        else:
            raise InvalidTransaction("Invalid application type.")

        # update the application
        application.status = Application.REJECTED

        # send back the updated application list
        self._set(state, [(application_addr, applications)])

    @staticmethod
    def _find_agent(agents, identifier):
        if agents is not None:
            for agent in agents.entries:
                if agent.identifier == identifier:
                    return agent
        return None

    @staticmethod
    def _find_application(applications, applicant,
                          record_identifier, application_type):
        if applications is not None:
            for application in applications.entries:
                if application.record_identifier == record_identifier and\
                        application.applicant == applicant and \
                        application.type == application_type and \
                        application.status == Application.OPEN:
                    return application
        return None

    @staticmethod
    def _find_record(records, identifier):
        if records is not None:
            for record in records.entries:
                if record.identifier == identifier:
                    return record
        return None

    @staticmethod
    def _get(state, addresses):
        entries = state.get(addresses)
        if entries:
            out = {}
            for e in entries:
                addr = e.address
                if e.data:
                    if addr.startswith(Addressing.agent_namespace()):
                        container = AgentContainer()
                    elif addr.startswith(Addressing.application_namespace()):
                        container = ApplicationContainer()
                    elif addr.startswith(Addressing.record_namespace()):
                        container = RecordContainer()
                    else:
                        raise InvalidTransaction("Unknown namespaces.")
                else:
                    container = None
                container.ParseFromString(e.data)
                out[addr] = container
            return out
        return {}

    @staticmethod
    def _set(state, items):
        entries = []
        for (addr, container) in items:
            entries.append(StateEntry(address=addr,
                                      data=container.SerializeToString()))
        result_addresses = state.set(entries)
        if result_addresses:
            for (addr, _) in items:
                if addr not in result_addresses:
                    raise InternalError("Error setting state, " +
                                        "address %s not set.", addr)
        else:
            raise InternalError("Error setting state nothing updated?")

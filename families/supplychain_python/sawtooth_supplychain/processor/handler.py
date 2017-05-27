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

from sawtooth_sdk.processor.state import StateEntry
from sawtooth_sdk.processor.exceptions import InvalidTransaction
from sawtooth_sdk.processor.exceptions import InternalError
from sawtooth_sdk.protobuf.transaction_pb2 import TransactionHeader

import sawtooth_supplychain.common.addressing as addressing


LOGGER = logging.getLogger(__name__)

SUPPLYCHAIN_VERSION = '0.5'
SUPPLYCHAIN_NAMESPACE = 'Supplychain'


def state_get_single(state, uid):
    entries_list = state.get([uid])
    if entries_list:
        return json.loads(entries_list[0].data.decode())
    return None


def state_put_single(state, uid, data):
    addresses = state.set(
        [StateEntry(address=uid,
                    data=json.dumps(data, sort_keys=True).encode())])
    if not addresses or uid not in addresses:
        raise InternalError("Error setting state, addresses returned: %s.",
                            addresses)


class SupplychainHandler(object):
    def __init__(self):
        pass

    @property
    def family_name(self):
        return 'sawtooth_supplychain'

    @property
    def family_versions(self):
        return ['1.0']

    @property
    def encodings(self):
        return ['application/json']

    @property
    def namespaces(self):
        return [addressing.get_namespace()]

    def apply(self, transaction, state):
        payload = json.loads(transaction.payload.decode())
        LOGGER.debug("SupplychainHandler.apply: %s", repr(payload))
        if payload['MessageType'] == 'Record':
            RecordHandler.apply(transaction, state)
        elif payload['MessageType'] == 'Agent':
            AgentHandler.apply(transaction, state)


class RecordHandler(object):
    @classmethod
    def apply(cls, transaction, state):
        payload = json.loads(transaction.payload.decode())

        LOGGER.debug("apply payload: %s", repr(payload))

        tnx_action = payload.get('Action', None)
        txnrecord_id = payload.get('RecordId', None)

        header = TransactionHeader()
        header.ParseFromString(transaction.header)
        tnx_originator = addressing.get_agent_id(header.signer_pubkey)

        # Retrieve the stored record data if an ID is provided.
        record_id = txnrecord_id
        record_store_key = record_id

        record_store = state_get_single(state, record_store_key)

        # Check Action
        if tnx_action == 'Create':
            if txnrecord_id is None:
                raise InvalidTransaction(
                    'Record id expected for CreateRecord')

            record_store = {}
            cls.create_record(tnx_originator, record_id, payload,
                              state, record_store)
        elif tnx_action == "CreateApplication":
            if txnrecord_id is None:
                raise InvalidTransaction(
                    'Record id expected for create_application')

            cls.create_application(tnx_originator, record_id, payload,
                                   state, record_store)
        elif tnx_action == "AcceptApplication":
            if txnrecord_id is None:
                raise InvalidTransaction(
                    'Record id expected for accept_application')

            cls.accept_application(tnx_originator, record_id, payload,
                                   state, record_store)
        elif tnx_action == "RejectApplication":
            if txnrecord_id is None:
                raise InvalidTransaction(
                    'Record id expected for reject_application')

            cls.reject_application(tnx_originator, record_id, payload,
                                   state, record_store)
        elif tnx_action == "CancelApplication":
            if txnrecord_id is None:
                raise InvalidTransaction(
                    'Record id expected for cancel_application')

            cls.cancel_application(tnx_originator, record_id, payload,
                                   state, record_store)
        elif tnx_action == "Finalize":
            if txnrecord_id is None:
                raise InvalidTransaction(
                    'Record id expected for Finalize')

            cls.finalize_record(tnx_originator, record_id, payload,
                                state, record_store)
        else:
            raise InvalidTransaction('Action {} is not valid'.
                                     format(tnx_action))

        # Store the record data back
        state_put_single(state, record_store_key, record_store)

    @classmethod
    def create_record(cls, originator, record_id, payload, state, my_store):
        sensor_id = payload.get('Sensor', None)
        sensor_idx = None
        if sensor_id is not None:
            sensor_idx = addressing.get_sensor_id(sensor_id)

        record_info = {}

        # Owner set below
        record_info['CurrentHolder'] = originator
        # Custodians set below
        record_info['Parents'] = payload.get('Parents', None)
        record_info['Timestamp'] = payload.get('Timestamp')
        record_info['Sensor'] = sensor_idx
        record_info['Final'] = False
        record_info['ApplicationFrom'] = None
        record_info['ApplicationType'] = None
        record_info['ApplicationTerms'] = None
        record_info['ApplicationStatus'] = None
        record_info['EncryptedConsumerAcccessible'] = None
        record_info['EncryptedOwnerAccessible'] = None

        my_store['RecordInfo'] = record_info
        my_store['StoredTelemetry'] = payload.get('Telemetry', {})
        my_store['DomainAttributes'] = payload.get('DomainAttributes', {})

        # Determine if this record has parents
        has_parents = record_info['Parents'] is not None and \
            len(record_info['Parents']) > 0

        # If there are parents update Owner and Custodian depending on the
        # ApplicationType
        if has_parents:
            # Use the first parent
            parent_id = record_info['Parents'][0]
            parent_store = state_get_single(state, parent_id)
            if parent_store['RecordInfo']['ApplicationType'] == "Owner":
                # Transfer ownership - in this case there should be
                # no custodians.
                if not parent_store['RecordInfo']['Custodians']:
                    raise InvalidTransaction(
                        "Cannot transfer ownership when custodian is present")
                record_info['Owner'] = originator
                record_info['Custodians'] = []
            else:
                # Transfer custodianship
                record_info['Owner'] = \
                    parent_store['RecordInfo']['Owner']
                record_info['Custodians'] = \
                    list(parent_store['RecordInfo']['Custodians'])

                # Check the next to last element of the Custodians array. If it
                # is the new holder, then this is a 'pop' operation. It's also
                # a pop if here is one custodian and the applicant is the
                # owner.
                is_pop = False
                if len(record_info['Custodians']) > 1 and \
                   record_info['Custodians'][-2] == originator:
                    is_pop = True
                elif len(record_info['Custodians']) == 1 and \
                        record_info['Owner'] == originator:
                    is_pop = True

                if is_pop:
                    record_info['Custodians'].pop()
                else:
                    record_info['Custodians'].append(originator)
        else:
            # No parents, just create a new record
            record_info['Owner'] = originator
            record_info['Custodians'] = []

        # If there are parents mark them as final.
        if has_parents:
            for parent in record_info['Parents']:
                parent_store = state_get_single(state, parent)
                parent_store['RecordInfo']['Final'] = True
                state_put_single(state, parent, parent_store)

                # Remove the record from the former owner - even if this
                # is a custodian transfer we need to store the new
                # record ID with the owner.
                AgentHandler.remove_record_owner(
                    state,
                    parent_store['RecordInfo']["Owner"],
                    parent)

                # Remove the previous holder
                AgentHandler.remove_record_holder(
                    state,
                    parent_store['RecordInfo']["CurrentHolder"],
                    parent)

                # Remove the accepted application from the new owner
                AgentHandler.remove_accepted_application(
                    state,
                    parent_store['RecordInfo']['ApplicationFrom'],
                    parent)

        # Record the owner of the new record in the agent
        AgentHandler.add_record_owner(
            state, record_info["Owner"], record_id,
            record_info["Owner"] == record_info["CurrentHolder"])
        # Record the new record holder in the agent
        AgentHandler.add_record_holder(
            state, record_info["CurrentHolder"], record_id)

        # Register the sensor
        if sensor_id is not None:
            if state_get_single(state, sensor_idx) is not None:
                sensor_store = state_get_single(state, sensor_idx)
            else:
                sensor_store = {}
            sensor_store["Record"] = record_id
            sensor_store["Name"] = sensor_id
            state_put_single(state, sensor_idx, sensor_store)

    @classmethod
    def create_application(cls, originator, record_id,
                           payload, state, my_store):
        LOGGER.debug('create_application: %s', my_store)
        record_info = my_store['RecordInfo']
        LOGGER.debug(record_info)
        # Agent ID who initiated the application
        record_info['ApplicationFrom'] = originator
        # custodian or owner
        record_info['ApplicationType'] = payload['ApplicationType']
        # Should be encrypted?
        record_info['ApplicationTerms'] = payload['ApplicationTerms']
        # To indicate acceptance (or not) of the application.
        record_info['ApplicationStatus'] = "Open"
        LOGGER.debug(record_info)
        # Record the new application in the current holder
        AgentHandler.add_open_application(state,
                                          record_info['ApplicationFrom'],
                                          record_info['CurrentHolder'],
                                          record_id)

    @classmethod
    def accept_application(cls, originator, record_id, payload, state,
                           my_store):
        # Mark the application as accepted. After this the new
        # owner/custodian is able to make a new record with this
        # record as the parent.
        record_info = my_store['RecordInfo']
        record_info['ApplicationStatus'] = "Accepted"

        # Record the accepted application in the new holder
        AgentHandler.remove_open_application(state,
                                             record_info['ApplicationFrom'],
                                             record_info['CurrentHolder'],
                                             record_id)
        AgentHandler.add_accepted_application(state,
                                              record_info['ApplicationFrom'],
                                              record_id,
                                              record_info['Sensor'])

    @classmethod
    def reject_application(cls, originator, record_id, payload, state,
                           my_store):
        # Mark the application as rejected.
        record_info = my_store['RecordInfo']
        record_info['ApplicationStatus'] = "Rejected"

        # Record the rejected application in the agent
        AgentHandler.remove_open_application(state,
                                             record_info['ApplicationFrom'],
                                             record_info['CurrentHolder'],
                                             record_id)

    @classmethod
    def cancel_application(cls, originator, record_id, payload, state,
                           my_store):
        # Mark the application as cancelled.
        record_info = my_store['RecordInfo']
        record_info['ApplicationStatus'] = "Cancelled"

        # Record the cancelled application in the agent
        AgentHandler.remove_open_application(state,
                                             record_info['ApplicationFrom'],
                                             record_info['CurrentHolder'],
                                             record_id)

    @classmethod
    def finalize_record(cls, originator, record_id, payload, state, my_store):
        record_info = my_store['RecordInfo']
        record_info['Final'] = True
        # Remove the record from the agent
        if record_info['Owner'] != originator:
            raise InvalidTransaction('Only the current owner can finalize')

        if record_info['CurrentHolder'] != originator:
            raise InvalidTransaction('Only the current holder can finalize')

        AgentHandler.remove_record_owner(state, originator, record_id)
        AgentHandler.remove_record_holder(state, originator, record_id)


class AgentHandler(object):
    @classmethod
    def apply(cls, transaction, state):
        payload = json.loads(transaction.payload.decode())

        LOGGER.debug("AgentHandler.apply payload: %s", repr(payload))

        tnx_action = payload.get('Action', None)
        tnx_name = payload.get('Name', None)
        tnx_type = payload.get('Type', None)
        tnx_url = payload.get('Url', None)

        header = TransactionHeader()
        header.ParseFromString(transaction.header)
        uid = addressing.get_agent_id(header.signer_pubkey)

        if tnx_name is None or tnx_name == '':
            raise InvalidTransaction('Name not set')

        if tnx_action == "Create":
            LOGGER.debug("AgentHandler.apply CREATE")
            if state_get_single(state, uid) is not None:
                raise InvalidTransaction('Agent ID already registered')

            my_store = {}
            my_store['Name'] = tnx_name
            my_store['Type'] = tnx_type
            my_store['Url'] = tnx_url
            my_store['OwnRecords'] = {}
            my_store['HoldRecords'] = {}
            my_store['OpenApplications'] = {}
            my_store['AcceptedApplications'] = {}

            state_put_single(state, uid, my_store)
        else:
            raise InvalidTransaction('Action {} is not valid'.
                                     format(tnx_action))

    @classmethod
    def update_record_tracking(cls, state, agent_id, updates):
        state_id = agent_id
        my_store = state_get_single(state, state_id)
        if my_store is None:
            raise InvalidTransaction("Identifer {} is not present in store".
                                     format(state_id))
        for update in updates:
            (field, record_id, value, exists_is_ok) = update
            if value == "del":
                if record_id not in my_store[field]:
                    raise InvalidTransaction(
                        "Record {} is not present in state".format(record_id))
                del my_store[field][record_id]
            else:
                if not exists_is_ok and record_id in my_store[field]:
                    raise InvalidTransaction(
                        "Record {} is already present in state".
                        format(record_id))
                my_store[field][record_id] = value
        state_put_single(state, state_id, my_store)

    @classmethod
    def add_record_owner(cls, state, identifier, record_id, own_and_hold):
        value = 1 if own_and_hold else 0
        AgentHandler.update_record_tracking(
            state, identifier, [("OwnRecords", record_id, value, True)])

    @classmethod
    def remove_record_owner(cls, state, identifier, record_id):
        AgentHandler.update_record_tracking(
            state, identifier, [("OwnRecords", record_id, "del", False)])

    @classmethod
    def add_record_holder(cls, state, identifier, record_id):
        AgentHandler.update_record_tracking(
            state, identifier, [("HoldRecords", record_id, 0, False)])

    @classmethod
    def remove_record_holder(cls, state, identifier, record_id):
        AgentHandler.update_record_tracking(
            state, identifier, [("HoldRecords", record_id, "del", False)])

    @classmethod
    def add_open_application(cls, state, applier_id, holder_id, record_id):
        AgentHandler.update_record_tracking(
            state, applier_id, [("OpenApplications", record_id, 1, False)])
        AgentHandler.update_record_tracking(
            state, holder_id, [("HoldRecords", record_id, 1, True)])

    @classmethod
    def remove_open_application(cls, state, applier_id, holder_id, record_id):
        AgentHandler.update_record_tracking(
            state, applier_id,
            [("OpenApplications", record_id, "del", False)])
        AgentHandler.update_record_tracking(
            state, holder_id,
            [("HoldRecords", record_id, 0, True)])

    @classmethod
    def add_accepted_application(cls, state, identifier, record_id, sensor_id):
        AgentHandler.update_record_tracking(
            state, identifier,
            [("AcceptedApplications", record_id, sensor_id, False)])

    @classmethod
    def remove_accepted_application(cls, state, identifier, record_id):
        AgentHandler.update_record_tracking(
            state, identifier,
            [("AcceptedApplications", record_id, "del", False)])

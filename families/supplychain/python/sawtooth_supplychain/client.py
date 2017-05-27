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

import base64
import hashlib
import json
import logging
import time
import requests

import sawtooth_signing.secp256k1_signer as signing

from sawtooth_sdk.protobuf.transaction_pb2 import TransactionHeader
from sawtooth_sdk.protobuf.transaction_pb2 import Transaction
from sawtooth_sdk.protobuf.batch_pb2 import BatchList
from sawtooth_sdk.protobuf.batch_pb2 import BatchHeader
from sawtooth_sdk.protobuf.batch_pb2 import Batch

from sawtooth_supplychain.common.addressing import Addressing
from sawtooth_supplychain.common.exceptions import SupplyChainException


from sawtooth_supplychain.protobuf.agent_pb2 import Agent
from sawtooth_supplychain.protobuf.agent_pb2 import AgentContainer
from sawtooth_supplychain.protobuf.application_pb2 import Application
from sawtooth_supplychain.protobuf.application_pb2 import ApplicationContainer
from sawtooth_supplychain.protobuf.record_pb2 import Record
from sawtooth_supplychain.protobuf.record_pb2 import RecordContainer

from sawtooth_supplychain.protobuf.payload_pb2 import SupplyChainPayload
from sawtooth_supplychain.protobuf.payload_pb2 import AgentCreatePayload
from sawtooth_supplychain.protobuf.payload_pb2 import ApplicationCreatePayload
from sawtooth_supplychain.protobuf.payload_pb2 import ApplicationAcceptPayload
from sawtooth_supplychain.protobuf.payload_pb2 import ApplicationRejectPayload
from sawtooth_supplychain.protobuf.payload_pb2 import ApplicationCancelPayload
from sawtooth_supplychain.protobuf.payload_pb2 import RecordCreatePayload
from sawtooth_supplychain.protobuf.payload_pb2 import RecordFinalizePayload

LOGGER = logging.getLogger(__name__)


def _sha512(data):
    return hashlib.sha512(data).hexdigest()


def _b64_dec(data):
    return base64.b64decode(data)


def _pb_dumps(obj):
    return obj.SerializeToString()


def _pb_loads(obj, encoded):
    obj.ParseFromString(encoded)
    return obj


def _decode_agent_container(encoded):
    return _pb_loads(AgentContainer(), encoded)


def _decode_agent(encoded):
    return _pb_loads(Agent(), encoded)


def _decode_application_container(encoded):
    return _pb_loads(ApplicationContainer(), encoded)


def _decode_application(encoded):
    return _pb_loads(Application(), encoded)


def _decode_record_container(encoded):
    return _pb_loads(RecordContainer(), encoded)


def _decode_record(encoded):
    return _pb_loads(Record(), encoded)


class SupplyChainClient(object):
    def __init__(self, base_url, keyfile):
        self._base_url = base_url
        try:
            with open(keyfile) as fd:
                self._private_key = fd.read().strip()
                fd.close()
        except:
            raise IOError("Failed to read keys.")

        self._public_key = signing.generate_pubkey(self._private_key)

    @property
    def public_key(self):
        return self._public_key

    def agent_create(self, name, wait=None):
        addrs = [Addressing.agent_address(self._public_key)]
        return self._send_txn(
            SupplyChainPayload.AGENT_CREATE,
            AgentCreatePayload(name=name),
            addrs, addrs, wait=wait)

    def agent_list(self):
        result = self._send_get("state?address={}".format(
            Addressing.agent_namespace()))
        try:
            data = self._get_result_list(result)
            out = []
            for state_obj in data:
                container = _decode_agent_container(
                    _b64_dec(state_obj['data']))
                out.extend(container.entries)
            return out
        except BaseException:
            return None

    def agent_get(self, public_key):
        address = Addressing.agent_address(public_key)
        result = self._send_get("state/{}".format(address))
        try:
            data = self._get_result_data(result)
            agents = _decode_agent_container(data)
            return next((agent for agent in agents.entries
                         if agent.identifier == public_key), None)
        except BaseException:
            return None

    def application_create(self, record_identifier, application_type,
                           terms="", creation_time=None, wait=None):
        outputs = [Addressing.application_address(record_identifier)]
        inputs = outputs + [Addressing.agent_address(self.public_key),
                            Addressing.record_address(record_identifier)]
        return self._send_txn(
            SupplyChainPayload.APPLICATION_CREATE,
            ApplicationCreatePayload(
                record_identifier=record_identifier,
                creation_time=creation_time or int(time.time()),
                type=application_type,
                terms=terms),
            inputs=inputs, outputs=outputs, wait=wait)

    def application_list(self):
        result = self._send_get("state?address={}".format(
            Addressing.application_namespace()))
        try:
            data = self._get_result_list(result)
            out = []
            for state_obj in data:
                container = _decode_application_container(
                    _b64_dec(state_obj['data']))
                out.extend(container.entries)
            return out
        except BaseException:
            return None

    def application_get(self, record_identifier, applicant,
                        application_type):
        address = Addressing.application_address(record_identifier)
        result = self._send_get("state/{}".format(address))

        try:
            data = self._get_result_data(result)
            applications = _decode_application_container(data)
            return next((app for app in applications.entries
                         if app.record_identifier == record_identifier and
                         app.applicant == applicant and
                         app.type == application_type
                         ), None)
        except BaseException:
            return None

    def application_accept(self, record_identifier,
                           applicant, application_type,
                           timestamp=None, wait=None):
        outputs = [Addressing.application_address(record_identifier),
                   Addressing.record_address(record_identifier)]
        inputs = outputs + [Addressing.agent_address(self.public_key),
                            Addressing.record_address(record_identifier)]
        return self._send_txn(
            SupplyChainPayload.APPLICATION_ACCEPT,
            ApplicationAcceptPayload(
                record_identifier=record_identifier,
                applicant=applicant,
                type=application_type,
                timestamp=timestamp or time.time()),
            inputs=inputs, outputs=outputs, wait=wait)

    def application_reject(self, record_identifier, applicant_public_key,
                           application_type, wait=None):
        outputs = [Addressing.application_address(record_identifier),
                   Addressing.record_address(record_identifier)]
        inputs = outputs + [Addressing.agent_address(self.public_key),
                            Addressing.record_address(record_identifier)]
        return self._send_txn(
            SupplyChainPayload.APPLICATION_REJECT,
            ApplicationRejectPayload(
                record_identifier=record_identifier,
                applicant=applicant_public_key,
                type=application_type),
            inputs=inputs, outputs=outputs, wait=wait)

    def application_cancel(self, record_identifier, application_type,
                           wait=None):
        outputs = [Addressing.application_address(record_identifier),
                   Addressing.record_address(record_identifier)]
        inputs = outputs + [Addressing.agent_address(self.public_key),
                            Addressing.record_address(record_identifier)]
        return self._send_txn(
            SupplyChainPayload.APPLICATION_CANCEL,
            ApplicationCancelPayload(
                record_identifier=record_identifier,
                applicant=self._public_key,
                type=application_type),
            inputs=inputs, outputs=outputs, wait=wait)

    def record_create(self, record_identifier, creation_time=None, wait=None):
        outputs = [Addressing.record_address(record_identifier)]
        inputs = outputs + \
            [Addressing.agent_address(self._public_key)]

        return self._send_txn(
            SupplyChainPayload.RECORD_CREATE,
            RecordCreatePayload(
                identifier=record_identifier,
                creation_time=creation_time or int(time.time())),
            inputs=inputs, outputs=outputs, wait=wait)

    def record_list(self):
        result = self._send_get("state?address={}".format(
            Addressing.record_namespace()))
        try:
            data = self._get_result_list(result)
            out = []
            for state_obj in data:
                container = _decode_record_container(
                    _b64_dec(state_obj['data']))
                out.extend(container.entries)
            return out
        except BaseException:
            return None

    def record_get(self, public_key):
        address = Addressing.record_address(public_key)
        result = self._send_get("state/{}".format(address))

        try:
            data = self._get_result_data(result)
            records = _decode_record_container(data)
            return next((record for record in records.entries
                         if record.identifier == public_key), None)
        except BaseException:
            return None

    def record_finalize(self, record_identifier, wait=None):
        addrs = [Addressing.record_address(record_identifier)]
        return self._send_txn(
            SupplyChainPayload.RECORD_FINALIZE,
            RecordFinalizePayload(identifier=record_identifier),
            addrs, addrs, wait=wait)

    @staticmethod
    def _get_result_data(result_json):
        result = json.loads(result_json)
        return _b64_dec(result['data'])

    @staticmethod
    def _get_result_list(result_json):
        result = json.loads(result_json)
        return result['data']

    def _send_post(self, suffix, data, content_type=None, wait=None):
        wait_param = '?wait={}'.format(wait) if wait and wait > 0 else ''
        url = "http://{}/{}{}".format(self._base_url, suffix, wait_param)
        LOGGER.info(url)
        headers = None
        if content_type is not None:
            headers = {'Content-Type': content_type}

        try:
            result = requests.post(url, headers=headers, data=data)
            if not result.ok:
                raise SupplyChainException("Error {}: {}".format(
                    result.status_code, result.reason))

        except BaseException as err:
            raise SupplyChainException(err)

        return result.text

    def _send_get(self, suffix):
        url = "http://{}/{}".format(self._base_url, suffix)
        LOGGER.info(url)
        try:
            result = requests.get(url)
            if not result.ok:
                raise SupplyChainException("Error {}: {}".format(
                    result.status_code, result.reason))

        except BaseException as err:
            raise SupplyChainException(err)

        return result.text

    def _send_txn(self, action, action_payload, inputs=None, outputs=None,
                  wait=None):
        payload = _pb_dumps(
            SupplyChainPayload(action=action, data=_pb_dumps(action_payload)))

        header = TransactionHeader(
            signer_pubkey=self._public_key,
            family_name="sawtooth_supplychain",
            family_version="0.5",
            inputs=inputs or [],
            outputs=outputs or [],
            dependencies=[],
            payload_encoding='application/protobuf',
            payload_sha512=_sha512(payload),
            batcher_pubkey=self._public_key,
            nonce=time.time().hex().encode()
        ).SerializeToString()

        signature = signing.sign(header, self._private_key)

        transaction = Transaction(
            header=header,
            payload=payload,
            header_signature=signature
        )

        batch_list = self._create_batch_list([transaction])

        result = self._send_post(
            "batches", batch_list.SerializeToString(),
            'application/octet-stream',
            wait=wait)

        return result

    def _create_batch_list(self, transactions):
        transaction_signatures = [t.header_signature for t in transactions]

        header = BatchHeader(
            signer_pubkey=self._public_key,
            transaction_ids=transaction_signatures
        ).SerializeToString()

        signature = signing.sign(header, self._private_key)

        batch = Batch(
            header=header,
            transactions=transactions,
            header_signature=signature
        )
        return BatchList(batches=[batch])

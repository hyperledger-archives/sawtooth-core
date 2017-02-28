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

import hashlib
import time

from sawtooth_signing import secp256k1_signer as signing

from sawtooth_sdk.protobuf.processor_pb2 import TpRegisterRequest
from sawtooth_sdk.protobuf.processor_pb2 import TpProcessResponse
from sawtooth_sdk.protobuf.processor_pb2 import TpProcessRequest

from sawtooth_sdk.protobuf.transaction_pb2 import Transaction
from sawtooth_sdk.protobuf.transaction_pb2 import TransactionHeader

from sawtooth_sdk.protobuf.batch_pb2 import Batch
from sawtooth_sdk.protobuf.batch_pb2 import BatchList
from sawtooth_sdk.protobuf.batch_pb2 import BatchHeader

from sawtooth_sdk.protobuf.state_context_pb2 import TpStateGetResponse
from sawtooth_sdk.protobuf.state_context_pb2 import TpStateGetRequest
from sawtooth_sdk.protobuf.state_context_pb2 import TpStateSetResponse
from sawtooth_sdk.protobuf.state_context_pb2 import TpStateSetRequest
from sawtooth_sdk.protobuf.state_context_pb2 import Entry


def _private():
    return signing.generate_privkey()


def _private_to_public(private):
    return signing.generate_pubkey(private)


def _sign(content, private):
    return signing.sign(content, private)


class MessageFactory(object):
    def __init__(self, encoding, family_name, family_version,
                 namespace, private=None, public=None):
        self.encoding = encoding
        self.family_name = family_name
        self.family_version = family_version
        self.namespace = namespace

        if private is None:
            private = _private()

        if public is None:
            public = _private_to_public(private)

        self._private = private
        self._public = public

    def sha512(self, content):
        return hashlib.sha512(content).hexdigest()

    def sha256(self, content):
        return hashlib.sha256(content).hexdigest()

    def get_public_key(self):
        return self._public

    def create_tp_register(self):
        return TpRegisterRequest(
            family=self.family_name,
            version=self.family_version,
            encoding=self.encoding,
            namespaces=[self.namespace]
        )

    def create_tp_response(self, status):
        responses = {
            "OK":
                TpProcessResponse.OK,
            "INVALID_TRANSACTION":
                TpProcessResponse.INVALID_TRANSACTION,
            "INTERNAL_ERROR":
                TpProcessResponse.INTERNAL_ERROR
        }
        return TpProcessResponse(status=responses[status])

    def _create_transaction_header(self, payload, inputs, outputs, deps):
        return TransactionHeader(
            signer_pubkey=self._public,
            family_name=self.family_name,
            family_version=self.family_version,
            inputs=inputs,
            outputs=outputs,
            dependencies=deps,
            payload_encoding=self.encoding,
            payload_sha512=self.sha512(payload),
            batcher_pubkey=self._public,
            nonce=str(time.time())
        ).SerializeToString()

    def _create_signature(self, header):
        return _sign(header, self._private)

    def _create_header_and_sig(self, payload, inputs, outputs, deps):
        header = self._create_transaction_header(
            payload, inputs, outputs, deps)
        signature = self._create_signature(header)
        return header, signature

    def create_transaction(self, payload, inputs, outputs, deps):
        header, signature = self._create_header_and_sig(
            payload, inputs, outputs, deps)

        return Transaction(
            header=header,
            payload=payload,
            header_signature=signature)

    def create_tp_process_request(self, payload, inputs, outputs, deps):
        header, signature = self._create_header_and_sig(
            payload, inputs, outputs, deps)

        return TpProcessRequest(
            header=header,
            payload=payload,
            signature=signature)

    def create_batch(self, transactions):
        # Transactions have a header_signature;
        # TpProcessRequests have a signature
        try:
            txn_signatures = [txn.header_signature for txn in transactions]
        except AttributeError:
            txn_signatures = [txn.signature for txn in transactions]

        header = BatchHeader(
            signer_pubkey=self._public,
            transaction_ids=txn_signatures
        ).SerializeToString()

        signature = _sign(header, self._private)

        batch = Batch(
            header=header,
            transactions=transactions,
            header_signature=signature)

        batch_list = BatchList(batches=[batch])

        return batch_list.SerializeToString()

    def create_get_request(self, addresses):
        return TpStateGetRequest(
            addresses=addresses
        )

    def create_get_response(self, address_data_map):

        # Each Entry has an address, and data.
        # Data can be anything, but transaction processors may assum a
        # certain data type. For example, intkey assumes a dictionary
        # with "Name" in it and stores the "Value". A dictionary is
        # used to deal with hash collisions.

        # GetResponse object has a list of Entry objects
        entries = [
            Entry(address=address, data=data)
            for address, data in address_data_map.items()
        ]

        # Create a GetResponse object
        return TpStateGetResponse(
            entries=entries
        )

    def create_set_request(self, address_data_map):
        entries = [
            Entry(address=address, data=data)
            for address, data in address_data_map.items()
        ]

        return TpStateSetRequest(
            entries=entries
        )

    def create_set_response(self, addresses):
        return TpStateSetResponse(
            addresses=addresses
        )

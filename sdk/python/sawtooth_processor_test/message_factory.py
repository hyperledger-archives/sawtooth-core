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
import bitcoin

from sawtooth_protobuf.processor_pb2 import TransactionProcessorRegisterRequest
from sawtooth_protobuf.processor_pb2 import TransactionProcessResponse

from sawtooth_protobuf.transaction_pb2 import TransactionHeader
from sawtooth_protobuf.transaction_pb2 import Transaction

from sawtooth_protobuf.state_context_pb2 import GetResponse
from sawtooth_protobuf.state_context_pb2 import GetRequest
from sawtooth_protobuf.state_context_pb2 import SetResponse
from sawtooth_protobuf.state_context_pb2 import SetRequest
from sawtooth_protobuf.state_context_pb2 import Entry


def _private():
    return bitcoin.random_key()


def _private_to_public(private):
    return bitcoin.encode_pubkey(
        bitcoin.privkey_to_pubkey(private), "hex"
    )


def _sign(content, private):
    return bitcoin.ecdsa_sign(content, private)


class MessageFactory:
    def __init__(
        self, encoding, family_name, family_version, namespace,
        private=None, public=None
    ):
        self._encoding = encoding
        self._family_name = family_name
        self._family_version = family_version
        self._namespace = namespace

        if private is None:
            private = _private()

        if public is None:
            public = _private_to_public(private)

        self._private = private
        self._public = public

    def _sha512(self, content):
        return hashlib.sha512(content).hexdigest()

    def get_public_key(self):
        return self._public

    def create_tp_register(self):
        return TransactionProcessorRegisterRequest(
            family=self._family_name,
            version=self._family_version,
            encoding=self._encoding,
            namespaces=[self._namespace]
        )

    def create_tp_response(self, status):
        d = {
            "OK":
                TransactionProcessResponse.OK,
            "INVALID_TRANSACTION":
                TransactionProcessResponse.INVALID_TRANSACTION,
            "INTERNAL_ERROR":
                TransactionProcessResponse.INTERNAL_ERROR
        }
        return TransactionProcessResponse(status=d[status])

    def create_transaction(self, payload, inputs, outputs, dependencies):

        header = TransactionHeader(
            signer=self._public,
            family_name=self._family_name,
            family_version=self._family_version,
            inputs=inputs,
            outputs=outputs,
            dependencies=dependencies,
            payload_encoding=self._encoding,
            payload_sha512=self._sha512(payload),
            batcher=self._public
        ).SerializeToString()

        signature = _sign(header, self._private)

        return Transaction(
            header=header,
            payload=payload,
            signature=signature
        )

    def create_get_request(self, addresses):
        return GetRequest(
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
        return GetResponse(
            entries=entries
        )

    def create_set_request(self, address_data_map):
        entries = [
            Entry(address=address, data=data)
            for address, data in address_data_map.items()
        ]

        return SetRequest(
            entries=entries
        )

    def create_set_response(self, addresses):
        return SetResponse(
            addresses=addresses
        )

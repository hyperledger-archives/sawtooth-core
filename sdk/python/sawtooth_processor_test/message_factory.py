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
import string
import time

from sawtooth_signing import create_context
from sawtooth_signing import CryptoFactory

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
from sawtooth_sdk.protobuf.state_context_pb2 import TpStateDeleteResponse
from sawtooth_sdk.protobuf.state_context_pb2 import TpStateDeleteRequest
from sawtooth_sdk.protobuf.state_context_pb2 import TpEventAddRequest
from sawtooth_sdk.protobuf.state_context_pb2 import TpEventAddResponse
from sawtooth_sdk.protobuf.state_context_pb2 import TpStateEntry

from sawtooth_sdk.protobuf.events_pb2 import Event


class InvalidMerkleAddressException(Exception):
    pass


def is_valid_merkle_address(address):
    return all(c in string.hexdigits.lower() for c in address) and \
        len(address) == 70


def _signer():
    context = create_context('secp256k1')
    return CryptoFactory(context).new_signer(
        context.new_random_private_key())


class MessageFactory(object):
    def __init__(self, family_name, family_version, namespace, signer=None):
        self.family_name = family_name
        self.family_version = family_version
        if isinstance(namespace, (list)):
            self.namespaces = namespace
        else:
            self.namespaces = [namespace]

        if signer is None:
            signer = _signer()

        self._signer = signer

    @property
    def namespace(self):
        return self.namespaces[0]

    @staticmethod
    def sha512(content):
        return hashlib.sha512(content).hexdigest()

    @staticmethod
    def sha256(content):
        return hashlib.sha256(content).hexdigest()

    def get_public_key(self):
        return self._signer.get_public_key().as_hex()

    def create_tp_register(self):
        return TpRegisterRequest(
            family=self.family_name,
            version=self.family_version,
            namespaces=self.namespaces)

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

    def _create_transaction_header(self, payload, inputs, outputs, deps,
                                   set_nonce=True, batcher_pub_key=None):

        if set_nonce:
            nonce = str(time.time())
        else:
            nonce = ""
        txn_pub_key = self._signer.get_public_key().as_hex()
        if batcher_pub_key is None:
            batcher_pub_key = txn_pub_key

        header = TransactionHeader(
            signer_public_key=txn_pub_key,
            family_name=self.family_name,
            family_version=self.family_version,
            inputs=inputs,
            outputs=outputs,
            dependencies=deps,
            payload_sha512=self.sha512(payload),
            batcher_public_key=batcher_pub_key,
            nonce=nonce
        )
        return header

    def _create_signature(self, header):
        return self._signer.sign(header)

    def _create_header_and_sig(self, payload, inputs, outputs, deps,
                               set_nonce=True, batcher=None):
        header = self._create_transaction_header(
            payload, inputs, outputs, deps, set_nonce, batcher)
        signature = self._create_signature(header.SerializeToString())
        return header, signature

    def create_transaction(self, payload, inputs, outputs, deps, batcher=None):
        header, signature = self._create_header_and_sig(
            payload, inputs, outputs, deps, batcher=batcher)

        return Transaction(
            header=header.SerializeToString(),
            payload=payload,
            header_signature=signature)

    @staticmethod
    def _validate_addresses(addresses):
        for a in addresses:
            if not is_valid_merkle_address(a):
                raise InvalidMerkleAddressException(
                    "{} is not a valid merkle trie address".format(a))

    def create_tp_process_request(self, payload, inputs, outputs, deps,
                                  set_nonce=True):
        header, signature = self._create_header_and_sig(
            payload, inputs, outputs, deps, set_nonce)

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
            signer_public_key=self._signer.get_public_key().as_hex(),
            transaction_ids=txn_signatures
        ).SerializeToString()

        signature = self._signer.sign(header)

        batch = Batch(
            header=header,
            transactions=transactions,
            header_signature=signature)

        batch_list = BatchList(batches=[batch])

        return batch_list.SerializeToString()

    def create_get_request(self, addresses):
        self._validate_addresses(addresses)
        return TpStateGetRequest(
            addresses=addresses
        )

    def create_get_response(self, address_data_map):

        # Each TpStateEntry has an address, and data.
        # Data can be anything, but transaction processors may assum a
        # certain data type. For example, intkey assumes a dictionary
        # with "Name" in it and stores the "Value". A dictionary is
        # used to deal with hash collisions.

        # GetResponse object has a list of TpStateEntry objects

        self._validate_addresses(
            [address for address, _ in address_data_map.items()])

        entries = [
            TpStateEntry(address=address, data=data)
            for address, data in address_data_map.items()
        ]

        # Create a GetResponse object
        return TpStateGetResponse(
            entries=entries
        )

    def create_set_request(self, address_data_map):
        self._validate_addresses(
            [address for address, _ in address_data_map.items()])

        entries = [
            TpStateEntry(address=address, data=data)
            for address, data in address_data_map.items()
        ]

        return TpStateSetRequest(
            entries=entries
        )

    def create_set_response(self, addresses):
        self._validate_addresses(addresses)
        return TpStateSetResponse(
            addresses=addresses
        )

    def create_delete_request(self, addresses):
        self._validate_addresses(addresses)
        return TpStateDeleteRequest(
            addresses=addresses
        )

    def create_delete_response(self, addresses):
        self._validate_addresses(addresses)
        return TpStateDeleteResponse(
            addresses=addresses
        )

    def create_add_event_request(self, event_type, attributes=None, data=None):
        attribute_list = []
        for attribute in attributes:
            attribute_list.append(
                Event.Attribute(key=attribute[0], value=attribute[1]))
        return TpEventAddRequest(
            event=Event(
                event_type=event_type,
                attributes=attribute_list,
                data=data))

    def create_add_event_response(self):
        return TpEventAddResponse(
            status=TpEventAddResponse.OK)

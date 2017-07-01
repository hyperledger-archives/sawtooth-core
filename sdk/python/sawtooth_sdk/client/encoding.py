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

from hashlib import sha512
from random import randint
from google.protobuf.message import DecodeError

from sawtooth_signing.secp256k1_signer import sign
from sawtooth_signing.secp256k1_signer import generate_pubkey
from sawtooth_sdk.protobuf.batch_pb2 import Batch
from sawtooth_sdk.protobuf.batch_pb2 import BatchHeader
from sawtooth_sdk.protobuf.batch_pb2 import BatchList
from sawtooth_sdk.protobuf.transaction_pb2 import Transaction
from sawtooth_sdk.protobuf.transaction_pb2 import TransactionHeader
from sawtooth_sdk.protobuf.transaction_pb2 import TransactionList


def _listify(item_or_items):
    """Wraps an item in a list if it is not already a list
    """
    if isinstance(item_or_items, list):
        return item_or_items
    return [item_or_items]


class TransactionEncoder(object):
    """Stores a private key and default TransactionHeader values, which will
    then be used to create and serialize Transactions. Any TransactionHeader
    value set will be used with EVERY Transaction this encoder creates.

    Args:
        private_key (bytes): The private key to sign Transactions with
        payload_encoder (function, optional): Run on each payload before
            creating Transaction, must return bytes
        batcher_pubkey (string or bytes, optional): Expected batcher public key
        dependencies (list of str, optional): Transaction ids that must be
            committed before every Transaction from this encoder (unusual)
        family_name (str, optional): Name of the designated Transaction Family
        family_version (str, optional): Version of Transaction Family
        inputs (list of str, optional): State addresses that every Transaction
            created by this encoder will read from (unusual)
        outputs (list of str, optional): State addresses that every Transaction
            created by this encoder will write to (unusual)
        payload_encoding (str, optional): The byte-encoding the Transaction
            Processor should expect

    Note:
        Every optional argument can be set or changed later as an attribute.
    """
    def __init__(self,
                 private_key,
                 payload_encoder=lambda x: x,
                 batcher_pubkey=None,
                 dependencies=None,
                 family_name=None,
                 family_version=None,
                 inputs=None,
                 outputs=None,
                 payload_encoding=None):
        self._private_key = private_key
        self._public_key = generate_pubkey(private_key, privkey_format='bytes')

        self.payload_encoder = payload_encoder

        # Set default headers as attributes so they can be modified later
        self.batcher_pubkey = (self._public_key
                               if batcher_pubkey is None
                               else batcher_pubkey)
        self.dependencies = dependencies
        self.family_name = family_name
        self.family_version = family_version
        self.inputs = inputs
        self.outputs = outputs
        self.payload_encoding = payload_encoding

    def create(self,
               payload,
               batcher_pubkey=None,
               dependencies=None,
               family_name=None,
               family_version=None,
               inputs=None,
               nonce=None,
               outputs=None,
               payload_encoding=None):
        """Creates a new Transaction from a payload, and a combination of both
        TransactionHeader values passed in as keyword arguments, and defaults
        set on TransactionEncoder.

        Args:
            payload (bytes): If no payload_encoder is set on the
                TransactionEncoder, the payload must be byte-encoded
            batcher_pubkey (string or bytes, optional): Batcher public key
            dependencies (list of str, optional): Transaction ids that must be
                committed before this Transaction
            family_name (str, optional): Name of Transaction Family
            family_version (str, optional): Version of Transaction Family
            inputs (list of str, optional): State addresses that Transaction
                created by this encoder will read from
            nonce (str, optional): Random string to ensure uniqueness
            outputs (list of str, optional): State addresses that Transaction
                created by this encoder will write to
            payload_encoding (str, optional): The byte-encoding the Transaction
                Processor should expect

        Raises:
            TypeError: Raised if a user-supplied required header was not set
                in either the TransactionEncoder, or during this method call.
                Required user-supplied headers include:
                    * family_name
                    * family_version
                    * payload_encoding
                    * inputs
                    * outputs

        Returns:
            Transaction: A signed Transaction Protobuf message
        """
        payload = self.payload_encoder(payload)
        payload_sha512 = sha512(payload).hexdigest()

        def resolve_required(key, value):
            value = value if value is not None else getattr(self, key)
            if value is None:
                raise TypeError('"{}" must be set in the TransactionEncoder '
                                'or as a keyword argument'.format(key))
            return value

        txn_header = TransactionHeader(
            family_name=resolve_required('family_name', family_name),
            family_version=resolve_required('family_version', family_version),
            inputs=resolve_required('inputs', inputs),
            outputs=resolve_required('outputs', outputs),
            payload_encoding=resolve_required('payload_encoding',
                                              payload_encoding),
            batcher_pubkey=(batcher_pubkey if batcher_pubkey is not None
                            else self.batcher_pubkey),
            dependencies=(dependencies if dependencies is not None
                          else self.dependencies),
            nonce=nonce if nonce is not None else str(randint(0, 100000000)),
            payload_sha512=payload_sha512,
            signer_pubkey=self._public_key)

        header_bytes = txn_header.SerializeToString()
        return Transaction(
            header=header_bytes,
            header_signature=sign(header_bytes,
                                  self._private_key,
                                  privkey_format='bytes'),
            payload=payload)

    def encode(self, transactions):
        """Wraps one or more Transaction messages in a TransactionList and
        serializes it for transmission to a batcher.

        Args:
            transactions (list of Transaction or Transaction): The Transaction
                or Transactions to wrap in a TransactionList

        Returns:
            bytes: a serialized TransactionList
        """
        transactions = _listify(transactions)
        txn_list = TransactionList(transactions=transactions)
        return txn_list.SerializeToString()

    def create_encoded(self,
                       payload,
                       batcher_pubkey=None,
                       dependencies=None,
                       family_name=None,
                       family_version=None,
                       inputs=None,
                       nonce=None,
                       outputs=None,
                       payload_encoding=None):
        """Convenience method which creates a single Transaction from a payload
        and supplied or default TransactionHeader values, before wrapping it
        in a TransactionList and serializing it. Accepts identical parameters
        to TransactionEncoder.create().

        Args:
            payload (bytes): If no payload_encoder is set on the
                TransactionEncoder, the payload must be byte-encoded
            batcher_pubkey (string or bytes, optional): Batcher public key
            dependencies (list of str, optional): Transaction ids that must be
                committed before this Transaction
            family_name (str, optional): Name of Transaction Family
            family_version (str, optional): Version of Transaction Family
            inputs (list of str, optional): State addresses that Transaction
                created by this encoder will read from
            nonce (str, optional): Random string to ensure uniqueness
            outputs (list of str, optional): State addresses that Transaction
                created by this encoder will write to
            payload_encoding (str, optional): The byte-encoding the Transaction
                Processor should expect

        Raises:
            TypeError: Raised if a user-supplied required header was not set
                in either the TransactionEncoder, or during this method call.
                Required user-supplied headers include:
                    * family_name
                    * family_version
                    * payload_encoding
                    * inputs
                    * outputs

        Returns:
            bytes: a serialized TransactionList
        """
        txn = self.create(payload,
                          batcher_pubkey=batcher_pubkey,
                          dependencies=dependencies,
                          family_name=family_name,
                          family_version=family_version,
                          inputs=inputs,
                          nonce=nonce,
                          outputs=outputs,
                          payload_encoding=payload_encoding)
        return self.encode(txn)


class BatchEncoder(object):
    """Stores a private key which can be used to create and sign Batches of
    Transactions.

    Args:
        private_key (bytes): The private key to sign Batches with
    """
    def __init__(self, private_key):
        self._private_key = private_key
        self._public_key = generate_pubkey(private_key, privkey_format='bytes')

    def create(self, transactions):
        """Creates and signs a new Batch message with one or more Transactions.
        Transactions can be input as Transaction instances or as a serialized
        TransactionList.

        Args:
            transactions (bytes or Transaction or list of Transaction):
                The Transactions to wrap in this Batch.

        Returns:
            Batch: A signed Transaction Protobuf message
        """
        try:
            txn_list = TransactionList()
            txn_list.ParseFromString(transactions)
            transactions = txn_list.transactions
        except (TypeError, DecodeError):
            transactions = _listify(transactions)

        batch_header = BatchHeader(
            signer_pubkey=self._public_key,
            transaction_ids=[t.header_signature for t in transactions])
        header_bytes = batch_header.SerializeToString()

        return Batch(
            header=header_bytes,
            header_signature=sign(header_bytes,
                                  self._private_key,
                                  privkey_format='bytes'),
            transactions=transactions)

    def encode(self, batches):
        """Wraps one or more Batch messages in a BatchList and serializes it
        for transmission to a validator.

        Args:
            batches (list of Batch or Batch): The Batch or Batches to wrap in
                a BatchList

        Returns:
            bytes: a serialized BatchList
        """
        batches = _listify(batches)
        batch_list = BatchList(batches=batches)
        return batch_list.SerializeToString()

    def create_encoded(self, transactions):
        """Convenience method which creates a single Batch from a Transaction
        or Transactions, before wrapping it in a BatchList and serializing it.
        Accepts identical parameters to BatchEncoder.create().

        Args:
            transactions (bytes or Transaction or list of Transaction):
                The Transactions to wrap in this Batch. Can be formatted as
                a serialized TransactionList, a single Transaction instance, or
                a list of Transaction instances.

        Returns:
            bytes: a serialized BatchList
        """
        batch = self.create(transactions)
        return self.encode(batch)

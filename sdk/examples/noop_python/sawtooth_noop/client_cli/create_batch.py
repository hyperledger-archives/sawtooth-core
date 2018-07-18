#!/usr/bin/python
#
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

import hashlib
import logging
import binascii
import random

import sawtooth_sdk.protobuf.batch_pb2 as batch_pb2
import sawtooth_sdk.protobuf.transaction_pb2 as transaction_pb2


LOGGER = logging.getLogger(__name__)


class NoopPayload:
    def __init__(self):
        self.nonce = binascii.b2a_hex(random.getrandbits(
            8 * 8).to_bytes(8, byteorder='little'))
        self._sha512 = None

    def sha512(self):
        if self._sha512 is None:
            self._sha512 = hashlib.sha512(self.nonce).hexdigest()
        return self._sha512


def create_noop_transaction(signer):
    payload = NoopPayload()

    header = transaction_pb2.TransactionHeader(
        signer_public_key=signer.get_public_key().as_hex(),
        family_name='noop',
        family_version='1.0',
        inputs=[],
        outputs=[],
        dependencies=[],
        payload_sha512=payload.sha512(),
        batcher_public_key=signer.get_public_key().as_hex(),
        nonce=hex(random.randint(0, 2**64)))

    header_bytes = header.SerializeToString()

    signature = signer.sign(header_bytes)

    transaction = transaction_pb2.Transaction(
        header=header_bytes,
        payload=payload.nonce,
        header_signature=signature)

    return transaction


def create_batch(transactions, signer):
    transaction_signatures = [t.header_signature for t in transactions]

    header = batch_pb2.BatchHeader(
        signer_public_key=signer.get_public_key().as_hex(),
        transaction_ids=transaction_signatures)

    header_bytes = header.SerializeToString()

    signature = signer.sign(header_bytes)

    batch = batch_pb2.Batch(
        header=header_bytes,
        transactions=transactions,
        header_signature=signature)

    return batch

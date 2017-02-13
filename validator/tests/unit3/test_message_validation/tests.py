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
import unittest
import cbor
import hashlib
import random
import queue
import string

from threading import Condition
from sawtooth_signing import pbct as signing
from sawtooth_validator.protobuf.transaction_pb2 import TransactionHeader, \
    Transaction
from sawtooth_validator.protobuf.batch_pb2 import BatchHeader, Batch
from sawtooth_validator.protobuf.block_pb2 import BlockHeader, Block
from sawtooth_validator.protobuf.network_pb2 import GossipMessage
from sawtooth_validator.protobuf import validator_pb2
from sawtooth_validator.gossip import signature_verifier as verifier


class TestMessageValidation(unittest.TestCase):
    def setUp(self):
        self.private_key = signing.generate_privkey()
        self.public_key = signing.encode_pubkey(
            signing.generate_pubkey(self.private_key), "hex")

    def broadcast(self, msg):
        pass

    def _create_transactions(self, count, valid=True, valid_batcher=True):
        txn_list = []

        for i in range(count):
            payload = {'Verb': 'set',
                       'Name': 'name' + str(random.randint(0, 100)),
                       'Value': random.randint(0, 100)}
            intkey_prefix = \
                hashlib.sha512('intkey'.encode('utf-8')).hexdigest()[0:6]

            addr = intkey_prefix + \
                hashlib.sha512(payload["Name"].encode('utf-8')).hexdigest()

            payload_encode = hashlib.sha512(cbor.dumps(payload)).hexdigest()

            header = TransactionHeader(
                signer_pubkey=self.public_key,
                family_name='intkey',
                family_version='1.0',
                inputs=[addr],
                outputs=[addr],
                dependencies=[],
                payload_encoding="application/cbor",
                payload_sha512=payload_encode)

            if valid_batcher:
                header.batcher_pubkey = self.public_key
            else:
                header.batcher_pubkey = "bad_batcher"

            header_bytes = header.SerializeToString()

            if valid:
                signature = signing.sign(
                    header_bytes,
                    self.private_key)
            else:
                signature = "bad_signature"

            transaction = Transaction(
                header=header_bytes,
                payload=cbor.dumps(payload),
                header_signature=signature)

            txn_list.append(transaction)

        return txn_list

    def _generate_id(self):
        return hashlib.sha512(''.join(
            [random.choice(string.ascii_letters)
                for _ in range(0, 1024)]).encode()).hexdigest()

    def _create_batches(self, batch_count, txn_count,
                        valid_batch=True, valid_txn=True,
                        valid_batcher=True):

        batch_list = []

        for i in range(batch_count):
            txn_list = self._create_transactions(txn_count, valid_txn,
                                                 valid_batcher)
            txn_sig_list = [txn.header_signature for txn in txn_list]

            batch_header = BatchHeader(signer_pubkey=self.public_key)
            batch_header.transaction_ids.extend(txn_sig_list)

            header_bytes = batch_header.SerializeToString()

            if valid_batch:
                signature = signing.sign(
                    header_bytes,
                    self.private_key)
            else:
                signature = "bad_signature"

            batch = Batch(header=header_bytes,
                          transactions=txn_list,
                          header_signature=signature)

            batch_list.append(batch)

        return batch_list

    def _create_blocks(self, block_count, batch_count,
                       valid_block=True, valid_batch=True):
        block_list = []

        for i in range(block_count):
            batch_list = self._create_batches(
                batch_count, 2, valid_batch=valid_batch)
            batch_ids = [batch.header_signature for batch in batch_list]

            block_header = BlockHeader(signer_pubkey=self.public_key,
                                       batch_ids=batch_ids)

            header_bytes = block_header.SerializeToString()

            if valid_block:
                signature = signing.sign(
                    header_bytes,
                    self.private_key)
            else:
                signature = "bad_signature"

            block = Block(header=header_bytes,
                          batches=batch_list,
                          header_signature=signature)

            block_list.append(block)

        return block_list

    def test_valid_transaction(self):
        txn_list = self._create_transactions(1)
        txn = txn_list[0]
        valid = verifier.validate_transaction(txn)
        self.assertTrue(valid)

    def test_invalid_transaction(self):
        # add invalid flag to _create transaction
        txn_list = self._create_transactions(1, valid=False)
        txn = txn_list[0]
        valid = verifier.validate_transaction(txn)
        self.assertFalse(valid)

    def test_valid_batch(self):
        batch_list = self._create_batches(1, 10)
        batch = batch_list[0]
        valid = verifier.validate_batch(batch)
        self.assertTrue(valid)

    def test_invalid_batch(self):
        # add invalid flag to create_batches
        batch_list = self._create_batches(1, 1, valid_batch=False)
        batch = batch_list[0]
        valid = verifier.validate_batch(batch)
        self.assertFalse(valid)

        # create an invalid txn in the batch
        batch_list = self._create_batches(1, 1, valid_txn=False)
        batch = batch_list[0]
        valid = verifier.validate_batch(batch)
        self.assertFalse(valid)

        # create an invalid txn with bad batcher
        batch_list = self._create_batches(1, 1, valid_batcher=False)
        batch = batch_list[0]
        valid = verifier.validate_batch(batch)
        self.assertFalse(valid)

    def test_valid_block(self):
        block_list = self._create_blocks(1, 1)
        block = block_list[0]
        valid = verifier.validate_block(block)
        self.assertTrue(valid)

    def test_invalid_block(self):
        block_list = self._create_blocks(1, 1, valid_batch=False)
        block = block_list[0]
        valid = verifier.validate_block(block)
        self.assertFalse(valid)

        block_list = self._create_blocks(1, 1, valid_block=False)
        block = block_list[0]
        valid = verifier.validate_block(block)
        self.assertFalse(valid)

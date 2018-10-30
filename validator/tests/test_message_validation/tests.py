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
import hashlib
import random
import string

import cbor

from sawtooth_signing import create_context
from sawtooth_signing import CryptoFactory
from sawtooth_validator.protobuf.transaction_pb2 import TransactionHeader, \
    Transaction
from sawtooth_validator.protobuf.batch_pb2 import BatchHeader, Batch
from sawtooth_validator.protobuf.block_pb2 import BlockHeader, Block
from sawtooth_validator.protobuf.consensus_pb2 import ConsensusPeerMessage
from sawtooth_validator.protobuf.consensus_pb2 import \
    ConsensusPeerMessageHeader
from sawtooth_validator.gossip import signature_verifier as verifier
from sawtooth_validator.gossip import structure_verifier


class TestMessageValidation(unittest.TestCase):
    def setUp(self):
        context = create_context('secp256k1')
        private_key = context.new_random_private_key()
        crypto_factory = CryptoFactory(context)
        self.signer = crypto_factory.new_signer(private_key)

    @property
    def public_key(self):
        return self.signer.get_public_key().as_hex()

    def broadcast(self, msg):
        pass

    def _create_transactions(self,
                             count,
                             matched_payload=True,
                             valid_signature=True,
                             valid_batcher=True):
        txn_list = []

        for _ in range(count):
            payload = {
                'Verb': 'set',
                'Name': 'name' + str(random.randint(0, 100)),
                'Value': random.randint(0, 100)
            }
            intkey_prefix = \
                hashlib.sha512('intkey'.encode('utf-8')).hexdigest()[0:6]

            addr = intkey_prefix + \
                hashlib.sha512(payload["Name"].encode('utf-8')).hexdigest()

            payload_encode = hashlib.sha512(cbor.dumps(payload)).hexdigest()

            header = TransactionHeader(
                signer_public_key=self.public_key,
                family_name='intkey',
                family_version='1.0',
                inputs=[addr],
                outputs=[addr],
                dependencies=[],
                payload_sha512=payload_encode)

            if valid_batcher:
                header.batcher_public_key = self.public_key
            else:
                header.batcher_public_key = "bad_batcher"

            header_bytes = header.SerializeToString()

            if valid_signature:
                signature = self.signer.sign(header_bytes)
            else:
                signature = "bad_signature"

            if not matched_payload:
                payload['Name'] = 'unmatched_payload'

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
                        valid_structure=True, valid_batcher=True):

        batch_list = []

        for _ in range(batch_count):
            txn_list = self._create_transactions(txn_count, valid_txn,
                                                 valid_batcher)
            txn_sig_list = [txn.header_signature for txn in txn_list]
            if not valid_structure:
                txn_sig_list.pop()

            batch_header = BatchHeader(signer_public_key=self.public_key)
            batch_header.transaction_ids.extend(txn_sig_list)

            header_bytes = batch_header.SerializeToString()

            if valid_batch:
                signature = self.signer.sign(header_bytes)
            else:
                signature = "bad_signature"

            batch = Batch(
                header=header_bytes,
                transactions=txn_list,
                header_signature=signature)

            batch_list.append(batch)

        return batch_list

    def _create_blocks(self, block_count, batch_count,
                       valid_block=True, valid_batch=True):
        block_list = []

        for _ in range(block_count):
            batch_list = self._create_batches(
                batch_count, 2, valid_batch=valid_batch)
            batch_ids = [batch.header_signature for batch in batch_list]

            block_header = BlockHeader(signer_public_key=self.public_key,
                                       batch_ids=batch_ids)

            header_bytes = block_header.SerializeToString()

            if valid_block:
                signature = self.signer.sign(header_bytes)
            else:
                signature = "bad_signature"

            block = Block(header=header_bytes,
                          batches=batch_list,
                          header_signature=signature)

            block_list.append(block)

        return block_list

    def _create_consensus_message(self, valid=True):
        name, version = "test", "1.0"
        content = b"123"
        message_type = "test"
        header_bytes = ConsensusPeerMessageHeader(
            signer_id=bytes.fromhex(self.public_key),
            content_sha512=hashlib.sha512(content).digest(),
            message_type=message_type,
            name=name,
            version=version,
        ).SerializeToString()

        if valid:
            signature = bytes.fromhex(self.signer.sign(header_bytes))
        else:
            signature = b"bad_signature"

        message = ConsensusPeerMessage(
            header=header_bytes,
            content=content,
            header_signature=signature)

        return message

    def test_valid_transaction(self):
        txn_list = self._create_transactions(1)
        txn = txn_list[0]
        valid = verifier.is_valid_transaction(txn)
        self.assertTrue(valid)

    def test_invalid_transaction(self):
        # add invalid flag to _create transaction
        txn_list = self._create_transactions(1, valid_signature=False)
        txn = txn_list[0]
        valid = verifier.is_valid_transaction(txn)
        self.assertFalse(valid)

    def test_unmatched_payload_transaction(self):
        # add invalid flag to _create transaction
        txn_list = self._create_transactions(1, matched_payload=False)
        txn = txn_list[0]
        valid = verifier.is_valid_transaction(txn)
        self.assertFalse(valid)

    def test_valid_batch(self):
        batch_list = self._create_batches(1, 10)
        batch = batch_list[0]
        valid = verifier.is_valid_batch(batch)
        self.assertTrue(valid)

    def test_invalid_batch(self):
        # add invalid flag to create_batches
        batch_list = self._create_batches(1, 1, valid_batch=False)
        batch = batch_list[0]
        valid = verifier.is_valid_batch(batch)
        self.assertFalse(valid)

        # create an invalid txn in the batch
        batch_list = self._create_batches(1, 1, valid_txn=False)
        batch = batch_list[0]
        valid = verifier.is_valid_batch(batch)
        self.assertFalse(valid)

        # create an invalid txn with bad batcher
        batch_list = self._create_batches(1, 1, valid_batcher=False)
        batch = batch_list[0]
        valid = verifier.is_valid_batch(batch)
        self.assertFalse(valid)

    def test_invalid_batch_structure(self):
        batch_list = self._create_batches(1, 2, valid_structure=False)
        batch = batch_list[0]
        valid = structure_verifier.is_valid_batch(batch)
        self.assertFalse(valid)

    def test_valid_block(self):
        block_list = self._create_blocks(1, 1)
        block = block_list[0]
        valid = verifier.is_valid_block(block)
        self.assertTrue(valid)

    def test_invalid_block(self):
        block_list = self._create_blocks(1, 1, valid_batch=False)
        block = block_list[0]
        valid = verifier.is_valid_block(block)
        self.assertFalse(valid)

        block_list = self._create_blocks(1, 1, valid_block=False)
        block = block_list[0]
        valid = verifier.is_valid_block(block)
        self.assertFalse(valid)

    def test_valid_consensus_message(self):
        message = self._create_consensus_message()
        self.assertTrue(verifier.is_valid_consensus_message(message))

    def test_invalid_consensus_message(self):
        message = self._create_consensus_message(valid=False)
        self.assertFalse(verifier.is_valid_consensus_message(message))

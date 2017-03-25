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
import unittest
import random
import hashlib
import cbor

import sawtooth_signing as signing
from sawtooth_validator.journal.completer import Completer
from sawtooth_validator.journal.block_store import BlockStore
from sawtooth_validator.journal.block_wrapper import NULL_BLOCK_IDENTIFIER
from sawtooth_validator.protobuf.transaction_pb2 import TransactionHeader, \
    Transaction
from sawtooth_validator.protobuf.batch_pb2 import BatchHeader, Batch
from sawtooth_validator.protobuf.block_pb2 import BlockHeader, Block
from test_completer.mock import MockGossip


class TestCompleter(unittest.TestCase):
    def setUp(self):
        self.block_store = BlockStore({})
        self.gossip = MockGossip()
        self.completer = Completer(self.block_store, self.gossip)
        self.completer._on_block_received = self._on_block_received
        self.completer._on_batch_received = self._on_batch_received
        self.private_key = signing.generate_privkey()
        self.public_key = signing.generate_pubkey(self.private_key)
        self.blocks = []
        self.batches = []

    def _on_block_received(self, block):
        print("Block received")
        return self.blocks.append(block.header_signature)

    def _on_batch_received(self, batch):
        print("Batch received")
        return self.batches.append(batch.header_signature)

    def _create_transactions(self, count, missing_dep=False):
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

            if missing_dep:
                header.dependencies.extend(["Missing"])

            header_bytes = header.SerializeToString()

            signature = signing.sign(
                header_bytes,
                self.private_key)

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
                        missing_dep=False):

        batch_list = []

        for i in range(batch_count):
            txn_list = self._create_transactions(txn_count,
                                                 missing_dep=missing_dep)
            txn_sig_list = [txn.header_signature for txn in txn_list]

            batch_header = BatchHeader(signer_pubkey=self.public_key)
            batch_header.transaction_ids.extend(txn_sig_list)

            header_bytes = batch_header.SerializeToString()


            signature = signing.sign(
                header_bytes,
                self.private_key)

            batch = Batch(header=header_bytes,
                          transactions=txn_list,
                          header_signature=signature)

            batch_list.append(batch)

        return batch_list

    def _create_blocks(self, block_count, batch_count,
                       missing_predecessor=False, missing_batch=False,
                       find_batch=True):
        block_list = []
        pred = 0
        for i in range(0, block_count):
            batch_list = self._create_batches(batch_count, 2)
            batch_ids = [batch.header_signature for batch in batch_list]

            if missing_predecessor:
                predecessor = "Missing"
            else:
                predecessor = (block_list[i-1].header_signature if i > 0 else
                    NULL_BLOCK_IDENTIFIER)

            block_header = BlockHeader(
                signer_pubkey=self.public_key,
                batch_ids=batch_ids,
                block_num=i,
                previous_block_id= predecessor
                    )

            header_bytes = block_header.SerializeToString()

            signature = signing.sign(
                header_bytes,
                self.private_key)

            if missing_batch:
                if find_batch:
                    self.completer.add_batch(batch_list[-1])
                batch_list = batch_list[:-1]


            block = Block(header=header_bytes,
                          batches=batch_list,
                          header_signature=signature)

            block_list.append(block)

        return block_list

    def test_good_block(self):
        """
        Add completed block to completer. Block should be passed to
        on_block_recieved.
        """
        block = self._create_blocks(1,1)[0]
        self.completer.add_block(block)
        self.assertIn(block.header_signature, self.blocks)

    def test_duplicate_block(self):
        """
        Submit same block twice.
        """
        block = block = self._create_blocks(1, 1)[0]
        self.completer.add_block(block)
        self.completer.add_block(block)
        self.assertIn(block.header_signature, self.blocks)
        self.assertEquals(len(self.blocks), 1)

    def test_block_missing_predecessor(self):
        """
        The block is completed but the predecessor is missing.
        """
        block = self._create_blocks(1, 1, missing_predecessor=True)[0]
        self.completer.add_block(block)
        self.assertEquals(len(self.blocks),0 )
        self.assertIn("Missing", self.gossip.requested_blocks)
        header = BlockHeader(previous_block_id=NULL_BLOCK_IDENTIFIER)
        missing_block = Block(header_signature="Missing",
                              header=header.SerializeToString())
        self.completer.add_block(missing_block)
        self.assertIn(block.header_signature, self.blocks)
        self.assertEquals(
            block,
            self.completer.get_block(block.header_signature).get_block())

    def test_block_with_extra_batch(self):
        """
        The block has a batch that is not in the batch_id list.
        """
        block = self._create_blocks(1, 1)[0]
        batches = self._create_batches(1, 1, True)
        block.batches.extend(batches)
        self.completer.add_block(block)
        self.assertEquals(len(self.blocks), 0)

    def test_block_missing_batch(self):
        """
        The block is a missing batch and the batch is in the cache. The Block
        will be build and passed to on_block_recieved. This puts the block
        in the self.blocks list.
        """
        block = self._create_blocks(1, 2, missing_batch=True)[0]
        self.completer.add_block(block)
        self.assertIn(block.header_signature, self.blocks)
        self.assertEquals(
            block,
            self.completer.get_block(block.header_signature).get_block())


    def test_block_missing_batch_not_in_cache(self):
        """
        The block is a missing batch and the batch is not in the cache.
          The batch will be requested and the block will not be passed to
          on_block_recieved.
        """
        block = self._create_blocks(
            1, 3, missing_batch=True, find_batch=False)[0]
        self.completer.add_block(block)
        header = BlockHeader()
        header.ParseFromString(block.header)
        self.assertIn(header.batch_ids[-1], self.gossip.requested_batches)

    def test_block_batches_wrong_order(self):
        """
        The block has all of its batches but they are in the wrong order. The
        batches will be reordered and the block will be passed to
        on_block_recieved.
        """
        block = self._create_blocks(1, 6)[0]
        batches = list(block.batches)
        random.shuffle(batches)
        del block.batches[:]
        block.batches.extend(batches)
        self.completer.add_block(block)
        self.assertIn(block.header_signature, self.blocks)

    def test_block_batches_wrong_batch(self):
        """
        The block has all the correct number of batches but one is not in the
        batch_id list. This block should be dropped.
        """
        block = self._create_blocks(1, 6)[0]
        batch = Batch(header_signature="Extra")
        batches = list(block.batches)
        batches[-1] = batch
        block.batches.extend(batches)
        self.completer.add_block(block)
        self.assertEquals(len(self.blocks), 0)

    def test_good_batch(self):
        """
        Add complete batch to completer. The batch should be passed to
        on_batch_received.
        """
        batch = self._create_batches(1, 1)[0]
        self.completer.add_batch(batch)
        self.assertIn(batch.header_signature, self.batches)
        self.assertEquals(batch,
                          self.completer.get_batch(batch.header_signature))

    def test_batch_with_missing_dep(self):
        """
        Add batch to completer that has a missing dependency. The missing
        transaction's batch should be requested add the missing batch is then
        added to the completer. The incomplete batch should be rechecked
        and passed to on_batch_received.
        """
        batch = self._create_batches(1, 1, missing_dep=True)[0]
        self.completer.add_batch(batch)
        self.assertIn("Missing",
                      self.gossip.requested_batches_by_transactin_id)

        missing = Transaction(header_signature="Missing")
        missing_batch= Batch(header_signature="Missing_batch",
                             transactions=[missing])
        self.completer.add_batch(missing_batch)
        self.assertIn(missing_batch.header_signature, self.batches )
        self.assertIn(batch.header_signature, self.batches)
        self.assertEquals(missing_batch,
                          self.completer.get_batch_by_transaction("Missing"))

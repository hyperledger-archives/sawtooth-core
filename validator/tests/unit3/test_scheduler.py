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
import unittest
import bitcoin

from sawtooth_validator.scheduler.serial import SerialScheduler

import sawtooth_validator.protobuf.batch_pb2 as batch_pb2
import sawtooth_validator.protobuf.transaction_pb2 as transaction_pb2


def create_transaction(name, private_key, public_key):
    payload = name
    addr = '000000' + hashlib.sha512(name.encode()).hexdigest()

    header = transaction_pb2.TransactionHeader(
        signer=public_key,
        family_name='scheduler_test',
        family_version='1.0',
        inputs=[addr],
        outputs=[addr],
        dependencies=[],
        payload_encoding="application/cbor",
        payload_sha512=hashlib.sha512(payload.encode()).hexdigest(),
        batcher=public_key)

    header_bytes = header.SerializeToString()

    signature = bitcoin.ecdsa_sign(
        header_bytes,
        private_key)

    transaction = transaction_pb2.Transaction(
        header=header_bytes,
        payload=payload.encode(),
        signature=signature)

    return transaction


def create_batch(transactions, private_key, public_key):
    transaction_signatures = [t.signature for t in transactions]

    header = batch_pb2.BatchHeader(
        signer=public_key,
        transaction_signatures=transaction_signatures)

    header_bytes = header.SerializeToString()

    signature = bitcoin.ecdsa_sign(
        header_bytes,
        private_key)

    batch = batch_pb2.Batch(
        header=header_bytes,
        transactions=transactions,
        signature=signature)

    return batch


class TestSerialScheduler(unittest.TestCase):
    def test_transaction_order(self):
        """Tests the that transactions are returned in order added.

        Adds three batches with varying number of transactions, then tests
        that they are returned in the appropriate order when using an iterator.

        This test also creates a second iterator and verifies that both
        iterators return the same transactions.

        This test also finalizes the scheduler and verifies that StopIteration
        is thrown by the iterator.
        """
        private_key = bitcoin.random_key()
        public_key = bitcoin.encode_pubkey(
            bitcoin.privkey_to_pubkey(private_key), "hex")

        scheduler = SerialScheduler()

        txns = []

        for names in [['a', 'b', 'c'], ['d', 'e'], ['f', 'g', 'h', 'i']]:
            batch_txns = []
            for name in names:
                txn = create_transaction(
                    name=name,
                    private_key=private_key,
                    public_key=public_key)

                batch_txns.append(txn)
                txns.append(txn)

            batch = create_batch(
                transactions=batch_txns,
                private_key=private_key,
                public_key=public_key)

            scheduler.add_batch(batch)

        iterable1 = iter(scheduler)
        iterable2 = iter(scheduler)
        for txn in txns:
            scheduled_txn = next(iterable1)
            self.assertEqual(scheduled_txn, next(iterable2))
            self.assertIsNotNone(scheduled_txn)
            self.assertEquals(txn.payload, scheduled_txn.payload)
            scheduler.mark_as_applied(scheduled_txn.signature)

        scheduler.finalize()
        with self.assertRaises(StopIteration):
            next(iterable1)

    def test_mark_as_applied(self):
        """Tests that mark_as_applied() has the correct behavior.

        Basically:
            1. Adds a batch which has two transactions.
            2. Calls next_transaction() to get the first Transaction.
            3. Calls next_transaction() to verify that it returns None.
            4. Calls mark_as_applied() to mark the first transaction applied.
            5. Calls next_transaction() to  get the second Transaction.

        Step 3 returns None because the first transaction hasn't been marked
        as applied, and the SerialScheduler will only return one
        not-applied Transaction at a time.

        Step 5 is expected to return the second Transaction, not None,
        since the first Transaction was marked as applied in the previous
        step.
        """
        private_key = bitcoin.random_key()
        public_key = bitcoin.encode_pubkey(
            bitcoin.privkey_to_pubkey(private_key), "hex")

        scheduler = SerialScheduler()

        txns = []

        for name in ['a', 'b']:
            txn = create_transaction(
                name=name,
                private_key=private_key,
                public_key=public_key)

            txns.append(txn)

        batch = create_batch(
            transactions=txns,
            private_key=private_key,
            public_key=public_key)

        scheduler.add_batch(batch)

        scheduled_txn = scheduler.next_transaction()
        self.assertIsNotNone(scheduled_txn)
        self.assertEquals('a', scheduled_txn.payload.decode())

        self.assertIsNone(scheduler.next_transaction())

        scheduler.mark_as_applied(scheduled_txn.signature)

        scheduled_txn = scheduler.next_transaction()
        self.assertIsNotNone(scheduled_txn)
        self.assertEquals('b', scheduled_txn.payload.decode())

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

from sawtooth_validator.context_manager import ContextManager
from sawtooth_validator.database import database

from sawtooth_validator.scheduler.serial import SerialScheduler

import sawtooth_validator.protobuf.batch_pb2 as batch_pb2
import sawtooth_validator.protobuf.transaction_pb2 as transaction_pb2


class TestDatabase(database.Database):
    def __init__(self):
        super(TestDatabase, self).__init__()
        self._data = dict()

    def get(self, key):
        return self._data.get(key)

    def __contains__(self, item):
        return item in self._data

    def set(self, key, value):
        self._data[key] = value

    def set_batch(self, kvpairs):
        for k, v in kvpairs:
            self._data[k] = v

    def close(self):
        pass

    def delete(self, key):
        pass

    def __len__(self):
        pass

    def keys(self):
        pass

    def sync(self):
        pass


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
        context_manager = ContextManager(TestDatabase())
        squash_handler = context_manager.get_squash_handler()
        first_state_root = context_manager.get_first_root()
        scheduler = SerialScheduler(squash_handler, first_state_root)

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
            scheduled_txn_info = next(iterable1)
            self.assertEqual(scheduled_txn_info, next(iterable2))
            self.assertIsNotNone(scheduled_txn_info)
            self.assertEquals(txn.payload, scheduled_txn_info.txn.payload)
            scheduler.mark_as_applied(scheduled_txn_info.txn.signature)

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

        context_manager = ContextManager(TestDatabase())
        squash_handler = context_manager.get_squash_handler()
        first_state_root = context_manager.get_first_root()
        scheduler = SerialScheduler(squash_handler, first_state_root)

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

        scheduled_txn_info = scheduler.next_transaction()
        self.assertIsNotNone(scheduled_txn_info)
        self.assertEquals('a', scheduled_txn_info.txn.payload.decode())

        self.assertIsNone(scheduler.next_transaction())

        scheduler.mark_as_applied(scheduled_txn_info.txn.signature)

        scheduled_txn_info = scheduler.next_transaction()
        self.assertIsNotNone(scheduled_txn_info)
        self.assertEquals('b', scheduled_txn_info.txn.payload.decode())

    def test_valid_batch_invalid_batch(self):
        """Tests the squash function. That the correct hash is being used
        for each txn and that the batch ending state hash is being set.

         Basically:
            1. Adds two batches, one where all the txns are valid,
               and one where one of the txns is invalid.
            2. Run through the scheduler executor interaction
               as txns are processed.
            3. Verify that the valid state root is obtained
               through the squash function.
            4. Verify that correct batch statuses are set
        """
        private_key = bitcoin.random_key()
        public_key = bitcoin.encode_pubkey(
            bitcoin.privkey_to_pubkey(private_key), "hex")

        context_manager = ContextManager(TestDatabase())
        squash_handler = context_manager.get_squash_handler()
        first_state_root = context_manager.get_first_root()
        scheduler = SerialScheduler(squash_handler, first_state_root)
        # 1)
        batch_signatures = []
        for names in [['a', 'b'], ['invalid', 'c']]:
            batch_txns = []
            for name in names:
                txn = create_transaction(
                    name=name,
                    private_key=private_key,
                    public_key=public_key)

                batch_txns.append(txn)

            batch = create_batch(
                transactions=batch_txns,
                private_key=private_key,
                public_key=public_key)

            batch_signatures.append(batch.signature)
            scheduler.add_batch(batch)
            scheduler.finalize()
        # 2)
        sched1 = iter(scheduler)
        invalid_payload = hashlib.sha512('invalid'.encode()).hexdigest()
        while not scheduler.complete():
            txn_info = next(sched1)
            txn_header = transaction_pb2.TransactionHeader()
            txn_header.ParseFromString(txn_info.txn.header)
            inputs_or_outputs = list(txn_header.inputs)
            c_id = context_manager.create_context(txn_info.state_hash,
                                                  inputs_or_outputs,
                                                  inputs_or_outputs)
            if txn_header.payload_sha512 == invalid_payload:
                scheduler.set_status(txn_info.txn.signature, False, c_id)
            else:
                context_manager.set(c_id, [{inputs_or_outputs[0]: 1}])
                scheduler.set_status(txn_info.txn.signature,
                                     True,
                                     c_id)

        sched2 = iter(scheduler)
        # 3)
        txn_infoA = next(sched2)
        self.assertEquals(first_state_root, txn_infoA.state_hash)

        txnA_header = transaction_pb2.TransactionHeader()
        txnA_header.ParseFromString(txn_infoA.txn.header)
        inputs_or_outputs = list(txnA_header.inputs)
        addressA = inputs_or_outputs[0]
        c_idA = context_manager.create_context(first_state_root,
                                               inputs_or_outputs,
                                               inputs_or_outputs)
        context_manager.set(c_idA, [{addressA: 1}])
        state_root2 = context_manager.commit_context([c_idA], virtual=False)
        txn_infoB = next(sched2)

        self.assertEquals(txn_infoB.state_hash, state_root2)

        txnB_header = transaction_pb2.TransactionHeader()
        txnB_header.ParseFromString(txn_infoB.txn.header)
        inputs_or_outputs = list(txnB_header.inputs)
        addressB = inputs_or_outputs[0]
        c_idB = context_manager.create_context(state_root2,
                                               inputs_or_outputs,
                                               inputs_or_outputs)
        context_manager.set(c_idB, [{addressB: 1}])
        state_root3 = context_manager.commit_context([c_idB], virtual=False)
        txn_infoInvalid = next(sched2)

        self.assertEquals(txn_infoInvalid.state_hash, state_root3)

        txn_infoC = next(sched2)
        self.assertEquals(txn_infoC.state_hash, state_root3)

        batch1_status = scheduler.batch_status(batch_signatures[0])
        self.assertTrue(batch1_status.valid)
        self.assertEquals(batch1_status.state_hash, state_root3)

        batch2_status = scheduler.batch_status(batch_signatures[1])
        self.assertFalse(batch2_status.valid)
        self.assertIsNone(batch2_status.state_hash)

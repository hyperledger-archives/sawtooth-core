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
import time
import tempfile


import gossip.signed_object as SigObj
from gossip.node import Node

from journal.transaction import Transaction
from journal.transaction_block import TransactionBlock
from journal.transaction import Status as tStatus
from journal.transaction_block import Status as tbStatus
from journal.journal_core import Journal


class TestingJournalTransaction(unittest.TestCase):

    def test_journal_transaction_init(self):
        # Test normal init of a transaction
        minfo = {'__SIGNATURE__': 'Test', '__NONCE__': time.time(),
                 'Dependencies': []}
        transaction = Transaction(minfo)
        self.assertEquals(transaction.Status, tStatus.unknown)
        self.assertFalse(transaction.InBlock)
        self.assertEquals(transaction.Dependencies, [])

    def test_journal_transaction_str(self):
        # Test str function for transaction
        minfo = {'__SIGNATURE__': 'Test', '__NONCE__': time.time(),
                 'Dependencies': []}
        transaction = Transaction(minfo)
        self.assertEquals(str(transaction), '/Transaction')

    def test_journal_transaction_apply(self):
        # Test Transaction apply, Does nothing at this point
        minfo = {'__SIGNATURE__': 'Test', '__NONCE__': time.time(),
                 'Dependencies': []}
        transaction = Transaction(minfo)
        transaction.apply("store")

    def test_journal_transaction_add_to_pending(self):
        # Test transaction add_to_pending, should always return true
        minfo = {'__SIGNATURE__': 'Test', '__NONCE__': time.time(),
                 'Dependencies': []}
        transaction = Transaction(minfo)
        self.assertTrue(transaction.add_to_pending())

    def test_journal_transaction_build_message(self):
        # Test that build_message returns a message of MessageType
        # TransactionMessage and that msg is linked to the transaction
        minfo = {'__SIGNATURE__': 'Test', '__NONCE__': time.time(),
                 'Dependencies': []}
        transaction = Transaction(minfo)
        msg = transaction.build_message()
        self.assertEquals(msg.MessageType,
                          "/journal.messages.TransactionMessage/Transaction")
        self.assertEquals(msg.Transaction, transaction)

    def test_journal_transaction_dump(self):
        # Test that transactions dump the correct info
        now = time.time()
        minfo = {'__SIGNATURE__': 'Test', '__NONCE__': now,
                 'Dependencies': []}
        transaction = Transaction(minfo)
        time.sleep(0.5)
        tDic = transaction.dump()
        new = time.time()
        self.assertLess(tDic["Nonce"], new)
        self.assertEquals(tDic["Dependencies"], [])
        self.assertEquals(tDic["TransactionType"], '/Transaction')


class TestingJournalTransactionBlock(unittest.TestCase):

    def test_journal_transaction_block_init(self):
        # Test normal init of a transaction
        minfo = {'__SIGNATURE__': 'Test', "BlockNum": 0}
        transBlock = TransactionBlock(minfo)
        self.assertEquals(transBlock.BlockNum, 0)
        self.assertEquals(transBlock.TransactionIDs, [])
        self.assertEquals(transBlock.Status, tbStatus.incomplete)
        self.assertEquals(transBlock.TransactionDepth, 0)

    def test_journal_transaction_block_str(self):
        # Test str function for a signed transaction block
        minfo = {'__SIGNATURE__': 'Test', "BlockNum": 0}
        transBlock = TransactionBlock(minfo)
        signingkey = SigObj.generate_signing_key()
        ident = SigObj.generate_identifier(signingkey)
        node = Node(identifier=ident, signingkey=signingkey,
                    address=("localhost", 8800))
        # Need to sign TransactionBlock, use sign_from_node form signed object
        transBlock.sign_from_node(node)
        self.assertEquals(str(transBlock), "{0}, {1}, {2}, {3:0.2f}"
                          .format(transBlock.BlockNum,
                                  transBlock.Identifier[:8],
                                  len(transBlock.TransactionIDs),
                                  transBlock.CommitTime))

    def test_journal_transaction_block_str_unsigned(self):
        # Test that an assertion error is caused if the Block is not signed
        minfo = {'__SIGNATURE__': 'Test', "BlockNum": 0}
        transBlock = TransactionBlock(minfo)
        try:
            str(transBlock)
            self.fail("This should cause an AssertError")
        except AssertionError, e:
            self.assertIsInstance(e, AssertionError)

    def test_journal_transaction_block_cmp_valid_blocks(self):
        # Test the overridden cmp function
        # Needs the Blocks to be signed and valid
        minfo = {'__SIGNATURE__': 'Test', "BlockNum": 0}
        transBlock1 = TransactionBlock(minfo)
        transBlock2 = TransactionBlock(minfo)
        signingkey = SigObj.generate_signing_key()
        ident = SigObj.generate_identifier(signingkey)
        node = Node(identifier=ident, signingkey=signingkey,
                    address=("localhost", 8800))
        # Need to sign TransactionBlock, use sign_from_node form signed object
        transBlock1.sign_from_node(node)
        transBlock2.sign_from_node(node)
        transBlock1.Status = tbStatus.valid
        transBlock2.Status = tbStatus.valid
        # Test Equal Transaction Blocks
        self.assertEquals(cmp(transBlock2, transBlock1), 0)
        # Test a Transaction Block with greater Transaction Depth
        transBlock2.TransactionDepth = 10
        self.assertEquals(cmp(transBlock2, transBlock1), 1)
        # Test a Transaction Block with lesser Transaction Depth
        transBlock1.TransactionDepth = 20
        self.assertEquals(cmp(transBlock2, transBlock1), -1)

    def test_journal_transaction_block_cmp_nonvalid_blocks(self):
        # Test that a ValueError is raised when a transBlock is not valid
        minfo = {'__SIGNATURE__': 'Test', "BlockNum": 0}
        transBlock1 = TransactionBlock(minfo)
        transBlock2 = TransactionBlock(minfo)
        signingkey = SigObj.generate_signing_key()
        ident = SigObj.generate_identifier(signingkey)
        node = Node(identifier=ident, signingkey=signingkey,
                    address=("localhost", 8800))
        # Need to sign TransactionBlock, use sign_from_node form signed object
        transBlock1.sign_from_node(node)
        transBlock2.sign_from_node(node)
        try:
            cmp(transBlock2, transBlock1)
            self.fail("This should cause a ValueError")
        except ValueError, e1:
            self.assertIsInstance(e1, ValueError)

    def test_journal_transaction_block_cmp_unsigned(self):
        # Test AssertionError is raised if TransactionBlock are not signed
        # Need a signature to use Identifier
        minfo = {'__SIGNATURE__': 'Test', "BlockNum": 0}
        transBlock1 = TransactionBlock(minfo)
        transBlock2 = TransactionBlock(minfo)
        transBlock1.Status = tbStatus.valid
        transBlock2.Status = tbStatus.valid
        try:
            cmp(transBlock2, transBlock1)
            self.fail("This should cause an AssertionError")
        except AssertionError, e2:
            self.assertIsInstance(e2, AssertionError)

    def test_journal_transaction_block_is_valid(self):
        # Test whether or not a transblock is valid
        minfo = {'__SIGNATURE__': 'Test', "BlockNum": 0}
        transBlock = TransactionBlock(minfo)
        signingkey = SigObj.generate_signing_key()
        ident = SigObj.generate_identifier(signingkey)
        node = Node(identifier=ident, signingkey=signingkey,
                    address=("localhost", 10000))
        # Takes a journal, create a temporary directory to use with the journal
        path = tempfile.mkdtemp()
        journal = Journal(node, DataDirectory=path)
        # Need to sign TransactionBlock, use sign_from_node form signed object
        transBlock.sign_from_node(node)
        self.assertTrue(transBlock.is_valid(journal))

    def test_journal_transaction_block_not_is_valid(self):
        # Test that an invalid Transblock does not get verified as valid
        minfo = {'__SIGNATURE__': 'Test', "BlockNum": 0}
        transBlock = TransactionBlock(minfo)
        signingkey = SigObj.generate_signing_key()
        ident = SigObj.generate_identifier(signingkey)
        node = Node(identifier=ident, signingkey=signingkey,
                    address=("localhost", 10001))
        # Takes a journal, create a temporary directory to use with the journal
        path = tempfile.mkdtemp()
        journal = Journal(node, DataDirectory=path)
        # Need to sign TransactionBlock, use sign_from_node form signed object
        try:
            transBlock.is_valid(journal)
        except AssertionError, e:
            self.assertIsInstance(e, AssertionError)

    def test_journal_transaction_block_missing_transactions(self):
        # Test missing transactions, should return list of missing transactions
        minfo = {'__SIGNATURE__': 'Test', "BlockNum": 0}
        transBlock = TransactionBlock(minfo)
        signingkey = SigObj.generate_signing_key()
        ident = SigObj.generate_identifier(signingkey)
        node = Node(identifier=ident, signingkey=signingkey,
                    address=("localhost", 10002))
        path = tempfile.mkdtemp()
        # Takes a journal, create a temporary directory to use with the journal
        journal = Journal(node, DataDirectory=path)
        transBlock.sign_from_node(node)
        missing = transBlock.missing_transactions(journal)
        # No missing transactions
        self.assertEquals(missing, [])

        minfo = {'__SIGNATURE__': 'Test', '__NONCE__': time.time(),
                 'Dependencies': []}
        transaction = Transaction(minfo)
        transaction.sign_from_node(node)
        transBlock.TransactionIDs += [transaction.Identifier]
        missing = transBlock.missing_transactions(journal)
        # One missing transactions
        self.assertEquals(missing, [transaction.Identifier])

        journal.TransactionStore[transaction.Identifier] = transaction
        missing = transBlock.missing_transactions(journal)
        # Back to no missing transactions
        self.assertEquals(missing, [])

    def test_journal_transaction_block_update_block_weight(self):
        # Test block update weight
        minfo = {'__SIGNATURE__': 'Test', "BlockNum": 0}
        transBlock = TransactionBlock(minfo)
        transBlock.Status = tbStatus.valid
        signingkey = SigObj.generate_signing_key()
        ident = SigObj.generate_identifier(signingkey)
        node = Node(identifier=ident, signingkey=signingkey,
                    address=("localhost", 10003))
        # Takes a journal, create a temporary directory to use with the journal
        path = tempfile.mkdtemp()
        journal = Journal(node, DataDirectory=path)
        transBlock.sign_from_node(node)
        transBlock.update_block_weight(journal)
        # No transactions
        self.assertEquals(transBlock.TransactionDepth, 0)

        minfo = {'__SIGNATURE__': 'Test', '__NONCE__': time.time(),
                 'Dependencies': []}
        transaction = Transaction(minfo)
        transaction.sign_from_node(node)
        transBlock.TransactionIDs += [transaction.Identifier]
        transBlock.update_block_weight(journal)
        # One transaction
        self.assertEquals(transBlock.TransactionDepth, 1)

        minfo = {'__SIGNATURE__': 'Test', "BlockNum": 1,
                 'PreviousBlockID': transBlock.Identifier}
        newTransBlock = TransactionBlock(minfo)
        newTransBlock.Status = tbStatus.valid
        journal.BlockStore[transBlock.Identifier] = transBlock
        newTransBlock.update_block_weight(journal)
        # Get depth from previous block
        self.assertEquals(newTransBlock.TransactionDepth, 1)

    def test_journal_transaction_block_build_message(self):
        # Test build_message, returns a TransactionBlockMessage
        minfo = {'__SIGNATURE__': 'Test', "BlockNum": 0}
        transBlock = TransactionBlock(minfo)
        signingkey = SigObj.generate_signing_key()
        ident = SigObj.generate_identifier(signingkey)
        node = Node(identifier=ident, signingkey=signingkey,
                    address=("localhost", 8800))
        transBlock.sign_from_node(node)
        transBlock.Status = tbStatus.valid
        msg = transBlock.build_message()
        self.assertEquals(msg.MessageType,
                          "/journal.messages.TransactionBlockMessage" +
                          "/TransactionBlock")
        self.assertEquals(msg.TransactionBlock, transBlock)

    def test_journal_transaction_block_dump(self):
        # Test that transactions dump the correct info
        minfo = {'__SIGNATURE__': 'Test', "BlockNum": 0}
        transBlock = TransactionBlock(minfo)
        signingkey = SigObj.generate_signing_key()
        ident = SigObj.generate_identifier(signingkey)
        node = Node(identifier=ident, signingkey=signingkey,
                    address=("localhost", 8800))
        transBlock.sign_from_node(node)
        transBlock.Status = tbStatus.valid
        tbDic = transBlock.dump()
        self.assertEquals(tbDic["TransactionIDs"], [])
        self.assertEquals(tbDic["TransactionBlockType"], "/TransactionBlock")
        self.assertEquals(tbDic["BlockNum"], 0)
        self.assertIsNotNone(tbDic["Signature"])
        self.assertNotEquals(tbDic["Signature"], "")

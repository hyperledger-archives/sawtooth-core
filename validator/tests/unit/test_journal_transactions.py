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

import tempfile
import time
import unittest

from sawtooth_signing import pbct_nativerecover as signing
from sawtooth_validator.consensus.dev_mode.dev_mode_consensus \
    import DevModeConsensus
from gossip import signed_object
from gossip.gossip_core import Gossip
from gossip.node import Node
from journal.journal_core import Journal
from journal.transaction import Status as tStatus
from journal.transaction import Transaction
from journal.transaction_block import Status as tbStatus
from journal.transaction_block import TransactionBlock


class TestingJournalTransaction(unittest.TestCase):

    def test_journal_transaction_init(self):
        # Test normal init of a transaction
        minfo = {'__SIGNATURE__': 'Test', '__NONCE__': time.time(),
                 'Dependencies': []}
        transaction = Transaction(minfo)
        self.assertEqual(transaction.Status, tStatus.unknown)
        self.assertFalse(transaction.InBlock)
        self.assertEqual(transaction.Dependencies, [])

    def test_journal_transaction_str(self):
        # Test str function for transaction
        minfo = {'__SIGNATURE__': 'Test', '__NONCE__': time.time(),
                 'Dependencies': []}
        transaction = Transaction(minfo)
        self.assertEqual(str(transaction), '/Transaction')

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
        self.assertEqual(msg.MessageType,
                         "/journal.messages.TransactionMessage/Transaction")
        self.assertEqual(msg.Transaction, transaction)

    def test_journal_transaction_dump(self):
        # Test that transactions dump the correct info
        now = time.time()
        minfo = {'__SIGNATURE__': 'Test', '__NONCE__': now,
                 'Dependencies': []}
        transaction = Transaction(minfo)
        time.sleep(0.5)
        t_dict = transaction.dump()
        new = time.time()
        self.assertLess(t_dict["Nonce"], new)
        self.assertEqual(t_dict["Dependencies"], [])
        self.assertEqual(t_dict["TransactionType"], '/Transaction')

    def test_is_valid_pub_key(self):
        pubkey = signing.generate_pubkey("5KQ4iQQGgbQX9MmfiPUwwHBL1R"
                                         "GPa86NwFbqrWoodjuzruqFVDd")
        pub = signing.encode_pubkey(pubkey, "hex")
        minfo = {'Nonce': 100, 'PublicKey': pub,
                 'TransactionType': '/Transaction', 'Dependencies': []}
        sig = signing.sign(
            signed_object.dict2cbor(minfo),
            "5KQ4iQQGgbQX9MmfiPUwwHBL1RGPa86NwFbqrWoodjuzruqFVDd"
        )
        # Create valid transaction
        minfo["Signature"] = sig
        temp = Transaction(minfo)
        self.assertTrue(temp.is_valid("unused"))

        # Change transaction after it was signed
        minfo["Nonce"] = time.time()
        temp = Transaction(minfo)
        self.assertFalse(temp.is_valid("unused"))


class TestingJournalTransactionBlock(unittest.TestCase):

    _next_port = 10000

    def _create_node(self):
        signingkey = signed_object.generate_signing_key()
        ident = signed_object.generate_identifier(signingkey)
        node = Node(identifier=ident, signingkey=signingkey,
                    address=("localhost", self._next_port))
        self.__class__._next_port = self._next_port + 1
        return node

    def _create_journal(self, node=None):
        node = node or self._create_node()
        gossip = Gossip(node)
        # Takes a journal, create a temporary directory to use with the journal
        path = tempfile.mkdtemp()
        journal = Journal(
            gossip.LocalNode,
            gossip,
            gossip.dispatcher,
            consensus=DevModeConsensus(),
            data_directory=path)
        return (gossip, journal)

    def test_journal_transaction_block_init(self):
        # Test normal init of a transaction
        minfo = {'__SIGNATURE__': 'Test', "BlockNum": 0}
        trans_block = TransactionBlock(minfo)
        self.assertEqual(trans_block.BlockNum, 0)
        self.assertEqual(trans_block.TransactionIDs, [])
        self.assertEqual(trans_block.Status, tbStatus.incomplete)
        self.assertEqual(trans_block.TransactionDepth, 0)

    def test_journal_transaction_block_str(self):
        # Test str function for a signed transaction block
        minfo = {'__SIGNATURE__': 'Test', "BlockNum": 0}
        trans_block = TransactionBlock(minfo)
        node = self._create_node()
        # Need to sign TransactionBlock, use sign_from_node form signed object
        trans_block.sign_from_node(node)
        self.assertEqual(str(trans_block), "{0}, {1}, {2}, {3:0.2f}"
                         .format(trans_block.BlockNum,
                                 trans_block.Identifier[:8],
                                 len(trans_block.TransactionIDs),
                                 trans_block.CommitTime))

    def test_journal_transaction_block_str_unsigned(self):
        # Test that an assertion error is caused if the Block is not signed
        minfo = {'__SIGNATURE__': 'Test', "BlockNum": 0}
        trans_block = TransactionBlock(minfo)
        try:
            str(trans_block)
            self.fail("This should cause an AssertError")
        except AssertionError, e:
            self.assertIsInstance(e, AssertionError)

    def test_journal_transaction_block_cmp_valid_blocks(self):
        # Test the overridden cmp function
        # Needs the Blocks to be signed and valid
        minfo = {'__SIGNATURE__': 'Test', "BlockNum": 0}
        trans_block1 = TransactionBlock(minfo)
        trans_block2 = TransactionBlock(minfo)
        node = self._create_node()
        # Need to sign TransactionBlock, use sign_from_node form signed object
        trans_block1.sign_from_node(node)
        trans_block2.sign_from_node(node)
        trans_block1.Status = tbStatus.valid
        trans_block2.Status = tbStatus.valid
        # Test Equal Transaction Blocks
        self.assertEquals(cmp(trans_block2, trans_block1), 0)
        # Test a Transaction Block with greater Transaction Depth
        trans_block2.TransactionDepth = 10
        self.assertEquals(cmp(trans_block2, trans_block1), 1)
        # Test a Transaction Block with lesser Transaction Depth
        trans_block1.TransactionDepth = 20
        self.assertEquals(cmp(trans_block2, trans_block1), -1)

    def test_journal_transaction_block_cmp_nonvalid_blocks(self):
        # Test that a ValueError is raised when a trans_block is not valid
        minfo = {'__SIGNATURE__': 'Test', "BlockNum": 0}
        trans_block1 = TransactionBlock(minfo)
        trans_block2 = TransactionBlock(minfo)
        node = self._create_node()
        # Need to sign TransactionBlock, use sign_from_node form signed object
        trans_block1.sign_from_node(node)
        trans_block2.sign_from_node(node)
        try:
            cmp(trans_block2, trans_block1)
            self.fail("This should cause a ValueError")
        except ValueError, e1:
            self.assertIsInstance(e1, ValueError)

    def test_journal_transaction_block_cmp_unsigned(self):
        # Test AssertionError is raised if TransactionBlock are not signed
        # Need a signature to use Identifier
        minfo = {'__SIGNATURE__': 'Test', "BlockNum": 0}
        trans_block1 = TransactionBlock(minfo)
        trans_block2 = TransactionBlock(minfo)
        trans_block1.Status = tbStatus.valid
        trans_block2.Status = tbStatus.valid
        try:
            cmp(trans_block2, trans_block1)
            self.fail("This should cause an AssertionError")
        except AssertionError, e2:
            self.assertIsInstance(e2, AssertionError)

    def test_journal_transaction_block_is_valid(self):
        # Test whether or not a transblock is valid
        minfo = {'__SIGNATURE__': 'Test', "BlockNum": 0}
        trans_block = TransactionBlock(minfo)
        (gossip, journal) = self._create_journal()
        # Need to sign TransactionBlock, use sign_from_node
        # from signed object
        trans_block.sign_from_node(gossip.LocalNode)
        self.assertTrue(trans_block.is_valid(journal))

    def test_journal_transaction_block_not_is_valid(self):
        # Test that an invalid transaction block does not get verified as valid
        minfo = {'__SIGNATURE__': 'Test', "BlockNum": 0}
        trans_block = TransactionBlock(minfo)
        (gossip, journal) = self._create_journal()
        # Need to sign TransactionBlock, use sign_from_node from signed object
        try:
            trans_block.is_valid(journal)
        except AssertionError, e:
            self.assertIsInstance(e, AssertionError)
        finally:
            if gossip is not None:
                gossip.shutdown()

    def test_journal_transaction_block_missing_transactions(self):
        # Test missing transactions, should return list of missing
        # transactions
        minfo = {'__SIGNATURE__': 'Test', "BlockNum": 0}
        trans_block = TransactionBlock(minfo)
        (gossip, journal) = self._create_journal()
        node = gossip.LocalNode
        trans_block.sign_from_node(node)
        missing = trans_block.missing_transactions(journal)
        # No missing transactions
        self.assertEqual(missing, [])

        minfo = {'__SIGNATURE__': 'Test', '__NONCE__': time.time(),
                 'Dependencies': []}
        transaction = Transaction(minfo)
        transaction.sign_from_node(node)
        trans_block.TransactionIDs += [transaction.Identifier]
        missing = trans_block.missing_transactions(journal)
        # One missing transactions
        self.assertEqual(missing, [transaction.Identifier])

        journal.transaction_store[transaction.Identifier] = transaction
        missing = trans_block.missing_transactions(journal)
        # Back to no missing transactions
        self.assertEqual(missing, [])

    def test_journal_transaction_block_update_block_weight(self):
        # Test block update weight
        minfo = {'__SIGNATURE__': 'Test', "BlockNum": 0}
        trans_block = TransactionBlock(minfo)
        trans_block.Status = tbStatus.valid

        (gossip, journal) = self._create_journal()
        node = gossip.LocalNode
        trans_block.sign_from_node(gossip.LocalNode)
        trans_block.update_block_weight(journal)
        # No transactions
        self.assertEqual(trans_block.TransactionDepth, 0)

        minfo = {'__SIGNATURE__': 'Test', '__NONCE__': time.time(),
                 'Dependencies': []}
        transaction = Transaction(minfo)
        transaction.sign_from_node(node)
        trans_block.TransactionIDs += [transaction.Identifier]
        trans_block.update_block_weight(journal)
        # One transaction
        self.assertEqual(trans_block.TransactionDepth, 1)

        minfo = {'__SIGNATURE__': 'Test', "BlockNum": 1,
                 'PreviousBlockID': trans_block.Identifier}
        new_trans_block = TransactionBlock(minfo)
        new_trans_block.Status = tbStatus.valid
        journal.block_store[trans_block.Identifier] = trans_block
        new_trans_block.update_block_weight(journal)
        # Get depth from previous block
        self.assertEqual(new_trans_block.TransactionDepth, 1)

    def test_journal_transaction_block_build_message(self):
        # Test build_message, returns a TransactionBlockMessage
        minfo = {'__SIGNATURE__': 'Test', "BlockNum": 0}
        trans_block = TransactionBlock(minfo)
        node = self._create_node()
        trans_block.sign_from_node(node)
        trans_block.Status = tbStatus.valid
        msg = trans_block.build_message()
        self.assertEqual(msg.MessageType,
                          "/journal.messages.TransactionBlockMessage" +
                          "/TransactionBlock")
        self.assertEqual(msg.TransactionBlock, trans_block)

    def test_journal_transaction_block_dump(self):
        # Test that transactions dump the correct info
        minfo = {'__SIGNATURE__': 'Test', "BlockNum": 0}
        trans_block = TransactionBlock(minfo)
        node = self._create_node()
        trans_block.sign_from_node(node)
        trans_block.Status = tbStatus.valid
        tb_dic = trans_block.dump()
        self.assertEqual(tb_dic["TransactionIDs"], [])
        self.assertEqual(tb_dic["TransactionBlockType"], "/TransactionBlock")
        self.assertEqual(tb_dic["BlockNum"], 0)
        self.assertIsNotNone(tb_dic["Signature"])
        self.assertNotEqual(tb_dic["Signature"], "")

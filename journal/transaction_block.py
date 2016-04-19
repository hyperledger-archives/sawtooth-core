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

import logging

from gossip import common, signed_object
from journal.messages import transaction_block_message

logger = logging.getLogger(__name__)


class Status(object):
    """Enumeration for status.

    Capture the various states of the block
        incomplete -- some transactions might be missing
        complete -- all transactions present, not confirmed
        valid -- all transaction present, confirmed valid
        invalid -- all transactions present, confirmed invalid
    """
    incomplete = 0
    complete = 1
    valid = 2
    invalid = 3


class TransactionBlock(signed_object.SignedObject):
    """A Transaction Block is a set of transactions to be applied to
    a ledger.

    Attributes:
        TransactionBlockTypeName (str): The name of the transaction
            block type.
        MessageType (type): The transaction block message class.
        BlockNum (int): The number of the block.
        PreviousBlockID (str): The ID of the previous block.
        TransactionIDs (list): A list of transaction IDs on this block.
        Status (Status): The status of the block.
        TransactionDepth (int): The number of transactions on the block.
    """
    TransactionBlockTypeName = "/TransactionBlock"
    MessageType = transaction_block_message.TransactionBlockMessage

    def __init__(self, minfo={}):
        """Constructor for the TransactionBlock class.

        Args:
            minfo (dict): A dict of values for initializing
                TransactionBlocks.
        """
        super(TransactionBlock, self).__init__(minfo)

        self.BlockNum = minfo.get('BlockNum', 0)
        self.PreviousBlockID = minfo.get('PreviousBlockID',
                                         common.NullIdentifier)
        self.TransactionIDs = []

        if 'TransactionIDs' in minfo:
            for txnid in minfo['TransactionIDs']:
                self.TransactionIDs.append(str(txnid))

        self.CommitTime = 0
        self.Status = Status.incomplete
        self.TransactionDepth = 0

    def __str__(self):
        return "{0}, {1}, {2}, {3:0.2f}".format(
            self.BlockNum, self.Identifier[:8], len(self.TransactionIDs),
            self.CommitTime)

    def __cmp__(self, other):
        """
        Compare two blocks, this will throw an error unless
        both blocks are valid.
        """
        if self.Status != Status.valid:
            raise ValueError('block {0} must be valid for comparison'.format(
                self.Identifier))

        if other.Status != Status.valid:
            raise ValueError('block {0} must be valid for comparison'.format(
                other.Identifier))

        if self.TransactionDepth < other.TransactionDepth:
            return -1
        elif self.TransactionDepth > other.TransactionDepth:
            return 1
        else:
            return cmp(self.Identifier, other.Identifier)

    def is_valid(self, journal):
        """Verify that the block received is valid.

        For now this simply verifies that the signature is correct.

        Args:
            journal (journal.Journal): Journal for pulling context.
        """
        return super(TransactionBlock, self).is_valid(None)

    def missing_transactions(self, journal):
        """Verify that all the transaction references in the block exist
        in the transaction store and request any that are missing.

        Args:
            journal (journal.Journal): Journal for pulling context.

        Returns:
            list: A list of missing transactions.
        """
        missing = []
        for txnid in self.TransactionIDs:
            if txnid not in journal.TransactionStore:
                missing.append(txnid)

        return missing

    def update_transaction_depth(self, journal):
        """Compute the depth of transactions.

        Args:
            journal (journal.Journal): Journal for pulling context.
        """
        assert self.Status == Status.valid
        self.TransactionDepth = len(self.TransactionIDs)

        if self.PreviousBlockID != common.NullIdentifier:
            assert self.PreviousBlockID in journal.BlockStore
            self.TransactionDepth += journal.BlockStore[
                self.PreviousBlockID].TransactionDepth

    def build_message(self):
        """Constructs a message containing the transaction block.

        Returns:
            msg (message.Message): A transaction block message containing the
                transaction block.
        """
        msg = self.MessageType()
        msg.TransactionBlock = self
        return msg

    def dump(self):
        """Builds a dict containing information about the transaction
        block.

        Returns:
            dict: A dict containing details about the transaction block.
        """
        result = super(TransactionBlock, self).dump()

        result['BlockNum'] = self.BlockNum
        result['PreviousBlockID'] = self.PreviousBlockID
        result['TransactionBlockType'] = self.TransactionBlockTypeName

        result['TransactionIDs'] = []
        for txnid in self.TransactionIDs:
            result['TransactionIDs'].append(str(txnid))

        return result

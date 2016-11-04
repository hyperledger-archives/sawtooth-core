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

from journal import transaction_block
from journal.messages import transaction_block_message

logger = logging.getLogger(__name__)


def register_message_handlers(journal):
    """Registers quorum transaction block message handlers with
    the journal.

    Args:
        journal (QuorumJournal): The journal on which to register the
            message handlers.
    """
    journal.dispatcher.register_message_handler(
        QuorumTransactionBlockMessage,
        transaction_block_message.transaction_block_message_handler)


class QuorumTransactionBlockMessage(
        transaction_block_message.TransactionBlockMessage):
    """Quorum transaction block messages represent the message format
    for exchanging information about quorum transaction blocks.

    Attributes:
        QuorumTransactionBlockMessage.MessageType (str): The class name of the
            message.
    """
    MessageType = \
        "/sawtooth_validator.consensus.quorum.QuorumTransactionBlock" \
        "/TransactionBlock"

    def __init__(self, minfo=None):
        """Constructor for QuorumTransactionBlockMessage.

        Args:
            minfo (dict): A dict of initial values for the new
                QuorumTransactionBlockMessage.
        """
        if minfo is None:
            minfo = {}
        super(QuorumTransactionBlockMessage, self).__init__(minfo)

        tinfo = minfo.get('TransactionBlock', {})
        self.TransactionBlock = QuorumTransactionBlock(tinfo)


class QuorumTransactionBlock(transaction_block.TransactionBlock):
    """A quorum transaction block is a set of quorum transactions to
    be applied to a ledger.

    Attributes:
        QuorumTransactionBlock.TransactionBlockTypeName (str): The name of the
            quorum block type.
        QuorumTransactionBlock.MessageType (type): The quorum transaction block
            message class.
        BlockNumber (int): The number of the block.
    """
    TransactionBlockTypeName = '/Quorum'
    MessageType = QuorumTransactionBlockMessage

    def __init__(self, minfo=None):
        """Constructor for the QuorumTransactionBlock class.

        Args:
            minfo (dict): A dict containing intitial values for
                the new QuorumTransactionBlock.
        """
        if minfo is None:
            minfo = {}
        super(QuorumTransactionBlock, self).__init__(minfo)
        self.BlockNumber = minfo.get('BlockNumber', 0)

    def __str__(self):
        return "{0}, {1}, {2:0.2f}, {3}".format(
            self.Identifier[:8], len(self.TransactionIDs), self.CommitTime,
            self.BlockNumber)

    def dump(self):
        """Returns a dict with information about the quorum transaction
        block.

        Returns:
            dict: A dict containing info about the quorum transaction
                block.
        """
        result = super(QuorumTransactionBlock, self).dump()
        result['BlockNumber'] = self.BlockNumber

        return result

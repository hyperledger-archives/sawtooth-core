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
    """Registers the transaction block message handlers with
    the journal.

    Args:
        journal (DevModeJournal): The journal on which to register the
            message handlers.
    """
    journal.register_message_handler(
        DevModeTransactionBlockMessage,
        transaction_block_message.transaction_block_message_handler)


class DevModeTransactionBlockMessage(
        transaction_block_message.TransactionBlockMessage):
    """DevMode transaction block messages represent the message format
    for exchanging information about dev_mode transaction blocks.

    Attributes:
        DevModeTransactionBlockMessage.MessageType (str): The class name of
            the message.
    """
    MessageType = \
        "/DevMode/TransactionBlock"

    def __init__(self, minfo={}):
        super(DevModeTransactionBlockMessage, self).__init__(minfo)

        tinfo = minfo.get('TransactionBlock', {})
        self.TransactionBlock = DevModeTransactionBlock(tinfo)


class DevModeTransactionBlock(transaction_block.TransactionBlock):
    """A DevMode transaction block is a set of transactions to
    be applied to a ledger.

    Attributes:
        DevModeTransactionBlock.TransactionBlockTypeName (str): The name of
            the transaction block type.
        DevModeTransactionBlock.MessageType (type): The dev_mode transaction
            block message class.
        DevModeTransactionBlock.WaitTimer (poet.wait_timer.WaitTimer): The wait
            timer for the block.
    """
    TransactionBlockTypeName = '/TransactionBlock/TransactionBlock'
    MessageType = DevModeTransactionBlockMessage

    def __init__(self, minfo={}):
        """Constructor for the DevModeTransactionBlock class.

        Args:
            minfo (dict): A dict of values for initializing
                DevModeTransactionBlocks.
        """
        super(DevModeTransactionBlock, self).__init__(minfo)

    def __str__(self):
        return "{0}, {1}, {2}".format(
            self.BlockNum,
            self.Identifier[:8],
            len(self.TransactionIDs)
        )

    def __cmp__(self, other):
        """
        Compare two blocks, this will throw an error unless
        both blocks are valid.
        """
        if self.Status != transaction_block.Status.valid:
            raise ValueError('block {0} must be valid for comparison'.format(
                self.Identifier))

        if other.Status != transaction_block.Status.valid:
            raise ValueError('block {0} must be valid for comparison'.format(
                other.Identifier))

        if self.TransactionDepth < other.TransactionDepth:
            return -1
        elif self.TransactionDepth > other.TransactionDepth:
            return 1
        else:
            return cmp(self.Identifier, other.Identifier)

    def is_valid(self, journal):
        """Verifies that the block received is valid.

        Args:
            journal (DevModeJournal): Journal for pulling context.
        """
        if not super(DevModeTransactionBlock, self).is_valid(journal):
            return False

        return True

    def dump(self):
        """Returns a dict with information about the transaction
        block.

        Returns:
            dict: A dict containing information about the
                transaction block.
        """
        result = super(DevModeTransactionBlock, self).dump()
        return result

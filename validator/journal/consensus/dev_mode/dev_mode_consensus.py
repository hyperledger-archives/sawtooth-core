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
from time import time
from journal.consensus.consensus_base import Consensus
from journal.consensus.dev_mode import dev_mode_transaction_block

logger = logging.getLogger(__name__)


class DevModeConsensus(Consensus):
    """Implements a journal based on the DevMode consensus.

    Attributes:
        block_publisher (EventHandler): The EventHandler tracking
            calls to make when the heartbeat timer fires.
    """
    def __init__(self,
                 block_publisher=None,
                 block_wait_time=None):
        """Constructor for the DevModeJournal class.

        Args:
            node (Node): The local node.
        """

        # the one who can publish blocks is always the genesis ledger
        self._block_publisher = True
        if block_publisher is not None:
            self._block_publisher = block_publisher
        self._block_wait_time = 1
        if block_wait_time is not None:
            self._block_wait_time = int(block_wait_time)

        self._next_block_time = time()

    def initialization_complete(self, journal):
        # initialize the block handlers
        dev_mode_transaction_block.register_message_handlers(journal)

    def build_block(self, journal, force=False):
        """Builds a transaction block that is specific to this particular
        consensus mechanism, in this case we build a block that contains a
        wait certificate.

        Args:
            force (boolean): Whether to force creation of the initial
                block.

        Returns:
            DevModeTransactionBlock: candidate transaction block
        """
        if not self._block_publisher:
            return None

        if not force and \
                len(journal.pending_transactions) == 0:
            return None

        logger.debug('attempt to build transaction block extending %s',
                     journal.most_recent_committed_block_id[:8])

        logger.info('build transaction block to extend %s'
                    'transactions', journal.most_recent_committed_block_id[:8])

        # Create a new block from all of our pending transactions
        new_block = dev_mode_transaction_block.DevModeTransactionBlock()
        new_block.BlockNum = journal.most_recent_committed_block.BlockNum \
            + 1 if journal.most_recent_committed_block else 0
        new_block.PreviousBlockID = journal.most_recent_committed_block_id
        journal.on_pre_build_block.fire(journal, new_block)

        logger.debug('created new pending block')

        self._next_block_time = time() + self._block_wait_time
        return new_block

    def claim_block(self, journal, block):
        """Claims the block and transmits a message to the network
        that the local node won.

        Args:
            nblock (DevModeTransactionBlock): The block to claim.
        """

        block.TransactionIDs = journal._prepare_transaction_list(
            journal.maximum_transactions_per_block)

        logger.info('node %s validates block with %d transactions',
                    journal.local_node.Name, len(block.TransactionIDs))

        # Claim the block
        block.sign_from_node(journal.local_node)
        journal.JournalStats.BlocksClaimed.increment()

        # And send out the message that we won
        msg = dev_mode_transaction_block.DevModeTransactionBlockMessage()
        msg.TransactionBlock = block
        return msg

    def verify_block(self, journal, block):
        return self.is_valid(self, journal)

    def check_claim_block(self, journal, block, now):
        return len(journal.pending_transactions) != 0 and \
            now > self._next_block_time

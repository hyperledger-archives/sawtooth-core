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
from journal import journal_core
from journal.consensus.dev_mode import dev_mode_transaction_block

logger = logging.getLogger(__name__)


class DevModeJournal(journal_core.Journal):
    """Implements a journal based on the DevMode consensus.

    Attributes:
        onHeartBeatTimer (EventHandler): The EventHandler tracking
            calls to make when the heartbeat timer fires.
    """
    def __init__(self,
                 local_node,
                 gossip,
                 gossip_dispatcher,
                 stat_domains,
                 minimum_transactions_per_block=None,
                 max_transactions_per_block=None,
                 max_txn_age=None,
                 genesis_ledger=None,
                 data_directory=None,
                 store_type=None,
                 block_wait_time=None):
        """Constructor for the DevModeJournal class.

        Args:
            node (Node): The local node.
        """

        super(DevModeJournal, self).__init__(
            local_node,
            gossip,
            gossip_dispatcher,
            stat_domains,
            minimum_transactions_per_block,
            max_transactions_per_block,
            max_txn_age,
            genesis_ledger,
            data_directory,
            store_type)

        # the one who can publish blocks is always the genesis ledger
        self.block_publisher = self.GenesisLedger
        self.block_wait_time = 1
        if block_wait_time is not None:
            self.block_wait_time = int(block_wait_time)

        # default invalid block wait times to 1 second setting to
        if not isinstance(self.block_wait_time, (int, long)):
            self.block_wait_time = 1

        self.next_block_time = time()
        self.dispatcher.on_heartbeat += self._check_claim_block

        # initialize the block handlers
        dev_mode_transaction_block.register_message_handlers(self)

    def build_transaction_block(self, force=False):
        """Builds a transaction block that is specific to this particular
        consensus mechanism, in this case we build a block that contains a
        wait certificate.

        Args:
            force (boolean): Whether to force creation of the initial
                block.

        Returns:
            DevModeTransactionBlock: candidate transaction block
        """
        if not self.block_publisher:
            return None

        if not force and \
                len(self.pending_transactions) == 0:
            return None

        logger.debug('attempt to build transaction block extending %s',
                     self.most_recent_committed_block_id[:8])

        logger.info('build transaction block to extend %s'
                    'transactions', self.most_recent_committed_block_id[:8])

        # Create a new block from all of our pending transactions
        new_block = dev_mode_transaction_block.DevModeTransactionBlock()
        new_block.BlockNum = self.most_recent_committed_block.BlockNum \
            + 1 if self.most_recent_committed_block else 0
        new_block.PreviousBlockID = self.most_recent_committed_block_id
        self.on_pre_build_block.fire(self, new_block)

        # must put a cap on the transactions in the block
        if len(new_block.TransactionIDs) >= \
                self.maximum_transactions_per_block:
            new_block.TransactionIDs = \
                new_block.TransactionIDs[:self.maximum_transactions_per_block]

        logger.debug('created new pending block')

        # fire the build block event handlers
        self.on_build_block.fire(self, new_block)

        self.next_block_time = time() + self.block_wait_time
        return new_block

    def claim_transaction_block(self, nblock):
        """Claims the block and transmits a message to the network
        that the local node won.

        Args:
            nblock (DevModeTransactionBlock): The block to claim.
        """
        # Get the list of prepared transactions, if there aren't enough
        # then just return
        self.pending_transaction_block = None

        txn_list = self._prepare_transaction_list(
            self.maximum_transactions_per_block)
        nblock.TransactionIDs = txn_list

        logger.info('node %s validates block with %d transactions',
                    self.local_node.Name, len(nblock.TransactionIDs))

        # Claim the block
        nblock.sign_from_node(self.local_node)
        self.JournalStats.BlocksClaimed.increment()

        # Fire the event handler for block claim
        self.on_claim_block.fire(self, nblock)

        # And send out the message that we won
        msg = dev_mode_transaction_block.DevModeTransactionBlockMessage()
        msg.TransactionBlock = nblock
        self.gossip.broadcast_message(msg)

    def _check_claim_block(self, now):
        if not self.block_publisher:
            return

        if self.pending_transaction_block and \
                len(self.pending_transactions) != 0 and \
                time() > self.next_block_time:
            self.claim_transaction_block(self.pending_transaction_block)

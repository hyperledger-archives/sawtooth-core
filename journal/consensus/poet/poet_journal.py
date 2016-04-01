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

import collections
import logging

from journal.consensus.poet import poet_transaction_block
from gossip import common, stats
from journal import journal_core
from journal.consensus.poet.wait_certificate import WaitTimer

logger = logging.getLogger(__name__)


class PoetJournal(journal_core.Journal):
    """Implements a journal based on the proof of elapsed time
    consensus mechanism.

    Attributes:
        onHeartBeatTimer (EventHandler): The EventHandler tracking
            calls to make when the heartbeat timer fires.
        MaximumBlocksToKeep (int): The maximum number of blocks to
            keep.
    """
    def __init__(self, node, **kwargs):
        """Constructor for the PoetJournal class.

        Args:
            node (Node): The local node.
        """
        super(PoetJournal, self).__init__(node, **kwargs)

        self.onHeartbeatTimer += self._check_certificate

        # initialize the poet handlers
        poet_transaction_block.register_message_handlers(self)

        # initialize stats specifically for the block chain journal
        self.JournalStats.add_metric(stats.Counter('BlocksClaimed'))

        # propagate the maximum blocks to keep
        self.MaximumBlocksToKeep = max(self.MaximumBlocksToKeep,
                                       WaitTimer.CertificateSampleLength)

    def build_transaction_block(self, force=False):
        """Builds a transaction block that is specific to this particular
        consensus mechanism, in this case we build a block that contains a
        wait certificate.

        Args:
            force (boolean): Whether to force creation of the initial
                block.

        Returns:
            PoetTransactionBlock: The constructed block with the wait
                certificate.
        """
        logger.debug('attempt to build transaction block extending %s',
                     self.MostRecentCommitedBlockID[:8])

        # Get the list of prepared transactions, if there aren't enough
        # then just return
        txnlist = self._preparetransactionlist(
            self.MaximumTransactionsPerBlock)
        if len(txnlist) < self.MinimumTransactionsPerBlock and not force:
            logger.debug('no transactions found, no block constructed')
            return None

        logger.info('build transaction block to extend %s with %s '
                    'transactions',
                    self.MostRecentCommitedBlockID[:8], len(txnlist))

        # Create a new block from all of our pending transactions
        nblock = poet_transaction_block.PoetTransactionBlock()
        nblock.BlockNum = self.MostRecentCommitedBlock.BlockNum \
            + 1 if self.MostRecentCommitedBlock else 0
        nblock.PreviousBlockID = self.MostRecentCommitedBlockID
        nblock.TransactionIDs = txnlist
        nblock.create_wait_timer(self._build_certificate_list(nblock))

        # must put a cap on the transactions in the block
        if len(nblock.TransactionIDs) >= self.MaximumTransactionsPerBlock:
            nblock.TransactionIDs = \
                nblock.TransactionIDs[:self.MaximumTransactionsPerBlock]

        logger.debug('created new pending block with timer <%s> and '
                     '%d transactions', nblock.WaitTimer,
                     len(nblock.TransactionIDs))

        # fire the build block event handlers
        self.onBuildBlock.fire(self, nblock)

        return nblock

    def claim_transaction_block(self, nblock):
        """Claims the block and transmits a message to the network
        that the local node won.

        Args:
            nblock (PoetTransactionBlock): The block to claim.
        """
        logger.info('node %s validates block with %d transactions',
                    self.LocalNode.Name, len(nblock.TransactionIDs))

        # Claim the block
        nblock.create_wait_certificate()
        nblock.sign_from_node(self.LocalNode)
        self.JournalStats.BlocksClaimed.increment()

        # Fire the event handler for block claim
        self.onClaimBlock.fire(self, nblock)

        # And send out the message that we won
        msg = poet_transaction_block.PoetTransactionBlockMessage()
        msg.TransactionBlock = nblock
        msg.SenderID = self.LocalNode.Identifier
        msg.sign_from_node(self.LocalNode)

        self.PendingTransactionBlock = None
        self.handle_message(msg)

    def _build_certificate_list(self, block):
        # for the moment we just dump all of these into one list,
        # not very efficient but it makes things a lot easier to maintain
        certs = collections.deque()
        count = WaitTimer.CertificateSampleLength

        while block.PreviousBlockID != common.NullIdentifier \
                and len(certs) < count:
            block = self.BlockStore[block.PreviousBlockID]
            certs.appendleft(block.WaitCertificate)

        # drop the root block off the computation
        return list(certs)

    def _check_certificate(self, now):
        if self.PendingTransactionBlock \
                and self.PendingTransactionBlock.wait_timer_is_expired(now):
            self.claim_transaction_block(self.PendingTransactionBlock)

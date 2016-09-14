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
import importlib

from time import time

from gossip import common, stats
from journal import journal_core
from journal.consensus.poet0 import poet_transaction_block
from journal.consensus.poet0.wait_timer import WaitTimer
from journal.consensus.poet0.wait_certificate import WaitCertificate

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

        enclave_module = None
        if 'PoetEnclaveImplementation' in kwargs:
            enclave_module = kwargs['PoetEnclaveImplementation']
        else:
            enclave_module = 'journal.consensus.poet0.poet_enclave_simulator' \
                             '.poet_enclave_simulator'

        poet_enclave = importlib.import_module(enclave_module)
        poet_enclave.initialize(**kwargs)
        WaitCertificate.poet_enclave = poet_enclave
        WaitTimer.poet_enclave = poet_enclave

        self.onHeartbeatTimer += self._check_certificate

        # initialize handlers
        poet_transaction_block.register_message_handlers(self)

        # initialize stats specifically for the block chain journal
        self.JournalStats.add_metric(stats.Value('LocalMeanTime', 0))
        self.JournalStats.add_metric(stats.Value('AggregateLocalMean', '0'))
        self.JournalStats.add_metric(stats.Value('PopulationEstimate', '0'))
        self.JournalStats.add_metric(stats.Value('ExpectedExpirationTime',
                                                 '0'))
        self.JournalStats.add_metric(stats.Value('Duration', '0'))

        # propagate the maximum blocks to keep
        self.MaximumBlocksToKeep = max(self.MaximumBlocksToKeep,
                                       WaitTimer.certificate_sample_length)

    def build_transaction_block(self, genesis=False):
        """Builds a transaction block that is specific to this particular
        consensus mechanism, in this case we build a block that contains a
        wait certificate.

        Args:
            genesis (boolean): Whether to force creation of the initial
                block.

        Returns:
            PoetTransactionBlock: The constructed block with the wait
                certificate.
        """
        logger.debug('attempt to build transaction block extending %s',
                     self.MostRecentCommittedBlockID[:8])
        with self._txn_lock:
            # Create a new block from all of our pending transactions
            nblock = poet_transaction_block.PoetTransactionBlock()
            nblock.BlockNum = self.MostRecentCommittedBlock.BlockNum \
                + 1 if self.MostRecentCommittedBlock else 0
            nblock.PreviousBlockID = self.MostRecentCommittedBlockID

            self.onPreBuildBlock.fire(self, nblock)

            # Get the list of prepared transactions, if there aren't enough
            # then just return
            txnlist = self._preparetransactionlist(
                self.MaximumTransactionsPerBlock)
            transaction_time_waiting = time() - self.TransactionEnqueueTime\
                if self.TransactionEnqueueTime is not None else 0
            if len(txnlist) < self.MinimumTransactionsPerBlock and\
                    not genesis and\
                    transaction_time_waiting <\
                    self.MaximumTransactionsWaitTime:
                logger.debug('Not enough transactions(%d, %d required) to '
                             'build block, no block constructed. Mandatory'
                             'block creation in %f seconds',
                             len(txnlist),
                             self.MinimumTransactionsPerBlock,
                             self.MaximumTransactionsWaitTime -
                             transaction_time_waiting)
                return None
            else:
                # we know that the transaction list is a subset of the
                # pending transactions, if it is less then all of them
                # then set the TransactionEnqueueTime we can track these
                # transactions wait time.
                remaining_transactions = len(self.PendingTransactions) - \
                    len(txnlist)
                self.TransactionEnqueueTime =\
                    time() if remaining_transactions > 0 else None

            logger.info('build transaction block to extend %s with %s '
                        'transactions',
                        self.MostRecentCommittedBlockID[:8], len(txnlist))

            # Create a new block from all of our pending transactions
            nblock = poet_transaction_block.PoetTransactionBlock()
            nblock.BlockNum = self.MostRecentCommittedBlock.BlockNum \
                + 1 if self.MostRecentCommittedBlock else 0
            nblock.PreviousBlockID = self.MostRecentCommittedBlockID
            nblock.TransactionIDs = txnlist

            nblock.create_wait_timer(
                self.LocalNode.signing_address(),
                self._build_certificate_list(nblock))

            self.JournalStats.LocalMeanTime.Value = nblock.WaitTimer.local_mean
            self.JournalStats.PopulationEstimate.Value = \
                round(nblock.WaitTimer.local_mean /
                      nblock.WaitTimer.target_wait_time, 2)

            if genesis:
                nblock.AggregateLocalMean = nblock.WaitTimer.local_mean

            self.JournalStats.PreviousBlockID.Value = nblock.PreviousBlockID

            # must put a cap on the transactions in the block
            if len(nblock.TransactionIDs) >= self.MaximumTransactionsPerBlock:
                nblock.TransactionIDs = \
                    nblock.TransactionIDs[:self.MaximumTransactionsPerBlock]

            logger.debug('created new pending block with timer <%s> and '
                         '%d transactions', nblock.WaitTimer,
                         len(nblock.TransactionIDs))

            self.JournalStats.ExpectedExpirationTime.Value = \
                round(nblock.WaitTimer.request_time +
                      nblock.WaitTimer.duration, 2)

            self.JournalStats.Duration.Value = \
                round(nblock.WaitTimer.duration, 2)

            for txnid in nblock.TransactionIDs:
                txn = self.TransactionStore[txnid]
                txn.InBlock = "Uncommitted"
                self.TransactionStore[txnid] = txn
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
        count = WaitTimer.certificate_sample_length

        while block.PreviousBlockID != common.NullIdentifier \
                and len(certs) < count:
            block = self.BlockStore[block.PreviousBlockID]
            certs.appendleft(block.WaitCertificate)

        # drop the root block off the computation
        return list(certs)

    def _check_certificate(self, now):
        with self._txn_lock:
            if self.PendingTransactionBlock:
                if self.PendingTransactionBlock.wait_timer_is_expired(now):
                    self.claim_transaction_block(self.PendingTransactionBlock)
            else:
                # No transaction block - check if we must make one due to time
                # waited
                if self.TransactionEnqueueTime is not None:
                    transaction_time_waiting = \
                        time() - self.TransactionEnqueueTime
                else:
                    transaction_time_waiting = 0
                if transaction_time_waiting > self.MaximumTransactionsWaitTime:
                    logger.debug("Transaction wait timeout "
                                 "calling build block")
                    self.PendingTransactionBlock = \
                        self.build_transaction_block()

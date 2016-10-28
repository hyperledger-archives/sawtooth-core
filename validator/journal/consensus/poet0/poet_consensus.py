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

from gossip import common, stats
from journal.consensus.consensus_base import Consensus
from journal.consensus.poet0 import poet_transaction_block
from journal.consensus.poet0.wait_timer import WaitTimer
from journal.consensus.poet0.wait_certificate import WaitCertificate

logger = logging.getLogger(__name__)


class PoetConsensus(Consensus):
    """Implements a Proof of Elapsed Time(PoET) consensus mechanism.
    """

    def __init__(self, kwargs):
        """Constructor for the PoetJournal class.

        Args:
            node (Node): The local node.
        """
        if 'PoetEnclaveImplementation' in kwargs:
            enclave_module = kwargs['PoetEnclaveImplementation']
        else:
            enclave_module = 'journal.consensus.poet0.poet_enclave_simulator' \
                             '.poet0_enclave_simulator'

        poet_enclave = importlib.import_module(enclave_module)
        poet_enclave.initialize(**kwargs)
        WaitCertificate.poet_enclave = poet_enclave
        WaitTimer.poet_enclave = poet_enclave

    def initialization_complete(self, journal):
        # propagate the maximum blocks to keep
        journal.maximum_blocks_to_keep = max(
            journal.maximum_blocks_to_keep,
            WaitTimer.certificate_sample_length)
        # initialize stats specifically for the block chain journal
        journal.JournalStats.add_metric(stats.Value('LocalMeanTime', 0))
        journal.JournalStats.add_metric(stats.Value('AggregateLocalMean', '0'))
        journal.JournalStats.add_metric(stats.Value('PopulationEstimate', '0'))
        journal.JournalStats.add_metric(stats.Value('ExpectedExpirationTime',
                                                    '0'))
        journal.JournalStats.add_metric(stats.Value('Duration', '0'))

        # initialize the block handlers
        poet_transaction_block.register_message_handlers(journal)

    def build_block(self, journal, genesis=False):
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
                     journal.most_recent_committed_block_id[:8])
        # Create a new block from all of our pending transactions
        nblock = poet_transaction_block.PoetTransactionBlock()
        nblock.BlockNum = journal.most_recent_committed_block.BlockNum \
            + 1 if journal.most_recent_committed_block else 0
        nblock.PreviousBlockID = journal.most_recent_committed_block_id

        journal.on_pre_build_block.fire(journal, nblock)

        txnlist = journal._prepare_transaction_list(
            journal.maximum_transactions_per_block)

        if len(txnlist) == 0 and not genesis:
            return None

        logger.info('build transaction block to extend %s with %s '
                    'transactions',
                    journal.most_recent_committed_block_id[:8], len(txnlist))

        # Create a new block from all of our pending transactions
        nblock = poet_transaction_block.PoetTransactionBlock()
        nblock.BlockNum = journal.most_recent_committed_block.BlockNum \
            + 1 if journal.most_recent_committed_block else 0
        nblock.PreviousBlockID = journal.most_recent_committed_block_id
        nblock.TransactionIDs = txnlist

        nblock.create_wait_timer(
            journal.local_node.signing_address(),
            self._build_certificate_list(journal.block_store, nblock))

        journal.JournalStats.LocalMeanTime.Value = \
            nblock.wait_timer.local_mean
        journal.JournalStats.PopulationEstimate.Value = \
            round(nblock.wait_timer.local_mean /
                  nblock.wait_timer.target_wait_time, 2)

        if genesis:
            nblock.AggregateLocalMean = nblock.wait_timer.local_mean

        journal.JournalStats.PreviousBlockID.Value = nblock.PreviousBlockID

        logger.debug('created new pending block with timer <%s> and '
                     '%d transactions', nblock.wait_timer,
                     len(nblock.TransactionIDs))

        journal.JournalStats.ExpectedExpirationTime.Value = \
            round(nblock.wait_timer.request_time +
                  nblock.wait_timer.duration, 2)

        journal.JournalStats.Duration.Value = \
            round(nblock.wait_timer.duration, 2)

        for txnid in nblock.TransactionIDs:
            txn = journal.transaction_store[txnid]
            txn.InBlock = "Uncommitted"
            journal.transaction_store[txnid] = txn

        return nblock

    def claim_block(self, journal, block):
        """Claims the block and transmits a message to the network
        that the local node won.

        Args:
            block (PoetTransactionBlock): The block to claim.
        Returns:
            message: the block message to broadcast to the network.
        """
        logger.info('node %s validates block with %d transactions',
                    journal.local_node.Name, len(block.TransactionIDs))

        # Claim the block
        block.create_wait_certificate()
        block.sign_from_node(journal.local_node)
        journal.JournalStats.BlocksClaimed.increment()

        # Fire the event handler for block claim
        journal.on_claim_block.fire(journal, block)

        # And send out the message that we won
        msg = poet_transaction_block.PoetTransactionBlockMessage()
        msg.TransactionBlock = block
        return msg

    def _build_certificate_list(self, block_store, block):
        # for the moment we just dump all of these into one list,
        # not very efficient but it makes things a lot easier to maintain
        certs = collections.deque()
        count = WaitTimer.certificate_sample_length

        while block.PreviousBlockID != common.NullIdentifier \
                and len(certs) < count:
            block = block_store[block.PreviousBlockID]
            certs.appendleft(block.wait_certificate)

        # drop the root block off the computation
        return list(certs)

    def check_claim_block(self, journal, block, now):
        return block.wait_timer_is_expired(now)

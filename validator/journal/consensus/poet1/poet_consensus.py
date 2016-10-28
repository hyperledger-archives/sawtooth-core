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
import hashlib

import pybitcointools

from gossip import common
from gossip import stats
from journal.consensus.consensus_base import Consensus
from journal.consensus.poet1 import poet_transaction_block
from journal.consensus.poet1 import validator_registry as val_reg
from journal.consensus.poet1.signup_info import SignupInfo
from journal.consensus.poet1.wait_timer import WaitTimer
from journal.consensus.poet1.wait_certificate import WaitCertificate

LOGGER = logging.getLogger(__name__)


class PoetConsensus(Consensus):
    """Implements a journal based on the proof of elapsed time
    consensus mechanism.

    Attributes:
        onHeartBeatTimer (EventHandler): The EventHandler tracking
            calls to make when the heartbeat timer fires.
        MaximumBlocksToKeep (int): The maximum number of blocks to
            keep.
    """

    def __init__(self, kwargs):
        """Constructor for the PoetJournal class.

        Args:
            kwargs (dict):
        """

        if 'PoetEnclaveImplementation' in kwargs:
            enclave_module = kwargs['PoetEnclaveImplementation']
        else:
            enclave_module = 'journal.consensus.poet1.poet_enclave_simulator' \
                             '.poet_enclave_simulator'

        poet_enclave = importlib.import_module(enclave_module)
        poet_enclave.initialize(**kwargs)
        WaitCertificate.poet_enclave = poet_enclave
        WaitTimer.poet_enclave = poet_enclave
        SignupInfo.poet_enclave = poet_enclave

    def initialization_complete(self, journal):
        """Processes all invocations that arrived while the ledger was
        being initialized.
        """
        # Before we allow the base journal to do anything that might result
        # in a wait timer or wait certificate being created, we have to ensure
        # the PoET enclave has been initialized.  This can be done in one of
        # two ways:
        # 1. If we have sealed signup data (meaning that we have previously
        #    created signup info), we can request that the enclave unseal it,
        #    in the process restoring the enclave to its previous state.
        # 2. Create new signup information.
        signup_info = None
        sealed_signup_data = journal.local_store.get('sealed_signup_data')

        if sealed_signup_data is not None:
            SignupInfo.unseal_signup_data(
                sealed_signup_data=sealed_signup_data)
        else:
            wait_certificate_id = journal.most_recent_committed_block_id
            public_key_hash = \
                hashlib.sha256(
                    pybitcointools.encode_public_key(
                        journal.local_node.public_key(),
                        'hex')).hexdigest()

            signup_info = \
                SignupInfo.create_signup_info(
                    originator_public_key_hash=public_key_hash,
                    validator_network_basename='Intel Validator Network',
                    most_recent_wait_certificate_id=wait_certificate_id)

            # Save off the sealed signup data
            journal.local_store.set(
                'sealed_signup_data',
                signup_info.sealed_signup_data)
            journal.local_store.sync()

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

        # If we created signup information, then insert ourselves into the
        # validator registry.
        if signup_info is not None:
            # Create a validator register transaction and sign it.  Wrap
            # the transaction in a message.  Broadcast it to out.
            transaction = \
                val_reg.ValidatorRegistryTransaction.register_validator(
                    journal.local_node.Name,
                    journal.local_node.Identifier,
                    signup_info)
            transaction.sign_from_node(journal.local_node)

            message = \
                val_reg.ValidatorRegistryTransactionMessage()
            message.Transaction = transaction

            LOGGER.info(
                'Register PoET 1 validator with name %s',
                journal.local_node.Name)

            journal.gossip.broadcast_message(message)

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
        LOGGER.debug('attempt to build transaction block extending %s',
                     journal.most_recent_committed_block_id[:8])
        # Create a new block from all of our pending transactions
        nblock = poet_transaction_block.PoetTransactionBlock()
        nblock.BlockNum = journal.most_recent_committed_block.BlockNum \
            + 1 if journal.most_recent_committed_block else 0
        nblock.PreviousBlockID = journal.most_recent_committed_block_id

        journal.on_pre_build_block.fire(journal, nblock)

        # Get the list of prepared transactions, if there aren't enough
        # then just return
        txnlist = journal._prepare_transaction_list(
            journal.maximum_transactions_per_block)
        if len(txnlist) == 0 and not genesis:
            return None

        LOGGER.info('build transaction block to extend %s with %s '
                    'transactions',
                    journal.most_recent_committed_block_id[:8], len(txnlist))

        # Create a new block from all of our pending transactions
        nblock = poet_transaction_block.PoetTransactionBlock()
        nblock.BlockNum = journal.most_recent_committed_block.BlockNum \
            + 1 if journal.most_recent_committed_block else 0
        nblock.PreviousBlockID = journal.most_recent_committed_block_id
        nblock.TransactionIDs = txnlist

        nblock.create_wait_timer(self._build_certificate_list(
            journal.block_store,
            nblock))

        journal.JournalStats.LocalMeanTime.Value = nblock.WaitTimer.local_mean
        journal.JournalStats.PopulationEstimate.Value = \
            round(nblock.WaitTimer.local_mean /
                  nblock.WaitTimer.target_wait_time, 2)

        if genesis:
            nblock.AggregateLocalMean = nblock.WaitTimer.local_mean

        journal.JournalStats.PreviousBlockID.Value = nblock.PreviousBlockID

        LOGGER.debug('created new pending block with timer <%s> and '
                     '%d transactions', nblock.WaitTimer,
                     len(nblock.TransactionIDs))

        journal.JournalStats.ExpectedExpirationTime.Value = \
            round(nblock.WaitTimer.request_time +
                  nblock.WaitTimer.duration, 2)

        journal.JournalStats.Duration.Value = \
            round(nblock.WaitTimer.duration, 2)

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
            genesis (bool): Are we claiming the genesis block?
        """
        LOGGER.info('node %s validates block with %d transactions',
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
            certs.appendleft(block.WaitCertificate)

        # drop the root block off the computation
        return list(certs)

    def check_claim_block(self, journal, block, now):
        return block.wait_timer_has_expired(now)

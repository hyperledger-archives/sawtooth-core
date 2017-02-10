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

from gossip import common
from gossip import stats
from sawtooth_signing import pbct_nativerecover as signing
from sawtooth_validator.consensus.consensus_base import Consensus
from sawtooth_validator.consensus.poet1 import poet_transaction_block
from sawtooth_validator.consensus.poet1 import validator_registry as val_reg
from sawtooth_validator.consensus.poet1.signup_info import SignupInfo
from sawtooth_validator.consensus.poet1.wait_timer import WaitTimer
from sawtooth_validator.consensus.poet1.wait_certificate import WaitCertificate

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
        self.poet_public_key = None

        if 'PoetEnclaveImplementation' in kwargs:
            enclave_module = kwargs['PoetEnclaveImplementation']
        else:
            enclave_module = 'sawtooth_validator.consensus.poet1.' \
                             'poet_enclave_simulator' \
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
            self.poet_public_key = \
                SignupInfo.unseal_signup_data(
                    validator_address=journal.local_node.signing_address(),
                    sealed_signup_data=sealed_signup_data)
        else:
            wait_certificate_id = journal.most_recent_committed_block_id
            public_key_hash = \
                hashlib.sha256(
                    signing.encode_pubkey(journal.local_node.public_key(),
                                          'hex')).hexdigest()

            signup_info = \
                SignupInfo.create_signup_info(
                    validator_address=journal.local_node.signing_address(),
                    originator_public_key_hash=public_key_hash,
                    most_recent_wait_certificate_id=wait_certificate_id)

            # Save off the sealed signup data
            journal.local_store.set(
                'sealed_signup_data',
                signup_info.sealed_signup_data)
            journal.local_store.sync()

            self.poet_public_key = signup_info.poet_public_key

        # propagate the maximum blocks to keep
        journal.maximum_blocks_to_keep = max(
            journal.maximum_blocks_to_keep,
            WaitTimer.certificate_sample_length)

        # initialize stats specifically for the block chain journal
        journal.JournalStats.add_metric(stats.Value('LocalMeanTime', 0))
        journal.JournalStats.add_metric(stats.Value('AggregateLocalMean', 0))
        journal.JournalStats.add_metric(stats.Value('PopulationEstimate', 0))
        journal.JournalStats.add_metric(stats.Value('ExpectedExpirationTime',
                                                    0))
        journal.JournalStats.add_metric(stats.Value('Duration', 0))

        # initialize the block handlers
        poet_transaction_block.register_message_handlers(journal)

        # If we created signup information, then advertise self to network
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
                'Advertise PoET 1 validator with name %s',
                journal.local_node.Name)

            journal.gossip.broadcast_message(message)

    def create_block(self, pub_key):
        """Creates a candidate transaction block.

        Args:
            pub_key: public key corresponding to the private key used to
                sign the block
        Returns:
            new transaction block.
        """
        minfo = {"PublicKey": pub_key}
        return poet_transaction_block.PoetTransactionBlock(minfo)

    def initialize_block(self, journal, block):
        """Builds a transaction block that is specific to this particular
        consensus mechanism, in this case we build a block that contains a
        wait certificate.

        Args:
            journal: the journal object
            block: the transaction block to initialize.
        Returns:
            PoetTransactionBlock: The constructed block with the wait
                certificate.
        """

        block.create_wait_timer(
            journal.local_node.signing_address(),
            self.build_certificate_list(journal.block_store, block))

        journal.JournalStats.LocalMeanTime.Value = \
            block.wait_timer.local_mean
        journal.JournalStats.PopulationEstimate.Value = \
            round(block.wait_timer.local_mean /
                  block.wait_timer.target_wait_time, 2)

        LOGGER.debug('created new pending block with timer <%s> and '
                     '%d transactions', block.wait_timer,
                     len(block.TransactionIDs))

        journal.JournalStats.ExpectedExpirationTime.Value = \
            round(block.wait_timer.request_time +
                  block.wait_timer.duration, 2)

        journal.JournalStats.Duration.Value = \
            round(block.wait_timer.duration, 2)

    def claim_block(self, journal, block):
        """Claims the block and transmits a message to the network
        that the local node won.

        Args:
            block (PoetTransactionBlock): The block to claim.
            genesis (bool): Are we claiming the genesis block?
        """

        block.create_wait_certificate()
        block.poet_public_key = self.poet_public_key
        block.sign_from_node(journal.local_node)
        journal.JournalStats.BlocksClaimed.increment()

    def create_block_message(self, block):
        msg = poet_transaction_block.PoetTransactionBlockMessage()
        msg.TransactionBlock = block
        return msg

    def build_certificate_list(self, block_store, block):
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
        return block.wait_timer_has_expired(now)

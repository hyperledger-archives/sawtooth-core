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
from sawtooth_validator.consensus.consensus_base import Consensus
from sawtooth_validator.consensus.poet0 import poet_transaction_block
from sawtooth_validator.consensus.poet0.wait_timer import WaitTimer
from sawtooth_validator.consensus.poet0.wait_certificate import WaitCertificate

LOGGER = logging.getLogger(__name__)


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
            enclave_module = 'sawtooth_validator.consensus.poet0.' \
                             'poet_enclave_simulator' \
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
        journal.JournalStats.add_metric(stats.Value('AggregateLocalMean', 0))
        journal.JournalStats.add_metric(stats.Value('PopulationEstimate', 0))
        journal.JournalStats.add_metric(stats.Value('ExpectedExpirationTime',
                                                    0))
        journal.JournalStats.add_metric(stats.Value('Duration', 0))

        # initialize the block handlers
        poet_transaction_block.register_message_handlers(journal)

    def create_block(self, pub_key):
        """Create candidate transaction block.

        Args:
            pub_key: public key corresponding to the private key used to
                sign the block
        Returns:
            new transaction block.
        """
        minfo = {"PublicKey": pub_key}
        return poet_transaction_block.PoetTransactionBlock(minfo)

    def initialize_block(self, journal, block):
        """Creates a wait certificate for a candidate transaction block.

        Args:

        Returns:
            None
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
            journal: the journal object.
            block (PoetTransactionBlock): The block to claim.
        Returns:
            None
        """
        block.create_wait_certificate()

    def create_block_message(self, block):
        """Create a message wrapper for a block this validator is claiming.

        :param block:
         block: the block to wrap in the message.

        :return:
         the message object to be sent.
        """
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
        return block.wait_timer_is_expired(now)

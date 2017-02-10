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
from sawtooth_validator.consensus.consensus_base import Consensus
from sawtooth_validator.consensus.dev_mode import dev_mode_transaction_block

LOGGER = logging.getLogger(__name__)


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

    def create_block(self, pub_key):
        """Build a new candidate transaction block.

        Args:
            pub_key: public key corresponding to the private key used to
                sign the block
        Returns:
            new transaction block.
        """
        if not self._block_publisher:
            return None
        self._next_block_time = time() + self._block_wait_time
        minfo = {"PublicKey": pub_key}
        return dev_mode_transaction_block.DevModeTransactionBlock(minfo)

    def initialize_block(self, journal, block):
        """Builds a transaction block that is specific to this particular
        consensus mechanism, in this case there is nothing to do.

        Args:
            jounrnal: the journal
            block: the block to initialize.
        Returns:
            None
        """
        pass

    def claim_block(self, journal, block):
        """ Nop there is no signing operations in devmode consensus.

        Args:
            block (DevModeTransactionBlock): The block to claim.
        """
        pass

    def create_block_message(self, block):
        """Create a message wrapper for a block this validator is claiming.

        :param block:
         block: the block to wrap in the message.

        :return:
         the message object to be sent.
        """
        msg = dev_mode_transaction_block.DevModeTransactionBlockMessage()
        msg.TransactionBlock = block
        return msg

    def verify_block(self, journal, block):
        return block.is_valid(self, journal)

    def check_claim_block(self, journal, block, now):
        return len(journal.pending_transactions) != 0 and \
            now > self._next_block_time

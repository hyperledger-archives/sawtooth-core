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
from abc import abstractmethod


class Consensus(object):
    """Consensus objects provide the following services to the Journal:
    1) Build candidate blocks ( this temporary until the block types are
    combined into a single block type)
    2) Check if it is time to claim the current candidate blocks.
    3) Provide the data a signatures required for a block to be validated by
    other consensus algorithms

    """
    def initialization_complete(self, journal):
        """Last call in the journal initialization sequence, giving the
        consensus object a chance to initialize and register it's messages
        """
        pass

    @abstractmethod
    def create_block(self, pub_key):
        """Build a new candidate transaction block. This can be called
        as a result of the previous candidate block being claimed or a new
        block arriving and becoming the current head of the chain after
        validation.

        This is really just a factory for the consensus families custom block
        type. This method is expected to be removed once block types are
        consolidated.

        Returns:
            block: the candidate transaction block
        """
        pass

    @abstractmethod
    def initialize_block(self, journal, block):
        """Do initialization necessary for the consensus to claim a block,
        this may include initiating voting activates, starting proof of work
        hash generation, or create a PoET wait timer.

        Args:
            journal (Journal): the current journal object
            block (TransactionBlock): the block to initialize.
        Returns:
            none
        """
        pass

    @abstractmethod
    def create_block_message(self, block):
        """Create a message wrapper for a block this validator is claiming.
        Factory method for a consensus specific block message.

        This method is expected to be removed as block and message types are
        consolidated.

        Args:
            block: the block to wrap in the message
        Returns:
            The message wrapping the block passed in.
        """
        pass

    @abstractmethod
    def check_claim_block(self, journal, block, now):
        """Check if a candidate block is ready to be claimed.

        Args:
            journal (Journal): the current journal object
            block: the block to be checked if it should be claimed
            now: the current time
        Returns:
            Boolean: True if the candidate block should be claimed.
        """
        pass

    @abstractmethod
    def claim_block(self, journal, block):
        """Finalize a block to be claimed. Provide any signatures and
        data updates that need to be applied to the block before it is
        signed and broadcast to the network.

        Args:
            journal (Journal): the current journal object
            block: The candidate block that
        Returns:
            None
        """
        pass

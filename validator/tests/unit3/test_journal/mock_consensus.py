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
import hashlib

from sawtooth_validator.journal.consensus.consensus\
    import BlockPublisherInterface
from sawtooth_validator.journal.consensus.consensus\
    import BlockVerifierInterface
from sawtooth_validator.journal.consensus.consensus\
    import ForkResolverInterface


class BlockPublisher(BlockPublisherInterface):
    """Consensus objects provide the following services to the Journal:
    1) Build candidate blocks ( this temporary until the block types are
    combined into a single block type)
    2) Check if it is time to claim the current candidate blocks.
    3) Provide the data a signatures required for a block to be validated by
    other consensus algorithms
    """
    def __init__(self, block_cache, state_view):
        self._block_cache = block_cache
        self._state_view = state_view

    def initialize_block(self, block):
        """Do initialization necessary for the consensus to claim a block,
        this may include initiating voting activates, starting proof of work
        hash generation, or create a PoET wait timer.

        Args:
            journal (Journal): the current journal object
            block (TransactionBlock): the block to initialize.
        Returns:
            none
        """
        block.block_header.consensus = b"test_mode"

    def check_publish_block(self, block):
        """Check if a candidate block is ready to be claimed.

        Args:
            journal (Journal): the current journal object
            block: the block to be checked if it should be claimed
            now: the current time
        Returns:
            Boolean: True if the candidate block should be claimed.
        """
        return True

    def finalize_block(self, block):
        """Finalize a block to be claimed. Provide any signatures and
        data updates that need to be applied to the block before it is
        signed and broadcast to the network.

        Args:
            journal (Journal): the current journal object
            block: The candidate block that
        Returns:
            None
        """
        hasher = hashlib.sha256()
        hasher.update(block.block_header.consensus)
        block.block_header.consensus = hasher.hexdigest().encode()


class BlockVerifier(BlockVerifierInterface):
    def __init__(self, block_cache, state_view):
        self._block_cache = block_cache
        self._state_view = state_view

    def verify_block(self, block_state):
        hasher = hashlib.sha256()
        hasher.update(b"test_mode")
        return block_state.consensus == hasher.hexdigest().encode()

    def compute_block_weight(self, block_state):
        return block_state.block_num


class ForkResolver(ForkResolverInterface):
    # Provides the fork resolution interface for the BlockValidator to use
    # when deciding between 2 forks.
    def __init__(self, block_cache):
        self._block_cache = block_cache

    def compare_forks(self, cur_fork_head, new_fork_head):
        """

        Args:
            cur_fork_head: The current head of the block chain.
            new_fork_head: The head of the fork that is being evaluated.
        Returns:
            bool: True if the new chain should replace the current chain.
            False if the new chain should be discarded.
        """
        return new_fork_head.block_num > cur_fork_head.block_num

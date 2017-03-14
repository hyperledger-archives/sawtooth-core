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


from sawtooth_validator.journal.consensus.consensus\
    import BlockPublisherInterface
from sawtooth_validator.journal.consensus.consensus\
    import BlockVerifierInterface
from sawtooth_validator.journal.consensus.consensus\
    import ForkResolverInterface


class BlockPublisher(BlockPublisherInterface):
    """ DevMode BlockPublisher implementation.
    """
    def __init__(self, block_cache, state_view, batch_publisher, data_dir):
        super().__init__(block_cache, state_view, batch_publisher, data_dir)

        self._block_cache = block_cache
        self._state_view = state_view
        self.batch_publisher = batch_publisher
        self._num_batches = 1
        self._count = 0

    def initialize_block(self, block_header):
        """Initialize the candidate block_header.
        Args:
            block_header (block_header): the block_header to initialize.
        Returns:
            Boolean: True if the candidate block_header should be built.
        """
        return True

    def check_publish_block(self, block_header):
        """Check if a candidate block_header is ready to be claimed.
        Args:
            block_header: the block_header to be checked if it
            should be claimed.
        Returns:
            Boolean: True if the candidate block_header should be claimed.
        """
        if self._count >= self._num_batches:
            self._count = 0
            return True
        self._count += 1
        return False

    def finalize_block(self, block_header):
        """Finalize a block_header to be claimed.

        Args:
            block_header: The candidate block_header to be finalized.
        Returns:
            Boolean: True if the candidate block should be finalized.
        """
        block_header.consensus = b"Devmode"
        return True


class BlockVerifier(BlockVerifierInterface):
    """DevMode BlockVerifier implementation
    """
    def __init__(self, block_cache, state_view, data_dir):
        super().__init__(block_cache, state_view, data_dir)

        self._block_cache = block_cache
        self._state_view = state_view

    def verify_block(self, block_state):
        return True


class ForkResolver(ForkResolverInterface):
    """ DevMode ForkResolver implementation
    """
    def __init__(self, block_cache, data_dir):
        super().__init__(block_cache, data_dir)

        self._block_cache = block_cache

    def compare_forks(self, cur_fork_head, new_fork_head):
        """
        Args:
            cur_fork_head (BlockWrapper): The current head of the block chain.
            new_fork_head (BlockWrapper): The head of the fork that is being
            evaluated.
        Returns:
            bool: True if the new chain should replace the current chain.
            False if the new chain should be discarded.
        """
        return new_fork_head.block_num > cur_fork_head.block_num

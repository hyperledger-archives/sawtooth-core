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

# pylint: disable=abstract-method
# pylint: disable=arguments-differ
# pylint: disable=useless-super-delegation

from sawtooth_validator.journal.consensus.consensus \
    import BlockPublisherInterface
from sawtooth_validator.journal.consensus.consensus \
    import BlockVerifierInterface
from sawtooth_validator.journal.consensus.consensus \
    import ForkResolverInterface


class BlockPublisher(BlockPublisherInterface):
    """ MockConsensus BlockPublisher
    """

    def __init__(self,
                 block_cache=None,
                 state_view_factory=None,
                 batch_publisher=None,
                 data_dir=None,
                 config_dir=None,
                 validator_id=None):
        super().__init__(
            block_cache,
            state_view_factory,
            batch_publisher,
            data_dir,
            config_dir,
            validator_id)

    def initialize_block(self, block_header):
        """
        Args:
            block_header (BlockHeader): the block_header to initialize.
        Returns:
            Boolean: True if the block should become a candidate
        """
        return True

    def check_publish_block(self, block_header):
        """Initialize the candidate block_header.
        Args:
            block_header (block_header): the block_header to check.
        Returns:
            Boolean: True if the candidate block_header should be built.
        """
        return True

    def finalize_block(self, block_header, weight=0):
        """Finalize a block_header to be claimed.

        Args:
            block_header: The candidate block_header to be finalized.
        Returns:
            Boolean: True if the candidate block should be claimed.
        """
        block_header.consensus = "test_mode:{}".format(weight).encode()
        return True


class BlockVerifier(BlockVerifierInterface):
    """MockConsensus BlockVerifier implementation
    """

    def __init__(self,
                 block_cache,
                 state_view_factory,
                 data_dir,
                 config_dir,
                 validator_id):
        super().__init__(
            block_cache,
            state_view_factory,
            data_dir,
            config_dir,
            validator_id)

    def verify_block(self, block_wrapper):
        return block_wrapper.consensus.startswith(b"test_mode")


class ForkResolver(ForkResolverInterface):
    """MockConsensus ForkResolver implementation
    """

    def __init__(self,
                 block_cache,
                 state_view_factory,
                 data_dir,
                 config_dir,
                 validator_id):
        super().__init__(
            block_cache,
            state_view_factory,
            data_dir,
            config_dir,
            validator_id)

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
        new_num = new_fork_head.block_num
        new_weight = 0
        if new_fork_head.consensus:
            new_weight = int(new_fork_head.consensus.decode().split(':')[1])
        cur_num = cur_fork_head.block_num
        cur_weight = 0
        if cur_fork_head.consensus:
            cur_weight = int(cur_fork_head.consensus.decode().split(':')[1])

        # chains are ordered by length first, then weight
        if new_num == cur_num:
            return new_weight > cur_weight

        return new_num > cur_num

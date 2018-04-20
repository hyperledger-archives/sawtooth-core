# Copyright 2017 Intel Corporation
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
from sawtooth_validator.journal.block_wrapper import NULL_BLOCK_IDENTIFIER
from sawtooth_validator.journal.consensus.consensus import \
    BlockPublisherInterface
from sawtooth_validator.journal.consensus.consensus import \
    BlockVerifierInterface
from sawtooth_validator.journal.consensus.consensus import \
    ForkResolverInterface


class BlockPublisher(BlockPublisherInterface):
    """The Genesis BlockPublisher is the basic publisher used only during the
    production of a genesis block. This block is marked with consensus field of
    `'Genesis'` and finalized as such.
    """

    def __init__(self,
                 block_cache,
                 state_view_factory,
                 batch_publisher,
                 config_dir,
                 data_dir,
                 validator_id):
        super().__init__(block_cache,
                         state_view_factory,
                         batch_publisher,
                         data_dir,
                         config_dir,
                         validator_id)

    def initialize_block(self, block_header):
        """Initializes the given block header with the consensus field set to
        `'Genesis'`.
        Args:
            block_header (BlockHeader): the BlockHeader to initialize.
        Returns:
            Boolean: `True` as the candidate block should always be built.
        """
        block_header.consensus = b"Genesis"
        return block_header.previous_block_id == NULL_BLOCK_IDENTIFIER

    def check_publish_block(self, block_header):
        """Returns True, as the genesis node can alway produce the  block.
        """
        return block_header.previous_block_id == NULL_BLOCK_IDENTIFIER

    def finalize_block(self, block_header):
        """Returns `True`, as the genesis block is always considered good by
        the genesis node.
        """
        return block_header.previous_block_id == NULL_BLOCK_IDENTIFIER


class BlockVerifier(BlockVerifierInterface):
    """The Genesis BlockVerifier validates that this consensus is only used in
    instances where the previous block id is the NULL_BLOCK_IDENTIFIER. In any
    other case, verification will fail.  This requires that any block beyond
    the genesis block must use a proper consensus module.
    """

    # pylint: disable=useless-super-delegation

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
        """Returns `True` if the previous block id is the NULL_BLOCK_IDENTIFIER
        """
        return block_wrapper.header.previous_block_id == NULL_BLOCK_IDENTIFIER


class ForkResolver(ForkResolverInterface):
    """The genesis ForkResolver should not ever be used.
    """
    # pylint: disable=useless-super-delegation

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
        """Returns False, acception only the current fork.
        """
        return False

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

import logging

from sawtooth_validator.journal.consensus.consensus \
    import ForkResolverInterface

LOGGER = logging.getLogger(__name__)


class PoetForkResolver(ForkResolverInterface):
    # Provides the fork resolution interface for the BlockValidator to use
    # when deciding between 2 forks.
    def __init__(self,
                 block_cache,
                 state_view_factory,
                 data_dir,
                 validator_id):
        """Initialize the object, is passed (read-only) state access objects.
            Args:
                block_cache (BlockCache): Dict interface to the block cache.
                    Any predecessor block to blocks handed to this object will
                    be present in this dict.
                state_view_factory (StateViewFactory): A factory that can be
                    used to create read-only views of state for a particular
                    merkle root, in particular the state as it existed when a
                    particular block was the chain head.
                data_dir (str): path to location where persistent data for the
                    consensus module can be stored.
                validator_id (str): A unique ID for this validator
            Returns:
                none.
        """
        super().__init__(
            block_cache,
            state_view_factory,
            data_dir,
            validator_id)

        self._block_cache = block_cache
        self._state_view_factory = state_view_factory
        self._data_dir = data_dir
        self._validator_id = validator_id

    def compare_forks(self, cur_fork_head, new_fork_head):
        """Given the head of two forks, return which should be the fork that
        the validator chooses.  When this is called both forks consist of
        only valid blocks.

        Args:
            cur_fork_head (Block): The current head of the block chain.
            new_fork_head (Block): The head of the fork that is being
            evaluated.
        Returns:
            Boolean: True if the new chain should replace the current chain.
            False if the new chain should be discarded.
        """
        if new_fork_head.block_num > cur_fork_head.block_num:
            LOGGER.info(
                'Chain with new fork head %s...%s longer (%d) than current '
                'chain head %s...%s (%d)',
                new_fork_head.header_signature[:8],
                new_fork_head.header_signature[-8:],
                new_fork_head.block_num,
                cur_fork_head.header_signature[:8],
                cur_fork_head.header_signature[-8:],
                cur_fork_head.block_num)
            return True
        elif new_fork_head.block_num < cur_fork_head.block_num:
            LOGGER.info(
                'Chain with current head %s...%s longer (%d) than new fork '
                'head %s...%s (%d)',
                cur_fork_head.header_signature[:8],
                cur_fork_head.header_signature[-8:],
                cur_fork_head.block_num,
                new_fork_head.header_signature[:8],
                new_fork_head.header_signature[-8:],
                new_fork_head.block_num)
            return False
        elif new_fork_head.header_signature > cur_fork_head.header_signature:
            LOGGER.info(
                'Signature of new fork head (%s...%s) > than current '
                '(%s...%s)',
                new_fork_head.header_signature[:8],
                new_fork_head.header_signature[-8:],
                cur_fork_head.header_signature[:8],
                cur_fork_head.header_signature[-8:])
            return True
        else:
            LOGGER.info(
                'Signature of current fork head (%s...%s) >= than new '
                '(%s...%s)',
                cur_fork_head.header_signature[:8],
                cur_fork_head.header_signature[-8:],
                new_fork_head.header_signature[:8],
                new_fork_head.header_signature[-8:])
            return False

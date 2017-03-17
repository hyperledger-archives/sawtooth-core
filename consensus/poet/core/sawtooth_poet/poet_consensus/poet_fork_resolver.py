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
    def __init__(self, block_cache, data_dir):
        super().__init__(block_cache, data_dir)

        self._block_cache = block_cache

    def compare_forks(self, cur_fork_head, new_fork_head):
        """Given the head of two forks, return which should be the fork that
        the validator chooses.  When this is called both forks consist of
        only valid blocks.

        Args:
            cur_fork_head (Block): The current head of the block chain.
            new_fork_head (Block): The head of the fork that is being
            evaluated.
            data_dir: path to location where persistent data for the consensus
            module can be stored.
        Returns:
            Boolean: True if the new chain should replace the current chain.
            False if the new chain should be discarded.
        """
        LOGGER.debug("PoetForkResolver.compare_forks()")
        return new_fork_head.block_num > cur_fork_head.block_num

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


class PublishingLimiter:
    """Used to determine whether or not a new candidate block should be
    built, without revealing how that decision is made."""

    def __init__(self):
        self._get_wip_batches_info = None
        self._get_wip_blocks = None

    def set_wip_batches_info_getter(self, get_wip_batches_info):
        self._get_wip_batches_info = get_wip_batches_info

    def set_wip_blocks_getter(self, get_wip_blocks):
        self._get_wip_blocks = get_wip_blocks

    def check_build_candidate_block(self):
        """Returns whether a new candidate block should be built."""
        # Checks should be ordered with respect to how costly they are

        # If there aren't any batches, there is no reason to build
        if self._get_wip_batches_info is not None:
            wip_len, _ = self._get_wip_batches_info()
            if wip_len == 0:
                return False

        # If there are no pending blocks, try to build one
        if self._get_wip_blocks is not None:
            wip_blocks = self._get_wip_blocks()
            if wip_blocks:
                return True

            # build forks
            forks = []
            for block in wip_blocks:
                added = False
                for fork in forks:
                    if block.previous_block_id == fork[-1].header_signature:
                        fork.append(block)
                        added = True

                    if block.header_signature == fork[0].previous_block_id:
                        fork.insert(0, block)
                        added = True

                if not added:
                    forks.append([block])

            # If any of these forks appear to be legitimate forks, don't try to
            # build a new block
            for fork in forks:
                if self._fork_seems_legit(fork):
                    return False

        # If none of the current forks seemed legitimate, then try to build
        return True

    @staticmethod
    def _fork_seems_legit(fork):
        """Check if the fork appears legitimate and we should be trying to
        catch up on it. Currently, we just check the fork length, which is not
        DoS resilient."""
        return len(fork) > 2

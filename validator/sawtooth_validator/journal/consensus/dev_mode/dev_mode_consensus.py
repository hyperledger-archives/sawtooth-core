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

import time
import random
import hashlib

from sawtooth_validator.journal.consensus.consensus\
    import BlockPublisherInterface
from sawtooth_validator.journal.consensus.consensus\
    import BlockVerifierInterface
from sawtooth_validator.journal.consensus.consensus\
    import ForkResolverInterface

from sawtooth_validator.state.config_view import ConfigView


class BlockPublisher(BlockPublisherInterface):
    """DevMode consensus uses genesis utility to configure Min/MaxWaitTime
     to determine when to claim a block.
     Default MinWaitTime to zero and MaxWaitTime is 0 or unset,
     ValidBlockPublishers default to None or an empty list.
     DevMode Consensus (BlockPublisher) will read these settings
     from the StateView when Constructed.
    """

    def __init__(self, block_cache, state_view, batch_publisher, data_dir):
        super().__init__(block_cache, state_view, batch_publisher, data_dir)

        self._block_cache = block_cache
        self._state_view = state_view

        self._start_time = 0
        self._wait_time = 0
        config_view = ConfigView(self._state_view)
        self._min_wait_time = config_view.get_setting(
            "sawtooth.consensus.min_wait_time", 0, int)
        self._max_wait_time = config_view.get_setting(
            "sawtooth.consensus.max_wait_time", 0, int)
        self._valid_block_publishers = config_view.get_setting(
            "sawtooth.consensus.valid_block_publishers", None, list)

    def initialize_block(self, block_header):
        """Do initialization necessary for the consensus to claim a block,
        this may include initiating voting activates, starting proof of work
        hash generation, or create a PoET wait timer.

        Args:
            block_header (BlockHeader): the BlockHeader to initialize.
        Returns:
            True
        """
        block_header.consensus = b"Devmode"
        self._start_time = time.time()
        self._wait_time = random.uniform(
            self._min_wait_time, self._max_wait_time)
        return True

    def check_publish_block(self, block_header):
        """Check if a candidate block is ready to be claimed.

        block_header (BlockHeader): the block_header to be checked if it
            should be claimed
        Returns:
            Boolean: True if the candidate block_header should be claimed.
        """
        if self._valid_block_publishers\
                and block_header.signer_pubkey \
                not in self._valid_block_publishers:
            return False
        elif self._min_wait_time == 0:
            return True
        elif self._min_wait_time > 0 and self._max_wait_time <= 0:
            if self._start_time + self._min_wait_time <= time.time():
                return True
        elif self._min_wait_time > 0 \
                and self._max_wait_time > self._min_wait_time:
            if self._start_time + self._wait_time <= time.time():
                return True
        else:
            return False

    def finalize_block(self, block_header):
        """Finalize a block to be claimed. Provide any signatures and
        data updates that need to be applied to the block before it is
        signed and broadcast to the network.

        Args:
            block_header (BlockHeader): The candidate block that needs to be
            finalized.
        Returns:
            True
        """
        return True


class BlockVerifier(BlockVerifierInterface):
    """DevMode BlockVerifier implementation
    """
    def __init__(self, block_cache, state_view, data_dir):
        super().__init__(block_cache, state_view, data_dir)

        self._block_cache = block_cache
        self._state_view = state_view

    def verify_block(self, block_wrapper):
        return block_wrapper.header.consensus == b"Devmode"


class ForkResolver(ForkResolverInterface):
    """Provides the fork resolution interface for the BlockValidator to use
    when deciding between 2 forks.
    """
    def __init__(self, block_cache, data_dir):
        super().__init__(block_cache, data_dir)

        self._block_cache = block_cache

    @staticmethod
    def hash_signer_pubkey(signer_pubkey, header_signature):
        m = hashlib.md5()
        m.update(signer_pubkey.encode())
        m.update(header_signature.encode())
        digest = m.hexdigest()
        number = int(digest, 16)
        return number

    def compare_forks(self, cur_fork_head, new_fork_head):
        """The longest chain is selected. If they are equal, then the hash
        value of the previous block id and publisher signature is computed.
        The lowest result value is the winning block.
        Args:
            cur_fork_head: The current head of the block chain.
            new_fork_head: The head of the fork that is being evaluated.
        Returns:
            bool: True if choosing the new chain head, False if choosing
            the current chain head.
        """

        if new_fork_head.block_num == cur_fork_head.block_num:
            cur_fork_hash = self.hash_signer_pubkey(
                cur_fork_head.header.signer_pubkey,
                cur_fork_head.header.previous_block_id)
            new_fork_hash = self.hash_signer_pubkey(
                new_fork_head.header.signer_pubkey,
                new_fork_head.header.previous_block_id)

            return new_fork_hash < cur_fork_hash

        else:
            return new_fork_head.block_num > cur_fork_head.block_num

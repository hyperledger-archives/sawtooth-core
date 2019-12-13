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
import logging

from sawtooth_validator.journal.block_wrapper import BlockWrapper
from sawtooth_validator.journal.consensus.consensus \
    import BlockPublisherInterface
from sawtooth_validator.journal.consensus.consensus \
    import BlockVerifierInterface
from sawtooth_validator.journal.consensus.consensus \
    import ForkResolverInterface

from sawtooth_validator.state.settings_view import SettingsView

LOGGER = logging.getLogger(__name__)


class BlockPublisher(BlockPublisherInterface):
    """DevMode consensus uses genesis utility to configure Min/MaxWaitTime
     to determine when to claim a block.
     Default MinWaitTime to zero and MaxWaitTime is 0 or unset,
     ValidBlockPublishers default to None or an empty list.
     DevMode Consensus (BlockPublisher) will read these settings
     from the StateView when Constructed.
    """

    def __init__(self,
                 block_cache,
                 state_view_factory,
                 batch_publisher,
                 data_dir,
                 config_dir,
                 validator_id):
        super().__init__(
            block_cache,
            state_view_factory,
            batch_publisher,
            data_dir,
            config_dir,
            validator_id)

        self._block_cache = block_cache
        self._state_view_factory = state_view_factory

        self._start_time = 0
        self._wait_time = 0

        # Set these to default values right now, when we asked to initialize
        # a block, we will go ahead and check real configuration
        self._min_wait_time = 0
        self._max_wait_time = 0
        self._valid_block_publishers = ()

    def initialize_block(self, block_header):
        """Do initialization necessary for the consensus to claim a block,
        this may include initiating voting activates, starting proof of work
        hash generation, or create a PoET wait timer.

        Args:
            block_header (BlockHeader): the BlockHeader to initialize.
        Returns:
            True
        """
        # Using the current chain head, we need to create a state view so we
        # can get our config values.
        state_view = \
            BlockWrapper.state_view_for_block(
                self._block_cache.block_store.chain_head,
                self._state_view_factory)

        settings_view = SettingsView(state_view)
        self._min_wait_time = settings_view.get_setting(
            "sawtooth.consensus.min_wait_time", self._min_wait_time, int)
        self._max_wait_time = settings_view.get_setting(
            "sawtooth.consensus.max_wait_time", self._max_wait_time, int)
        self._valid_block_publishers = settings_view.get_setting(
            "sawtooth.consensus.valid_block_publishers",
            self._valid_block_publishers,
            list)

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
        if any(publisher_key != block_header.signer_public_key
               for publisher_key in self._valid_block_publishers):
            return False

        if self._min_wait_time == 0:
            return True

        if self._min_wait_time < 0:
            return False

        assert self._min_wait_time > 0

        if self._max_wait_time <= 0:
            return self._start_time + self._min_wait_time <= time.time()

        assert self._max_wait_time > 0

        if self._max_wait_time <= self._min_wait_time:
            return False

        assert 0 < self._min_wait_time < self._max_wait_time

        return self._start_time + self._wait_time <= time.time()

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
        return block_wrapper.header.consensus == b"Devmode"


class ForkResolver(ForkResolverInterface):
    """Provides the fork resolution interface for the BlockValidator to use
    when deciding between 2 forks.
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

    @staticmethod
    def hash_signer_public_key(signer_public_key, header_signature):
        m = hashlib.sha256()
        m.update(signer_public_key.encode())
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

        # If the new fork head is not DevMode consensus, bail out.  This should
        # never happen, but we need to protect against it.
        if new_fork_head.consensus != b"Devmode":
            raise \
                TypeError(
                    'New fork head {} is not a DevMode block'.format(
                        new_fork_head.identifier[:8]))

        # If the current fork head is not DevMode consensus, check the new fork
        # head to see if its immediate predecessor is the current fork head. If
        # so that means that consensus mode is changing.  If not, we are again
        # in a situation that should never happen, but we need to guard
        # against.
        if cur_fork_head.consensus != b"Devmode":
            if new_fork_head.previous_block_id == cur_fork_head.identifier:
                LOGGER.info(
                    'Choose new fork %s: New fork head switches consensus to '
                    'DevMode',
                    new_fork_head.identifier[:8])
                return True

            raise \
                TypeError(
                    'Trying to compare a DevMode block {} to a non-DevMode '
                    'block {} that is not the direct predecessor'.format(
                        new_fork_head.identifier[:8],
                        cur_fork_head.identifier[:8]))

        if new_fork_head.block_num == cur_fork_head.block_num:
            cur_fork_hash = self.hash_signer_public_key(
                cur_fork_head.header.signer_public_key,
                cur_fork_head.header.previous_block_id)
            new_fork_hash = self.hash_signer_public_key(
                new_fork_head.header.signer_public_key,
                new_fork_head.header.previous_block_id)

            result = new_fork_hash < cur_fork_hash

        else:
            result = new_fork_head.block_num > cur_fork_head.block_num

        return result

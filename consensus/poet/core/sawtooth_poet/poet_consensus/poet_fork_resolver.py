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

from sawtooth_poet.poet_consensus.consensus_state_store \
    import ConsensusStateStore
from sawtooth_poet.poet_consensus.poet_config_view import PoetConfigView
from sawtooth_poet.poet_consensus import poet_enclave_factory as factory
from sawtooth_poet.poet_consensus import utils
from sawtooth_poet_common.validator_registry_view.validator_registry_view \
    import ValidatorRegistryView

from sawtooth_validator.journal.block_wrapper import BlockWrapper
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
        self._consensus_state_store = \
            ConsensusStateStore(
                data_dir=self._data_dir,
                validator_id=self._validator_id)

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
        chosen_fork_head = None

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
            chosen_fork_head = new_fork_head
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
            chosen_fork_head = cur_fork_head
        elif new_fork_head.header_signature > cur_fork_head.header_signature:
            LOGGER.info(
                'Signature of new fork head (%s...%s) > than current '
                '(%s...%s)',
                new_fork_head.header_signature[:8],
                new_fork_head.header_signature[-8:],
                cur_fork_head.header_signature[:8],
                cur_fork_head.header_signature[-8:])
            chosen_fork_head = new_fork_head
        else:
            LOGGER.info(
                'Signature of current fork head (%s...%s) >= than new '
                '(%s...%s)',
                cur_fork_head.header_signature[:8],
                cur_fork_head.header_signature[-8:],
                new_fork_head.header_signature[:8],
                new_fork_head.header_signature[-8:])
            chosen_fork_head = cur_fork_head

        # Now that we have chosen a fork for the chain head, if
        # we chose the new fork, we need to create consensus state
        # store information for the new fork's chain head.
        if chosen_fork_head == new_fork_head:
            # Get the state view for the previous block in the chain so we can
            # create a PoET enclave
            previous_block = None
            try:
                previous_block = \
                    self._block_cache[new_fork_head.previous_block_id]
            except KeyError:
                pass

            state_view = \
                BlockWrapper.state_view_for_block(
                    block_wrapper=previous_block,
                    state_view_factory=self._state_view_factory)

            poet_enclave_module = \
                factory.PoetEnclaveFactory.get_poet_enclave_module(state_view)

            validator_registry_view = ValidatorRegistryView(state_view)
            try:
                # Get the validator info for the validator that claimed the
                # fork head
                validator_info = \
                    validator_registry_view.get_validator_info(
                        new_fork_head.header.signer_pubkey)

                # Get the consensus state for the new fork head's previous
                # block and update the consensus-wide statistics for the new
                # fork head.
                consensus_state = \
                    utils.get_consensus_state_for_block_id(
                        block_id=new_fork_head.previous_block_id,
                        block_cache=self._block_cache,
                        state_view_factory=self._state_view_factory,
                        consensus_state_store=self._consensus_state_store,
                        poet_enclave_module=poet_enclave_module)

                consensus_state.total_block_claim_count += 1

                # In order to perform the zTest we need to calculate for this
                # block the expected number of blocks a validator should have
                # won based upon the population estimate and keep track of the
                # number of blocks covered by the zTest
                poet_config_view = PoetConfigView(state_view)

                if consensus_state.total_block_claim_count > \
                        poet_config_view.fixed_duration_block_count:
                    wait_certificate = \
                        utils.deserialize_wait_certificate(
                            new_fork_head,
                            poet_enclave_module)
                    consensus_state.expected_block_claim_count += \
                        1.0 / wait_certificate.population_estimate
                    consensus_state.ztest_block_claim_count += 1

                # Get and update the validator state/statistics for the
                # validator that claimed the new fork head.
                validator_state = \
                    utils.get_current_validator_state(
                        validator_info=validator_info,
                        consensus_state=consensus_state,
                        block_cache=self._block_cache)
                consensus_state.set_validator_state(
                    validator_id=validator_info.id,
                    validator_state=utils.create_next_validator_state(
                        validator_info=validator_info,
                        current_validator_state=validator_state,
                        current_block_count=consensus_state.
                        total_block_claim_count,
                        poet_config_view=poet_config_view,
                        block_cache=self._block_cache))

                # Store the updated consensus state for this block.
                self._consensus_state_store[new_fork_head.identifier] = \
                    consensus_state

                LOGGER.debug(
                    'Create consensus state: BID=%s, EBC=%f, TBCC=%d, '
                    'ZBCC=%d',
                    new_fork_head.identifier[:8],
                    consensus_state.expected_block_claim_count,
                    consensus_state.total_block_claim_count,
                    consensus_state.ztest_block_claim_count)
            except KeyError:
                # This _should_ never happen.  The new potential fork head
                # has to have been a PoET block and for it to be verified
                # by the PoET block verifier, it must have been signed by
                # validator in the validator registry.  If not found, we
                # are going to just stick with the current fork head.
                LOGGER.error(
                    'New fork head claimed by validator not in validator '
                    'registry: %s...%s',
                    new_fork_head.header.signer_pubkey[:8],
                    new_fork_head.header.signer_pubkey[-8:])
                chosen_fork_head = cur_fork_head

        return chosen_fork_head == new_fork_head

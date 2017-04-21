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

from sawtooth_poet.poet_consensus.consensus_state import ConsensusState
from sawtooth_poet.poet_consensus.consensus_state_store \
    import ConsensusStateStore
from sawtooth_poet.poet_consensus import poet_enclave_factory as factory
from sawtooth_poet.poet_consensus import utils
from sawtooth_poet.poet_consensus.poet_config_view import PoetConfigView

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

        state_view = \
            BlockWrapper.state_view_for_block(
                block_wrapper=cur_fork_head,
                state_view_factory=self._state_view_factory)
        poet_enclave_module = \
            factory.PoetEnclaveFactory.get_poet_enclave_module(state_view)

        current_fork_wait_certificate = \
            utils.deserialize_wait_certificate(
                block=cur_fork_head,
                poet_enclave_module=poet_enclave_module)
        new_fork_wait_certificate = \
            utils.deserialize_wait_certificate(
                block=new_fork_head,
                poet_enclave_module=poet_enclave_module)

        # This should never, ever, ever happen (at least we hope), but
        # defensively protect against having to choose between two non-PoET
        # fork heads.
        if current_fork_wait_certificate is None and \
                new_fork_wait_certificate is None:
            raise TypeError('Neither block is a PoET block')

        # Criterion#1: We will always choose a PoET block over a non-PoET
        # block
        if new_fork_wait_certificate is None:
            LOGGER.info(
                'Choose current fork %s: New fork head is not a PoET '
                'block',
                cur_fork_head.header_signature[:8])
            chosen_fork_head = cur_fork_head
        elif current_fork_wait_certificate is None:
            LOGGER.info(
                'Choose new fork %s: Current fork head is not a PoET '
                'block',
                new_fork_head.header_signature[:8])
            chosen_fork_head = new_fork_head

        # Criterion#2: If they share the same immediate previous block,
        # then the one with the smaller wait duration is chosen
        elif cur_fork_head.previous_block_id == \
                new_fork_head.previous_block_id:
            if current_fork_wait_certificate.duration < \
                    new_fork_wait_certificate.duration:
                LOGGER.info(
                    'Choose current fork %s: Current fork wait duration '
                    '(%f) less than new fork wait duration (%f)',
                    cur_fork_head.header_signature[:8],
                    current_fork_wait_certificate.duration,
                    new_fork_wait_certificate.duration)
                chosen_fork_head = cur_fork_head
            elif new_fork_wait_certificate.duration < \
                    current_fork_wait_certificate.duration:
                LOGGER.info(
                    'Choose new fork %s: New fork wait duration (%f) '
                    'less than new fork wait duration (%f)',
                    new_fork_head.header_signature[:8],
                    new_fork_wait_certificate.duration,
                    current_fork_wait_certificate.duration)
                chosen_fork_head = new_fork_head

        # Criterion#3: If they don't share the same immediate previous
        # block, then the one with the higher aggregate local mean wins
        else:
            # Get the consensus state for the current fork head and the
            # block immediately before the new fork head (as we haven't
            # committed to the block yet).  So that the new fork doesn't
            # have to fight with one hand tied behind its back, add the
            # new fork head's wait certificate's local mean to the
            # aggregate local mean for the predecessor block's consensus
            # state for the comparison.
            current_fork_consensus_state = \
                ConsensusState.consensus_state_for_block_id(
                    block_id=cur_fork_head.identifier,
                    block_cache=self._block_cache,
                    state_view_factory=self._state_view_factory,
                    consensus_state_store=self._consensus_state_store,
                    poet_enclave_module=poet_enclave_module)
            new_fork_consensus_state = \
                ConsensusState.consensus_state_for_block_id(
                    block_id=new_fork_head.previous_block_id,
                    block_cache=self._block_cache,
                    state_view_factory=self._state_view_factory,
                    consensus_state_store=self._consensus_state_store,
                    poet_enclave_module=poet_enclave_module)
            new_fork_aggregate_local_mean = \
                new_fork_consensus_state.aggregate_local_mean + \
                new_fork_wait_certificate.local_mean

            if current_fork_consensus_state.aggregate_local_mean > \
                    new_fork_aggregate_local_mean:
                LOGGER.info(
                    'Choose current fork %s: Current fork aggregate '
                    'local mean (%f) greater than new fork aggregate '
                    'local mean (%f)',
                    cur_fork_head.header_signature[:8],
                    current_fork_consensus_state.aggregate_local_mean,
                    new_fork_aggregate_local_mean)
                chosen_fork_head = cur_fork_head
            elif new_fork_aggregate_local_mean > \
                    current_fork_consensus_state.aggregate_local_mean:
                LOGGER.info(
                    'Choose new fork %s: New fork aggregate local mean '
                    '(%f) greater than current fork aggregate local mean '
                    '(%f)',
                    new_fork_head.header_signature[:8],
                    new_fork_aggregate_local_mean,
                    current_fork_consensus_state.aggregate_local_mean)
                chosen_fork_head = new_fork_head

        # Criterion#4: If we have gotten to this point and we have not chosen
        # yet, we are going to fall back on using the block identifiers
        # (header signatures) . The lexicographically larger one will be the
        # chosen one.  The chance that they are equal are infinitesimally
        # small.
        if chosen_fork_head is None:
            if cur_fork_head.header_signature > \
                    new_fork_head.header_signature:
                LOGGER.info(
                    'Choose current fork %s: Current fork header signature'
                    '(%s) greater than new fork header signature (%s)',
                    cur_fork_head.header_signature[:8],
                    cur_fork_head.header_signature[:8],
                    new_fork_head.header_signature[:8])
                chosen_fork_head = cur_fork_head
            else:
                LOGGER.info(
                    'Choose new fork %s: New fork header signature (%s) '
                    'greater than current fork header signature (%s)',
                    new_fork_head.header_signature[:8],
                    new_fork_head.header_signature[:8],
                    cur_fork_head.header_signature[:8])
                chosen_fork_head = new_fork_head

        # Now that we have chosen a fork for the chain head, if we chose the
        # new fork and it is a PoET block (i.e., it has a wait certificate),
        # we need to create consensus state store information for the new
        # fork's chain head.
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

            validator_registry_view = ValidatorRegistryView(state_view)
            try:
                # Get the validator info for the validator that claimed the
                # fork head
                validator_info = \
                    validator_registry_view.get_validator_info(
                        new_fork_head.header.signer_pubkey)

                # Get the consensus state for the new fork head's previous
                # block, let the consensus state update itself appropriately
                # based upon the validator claiming a block, and then
                # associate the consensus state with the new block in the
                # store.
                consensus_state = \
                    ConsensusState.consensus_state_for_block_id(
                        block_id=new_fork_head.previous_block_id,
                        block_cache=self._block_cache,
                        state_view_factory=self._state_view_factory,
                        consensus_state_store=self._consensus_state_store,
                        poet_enclave_module=poet_enclave_module)
                consensus_state.validator_did_claim_block(
                    validator_info=validator_info,
                    wait_certificate=utils.deserialize_wait_certificate(
                        block=new_fork_head,
                        poet_enclave_module=poet_enclave_module),
                    poet_config_view=PoetConfigView(state_view))
                self._consensus_state_store[new_fork_head.identifier] = \
                    consensus_state

                LOGGER.debug(
                    'Create consensus state: BID=%s, ALM=%f, TBCC=%d',
                    new_fork_head.identifier[:8],
                    consensus_state.aggregate_local_mean,
                    consensus_state.total_block_claim_count)
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

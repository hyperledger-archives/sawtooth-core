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

from sawtooth_validator.journal.block_wrapper import BlockWrapper
from sawtooth_validator.journal.consensus.consensus \
    import BlockVerifierInterface

from sawtooth_poet.poet_consensus.consensus_state import ConsensusState
from sawtooth_poet.poet_consensus.consensus_state_store \
    import ConsensusStateStore
from sawtooth_poet.poet_consensus.poet_config_view import PoetConfigView
from sawtooth_poet.poet_consensus import poet_enclave_factory as factory
from sawtooth_poet.poet_consensus import utils

from sawtooth_poet_common.validator_registry_view.validator_registry_view \
    import ValidatorRegistryView

LOGGER = logging.getLogger(__name__)


class PoetBlockVerifier(BlockVerifierInterface):
    """BlockVerifier provides services for the Journal(ChainController) to
    determine if a block is valid (for the consensus rules) to be
    considered as part of the fork being evaluated. BlockVerifier must be
    independent of block publishing activities.
    """
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

    def verify_block(self, block_wrapper):
        """Check that the block received conforms to the consensus rules.

        Args:
            block_wrapper (BlockWrapper): The block to validate.
        Returns:
            Boolean: True if the Block is valid, False if the block is invalid.
        """
        # Get the state view for the previous block in the chain so we can
        # create a PoET enclave and validator registry view
        previous_block = None
        try:
            previous_block = \
                self._block_cache[block_wrapper.previous_block_id]
        except KeyError:
            pass

        state_view = \
            BlockWrapper.state_view_for_block(
                block_wrapper=previous_block,
                state_view_factory=self._state_view_factory)

        poet_enclave_module = \
            factory.PoetEnclaveFactory.get_poet_enclave_module(state_view)

        validator_registry_view = ValidatorRegistryView(state_view)
        # Grab the validator info based upon the block signer's public
        # key
        try:
            validator_info = \
                validator_registry_view.get_validator_info(
                    block_wrapper.header.signer_pubkey)
        except KeyError:
            LOGGER.error(
                'Block %s rejected: Received block from an unregistered '
                'validator %s...%s',
                block_wrapper.identifier[:8],
                block_wrapper.header.signer_pubkey[:8],
                block_wrapper.header.signer_pubkey[-8:])
            return False

        LOGGER.debug(
            'Block Signer Name=%s, ID=%s...%s, PoET public key='
            '%s...%s',
            validator_info.name,
            validator_info.id[:8],
            validator_info.id[-8:],
            validator_info.signup_info.poet_public_key[:8],
            validator_info.signup_info.poet_public_key[-8:])

        # For the candidate block, reconstitute the wait certificate
        # and verify that it is valid
        wait_certificate = \
            utils.deserialize_wait_certificate(
                block=block_wrapper,
                poet_enclave_module=poet_enclave_module)
        if wait_certificate is None:
            LOGGER.error(
                'Block %s rejected: Block from validator %s (ID=%s...%s) was '
                'not created by PoET consensus module',
                block_wrapper.identifier[:8],
                validator_info.name,
                validator_info.id[:8],
                validator_info.id[-8:])
            return False

        # Get the consensus state and PoET configuration view for the block
        # that is being built upon
        consensus_state = \
            ConsensusState.consensus_state_for_block_id(
                block_id=block_wrapper.previous_block_id,
                block_cache=self._block_cache,
                state_view_factory=self._state_view_factory,
                consensus_state_store=self._consensus_state_store,
                poet_enclave_module=poet_enclave_module)
        poet_config_view = PoetConfigView(state_view=state_view)

        previous_certificate_id = \
            utils.get_previous_certificate_id(
                block_header=block_wrapper.header,
                block_cache=self._block_cache,
                poet_enclave_module=poet_enclave_module)
        try:
            wait_certificate.check_valid(
                poet_enclave_module=poet_enclave_module,
                previous_certificate_id=previous_certificate_id,
                poet_public_key=validator_info.signup_info.poet_public_key,
                consensus_state=consensus_state,
                poet_config_view=poet_config_view)
        except ValueError as error:
            LOGGER.error(
                'Block %s rejected: Wait certificate check failed - %s',
                block_wrapper.identifier[:8],
                error)
            return False

        # Reject the block if the validator has already claimed the key bock
        # limit for its current PoET key pair.
        if consensus_state.validator_has_claimed_block_limit(
                validator_info=validator_info,
                poet_config_view=poet_config_view):
            LOGGER.error(
                'Block %s rejected: Validator has reached maximum number of '
                'blocks with key pair.',
                block_wrapper.identifier[:8])
            return False

        # Reject the block if the validator has not waited the required number
        # of blocks between when the block containing its validator registry
        # transaction was committed to the chain and trying to claim this
        # block
        if consensus_state.validator_is_claiming_too_early(
                validator_info=validator_info,
                block_number=block_wrapper.block_num,
                validator_registry_view=validator_registry_view,
                poet_config_view=poet_config_view,
                block_store=self._block_cache.block_store):
            LOGGER.error(
                'Block %s rejected: Validator has not waited long enough '
                'since registering validator information.',
                block_wrapper.identifier[:8])
            return False

        # Reject the block if the validator is claiming blocks at a rate that
        # is more frequent than is statistically allowed (i.e., zTest)
        if consensus_state.validator_is_claiming_too_frequently(
                validator_info=validator_info,
                previous_block_id=block_wrapper.previous_block_id,
                poet_config_view=poet_config_view,
                population_estimate=wait_certificate.population_estimate(
                    poet_config_view=poet_config_view),
                block_cache=self._block_cache,
                poet_enclave_module=poet_enclave_module):
            LOGGER.error(
                'Block %s rejected: Validator is claiming blocks too '
                'frequently.',
                block_wrapper.identifier[:8])
            return False

        return True

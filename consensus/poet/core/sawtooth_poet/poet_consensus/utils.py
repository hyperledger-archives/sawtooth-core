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

import collections
import json
import logging

from sawtooth_validator.journal.block_wrapper import NULL_BLOCK_IDENTIFIER

from sawtooth_poet_common.validator_registry_view.validator_registry_view \
    import ValidatorRegistryView

from sawtooth_poet.poet_consensus.poet_config_view import PoetConfigView
from sawtooth_poet.poet_consensus.wait_certificate import WaitCertificate
from sawtooth_poet.poet_consensus.consensus_state import ConsensusState
from sawtooth_poet.poet_consensus.consensus_state import ValidatorState

LOGGER = logging.getLogger(__name__)


def _block_for_id(block_id, block_cache):
    """A convenience method retrieving a block given a block ID.  Takes care
    of the special case of NULL_BLOCK_IDENTIFIER.

    Args:
        block_id (str): The ID of block to retrieve.
        block_cache (BlockCache): Block cache from which block will be
            retrieved.

    Returns:
        BlockWrapper for block, or None for no block found.
    """
    block = None
    try:
        block = \
            None if block_id_is_genesis(block_id) else block_cache[block_id]
    except KeyError:
        LOGGER.error('Failed to retrieve block: %s', block_id[:8])

    return block


def block_id_is_genesis(block_id):
    """Determines if the block ID represents the genesis block.

    Args:
        block_id (str): The block ID to check

    Returns:
        True if this ID represents the block ID, or False otherwise.
    """
    return block_id == NULL_BLOCK_IDENTIFIER


def deserialize_wait_certificate(block, poet_enclave_module):
    """Deserializes the wait certificate associated with the block.

    Args:
        block (Block or BlockWrapper): The block that has the wait certificate
        poet_enclave_module (module): The PoET enclave module

    Returns:
        WaitCertificate: The reconstituted wait certificate associated
            with the block or None if cannot deserialize
    """
    # The wait certificate is a JSON string placed in the consensus
    # field/property of the block header.  Parse the JSON and then use the
    # serialized wait certificate and signature to create a
    # WaitCertificate object.
    wait_certificate = None
    try:
        wait_certificate_dict = json.loads(block.header.consensus.decode())
        wait_certificate = \
            WaitCertificate.wait_certificate_from_serialized(
                poet_enclave_module=poet_enclave_module,
                serialized=wait_certificate_dict['SerializedCertificate'],
                signature=wait_certificate_dict['Signature'])
    except (json.decoder.JSONDecodeError, KeyError):
        pass

    return wait_certificate


def build_certificate_list(block_header,
                           block_cache,
                           poet_enclave_module,
                           maximum_number):
    """Builds a list of up to maximum_length wait certificates for the blocks
    immediately preceding the block represented by block_header.

    Args:
        block_header (BlockHeader): The header for the block
        block_cache (BlockCache): The cache of blocks that are predecessors
            to the block represented by block_header
        poet_enclave_module (module): The PoET enclave module
        maximum_number (int): The maximum number of certificates to return

    Returns:
        A list of wait certificates
    """

    # Create a list of certificates starting with the immediate predecessor
    # to the block represented by block_header.  We will use a deque because
    # we are walking the blocks in reverse order.
    certificates = collections.deque()
    block_id = block_header.previous_block_id

    try:
        while not block_id_is_genesis(block_id) and \
                len(certificates) < maximum_number:
            # Grab the block from the block store, use the consensus
            # property to reconstitute the wait certificate, and add
            # the wait certificate to the list.  If we get to a block
            # that does not have a wait certificate, we stop.
            block = block_cache[block_id]
            wait_certificate = \
                deserialize_wait_certificate(
                    block=block,
                    poet_enclave_module=poet_enclave_module)

            if wait_certificate is None:
                break

            certificates.appendleft(wait_certificate)

            # Move to the previous block
            block_id = block.header.previous_block_id
    except KeyError as ke:
        LOGGER.error('Error getting block: %s', ke)

    return list(certificates)


def get_current_validator_state(validator_info,
                                consensus_state,
                                block_cache):
    """Fetches the current validator state for the validator, creating it if
    necessary.

    Args:
        validator_info (ValidatorInfo): The validator information
            corresponding to the consensus state
        consensus_state (ConsensusState): The consensus state from which
            validator state should be fetched/derived.
        block_cache (BlockCache): The block store cache

    Returns:
        ValidatorState object representing the validator's state at the
            point in time of the consensus state
    """
    # Fetch the validator state.  If it doesn't exist, then create an initial
    # validator state object, including figuring out the block number in which
    # the validator was most-recently registered.
    validator_state = \
        consensus_state.get_validator_state(
            validator_id=validator_info.id)

    if validator_state is None:
        enclosing_block = \
            block_cache.block_store.get_block_by_transaction_id(
                validator_info.transaction_id)
        validator_state = \
            ValidatorState(
                commit_block_number=enclosing_block.block_num,
                key_block_claim_count=0,
                poet_public_key=validator_info.signup_info.poet_public_key,
                total_block_claim_count=0,
                ztest_block_claim_count=0)

    return validator_state


def create_next_validator_state(validator_info,
                                current_validator_state,
                                current_block_count,
                                poet_config_view,
                                block_cache):
    """Starting with the current validator state, create the next validator
     validator state for the validator.

    Args:
        validator_info (ValidatorInfo): Information about the validator
        current_validator_state (ValidatorState): The current validator
            state upon which we are going to base the next validator state
        current_block_count (int): The number of blocks in the chain
        poet_config_view (PoetConfigView): The current PoET configuration
            view
        block_cache (BlockCache): The block store cache

    Returns:
        ValidatorState object representing new validator state
    """

    total_block_claim_count = \
        current_validator_state.total_block_claim_count + 1

    # If we are now beyond the fixed duration blocks (i.e., blocks for which
    # the wait timer local mean is a simple ratio of target to initial wait
    # time), then also increment the number of blocks for this validator that
    # are governed by the zTest.
    if current_block_count > poet_config_view.fixed_duration_block_count:
        ztest_block_claim_count = \
            current_validator_state.ztest_block_claim_count + 1
    else:
        ztest_block_claim_count = 0

    # If the PoET public keys match, then we are doing a simple statistics
    # update
    if validator_info.signup_info.poet_public_key == \
            current_validator_state.poet_public_key:
        commit_block_number = current_validator_state.commit_block_number
        key_block_claim_count = \
            current_validator_state.key_block_claim_count + 1

    # Otherwise, we are resetting statistics for the validator.  This includes
    # using the validator info's transaction ID to get the block number of the
    # block that committed the validator registry transaction
    else:
        commit_block_number = \
            block_cache.block_store.get_block_by_transaction_id(
                validator_info.transaction_id).block_num
        key_block_claim_count = 1

    LOGGER.debug(
        'Create validator state for %s: PPK=%s...%s, CBN=%d, KBCC=%d, '
        'TBCC=%d, ZBCC=%d',
        validator_info.name,
        validator_info.signup_info.poet_public_key[:8],
        validator_info.signup_info.poet_public_key[-8:],
        commit_block_number,
        key_block_claim_count,
        total_block_claim_count,
        ztest_block_claim_count)

    return \
        ValidatorState(
            commit_block_number=commit_block_number,
            key_block_claim_count=key_block_claim_count,
            poet_public_key=validator_info.signup_info.poet_public_key,
            total_block_claim_count=total_block_claim_count,
            ztest_block_claim_count=ztest_block_claim_count)


BlockInfo = \
    collections.namedtuple(
        'BlockInfo',
        ['wait_certificate', 'validator_info', 'poet_config_view'])

""" Instead of creating a full-fledged class, let's use a named tuple for
the block info.  The block info represents the information we need to
create consensus state.  A block info object contains:

wait_certificate (WaitCertificate): The PoET wait certificate object for
    the block
validator_info (ValidatorInfo): The validator registry information for the
    validator that claimed the block
poet_config_view (PoetConfigView): The PoET cofiguration view associated with
    the block
"""


def get_consensus_state_for_block_id(
        block_id,
        block_cache,
        state_view_factory,
        consensus_state_store,
        poet_enclave_module):
    """Returns the consensus state for the block referenced by block ID,
        creating it from the consensus state history if necessary.

    Args:
        block_id (str): The ID of the block for which consensus state will
            be returned.
        block_cache (BlockCache): The block store cache
        state_view_factory (StateViewFactory): A factory that can be used
            to create state view object corresponding to blocks
        consensus_state_store (ConsensusStateStore): The consensus state
            store
        poet_enclave_module (module): The PoET enclave module

    Returns:
        ConsensusState object representing the consensus state for the block
            referenced by block_id
    """

    consensus_state = None
    previous_wait_certificate = None
    blocks = collections.OrderedDict()

    # Starting at the chain head, walk the block store backwards until we
    # either get to the root or we get a block for which we have already
    # created consensus state
    while True:
        block = _block_for_id(block_id=block_id, block_cache=block_cache)
        if block is None:
            break

        # Try to fetch the consensus state.  If that succeeds, we can
        # stop walking back as we can now build on that consensus
        # state.
        consensus_state = consensus_state_store.get(block_id=block_id)
        if consensus_state is not None:
            break

        wait_certificate = \
            deserialize_wait_certificate(
                block=block,
                poet_enclave_module=poet_enclave_module)

        # If this is a PoET block (i.e., it has a wait certificate), get the
        # validator info for the validator that signed this block and add the
        # block information we will need to set validator state in the block's
        # consensus state.
        if wait_certificate is not None:
            state_view = \
                state_view_factory.create_view(
                    state_root_hash=block.state_root_hash)
            validator_registry_view = \
                ValidatorRegistryView(state_view=state_view)
            validator_info = \
                validator_registry_view.get_validator_info(
                    validator_id=block.header.signer_pubkey)

            LOGGER.debug(
                'We need to build consensus state for block: %s...%s',
                block_id[:8],
                block_id[-8:])

            blocks[block_id] = \
                BlockInfo(
                    wait_certificate=wait_certificate,
                    validator_info=validator_info,
                    poet_config_view=PoetConfigView(state_view))

        # Otherwise, this is a non-PoET block.  If we don't have any blocks
        # yet or the last block we processed was a PoET block, put a
        # placeholder in the list so that when we get to it we know that we
        # need to reset the statistics.
        elif len(blocks) == 0 or previous_wait_certificate is not None:
            blocks[block_id] = \
                BlockInfo(
                    wait_certificate=None,
                    validator_info=None,
                    poet_config_view=None)

        previous_wait_certificate = wait_certificate

        # Move to the previous block
        block_id = block.previous_block_id

    # At this point, if we have not found any consensus state, we need to
    # create default state from which we can build upon
    if consensus_state is None:
        consensus_state = ConsensusState()

    # Now, walk through the blocks for which we were supposed to create
    # consensus state, from oldest to newest (i.e., in the reverse order in
    # which they were added), and store state for PoET blocks so that the next
    # time we don't have to walk so far back through the block chain.
    for block_id, block_info in reversed(blocks.items()):
        # If the block was not a PoET block (i.e., didn't have a wait
        # certificate), reset the consensus state statistics.  We are not
        # going to store this in the consensus state store, but we will use it
        # as the starting for the next PoET block.
        if block_info.wait_certificate is None:
            consensus_state = ConsensusState()

        # Otherwise, update the consensus state statistics and fetch the
        # validator state for the validator which claimed the block, create
        # updated validator state for the validator, set/update the validator
        # state in the consensus state object, and then associate the
        # consensus state with the corresponding block in the consensus state
        # store.
        else:
            consensus_state.total_block_claim_count += 1

            # In order to perform the zTest we need to calculate for this
            # block the expected number of blocks a validator should have
            # won based upon the population estimate and keep track of the
            # number of blocks covered by the zTest.
            if consensus_state.total_block_claim_count > \
                    block_info.poet_config_view.fixed_duration_block_count:
                consensus_state.expected_block_claim_count += \
                    1.0 / block_info.wait_certificate.population_estimate
                consensus_state.ztest_block_claim_count += 1

            validator_state = \
                get_current_validator_state(
                    validator_info=block_info.validator_info,
                    consensus_state=consensus_state,
                    block_cache=block_cache)
            consensus_state.set_validator_state(
                validator_id=block_info.validator_info.id,
                validator_state=create_next_validator_state(
                    validator_info=block_info.validator_info,
                    current_validator_state=validator_state,
                    current_block_count=consensus_state.
                    total_block_claim_count,
                    poet_config_view=block_info.poet_config_view,
                    block_cache=block_cache))

            LOGGER.debug(
                'Create consensus state: BID=%s, EBC=%f, TBCC=%d, '
                'ZBCC=%d',
                block_id[:8],
                consensus_state.expected_block_claim_count,
                consensus_state.total_block_claim_count,
                consensus_state.ztest_block_claim_count)

            consensus_state_store[block_id] = consensus_state

    return consensus_state

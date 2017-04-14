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

import math
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
    # validator state object
    validator_state = \
        consensus_state.get_validator_state(
            validator_id=validator_info.id)

    if validator_state is None:
        validator_state = \
            ValidatorState(
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
        key_block_claim_count = \
            current_validator_state.key_block_claim_count + 1

    # Otherwise, we are resetting statistics for the validator.  This includes
    # using the validator info's transaction ID to get the block number of the
    # block that committed the validator registry transaction
    else:
        key_block_claim_count = 1

    LOGGER.debug(
        'Create validator state for %s: PPK=%s...%s, KBCC=%d, TBCC=%d, '
        'ZBCC=%d',
        validator_info.name,
        validator_info.signup_info.poet_public_key[:8],
        validator_info.signup_info.poet_public_key[-8:],
        key_block_claim_count,
        total_block_claim_count,
        ztest_block_claim_count)

    return \
        ValidatorState(
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


def validator_has_claimed_maximum_number_of_blocks(validator_info,
                                                   validator_state,
                                                   key_block_claim_limit):
    """Determines if a validator has already claimed the maximum number of
    blocks allowed with its PoET key pair.

    Args:
        validator_info (ValidatorInfo): The current validator information
        validator_state (ValidatorState): The current state for the validator
            for which the maximum block claim count is being tested
        key_block_claim_limit (int): The limit of number of blocks that can be
            claimed with a PoET key pair

    Returns:
        True if the validator has already claimed the maximum number of blocks
        with its current PoET key pair, False otherwise
    """

    if validator_state.poet_public_key == \
            validator_info.signup_info.poet_public_key:
        if validator_state.key_block_claim_count >= key_block_claim_limit:
            LOGGER.error(
                'Validator %s (ID=%s...%s) has reached block claim limit for '
                'current PoET keys %d >= %d',
                validator_info.name,
                validator_info.id[:8],
                validator_info.id[-8:],
                validator_state.key_block_claim_count,
                key_block_claim_limit)
            return True
        else:
            LOGGER.debug(
                'Validator %s (ID=%s...%s): Claimed %d block(s) out of %d',
                validator_info.name,
                validator_info.id[:8],
                validator_info.id[-8:],
                validator_state.key_block_claim_count,
                key_block_claim_limit)
    else:
        LOGGER.debug(
            'Validator %s (ID=%s...%s): Claimed 0 block(s) out of %d',
            validator_info.name,
            validator_info.id[:8],
            validator_info.id[-8:],
            key_block_claim_limit)

    return False


def validator_has_claimed_too_early(validator_info,
                                    consensus_state,
                                    block_number,
                                    validator_registry_view,
                                    poet_config_view,
                                    block_store):
    """Determines if a validator has tried to claim a block too early (i.e,
    has not waited the required number of blocks between when the block
    containing its validator registry transaction was committed to the
    chain and trying to claim a block).

    Args:
        validator_info (ValidatorInfo): The current validator information
        consensus_state (ConsensusState): The current consensus state
        block_number (int): The block number of the block that the validator
            is attempting to claim
        validator_registry_view (ValidatorRegistry): The current validator
            registry view
        poet_config_view (PoetConfigView): The current PoET configuration view
        block_store (BlockStore): The block store

    Returns:
        True if the validator has not waited the required number of blocks
        before attempting to claim a block, False otherwise
    """

    # While having a block claim delay is nice, it turns out that in
    # practice the claim delay should not be more than one less than
    # the number of validators.  It helps to imagine the scenario
    # where each validator hits their block claim limit in sequential
    # blocks and their new validator registry information is updated
    # in the following block by another validator, assuming that there
    # were no forks.  If there are N validators, once all N validators
    # have updated their validator registry information, there will
    # have been N-1 block commits and the Nth validator will only be
    # able to get its updated validator registry information updated
    # if the first validator that kicked this off is now able to claim
    # a block.  If the block claim delay was greater than or equal to
    # the number of validators, at this point no validators would be
    # able to claim a block.
    number_of_validators = len(validator_registry_view.get_validators())
    block_claim_delay = \
        min(poet_config_view.block_claim_delay, number_of_validators - 1)

    # While a validator network is starting up, we need to be careful
    # about applying the block claim delay because if we are too
    # aggressive we will get ourselves into a situation where the
    # block claim delay will prevent any validators from claiming
    # blocks.  So, until we get at least block_claim_delay blocks
    # we are going to choose not to enforce the delay.
    if consensus_state.total_block_claim_count <= block_claim_delay:
        LOGGER.debug(
            'Skipping block claim delay check.  Only %d block(s) in '
            'the chain.  Claim delay is %d block(s). %d validator(s) '
            'registered.',
            consensus_state.total_block_claim_count,
            block_claim_delay,
            number_of_validators)
        return False

    # Figure out the block in which the current validator information
    # was committed.
    commit_block = \
        block_store.get_block_by_transaction_id(validator_info.transaction_id)
    blocks_claimed_since_registration = \
        block_number - commit_block.block_num - 1

    if block_claim_delay > blocks_claimed_since_registration:
        LOGGER.error(
            'Validator %s (ID=%s...%s): Committed in block %d, trying to '
            'claim block %d, must wait until block %d',
            validator_info.name,
            validator_info.id[:8],
            validator_info.id[-8:],
            commit_block.block_num,
            block_number,
            commit_block.block_num + block_claim_delay + 1)
        return True

    LOGGER.debug(
        'Validator %s (ID=%s...%s): Committed in block %d, trying to '
        'claim block %d',
        validator_info.name,
        validator_info.id[:8],
        validator_info.id[-8:],
        commit_block.block_num,
        block_number)

    return False


def validator_has_claimed_too_frequently(validator_info,
                                         consensus_state,
                                         validator_state,
                                         poet_config_view,
                                         population_estimate):
    """Determine if allowing the validator to claim a block would allow it to
    claim blocks more frequently that statistically expected (i.e, zTest).

    Args:
        validator_info (ValidatorInfo): The current validator information
        consensus_state (ConsensusState): The current consensus state
        validator_state (ValidatorState): The current validator state for the
            validator that is attempting to claim the block
        poet_config_view (PoetConfigView): The current PoET configuration view
        population_estimate (float): The population estimate for the candidate
            block

    Returns:
        True if allowing the validator to claim the block would result in the
        validator being allowed to claim more frequently than statistically
        expected, False otherwise
    """

    # If there are enough blocks in the block chain that we should apply the
    # zTest (i.e., we have progressed past the blocks for which the local mean
    # is calculated as a fixed ratio of the target to initial wait times) and
    # this validator has already claimed more then the zTest minimum number of
    # observable wins, then ensure that the validator that claimed this block
    # is not winning elections more often than statistically expected (i.e.,
    # the zTest).
    if consensus_state.total_block_claim_count >= \
            poet_config_view.fixed_duration_block_count and \
            validator_state.ztest_block_claim_count >= \
            poet_config_view.ztest_minimum_win_count:

        # We are now going to compute a "1 sample Z test" for each progressive
        # range of results in the history.  Test the hypothesis that validator
        # won elections (i.e., was able to claim blocks) with higher mean that
        # expected.
        #
        # See: http://www.cogsci.ucsd.edu/classes/SP07/COGS14/NOTES/
        #             binomial_ztest.pdf
        #
        # Note that it doesn't appear that we are doing a "1 sample Z test" as
        # we don't walk through all of the blocks, but because of the way in
        # which the accumulated expected block claim count is we are still
        # testing at each block in chain so it is progressive.

        # If allowing the validator to claim this block would result in
        # expected block claim count would suggest, we need to determine if
        # its claim total is outside the allowed maximum win deviation that
        # dictates our confidence interval that we detect claiming too often.
        # If so, then we reject the block.
        observed_wins = validator_state.ztest_block_claim_count + 1
        expected_wins = \
            consensus_state.expected_block_claim_count + \
            1.0 / population_estimate
        block_count = consensus_state.ztest_block_claim_count + 1
        probability = expected_wins / block_count
        standard_deviation = \
            math.sqrt(block_count * probability * (1.0 - probability))
        z_score = (observed_wins - expected_wins) / standard_deviation

        if z_score > poet_config_view.ztest_maximum_win_deviation:
            LOGGER.error(
                'Validator %s (ID=%s...%s) winning too frequently. %f > %f, '
                'Expected=%f, Observed=%d',
                validator_info.name,
                validator_info.id[:8],
                validator_info.id[-8:],
                z_score,
                poet_config_view.ztest_maximum_win_deviation,
                expected_wins,
                observed_wins)
            return True

        LOGGER.debug(
            'Validator %s (ID=%s...%s): %f <= %f, Expected=%f, Observed=%d',
            validator_info.name,
            validator_info.id[:8],
            validator_info.id[-8:],
            z_score,
            poet_config_view.ztest_maximum_win_deviation,
            expected_wins,
            observed_wins)

    return False

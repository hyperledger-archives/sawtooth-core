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
import logging
import collections
import itertools
import threading

import cbor

from sawtooth_poet.poet_consensus import utils
from sawtooth_poet.poet_consensus.poet_config_view import PoetConfigView

from sawtooth_poet_common.validator_registry_view.validator_registry_view \
    import ValidatorRegistryView

LOGGER = logging.getLogger(__name__)

ValidatorState = \
    collections.namedtuple(
        'ValidatorState',
        ['key_block_claim_count',
         'poet_public_key',
         'total_block_claim_count'
         ])
""" Instead of creating a full-fledged class, let's use a named tuple for
the validator state.  The validator state represents the state for a single
validator at a point in time.  A validator state object contains:

key_block_claim_count (int): The number of blocks that the validator has
claimed using the current PoET public key
poet_public_key (str): The current PoET public key for the validator
total_block_claim_count (int): The total number of the blocks that the
    validator has claimed
"""


class ConsensusState(object):
    """Represents the consensus state at a particular point in time (i.e.,
    when the block that this consensus state corresponds to was committed to
    the block chain).

    Attributes:
        aggregate_local_mean (float): The sum of the local means for the PoET
            blocks since the last non-PoET block
        total_block_claim_count (int): The number of blocks that have been
            claimed by all validators
    """

    _BlockInfo = \
        collections.namedtuple(
            '_BlockInfo',
            ['wait_certificate', 'validator_info', 'poet_config_view'])

    """ Instead of creating a full-fledged class, let's use a named tuple for
    the block info.  The block info represents the information we need to
    create consensus state.  A block info object contains:

    wait_certificate (WaitCertificate): The PoET wait certificate object for
        the block
    validator_info (ValidatorInfo): The validator registry information for the
        validator that claimed the block
    poet_config_view (PoetConfigView): The PoET configuration view associated
        with the block
    """

    _PopulationSample = \
        collections.namedtuple(
            '_PopulationSample', ['duration', 'local_mean'])

    """ Instead of creating a full-fledged class, let's use a named tuple for
    the population sample.  The population sample represents the information
    we need to create the population estimate, which in turn is used to compute
    the local mean.  A population sample object contains:

    duration (float): The duration from a wait certificate/timer
    local_mean (float): The local mean from a wait certificate/timer
    """

    _EstimateInfo = collections.namedtuple('_EstimateInfo',
                                           ['population_estimate',
                                            'previous_block_id',
                                            'validator_id'])

    """ Instead of creating a full-fledged class, let's use a named tuple for
    the population estimates.  The population estimate represents what we need
    to help in computing zTest results.  A population estimate object contains:

    population_estimate (float): The population estimate for the corresponding
        block
    previous_block_id (str): The ID of the block previous to the one that this
        population estimate corresponds to
    validator_id (str): The ID of the validator that won the corresponding
        block
    """

    # The population estimate cache is a mapping of block ID to its
    # corresponding _EstimateInfo object.  This is used so that when building
    # the population list, we don't have to always walk back the entire list
    _population_estimate_cache = {}
    _population_estimate_cache_lock = threading.Lock()

    @staticmethod
    def consensus_state_for_block_id(block_id,
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
                store that is used to store interim consensus state created
                up to resulting consensus state
            poet_enclave_module (module): The PoET enclave module

        Returns:
            ConsensusState object representing the consensus state for the
                block referenced by block_id
        """

        consensus_state = None
        previous_wait_certificate = None
        blocks = collections.OrderedDict()

        # Starting at the chain head, walk the block store backwards until we
        # either get to the root or we get a block for which we have already
        # created consensus state
        while True:
            block = \
                ConsensusState._block_for_id(
                    block_id=block_id,
                    block_cache=block_cache)
            if block is None:
                break

            # Try to fetch the consensus state.  If that succeeds, we can
            # stop walking back as we can now build on that consensus
            # state.
            consensus_state = consensus_state_store.get(block_id=block_id)
            if consensus_state is not None:
                break

            wait_certificate = \
                utils.deserialize_wait_certificate(
                    block=block,
                    poet_enclave_module=poet_enclave_module)

            # If this is a PoET block (i.e., it has a wait certificate), get
            # the validator info for the validator that signed this block and
            # add the block information we will need to set validator state in
            # the block's consensus state.
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
                    ConsensusState._BlockInfo(
                        wait_certificate=wait_certificate,
                        validator_info=validator_info,
                        poet_config_view=PoetConfigView(state_view))

            # Otherwise, this is a non-PoET block.  If we don't have any blocks
            # yet or the last block we processed was a PoET block, put a
            # placeholder in the list so that when we get to it we know that we
            # need to reset the statistics.
            elif len(blocks) == 0 or previous_wait_certificate is not None:
                blocks[block_id] = \
                    ConsensusState._BlockInfo(
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
        # which they were added), and store state for PoET blocks so that the
        # next time we don't have to walk so far back through the block chain.
        for block_id, block_info in reversed(blocks.items()):
            # If the block was not a PoET block (i.e., didn't have a wait
            # certificate), reset the consensus state statistics.  We are not
            # going to store this in the consensus state store, but we will use
            # it as the starting for the next PoET block.
            if block_info.wait_certificate is None:
                consensus_state = ConsensusState()

            # Otherwise, let the consensus state update itself appropriately
            # based upon the validator claiming a block, and then associate the
            # consensus state with the new block in the store.

            # validator state for the validator which claimed the block, create
            # updated validator state for the validator, set/update the
            # validator state in the consensus state object, and then associate
            # the consensus state with the corresponding block in the consensus
            # state store.
            else:
                consensus_state.validator_did_claim_block(
                    validator_info=block_info.validator_info,
                    wait_certificate=block_info.wait_certificate,
                    poet_config_view=block_info.poet_config_view)
                consensus_state_store[block_id] = consensus_state

                LOGGER.debug(
                    'Create consensus state: BID=%s, ALM=%f, TBCC=%d',
                    block_id[:8],
                    consensus_state.aggregate_local_mean,
                    consensus_state.total_block_claim_count)

        return consensus_state

    def __init__(self):
        """Initialize a ConsensusState object

        Returns:
            None
        """
        self._aggregate_local_mean = 0.0
        self._population_samples = collections.deque()
        self._total_block_claim_count = 0
        self._validators = {}

    @property
    def aggregate_local_mean(self):
        return self._aggregate_local_mean

    @property
    def total_block_claim_count(self):
        return self._total_block_claim_count

    @staticmethod
    def _check_validator_state(validator_state):
        if not isinstance(
                validator_state.key_block_claim_count, int) \
                or validator_state.key_block_claim_count < 0:
            raise \
                ValueError(
                    'key_block_claim_count ({}) is invalid'.format(
                        validator_state.key_block_claim_count))

        if not isinstance(
                validator_state.poet_public_key, str) \
                or len(validator_state.poet_public_key) < 1:
            raise \
                ValueError(
                    'poet_public_key ({}) is invalid'.format(
                        validator_state.poet_public_key))

        if not isinstance(
                validator_state.total_block_claim_count, int) \
                or validator_state.total_block_claim_count < 0:
            raise \
                ValueError(
                    'total_block_claim_count ({}) is invalid'.format(
                        validator_state.total_block_claim_count))

        if validator_state.key_block_claim_count > \
                validator_state.total_block_claim_count:
            raise \
                ValueError(
                    'total_block_claim_count ({}) is less than '
                    'key_block_claim_count ({})'.format(
                        validator_state.total_block_claim_count,
                        validator_state.key_block_claim_count))

    @staticmethod
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
                None if utils.block_id_is_genesis(block_id) else \
                block_cache[block_id]
        except KeyError:
            LOGGER.error('Failed to retrieve block: %s', block_id[:8])

        return block

    def _build_population_estimate_list(self,
                                        block_id,
                                        poet_config_view,
                                        block_cache,
                                        poet_enclave_module):
        """Starting at the block provided, walk back the blocks and collect the
        population estimates.

        Args:
            block_id (str): The ID of the block to start with
            poet_config_view (PoetConfigView): The current PoET configuration
                view
            block_cache (BlockCache): The block store cache
            poet_enclave_module (module): The PoET enclave module

        Returns:
            deque: The list, in order of most-recent block to least-recent
                block, of _PopulationEstimate objects.
        """
        population_estimate_list = collections.deque()

        # Until we get to the first fixed-duration block (i.e., a block for
        # which the local mean is simply a ratio of the target and initial wait
        # times), first look in our population estimate cache for the
        # population estimate information and if not there fetch the block.
        # Then add the value to the population estimate list.
        #
        # Note that since we know the total block claim count from the
        # consensus state object, we don't have to worry about non-PoET blocks.
        # Using that value and the fixed duration block count from the PoET
        # configuration view, we know now many blocks to get.
        number_of_blocks = \
            self.total_block_claim_count - \
            poet_config_view.population_estimate_sample_size
        with ConsensusState._population_estimate_cache_lock:
            for _ in range(number_of_blocks):
                population_cache_entry = \
                    ConsensusState._population_estimate_cache.get(block_id)
                if population_cache_entry is None:
                    block = block_cache[block_id]
                    wait_certificate = \
                        utils.deserialize_wait_certificate(
                            block=block,
                            poet_enclave_module=poet_enclave_module)
                    population_cache_entry = \
                        ConsensusState._EstimateInfo(
                            population_estimate=wait_certificate.
                            population_estimate,
                            previous_block_id=block.previous_block_id,
                            validator_id=block.header.signer_pubkey)
                    ConsensusState._population_estimate_cache[block_id] = \
                        population_cache_entry

                population_estimate_list.append(population_cache_entry)
                block_id = population_cache_entry.previous_block_id

        return population_estimate_list

    def get_validator_state(self, validator_info):
        """Return the validator state for a particular validator
        Args:
            validator_info (ValidatorInfo): The validator information for the
                validator for which validator or state information is being
                requested
        Returns:
            ValidatorState: The validator state if it exists or the default
                initial state if it does not
        """

        # Fetch the validator state.  If it doesn't exist, then create a
        # default validator state object and store it for further requests
        validator_state = self._validators.get(validator_info.id)

        if validator_state is None:
            validator_state = \
                ValidatorState(
                    key_block_claim_count=0,
                    poet_public_key=validator_info.signup_info.
                    poet_public_key,
                    total_block_claim_count=0)
            self._validators[validator_info.id] = validator_state

        return validator_state

    def validator_did_claim_block(self,
                                  validator_info,
                                  wait_certificate,
                                  poet_config_view):
        """For the validator that is referenced by the validator information
        object, update its state based upon it claiming a block.

        Args:
            validator_info (ValidatorInfo): Information about the validator
            wait_certificate (WaitCertificate): The wait certificate
                associated with the block being claimed
            poet_config_view (PoetConfigView): The current PoET configuration
                view

        Returns:
            None
        """
        # Update the consensus state statistics.
        self._aggregate_local_mean += wait_certificate.local_mean
        self._total_block_claim_count += 1

        # Add the wait certificate information to our population sample,
        # evicting the oldest entry if already have at least
        # population_estimate_sample_size entries.
        self._population_samples.append(
            ConsensusState._PopulationSample(
                duration=wait_certificate.duration,
                local_mean=wait_certificate.local_mean))
        while len(self._population_samples) > \
                poet_config_view.population_estimate_sample_size:
            self._population_samples.popleft()

        # We need to fetch the current state for the validator
        validator_state = \
            self.get_validator_state(validator_info=validator_info)

        total_block_claim_count = \
            validator_state.total_block_claim_count + 1

        # If the PoET public keys match, then we are doing a simple statistics
        # update
        if validator_info.signup_info.poet_public_key == \
                validator_state.poet_public_key:
            key_block_claim_count = \
                validator_state.key_block_claim_count + 1

        # Otherwise, we are resetting statistics for the validator.  This
        # includes using the validator info's transaction ID to get the block
        # number of the block that committed the validator registry
        # transaction.
        else:
            key_block_claim_count = 1

        LOGGER.debug(
            'Update state for %s (ID=%s...%s): PPK=%s...%s, KBCC=%d, TBCC=%d',
            validator_info.name,
            validator_info.id[:8],
            validator_info.id[-8:],
            validator_info.signup_info.poet_public_key[:8],
            validator_info.signup_info.poet_public_key[-8:],
            key_block_claim_count,
            total_block_claim_count)

        # Update our copy of the validator state
        self._validators[validator_info.id] = \
            ValidatorState(
                key_block_claim_count=key_block_claim_count,
                poet_public_key=validator_info.signup_info.poet_public_key,
                total_block_claim_count=total_block_claim_count)

    def validator_has_claimed_block_limit(self,
                                          validator_info,
                                          poet_config_view):
        """Determines if a validator has already claimed the maximum number of
        blocks allowed with its PoET key pair.
        Args:
            validator_info (ValidatorInfo): The current validator information
            poet_config_view (PoetConfigView): The limit of number of blocks
             that can be claimed with a PoET key pair
        Returns:
            Boolean: True if the validator has already claimed the maximum
                number of blocks with its current PoET key pair, False
                otherwise
        """
        key_block_claim_limit = poet_config_view.key_block_claim_limit
        validator_state = \
            self.get_validator_state(validator_info=validator_info)

        if validator_state.poet_public_key == \
                validator_info.signup_info.poet_public_key:
            if validator_state.key_block_claim_count >= key_block_claim_limit:
                LOGGER.error(
                    'Validator %s (ID=%s...%s): Reached block claim limit '
                    'for PoET keys %d >= %d',
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

    def validator_is_claiming_too_early(self,
                                        validator_info,
                                        block_number,
                                        validator_registry_view,
                                        poet_config_view,
                                        block_store):
        """Determines if a validator has tried to claim a block too early
        (i.e, has not waited the required number of blocks between when the
        block containing its validator registry transaction was committed to
        the chain and trying to claim a block).
        Args:
            validator_info (ValidatorInfo): The current validator information
            block_number (int): The block number of the block that the
                validator is attempting to claim
            validator_registry_view (ValidatorRegistry): The current validator
                registry view
            poet_config_view (PoetConfigView): The current PoET configuration
                view
            block_store (BlockStore): The block store
        Returns:
            Boolean: True if the validator has not waited the required number
                of blocks before attempting to claim a block, False otherwise
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
        if self.total_block_claim_count <= block_claim_delay:
            LOGGER.debug(
                'Skipping block claim delay check.  Only %d block(s) in '
                'the chain.  Claim delay is %d block(s). %d validator(s) '
                'registered.',
                self.total_block_claim_count,
                block_claim_delay,
                number_of_validators)
            return False

        # Figure out the block in which the current validator information
        # was committed.
        commit_block = \
            block_store.get_block_by_transaction_id(
                validator_info.transaction_id)
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

    def validator_is_claiming_too_frequently(self,
                                             validator_info,
                                             previous_block_id,
                                             poet_config_view,
                                             population_estimate,
                                             block_cache,
                                             poet_enclave_module):
        """Determine if allowing the validator to claim a block would allow it
        to claim blocks more frequently that statistically expected (i.e,
        zTest).

        Args:
            validator_info (ValidatorInfo): The current validator information
            previous_block_id (str): The ID of the block that is the immediate
                predecessor of the block that the validator is attempting to
                claim
            poet_config_view (PoetConfigView): The current PoET configuration
                view
            population_estimate (float): The population estimate for the
                candidate block
            block_cache (BlockCache): The block store cache
            poet_enclave_module (module): The PoET enclave module

        Returns:
            True if allowing the validator to claim the block would result in
            the validator being allowed to claim more frequently than
            statistically expected, False otherwise
        """
        # If there are note enough blocks in the block chain to apply the zTest
        # (i.e., we have not progressed past the blocks for which the local
        # mean is calculated as a fixed ratio of the target to initial wait),
        # simply short-circuit the test an allow the block to be claimed.
        if self.total_block_claim_count < \
                poet_config_view.population_estimate_sample_size:
            return False

        # Build up the population estimate list for the block chain and then
        # add the new information (i.e., the validator trying to claim as well
        # as the population estimate) to the front to maintain the order of
        # most-recent to least-recent.
        population_estimate_list = \
            self._build_population_estimate_list(
                block_id=previous_block_id,
                poet_config_view=poet_config_view,
                block_cache=block_cache,
                poet_enclave_module=poet_enclave_module)
        population_estimate_list.appendleft(
            ConsensusState._EstimateInfo(
                population_estimate=population_estimate,
                previous_block_id=previous_block_id,
                validator_id=validator_info.id))

        observed_wins = 0
        expected_wins = 0
        block_count = 0
        minimum_win_count = poet_config_view.ztest_minimum_win_count
        maximum_win_deviation = poet_config_view.ztest_maximum_win_deviation

        # We are now going to compute a "1 sample Z test" for each
        # progressive range of results in the history.  Test the
        # hypothesis that validator won elections (i.e., was able to
        # claim blocks) with higher mean that expected.
        #
        # See: http://www.cogsci.ucsd.edu/classes/SP07/COGS14/NOTES/
        #             binomial_ztest.pdf

        for estimate_info in population_estimate_list:
            # Keep track of the number of blocks and the expected number of
            # wins up to this point.
            block_count += 1
            expected_wins += 1.0 / estimate_info.population_estimate

            # If the validator trying to claim the block also claimed this
            # block, update the number of blocks won and if we have seen more
            # than the number of wins necessary to trigger the zTest, then we
            # are going to figure out if the validator is winning too
            # frequently.
            if estimate_info.validator_id == validator_info.id:
                observed_wins += 1
                if observed_wins > minimum_win_count and \
                        observed_wins > expected_wins:
                    probability = expected_wins / block_count
                    standard_deviation = \
                        math.sqrt(block_count * probability *
                                  (1.0 - probability))
                    z_score = \
                        (observed_wins - expected_wins) / \
                        standard_deviation
                    if z_score > maximum_win_deviation:
                        LOGGER.error(
                            'Validator %s (ID=%s...%s): zTest failed at depth '
                            '%d, z_score=%f, expected=%f, observed=%d',
                            validator_info.name,
                            validator_info.id[:8],
                            validator_info.id[-8:],
                            block_count,
                            z_score,
                            expected_wins,
                            observed_wins)
                        return True

        LOGGER.debug(
            'Validator %s (ID=%s...%s): zTest succeeded with depth %d, '
            'expected=%f, observed=%d',
            validator_info.name,
            validator_info.id[:8],
            validator_info.id[-8:],
            block_count,
            expected_wins,
            observed_wins)

        LOGGER.debug(
            'zTest history: %s',
            ['{:.4f}'.format(x.population_estimate) for x in
             itertools.islice(population_estimate_list, 0, 3)])

        return False

    def serialize_to_bytes(self):
        """Serialized the consensus state object to a byte string suitable
        for storage

        Returns:
            bytes: serialized version of the consensus state object
        """
        # For serialization, the easiest thing to do is to convert ourself to
        # a dictionary and convert to CBOR.  The deque object cannot be
        # automatically serialized, so convert it to a list first.  We will
        # reconstitute it to a deque upon parsing.
        self_dict = {
            '_aggregate_local_mean': self._aggregate_local_mean,
            '_population_samples': list(self._population_samples),
            '_total_block_claim_count': self._total_block_claim_count,
            '_validators': self._validators
        }
        return cbor.dumps(self_dict)

    def parse_from_bytes(self, buffer):
        """Returns a consensus state object re-created from the serialized
        consensus state provided.

        Args:
            buffer (bytes): A byte string representing the serialized
                version of a consensus state to re-create.  This was created
                by a previous call to serialize_to_bytes

        Returns:
            ConsensusState: object representing the serialized byte string
                provided

        Raises:
            ValueError: failure to parse into a valid ConsensusState object
        """
        try:
            # Deserialize the CBOR back into a dictionary and set the simple
            # fields, doing our best to check validity.
            self_dict = cbor.loads(buffer)

            if not isinstance(self_dict, dict):
                raise \
                    ValueError(
                        'buffer is not a valid serialization of a '
                        'ConsensusState object')

            self._aggregate_local_mean = \
                float(self_dict['_aggregate_local_mean'])
            self._population_samples = collections.deque()
            for sample in self_dict['_population_samples']:
                (duration, local_mean) = [float(value) for value in sample]
                if not math.isfinite(duration) or duration < 0:
                    raise \
                        ValueError(
                            'duration ({}) is invalid'.format(duration))
                if not math.isfinite(local_mean) or local_mean < 0:
                    raise \
                        ValueError(
                            'local_mean ({}) is invalid'.format(local_mean))
                self._population_samples.append(
                    ConsensusState._PopulationSample(
                        duration=duration,
                        local_mean=local_mean))
            self._total_block_claim_count = \
                int(self_dict['_total_block_claim_count'])
            validators = self_dict['_validators']

            if not math.isfinite(self.aggregate_local_mean) or \
                    self.aggregate_local_mean < 0:
                raise \
                    ValueError(
                        'aggregate_local_mean ({}) is invalid'.format(
                            self.aggregate_local_mean))
            if self.total_block_claim_count < 0:
                raise \
                    ValueError(
                        'total_block_claim_count ({}) is invalid'.format(
                            self.total_block_claim_count))

            if not isinstance(validators, dict):
                raise ValueError('_validators is not a dict')

            # Now walk through all of the key/value pairs in the the
            # validators dictionary and reconstitute the validator state from
            # them, again trying to validate the data the best we can.  The
            # only catch is that because the validator state objects are named
            # tuples, cbor.dumps() treated them as tuples and so we lost the
            # named part.  When re-creating the validator state, are going to
            # leverage the namedtuple's _make method.

            self._validators = {}
            for key, value in validators.items():
                validator_state = ValidatorState._make(value)

                self._check_validator_state(validator_state)
                self._validators[str(key)] = validator_state

        except (LookupError, ValueError, KeyError, TypeError) as error:
            raise \
                ValueError(
                    'Error parsing ConsensusState buffer: {}'.format(error))

    def __str__(self):
        validators = \
            ['{}: {{KBCC={}, PPK={}, TBCC={} }}'.format(
                key[:8],
                value.key_block_claim_count,
                value.poet_public_key[:8],
                value.total_block_claim_count) for
             key, value in self._validators.items()]

        return \
            'ALM={:.4f}, TBCC={}, PS={}, V={}'.format(
                self.aggregate_local_mean,
                self.total_block_claim_count,
                self._population_samples,
                validators)

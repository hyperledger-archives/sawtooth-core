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

import collections
import logging
import importlib
import hashlib
import random
import math

from sawtooth_signing import secp256k1_signer as signing
from sawtooth_validator.journal.block_wrapper import NULL_BLOCK_IDENTIFIER
from sawtooth_validator.journal.consensus.poet1 import poet_transaction_block

# Disabled pylint as this package no longer exists and will be replaced as PoET
# is integrated into the validator.
# pylint: disable=no-name-in-module
from sawtooth_validator.journal.consensus.poet1\
    import validator_registry as val_reg

from sawtooth_validator.journal.consensus.poet1.signup_info import SignupInfo
from sawtooth_validator.journal.consensus.poet1.wait_timer import WaitTimer
from sawtooth_validator.journal.consensus.poet1.wait_certificate\
    import WaitCertificate

LOGGER = logging.getLogger(__name__)

BlockInformation = collections.namedtuple('BlockInformation',
                                          ['originator_id',
                                           'population_estimate'])


class PoetConsensus(object):
    """Implements a journal based on the proof of elapsed time
    consensus mechanism.

    Attributes:
        onHeartBeatTimer (EventHandler): The EventHandler tracking
            calls to make when the heartbeat timer fires.
        MaximumBlocksToKeep (int): The maximum number of blocks to
            keep.
    """

    # The default maximum number of blocks that a validator can claim
    # before it is required to submit new signup information
    __BLOCK_CLAIM_THRESHOLD = 25

    # The default number of blocks that a validator can claim before it
    # will start testing (through a random algorithm) whether it will
    # submit new signup information
    __BLOCK_CLAIM_TRIGGER = 20

    # The default maximum deviation from the expected win frequency
    # for a particular validator before the z-test will fail and the
    # claimed block will be rejected.  Deviations and corresponding
    # confidence intervals:
    # 3.075 ==> 99.9%
    # 2.575 ==> 99.5%
    # 2.321 ==> 99%
    # 1.645 ==> 95%
    __MAXIMUM_WIN_DEVIATION = 3.075

    # The default minimum number of observations before the deviation
    # from expected win frequency is checked
    __MINIMUM_WIN_OBSERVATIONS = 3

    # The default number of blocks that a validator must wait after its
    # validator registry entry was created/updated before it is allowed to
    # claim a block.
    __BLOCK_CLAIM_DELAY = 1

    def __init__(self, kwargs):
        """Constructor for the PoetJournal class.

        Args:
            kwargs (dict):
        """
        self.poet_public_key = None
        self._validator_statistics = None
        self._population_cache = {}

        if 'PoetEnclaveImplementation' in kwargs:
            enclave_module = kwargs['PoetEnclaveImplementation']
        else:
            enclave_module = 'sawtooth_validator.consensus.poet1.' \
                             'poet_enclave_simulator' \
                             '.poet_enclave_simulator'

        self._block_claim_threshold = \
            max(
                int(
                    kwargs.get(
                        'BlockClaimThreshold',
                        self.__BLOCK_CLAIM_THRESHOLD)),
                1)
        LOGGER.debug(
            'Validators may only claim %d block(s) before being required to '
            'obtain new keys',
            self._block_claim_threshold)

        self._block_claim_trigger = \
            min(
                int(
                    kwargs.get(
                        'BlockClaimTrigger',
                        self.__BLOCK_CLAIM_TRIGGER)),
                self._block_claim_threshold)
        LOGGER.debug(
            'After claiming %d block(s), validator will begin randomly '
            'determining if it wants to create new keys',
            self._block_claim_trigger)

        self._maximum_win_deviation = \
            float(
                kwargs.get(
                    'MaximumWinDeviation',
                    self.__MAXIMUM_WIN_DEVIATION))
        LOGGER.debug(
            'A validator will be allowed a maximum deviation of %f from '
            'the expected election win frequency',
            self._maximum_win_deviation)

        self._minimum_win_observations = \
            max(
                int(
                    kwargs.get(
                        'MinimumWinObservations',
                        self.__MINIMUM_WIN_OBSERVATIONS)),
                1)
        LOGGER.debug(
            'A validator must win at least %d block election(s) before zTest '
            'is used to check its win frequency is tested against the '
            'maximum deviation',
            self._minimum_win_observations)

        self._block_claim_delay = \
            max(
                int(
                    kwargs.get(
                        'BlockClaimDelay',
                        self.__BLOCK_CLAIM_DELAY)),
                0)
        LOGGER.debug(
            'A validator must wait at least %d committed block(s) after its '
            'keys are added/refreshed before it will be allowed to claim a '
            'block.',
            self._block_claim_delay)

        # We are going to sum up the numbers between the trigger and the
        # threshold (inclusive), shifting all numbers "left" by (trigger - 1)
        # i.e., n * (n + 1) / 1, where n is the number of claims between
        # trigger and threshold, inclusive.  If trigger and threshold are the
        # same, n is 1.
        #
        # Later, when we check to see if we want to create new signup
        # information, we are going to make the same calculation, but using
        # the claim count instead of threshold, meaning that the closer we get
        # to the threshold, the more likely it is we will generate new keys,
        # guaranteeing that when the claimed count hits the threshold, we will
        # generate new keys with 100% probability.
        self._weighted_range = \
            (self._block_claim_threshold - self._block_claim_trigger + 1) * \
            (self._block_claim_threshold - self._block_claim_trigger + 2) / 2

        poet_enclave = importlib.import_module(enclave_module)
        poet_enclave.initialize(**kwargs)
        WaitCertificate.poet_enclave = poet_enclave
        WaitTimer.poet_enclave = poet_enclave
        SignupInfo.poet_enclave = poet_enclave

    @staticmethod
    def _retrieve_validator_registration(journal, block_id, originator_id):
        registration = None
        try:
            # Retrieve the validator registry transaction store so we can query
            # information about a registration
            store = \
                val_reg.ValidatorRegistryTransaction.get_store(
                    journal=journal,
                    block_id=block_id)

            registration = store.get(originator_id)
        except KeyError:
            raise ValueError(
                'Unable to retrieve registration information for validator '
                '{}'.format(
                    originator_id))

        return registration

    @staticmethod
    def _number_of_registered_validators(journal, block_id):
        return \
            len(
                val_reg.ValidatorRegistryTransaction.get_store(
                    journal=journal,
                    block_id=block_id))

    def _update_validator_claimed_block_count(self,
                                              journal,
                                              block,
                                              increment_value,
                                              default_initial_value,
                                              sync_local_store=True,
                                              reset_on_different_key=True):
        # Retrieve the validator registration information for the validator
        # that is the originator for the block in question
        registration = \
            PoetConsensus._retrieve_validator_registration(
                journal=journal,
                block_id=block.Identifier,
                originator_id=block.OriginatorID)

        # Get the statistics for the validator that claimed the block,
        # creating them if they don't already exist.
        statistics = \
            self._validator_statistics.setdefault(
                block.OriginatorID,
                {
                    'poet_public_key': registration['poet-public-key'],
                    'claimed_block_count': default_initial_value
                })

        # Compare the PoET public key in our statistics entry with the PoET
        # public key for the validator.  If they are different then that means
        # that the originator used a different key to sign this block than
        # previous blocks seen - in that case, reset the statistics (if
        # requested to do so).
        if registration['poet-public-key'] != \
                statistics['poet_public_key'] and reset_on_different_key:
            statistics['poet_public_key'] = \
                registration['poet-public-key']
            statistics['claimed_block_count'] = default_initial_value

        # If the PoET public keys are the same, then update the block commit
        # count appropriately.
        if registration['poet-public-key'] == statistics['poet_public_key']:
            statistics['claimed_block_count'] += increment_value

        # A guard to keep our statistics in the reasonable range
        if statistics['claimed_block_count'] < 0:
            statistics['claimed_block_count'] = 0
        elif statistics['claimed_block_count'] > \
                self._block_claim_threshold:
            statistics['claimed_block_count'] = self._block_claim_threshold

        # Update the in-memory local store and if requested, also sync the
        # local store to the persisted backing storage.
        journal.local_store.set(
            'validator_statistics',
            self._validator_statistics)
        if sync_local_store:
            journal.local_store.sync()

    def _on_journal_restored(self, journal):
        """
        Callback journal makes if the journal was restored from local
        storage.  We use the opportunity to build up our local block
        commit statistics.

        Args:
            journal (Journal): The journal object that was restored.

        Returns:
            True on success, False on failure
        """
        # Since we are restoring from local store, we need to reset statistics
        self._validator_statistics = {}

        # We are going to walk the blocks backwards from newest to oldest
        for block in journal.iter_committed_blocks():
            try:
                # Update the stats for this validator, however don't let the
                # function sync the local store as we'll do that when we have
                # walked all of the blocks.  Also, if we find a different
                # PoET public key for the validator, do not reset the
                # statistics as we have hit an old, out-of-date PoET public
                # key for the validator.
                self._update_validator_claimed_block_count(
                    journal=journal,
                    block=block,
                    increment_value=1,
                    default_initial_value=0,
                    sync_local_store=False,
                    reset_on_different_key=False)
            except ValueError as error:
                LOGGER.error('Caught Exception: %s', str(error))

        for originator, statistics in self._validator_statistics.iteritems():
            LOGGER.debug(
                'Validator with ID %s has claimed %d block(s) with PoET '
                'public key %s',
                originator,
                statistics['claimed_block_count'],
                statistics['poet_public_key'])

        # Sync the statistics back so they are persisted
        journal.local_store.set(
            'validator_statistics',
            self._validator_statistics)
        journal.local_store.sync()

        return True

    def _on_journal_initialization_complete(self, journal):
        """
        Callback journal makes after the journal has completed initialization

        Args:
            journal (Journal): The journal object that has completed
                initialization.

        Returns:
            True
        """
        # If we have sealed signup data (meaning that we have previously
        # created signup info), we can request that the enclave unseal it,
        # in the process restoring the enclave to its previous state.  If
        # we don't have sealed signup data, we need to create and register it.
        #
        # Note - this MUST be done AFTER the journal has completed
        # initialization so that there is at least one peer node to which
        # we can send the validator registry transaction to.  Otherwise,
        # we will never, ever be able to be added to the validator registry
        # and, to paraphrase Martha Stewart, that is a bad thing.

        sealed_signup_data = journal.local_store.get('sealed_signup_data')

        if sealed_signup_data is not None:
            self.poet_public_key = \
                SignupInfo.unseal_signup_data(
                    validator_address=journal.local_node.signing_address(),
                    sealed_signup_data=sealed_signup_data)

            LOGGER.info(
                'Restore signup info for %s (ID = %s, PoET public key = %s)',
                journal.local_node.Name,
                journal.local_node.Identifier,
                self.poet_public_key)
        else:
            self.register_signup_information(journal)

        return True

    def _on_block_test(self, journal, block):
        """
        Callback the journal makes to allow us to check a candidate block to
        see if we believe it to be valid.  It is in here that we will enforce
        PoET 1 policies.

        Args:
            journal (Journal): The journal to which the candidate belongs
            block (PoetTransactionBlock): The candidate block to test

        Returns:
            True if we accept the block as a valid block, False otherwise
        """
        return self._block_can_be_claimed(journal=journal, block=block)

    def _on_commit_block(self, journal, block):
        """
        Callback the journal makes when it commits a block.  We use the
        callback as an opportunity to update our block commit statistics.

        Args:
            journal (Journal): The journal object that committed the block.
            block (PoetTransactionBlock): The block that was committed.

        Returns:
            True on success, False on failure.
        """
        LOGGER.info(
            'Block %s has been claimed by %s',
            block.Identifier,
            block.OriginatorID)

        self._update_validator_claimed_block_count(
            journal=journal,
            block=block,
            increment_value=1,
            default_initial_value=0)

        statistics = self._validator_statistics[block.OriginatorID]
        LOGGER.debug(
            'After block commit, validator %s has claimed %d block(s) with '
            'PoET public key %s',
            block.OriginatorID,
            statistics['claimed_block_count'],
            statistics['poet_public_key'])

        # If we are the validator that claimed the block, we need to see
        # if we need to get new signup information to ensure that we are
        # able to continue claiming blocks
        if journal.local_node.Identifier == block.OriginatorID:
            if self._should_reregister_signup_information(
                    statistics['claimed_block_count']):
                LOGGER.info(
                    'Validator has decided to refresh signup information '
                    '(claim count = %d, trigger = %d threshold = %d).',
                    statistics['claimed_block_count'],
                    self._block_claim_trigger,
                    self._block_claim_threshold)

                self.register_signup_information(journal)

        return True

    def _on_decommit_block(self, journal, block):
        """
        Callback the journal makes when it de-commits a block.  We use the
        callback as an opportunity to update our block commit statistics.

        Args:
            journal (Journal): The journal object that de-committed the block.
            block (PoetTransactionBlock): The block that was de-committed.

        Returns:
            True on success, False on failure.
        """
        LOGGER.info(
            'Block %s by validator %s will be de-committed',
            block.Identifier,
            block.OriginatorID)

        # Update the statistics for this validator.  In this case, we are
        # going to assume the worst and set the default block count to the
        # threshold as it turns out that we either don't have statistics for
        # this validator or de-committing the one or more blocks caused the
        # validator to temporarily revert to a previous public key.
        self._update_validator_claimed_block_count(
            journal=journal,
            block=block,
            increment_value=-1,
            default_initial_value=self._block_claim_threshold)

        statistics = self._validator_statistics[block.OriginatorID]
        LOGGER.debug(
            'After block de-commit, validator %s has claimed %d block(s) '
            'with PoET public key %s',
            block.OriginatorID,
            statistics['claimed_block_count'],
            statistics['poet_public_key'])

        return True

    def _should_reregister_signup_information(self, block_claim_count):
        # If the block claim count has hit the trigger, we are going to
        # randomly determine if we want to generate new keys.  The random
        # distribution is based upon the sum of the range between the
        # trigger and the threshold and the range between the trigger and
        # the claim count.  Assuming that S represents the sum of the range
        # between the trigger and the threshold, the probabilities (starting
        # with claim count == trigger, up through claim count == threshold:
        # 1 / S, 3 / S, 6 / S, ..., S / S
        if block_claim_count >= self._block_claim_trigger:
            LOGGER.debug(
                'Claim count has triggered key regeneration check (%d >= %d)',
                block_claim_count,
                self._block_claim_trigger)
            weighted_distance = \
                (block_claim_count - self._block_claim_trigger + 1) * \
                (block_claim_count - self._block_claim_trigger + 2) / 2
            if random.randint(1, self._weighted_range) <= weighted_distance:
                return True

        return False

    def _validator_has_claimed_too_soon(self, journal, block, registration):
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
        # if the first validator that kicked this off is no able to claim
        # a block.
        number_of_validators = \
            self._number_of_registered_validators(
                journal=journal,
                block_id=journal.most_recent_committed_block_id)
        block_claim_delay = \
            min(self._block_claim_delay, number_of_validators - 1)

        # While a validator network is starting up, we need to be careful
        # about applying the block claim delay because if we are too
        # aggressive we will get ourselves into a situation where the
        # block claim delay will prevent any validators from claiming
        # blocks.  So, until we get at least block_claim_delay blocks
        # per validator, we are going to choose not to enforce the delay.
        if journal.committed_block_count > \
                number_of_validators * block_claim_delay:
            blocks_since_registration = \
                block.BlockNum - registration['updated-in-block-number'] - 1

            if block_claim_delay > blocks_since_registration:
                LOGGER.error(
                    'Validator %s is trying to claim a block before waiting '
                    'for the block claim delay. Registered %d block(s) ago. '
                    'Claim delay is %d.',
                    registration['validator-id'],
                    blocks_since_registration,
                    block_claim_delay)
                return True

            LOGGER.debug(
                'There has(have) been %d block(s) claimed since Validator %s '
                'was registered and block claim delay is %d block(s). '
                'Check passed.',
                blocks_since_registration,
                registration['validator-id'],
                block_claim_delay)
        else:
            LOGGER.info(
                'Skipping block claim delay check as there is(are) only %d '
                'block(s) in the chain and the claim delay is %d block(s) '
                'and there is(are) %d validator(s) registered.',
                journal.committed_block_count,
                block_claim_delay,
                number_of_validators)

        return False

    def _validator_has_reached_claim_limit(self, originator_id, registration):
        # Get the statistics, creating them if they don't already
        # exist
        statistics = \
            self._validator_statistics.setdefault(
                originator_id,
                {
                    'poet_public_key': registration['poet-public-key'],
                    'claimed_block_count': 0
                })

        # If the validator has already reached the claim limit for the
        # public key, then we reject the block as the validator needs
        # to get new signup information.
        if (registration['poet-public-key'] ==
                statistics['poet_public_key']) and \
                (statistics['claimed_block_count'] >=
                    self._block_claim_threshold):
            LOGGER.error(
                'Validator %s has reached block claim limit '
                '(%d >= %d) with current signup information',
                originator_id,
                statistics['claimed_block_count'],
                self._block_claim_threshold)
            return True

        return False

    def _build_population_list(self, journal, block):
        population_list = []

        # Starting with the block previous to the one provided, walk the
        # blocks backwards until we get to the root
        block_id = block.PreviousBlockID
        while block_id != NULL_BLOCK_IDENTIFIER:
            other_block = journal.block_store[block_id]

            # If we haven't cached the information for this block, then
            # do so first
            population_cache_entry = self._population_cache.get(block_id)
            if population_cache_entry is None:
                originator_id = other_block.OriginatorID
                population_estimate = \
                    other_block.wait_certificate.population_estimate
                block_info = \
                    BlockInformation(
                        originator_id=originator_id,
                        population_estimate=population_estimate)

            # Now add it to the population list and get the previous block
            population_list.append(block_info)
            block_id = other_block.PreviousBlockID

        # Drop the first WaitTimer.fixed_duration_blocks blocks from the list
        # as the population numbers for these blocks are meaningless since
        # the duration was fixed.
        return population_list[:-WaitTimer.fixed_duration_blocks]

    def _validator_is_winning_too_frequently(self,
                                             journal,
                                             block,
                                             pre_claim_test=False):
        # Build up the population list for the block chain and if empty, then
        # don't bother with the z-test
        population_list = \
            self._build_population_list(journal=journal, block=block)
        if population_list:
            # If we are testing before claiming, set the originator ID to our
            # own as it will not be retrievable from the block (as it hasn't
            # been signed yet) and get the population estimate from the wait
            # timer.  Otherwise, get it from the block.
            if pre_claim_test:
                originator_id = journal.local_node.Identifier
                population_estimate = block.wait_timer.population_estimate
            else:
                originator_id = block.OriginatorID
                population_estimate = \
                    block.wait_certificate.population_estimate

            # Insert this block information at the front
            population_list.insert(
                0,
                BlockInformation(
                    originator_id=originator_id,
                    population_estimate=population_estimate))

            observed_wins = 0
            expected_wins = 0
            block_count = 0

            # We are now going to compute a "1 sample Z test" for each
            # progressive range of results in the history.  Test the
            # hypothesis that validator won elections (i.e., was able to
            # claim blocks) with higher mean that expected.
            #
            # See: http://www.cogsci.ucsd.edu/classes/SP07/COGS14/NOTES/
            #             binomial_ztest.pdf

            for block_info in population_list:
                block_count += 1
                expected_wins += 1.0 / block_info.population_estimate
                if block_info.originator_id == originator_id:
                    observed_wins += 1
                    if observed_wins > self._minimum_win_observations and \
                            observed_wins > expected_wins:
                        probability = expected_wins / block_count
                        standard_deviation = \
                            math.sqrt(block_count * probability *
                                      (1.0 - probability))
                        z_score = \
                            (observed_wins - expected_wins) / \
                            standard_deviation
                        if z_score > self._maximum_win_deviation:
                            LOGGER.info(
                                'zTest failed for %s at depth %d with z=%f, '
                                'expected=%f, observed=%d',
                                originator_id,
                                block_count,
                                z_score,
                                expected_wins,
                                observed_wins)
                            return True

            LOGGER.debug(
                'zTest succeeded for %s with block depth %d, expected=%f, '
                'observed=%g',
                originator_id,
                block_count,
                expected_wins,
                observed_wins)
            LOGGER.debug(
                'zTest history: %s',
                ['{0}:{1:0.2f}'.format(
                    x.originator_id[:8],
                    x.population_estimate) for x in population_list[:3]])

        return False

    def _block_can_be_claimed(self, journal, block, pre_claim_test=False):
        # If there are no committed blocks, we are testing the genesis block.
        # That means that no validator registration information exists and
        # therefore we cannot even hope to gather any statistics.  So, we will
        # have to just assume, for the time being, that the block can be
        # claimed unless some further test rejects it.
        if journal.committed_block_count != 0:
            # If we are testing before we try to claim the block, then we use
            # the local node identifier as the originator of the block as we
            # cannot get the originator ID from the block until it is signed.
            if pre_claim_test:
                originator_id = journal.local_node.Identifier
            else:
                originator_id = block.OriginatorID

            try:
                # Retrieve the validator registry transaction information.
                # Note that we have to use the most-recently-committed block
                # as the block under test has no transaction store associated
                # with it.  Been there, done that...didn't work.  =)  If there
                # is no validator registration information, then we will reject
                # the block as we have no way to validate it.
                registration = \
                    PoetConsensus._retrieve_validator_registration(
                        journal=journal,
                        block_id=journal.most_recent_committed_block_id,
                        originator_id=originator_id)

                # If we are testing before trying to claim, then we need to
                # make sure that we will be signing the wait certificate with
                # the private key that corresponds to the publicly-known public
                # key.
                if pre_claim_test:
                    if registration['poet-public-key'] != self.poet_public_key:
                        raise \
                            ValueError(
                                "Our current PoET public key does not match "
                                "the globally-visible one.  Wait until "
                                "another validator has added our new key to "
                                "the validator registry.")

                # Test to see if the validator has waited the required number
                # of blocks between its keys being added to the blockchain and
                # this block.
                if self._validator_has_claimed_too_soon(
                        journal=journal,
                        block=block,
                        registration=registration):
                    raise \
                        ValueError(
                            'Validator {0} did not wait long enough before '
                            'trying to claim a block.  Only waited {1} '
                            'blocks instead of {2}'.format(
                                originator_id,
                                block.BlockNum -
                                registration['updated-in-block-number'],
                                self._block_claim_delay))

                # Test to see if the validator has reached its claim limit
                if self._validator_has_reached_claim_limit(
                        originator_id=originator_id,
                        registration=registration):
                    raise \
                        ValueError(
                            'Validator {} has reached block claim '
                            'limit'.format(
                                originator_id))

                # Test to see if a validator is winning too frequently
                if self._validator_is_winning_too_frequently(
                        journal=journal,
                        block=block,
                        pre_claim_test=pre_claim_test):
                    raise \
                        ValueError(
                            'Validator {} is winning elections to '
                            'frequently'.format(
                                originator_id))
            except ValueError as error:
                LOGGER.error('Block cannot be claimed: %s', error)
                return False

        return True

    def register_signup_information(self, journal):
        wait_certificate_id = journal.most_recent_committed_block_id
        public_key_hash = \
            hashlib.sha256(
                signing.encode_pubkey(journal.local_node.public_key(),
                                      'hex')).hexdigest()

        signup_info = \
            SignupInfo.create_signup_info(
                validator_address=journal.local_node.signing_address(),
                originator_public_key_hash=public_key_hash,
                most_recent_wait_certificate_id=wait_certificate_id)

        # Save off the sealed signup data and cache the PoET public key
        journal.local_store.set(
            'sealed_signup_data',
            signup_info.sealed_signup_data)
        journal.local_store.sync()

        self.poet_public_key = signup_info.poet_public_key

        LOGGER.debug(
            'Register %s (%s)',
            journal.local_node.Name,
            journal.local_node.Identifier)

        # Create a validator register transaction and sign it.  Wrap
        # the transaction in a message.  Broadcast it to out.
        transaction = \
            val_reg.ValidatorRegistryTransaction.register_validator(
                journal.local_node.Name,
                journal.local_node.Identifier,
                signup_info)
        transaction.sign_from_node(journal.local_node)

        message = \
            val_reg.ValidatorRegistryTransactionMessage()
        message.Transaction = transaction

        LOGGER.info(
            'Advertise PoET 1 validator %s (ID = %s) has PoET public key '
            '%s',
            journal.local_node.Name,
            journal.local_node.Identifier,
            signup_info.poet_public_key)

        journal.gossip.broadcast_message(message)

    def initialization_complete(self, journal):
        """Processes all invocations that arrived while the ledger was
        being initialized.
        """
        # propagate the maximum blocks to keep
        journal.maximum_blocks_to_keep = max(
            journal.maximum_blocks_to_keep,
            WaitTimer.certificate_sample_length)

        # initialize the block handlers
        poet_transaction_block.register_message_handlers(journal)

        # Load our validator statistics.  If they exist, we are going to be
        # optimistic and assume they are in sync with block chain.  If they
        # don't exist, we are going to walk the block chain and initialize
        # them.
        self._validator_statistics = \
            journal.local_store.get('validator_statistics')
        if self._validator_statistics is None:
            self._validator_statistics = {}

        # If the journal is restored from local store, we want to know so
        # that we can build up or stats from the restored blocks
        journal.on_restored += self._on_journal_restored

        # We want to know when the journal has completed initialization.  This
        # turns out to be very important - up until that point, we are not
        # able to send out any transactions (such as validator registry
        # transactions), which is really important because that will keep us
        # from ever joining a validator network for the first time.
        journal.on_initialization_complete += \
            self._on_journal_initialization_complete

        # We want the ability to test a block before it gets claimed so that
        # we can enforce PoET 1 policies
        journal.on_block_test += self._on_block_test

        # We want to know when a block is committed or decommitted so that
        # we can keep track of validator statistics
        journal.on_commit_block += self._on_commit_block
        journal.on_decommit_block += self._on_decommit_block

    def create_block(self):
        """Creates a candidate transaction block.

        Returns:
            A new PoET transaction block on success, None on failure
        """
        return poet_transaction_block.PoetTransactionBlock()

    def initialize_block(self, journal, block):
        """Builds a transaction block that is specific to this particular
        consensus mechanism, in this case we build a block that contains a
        wait certificate.

        Args:
            journal: the journal object
            block: the transaction block to initialize.
        Returns:
            PoetTransactionBlock: The constructed block with the wait
                certificate.
        """

        block.create_wait_timer(
            journal.local_node.signing_address(),
            self.build_certificate_list(journal.block_store, block))

        journal.JournalStats.LocalMeanTime.Value = \
            block.wait_timer.local_mean
        journal.JournalStats.PopulationEstimate.Value = \
            round(block.wait_timer.local_mean /
                  block.wait_timer.target_wait_time, 2)

        LOGGER.debug('created new pending block with timer <%s> and '
                     '%d transaction(s)', block.wait_timer,
                     len(block.TransactionIDs))

        journal.JournalStats.ExpectedExpirationTime.Value = \
            round(block.wait_timer.request_time +
                  block.wait_timer.duration, 2)

        journal.JournalStats.Duration.Value = \
            round(block.wait_timer.duration, 2)

    def claim_block(self, journal, block):
        """
        Claims the block (i.e., in our case, creates a wait certificate
        for it and attaches our PoET public key to it).

        Args:
            journal (Journal): The journal object that is keeping track of
                blocks
            block (PoetTransactionBlock): The block to claim.
        """
        if not self._block_can_be_claimed(journal=journal,
                                          block=block,
                                          pre_claim_test=True):
            raise ValueError('Could not claim block')

        # If we got this far, we are fairly confident in creating a wait
        # certificate for the block and embedding our public key.
        block.create_wait_certificate()
        block.poet_public_key = self.poet_public_key

    def create_block_message(self, block):
        msg = poet_transaction_block.PoetTransactionBlockMessage()
        msg.transaction_block = block
        return msg

    def build_certificate_list(self, block_store, block):
        # for the moment we just dump all of these into one list,
        # not very efficient but it makes things a lot easier to maintain
        certs = collections.deque()
        count = WaitTimer.certificate_sample_length

        while block.PreviousBlockID != NULL_BLOCK_IDENTIFIER \
                and len(certs) < count:
            block = block_store[block.PreviousBlockID]
            certs.appendleft(block.wait_certificate)

        # drop the root block off the computation
        return list(certs)

    def check_claim_block(self, journal, block, now):
        return block.wait_timer_has_expired(now)

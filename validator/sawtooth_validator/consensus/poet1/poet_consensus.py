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

from gossip import common
from gossip import stats
from sawtooth_signing import pbct_nativerecover as signing
from sawtooth_validator.consensus.consensus_base import Consensus
from sawtooth_validator.consensus.poet1 import poet_transaction_block
from sawtooth_validator.consensus.poet1 import validator_registry as val_reg
from sawtooth_validator.consensus.poet1.signup_info import SignupInfo
from sawtooth_validator.consensus.poet1.wait_timer import WaitTimer
from sawtooth_validator.consensus.poet1.wait_certificate import WaitCertificate

LOGGER = logging.getLogger(__name__)


class PoetConsensus(Consensus):
    """Implements a journal based on the proof of elapsed time
    consensus mechanism.

    Attributes:
        onHeartBeatTimer (EventHandler): The EventHandler tracking
            calls to make when the heartbeat timer fires.
        MaximumBlocksToKeep (int): The maximum number of blocks to
            keep.
    """

    __BLOCK_COMMIT_THRESHOLD = 25

    def __init__(self, kwargs):
        """Constructor for the PoetJournal class.

        Args:
            kwargs (dict):
        """
        self.poet_public_key = None
        self._validator_statistics = None

        if 'PoetEnclaveImplementation' in kwargs:
            enclave_module = kwargs['PoetEnclaveImplementation']
        else:
            enclave_module = 'sawtooth_validator.consensus.poet1.' \
                             'poet_enclave_simulator' \
                             '.poet_enclave_simulator'

        self._block_commit_threshold = \
            kwargs.get('BlockCommitThreshold', self.__BLOCK_COMMIT_THRESHOLD)
        LOGGER.debug(
            'Validators may only commit %d block(s) before obtaining new '
            'keys',
            self._block_commit_threshold)

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
                journal.get_transaction_store(
                    family=val_reg.ValidatorRegistryTransaction,
                    block_id=block_id)

            registration = store.get(originator_id)
        except KeyError:
            raise ValueError(
                'Unable to retrieve registration information for validator '
                '{}'.format(
                    originator_id))

        return registration

    def _update_validator_committed_block_count(self,
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
                    'committed_block_count': default_initial_value
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
            statistics['committed_block_count'] = default_initial_value

        # If the PoET public keys are the same, then update the block commit
        # count appropriately.
        if registration['poet-public-key'] == statistics['poet_public_key']:
            statistics['committed_block_count'] += increment_value

        # A guard to keep our statistics in the reasonable range
        if statistics['committed_block_count'] < 0:
            statistics['committed_block_count'] = 0
        elif statistics['committed_block_count'] > self._block_commit_threshold:
            statistics['committed_block_count'] = self._block_commit_threshold

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
                self._update_validator_committed_block_count(
                    journal=journal,
                    block=block,
                    increment_value=1,
                    default_initial_value=0,
                    sync_local_store=False,
                    reset_on_different_key=False)
            except ValueError, error:
                LOGGER.error('Caught Exception: %s', str(error))

        for originator, statistics in self._validator_statistics.iteritems():
            LOGGER.debug(
                'Validator with ID %s has committed %d block(s) with PoET '
                'public key %s',
                originator,
                statistics['committed_block_count'],
                statistics['poet_public_key'])

        # Sync the statistics back so they are persisted
        journal.local_store.set(
            'validator_statistics',
            self._validator_statistics)
        journal.local_store.sync()

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
        # If there are no committed blocks, we are testing the genesis block.
        # That means that no validator registration information exists and
        # therefore we cannot even hope to gather any statistics.  So, we will
        # have to just assume, for the time being, that the block is valid,
        # although other checks may determine it is invalid.
        if journal.committed_block_count != 0:
            try:
                # Retrieve the validator registry transaction information.
                # Note that we have to use the most-recently-committed block
                # as the block under test has not transaction store associated
                # with it.  Been there, done that...didn't work.  =)
                registration = \
                    PoetConsensus._retrieve_validator_registration(
                        journal=journal,
                        block_id=journal.most_recent_committed_block_id,
                        originator_id=block.OriginatorID)

                # Get the statistics, creating them if they don't already
                # exist
                statistics = \
                    self._validator_statistics.setdefault(
                        block.OriginatorID,
                        {
                            'poet_public_key': registration['poet-public-key'],
                            'committed_block_count': 0
                        })

                # If the validator has already reached commit limit for the
                # public key, then we reject the block as the validator needs
                # to get new signup information
                if (registration['poet-public-key'] ==
                        statistics['poet_public_key']) and \
                    (statistics['committed_block_count'] >=
                        self._block_commit_threshold):
                    LOGGER.error(
                        'Validator %s has reached block commit limit '
                        '(%d >= %d) with current signup information',
                        block.OriginatorID,
                        statistics['committed_block_count'],
                        self._block_commit_threshold)
                    return False

            except ValueError, error:
                LOGGER.error('Error attempting to verify block: %s', error)

        return True

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
            'Block %s has been committed by %s',
            block.Identifier,
            block.OriginatorID)

        self._update_validator_committed_block_count(
            journal=journal,
            block=block,
            increment_value=1,
            default_initial_value=0)

        statistics = self._validator_statistics[block.OriginatorID]
        LOGGER.debug(
            'After block commit, validator %s has committed %d block(s) with '
            'PoET public key %s',
            block.OriginatorID,
            statistics['committed_block_count'],
            statistics['poet_public_key'])

        # If we are the validator that committed the block, we need to see
        # if we need to get new signup information to ensure that we are
        # able to continue claiming blocks
        if journal.local_node.Identifier == block.OriginatorID:
            if statistics['committed_block_count'] >= \
                    self._block_commit_threshold:
                LOGGER.info(
                    'Validator has reached block commit threshold '
                    '(%d >= %d). We need to refresh our signup information.',
                    statistics['committed_block_count'],
                    self._block_commit_threshold)

                self._register_signup_information(journal)

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
            'Block %s has been de-committed by %s',
            block.Identifier,
            block.OriginatorID)

        # Update the statistics for this validator.  In this case, we are
        # going to assume the worst and set the default block count to the
        # threshold it turns out that we either don't have statistics for this
        # validator or de-committing the one or more blocks caused the
        # validator to temporarily revert to a previous public key.
        self._update_validator_committed_block_count(
            journal=journal,
            block=block,
            increment_value=-1,
            default_initial_value=self._block_commit_threshold)

        statistics = self._validator_statistics[block.OriginatorID]
        LOGGER.debug(
            'After block de-commit, validator %s has committed %d block(s) '
            'with PoET public key %s',
            block.OriginatorID,
            statistics['committed_block_count'],
            statistics['poet_public_key'])

        return True

    def _register_signup_information(self, journal):
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

        # initialize stats specifically for the block chain journal
        journal.JournalStats.add_metric(stats.Value('LocalMeanTime', 0))
        journal.JournalStats.add_metric(stats.Value('AggregateLocalMean', 0))
        journal.JournalStats.add_metric(stats.Value('PopulationEstimate', 0))
        journal.JournalStats.add_metric(stats.Value('ExpectedExpirationTime',
                                                    0))
        journal.JournalStats.add_metric(stats.Value('Duration', 0))

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
        journal.on_journal_restored += self._on_journal_restored

        # We want the ability to test a block before it gets committed so that
        # we can enforce PoET 1 policies
        journal.on_block_test += self._on_block_test

        # We want to know when a block is committed or decommitted so that
        # we can keep track of validator statistics
        journal.on_commit_block += self._on_commit_block
        journal.on_decommit_block += self._on_decommit_block

        # Before we allow the base journal to do anything that might result
        # in a wait timer or wait certificate being created, we have to ensure
        # the PoET enclave has been initialized.  This can be done in one of
        # two ways:
        # 1. If we have sealed signup data (meaning that we have previously
        #    created signup info), we can request that the enclave unseal it,
        #    in the process restoring the enclave to its previous state.
        # 2. Create new signup information.
        sealed_signup_data = journal.local_store.get('sealed_signup_data')

        if sealed_signup_data is not None:
            self.poet_public_key = \
                SignupInfo.unseal_signup_data(
                    validator_address=journal.local_node.signing_address(),
                    sealed_signup_data=sealed_signup_data)

            LOGGER.debug(
                'Restore signup info for %s (ID = %s, PoET public key = %s)',
                journal.local_node.Name,
                journal.local_node.Identifier,
                self.poet_public_key)
        else:
            self._register_signup_information(journal)

    def create_block(self):
        """Creates a candidate transaction block.

        Args:

        Returns:
            None
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
        # If there are no committed blocks, we are trying to claim the
        # genesis block.  That means that no validator registration
        # information exists and therefore we cannot even hope to check any
        # statistics.  So, we will have to just assume, for the time being,
        # that the we can claim the block, although other checks may determine
        # later that the block is invalid.  Can't fault us for trying,
        # though. =)
        if journal.committed_block_count != 0:
            # Before we can lay claim to the block, there are some
            # criteria that need to be met:
            # 1.  Our validator registry information needs to be on
            #     the block chain.
            # 2.  The PoET public key in said validator registry
            #     information needs to match our current PoET public
            #     key.
            # 3.  We cannot have already hit the block commit limit for
            #     our keys.
            # Failure to meet this criteria would result in death and
            # destruction if we tried to claim a block.  Okay, it is not
            # quite that dire, but other validators would refuse to commit the
            # block, our friends would shun us, our dog would run away, our
            # truck would break down, and we would be reduced to writing sad
            # country music songs for a living.

            # Retrieve the validator registry information for the most-
            # recently-committed block.  Failure to do so will indicate that
            # we cannot claim the block as we need to wait until registration
            # information is on the block chain.
            try:
                registration = \
                    PoetConsensus._retrieve_validator_registration(
                        journal=journal,
                        block_id=journal.most_recent_committed_block_id,
                        originator_id=journal.local_node.Identifier)
            except ValueError, error:
                LOGGER.error(
                    'Could not retrieve our validator registry information')
                raise

            # Make sure we will sign the wait certificate with the secret key
            # corresponding to the public key that the other validators know
            # about.
            if registration['poet-public-key'] != self.poet_public_key:
                raise \
                    ValueError(
                        "Our current PoET public key does not match the "
                        "globally-visible one.  We cannot in good conscience "
                        "waste the other validators' time, only to have them "
                        "reject the block when trying to commit it.  Our "
                        "fragile ego would not be able to handle that kind of "
                        "rejection.")

            # Get our statistics, creating them if they don't already exist (we
            # create them as this may be the first block we can claim).
            statistics = \
                self._validator_statistics.setdefault(
                    journal.local_node.Identifier,
                    {
                        'poet_public_key': self.poet_public_key,
                        'committed_block_count': 0
                    })

            # If the validator has already reached commit the limit for its
            # current public key, then we reject the block as the validator
            # should be getting new validator registration information.
            #
            # As an aside, this third check should be completely unnecessary
            # as we _should_ have detected this in the _on_commit_block
            # callback.  However, when in doubt, choose the belt and
            # suspenders approach.
            if (registration['poet-public-key'] ==
                    statistics['poet_public_key']) and \
                (statistics['committed_block_count'] >=
                    self._block_commit_threshold):
                self._register_signup_information(journal)
                raise \
                    ValueError(
                        'Validator %s has reached block commit limit '
                        '(%d >= %d) with current signup information'.format(
                            journal.local_node.Identifier,
                            statistics['committed_block_count'],
                            self._block_commit_threshold))

            # Note - we don't update our block commit statistics here.  We
            # wait until the _on_block_commit callback.  Claiming and actually
            # getting the block committed are two different things.

        # If we got this far, we are fairly confident in creating a wait
        # certificate for the block and embedding our public key.
        block.create_wait_certificate()
        block.poet_public_key = self.poet_public_key

    def create_block_message(self, block):
        msg = poet_transaction_block.PoetTransactionBlockMessage()
        msg.TransactionBlock = block
        return msg

    def build_certificate_list(self, block_store, block):
        # for the moment we just dump all of these into one list,
        # not very efficient but it makes things a lot easier to maintain
        certs = collections.deque()
        count = WaitTimer.certificate_sample_length

        while block.PreviousBlockID != common.NullIdentifier \
                and len(certs) < count:
            block = block_store[block.PreviousBlockID]
            certs.appendleft(block.wait_certificate)

        # drop the root block off the computation
        return list(certs)

    def check_claim_block(self, journal, block, now):
        return block.wait_timer_has_expired(now)

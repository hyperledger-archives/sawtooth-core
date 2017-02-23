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

import logging
import hashlib
from threading import RLock

# Disabled pylint as these packages no longer exists and will be replaced as
# PoET is integrated into the validator.
# pylint: disable=import-error
# pylint: disable=no-name-in-module
from journal import transaction_block
from journal.messages import transaction_block_message
from sawtooth_validator.consensus.poet1.validator_registry \
    import ValidatorRegistryTransaction

from sawtooth_validator.journal.consensus.poet1.wait_certificate\
    import WaitCertificate
from sawtooth_validator.journal.consensus.poet1.wait_certificate\
    import WaitTimer
from sawtooth_validator.journal.block_wrapper import NULL_BLOCK_IDENTIFIER

LOGGER = logging.getLogger(__name__)


def register_message_handlers(journal):
    """Registers transaction block message handlers with the journal.

    Args:
        journal (PoetJournal): The journal on which to register the
            message handlers.
    """
    journal.dispatcher.register_message_handler(
        PoetTransactionBlockMessage,
        transaction_block_message.transaction_block_message_handler)


class PoetTransactionBlockMessage(
        transaction_block_message.TransactionBlockMessage):
    """Represents the message format for exchanging information about blocks.

    Attributes:
        PoetTransactionBlockMessage.MessageType (str): The class name of
            the message.
    """
    MessageType = "/Poet1/TransactionBlock"

    def __init__(self, minfo=None):
        if minfo is None:
            minfo = {}
        super(PoetTransactionBlockMessage, self).__init__(minfo)

        tinfo = minfo.get('TransactionBlock', {})
        self.transaction_block = PoetTransactionBlock(tinfo)


class PoetTransactionBlock(transaction_block.TransactionBlock):
    """A set of transactions to be applied to a ledger, and proof of wait data.

    Attributes:
        PoetTransactionBlock.TransactionBlockTypeName (str): The name of the
            transaction block type.
        PoetTransactionBlock.MessageType (type): The message class.
        wait_timer (wait_timer.WaitTimer): The wait timer for the block.
        wait_certificate (wait_certificate.WaitCertificate): The wait
            certificate for the block.
    """
    TransactionBlockTypeName = '/Poet/PoetTransactionBlock'
    MessageType = PoetTransactionBlockMessage

    def __init__(self, minfo=None):
        """Constructor for the PoetTransactionBlock class.

        Args:
            minfo (dict): A dict of values for initializing
                PoetTransactionBlocks.
        """
        if minfo is None:
            minfo = {}
        super(PoetTransactionBlock, self).__init__(minfo)

        self._lock = RLock()
        self.wait_timer = None
        self.wait_certificate = None
        self.poet_public_key = minfo.get('PoetPublicKey')

        if 'WaitCertificate' in minfo:
            wc = minfo.get('WaitCertificate')
            serialized_certificate = wc.get('SerializedCertificate')
            signature = wc.get('Signature')

            self.wait_certificate = \
                WaitCertificate.wait_certificate_from_serialized(
                    serialized=serialized_certificate,
                    signature=signature)

        self.aggregate_local_mean = 0.0

    def __getstate__(self):
        state = self.__dict__.copy()
        del state['_lock']
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        self._lock = RLock()

    def __str__(self):
        return "{0}, {1}, {2}, {3:0.2f}, {4}".format(
            self.BlockNum, self.Identifier[:8], len(self.TransactionIDs),
            self.CommitTime, self.wait_certificate)

    def __cmp__(self, other):
        """
        Compare two blocks, this will throw an error unless
        both blocks are valid.
        """

        if self.Status != transaction_block.Status.valid:
            raise ValueError('block {0} must be valid for comparison'.format(
                self.Identifier))

        if other.Status != transaction_block.Status.valid:
            raise ValueError('block {0} must be valid for comparison'.format(
                other.Identifier))

        # Criteria #1: if both blocks share the same previous block,
        # then the block with the smallest duration wins
        if self.PreviousBlockID == other.PreviousBlockID:
            if self.wait_certificate.duration < \
                    other.wait_certificate.duration:
                return 1
            elif self.wait_certificate.duration > \
                    other.wait_certificate.duration:
                return -1
        # Criteria #2: if there is a difference between the immediate
        # ancestors then pick the chain with the highest aggregate
        # local mean, this will be the largest population (more or less)
        else:
            if self.aggregate_local_mean > other.aggregate_local_mean:
                return 1
            elif self.aggregate_local_mean < other.aggregate_local_mean:
                return -1
        # Criteria #3... use number of transactions as a tie breaker, this
        # should not happen except in very rare cases
        return super(PoetTransactionBlock, self).__cmp__(other)

    def update_block_weight(self, journal):
        with self._lock:
            assert self.Status == transaction_block.Status.valid
            super(PoetTransactionBlock, self).update_block_weight(journal)

            assert self.wait_certificate
            self.aggregate_local_mean = self.wait_certificate.local_mean

            if self.PreviousBlockID != NULL_BLOCK_IDENTIFIER:
                assert self.PreviousBlockID in journal.block_store
                self.aggregate_local_mean += \
                    journal.block_store[self.PreviousBlockID].\
                    aggregate_local_mean
            else:
                self.aggregate_local_mean = self.wait_certificate.local_mean

    def is_valid(self, journal):
        """Verifies that the block received is valid.

        This includes checks for valid signature and a valid
        WaitCertificate.

        Args:
            journal (PoetJournal): Journal for pulling context.
        """
        with self._lock:
            if not super(PoetTransactionBlock, self).is_valid(journal):
                return False

            if not self.wait_certificate:
                LOGGER.info('not a valid block, no wait certificate')
                return False

            # We need to get the PoET public key for the originator
            # of the transaction block.  To do that, we first need to get
            # the store for validator signup information.  Then from that
            # we can do an indexed search for the registration entry and
            # therefore the PoET public key.
            poet_public_key = None

            # First we need to get the store for validator signup information
            store = \
                journal.get_transaction_store(
                    family=ValidatorRegistryTransaction,
                    block_id=self.PreviousBlockID)
            if store is None:
                LOGGER.error(
                    'Unable to retrieve %s store for block_id=%s',
                    ValidatorRegistryTransaction.TransactionTypeName,
                    self.PreviousBlockID)
                return False

            try:
                registration = store.get(self.OriginatorID)
                poet_public_key = registration.get('poet-public-key')
            except KeyError:
                if len(journal.committed_block_ids()) == 0:
                    LOGGER.info('processing seed block')
                    if len(store.keys()) != 0:
                        LOGGER.info('validator registry already seeded')
                        return False
                    poet_public_key = self.poet_public_key
                else:
                    LOGGER.info(
                        'Cannot validate wait certificate because cannot '
                        'retrieve PoET public key for validator with ID=%s',
                        self.OriginatorID)
                    return False

            if poet_public_key is None:
                LOGGER.warning('PoET public key is invalid')
                return False

            LOGGER.debug(
                'Validator ID %s <==> PoET Public Key %s',
                self.OriginatorID,
                poet_public_key)

            try:
                self.wait_certificate.check_valid(
                    certificates=journal.consensus.build_certificate_list(
                        journal.block_store, self),
                    poet_public_key=poet_public_key)
            except (ValueError, TypeError) as err:
                LOGGER.error('Wait certificate is not valid: %s', err)
                return False

        return True

    def create_wait_timer(self, validator_address, certlist):
        """Creates a wait timer for the journal based on a list
        of wait certificates.

        Args:
            validator_address (str): The address of the validator that is
                creating the wait timer.
            certlist (list): A list of wait certificates.
        """
        with self._lock:
            self.wait_timer = \
                WaitTimer.create_wait_timer(
                    validator_address=validator_address,
                    certificates=certlist)

    def create_wait_certificate(self):
        """Create a wait certificate for the journal based on the wait timer.
        """
        with self._lock:
            LOGGER.debug("WAIT_TIMER: %s", str(self.wait_timer))
            hasher = hashlib.sha256()
            for tid in self.TransactionIDs:
                hasher.update(tid.encode())
            block_digest = hasher.hexdigest()

            self.wait_certificate = \
                WaitCertificate.create_wait_certificate(
                    wait_timer=self.wait_timer,
                    block_digest=block_digest)
            if self.wait_certificate:
                self.wait_timer = None

    def wait_timer_has_expired(self, now):
        """Determines if the wait timer has expired.

        Returns:
            bool: Whether or not the wait timer has expired.
        """
        with self._lock:
            return self.wait_timer.has_expired(now)

    def dump(self):
        """Returns a dict with information about the block.

        Returns:
            dict: A dict containing information about the block.
        """
        with self._lock:
            result = super(PoetTransactionBlock, self).dump()
            result['WaitCertificate'] = self.wait_certificate.dump()
            result['PoetPublicKey'] = self.poet_public_key

            return result

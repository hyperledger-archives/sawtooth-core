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

from journal import transaction_block
from journal.messages import transaction_block_message
from journal.consensus.poet.wait_certificate import WaitCertificate, WaitTimer

logger = logging.getLogger(__name__)


def register_message_handlers(journal):
    """Registers poet transaction block message handlers with
    the journal.

    Args:
        journal (PoetJournal): The journal on which to register the
            message handlers.
    """
    journal.register_message_handler(
        PoetTransactionBlockMessage,
        transaction_block_message.transaction_block_message_handler)


class PoetTransactionBlockMessage(
        transaction_block_message.TransactionBlockMessage):
    """Poet transaction block messages represent the message format
    for exchanging information about poet transaction blocks.

    Attributes:
        PoetTransactionBlockMessage.MessageType (str): The class name of
            the message.
    """
    MessageType = \
        "/journal.consensus.poet.PoetTransactionBlock/TransactionBlock"

    def __init__(self, minfo={}):
        super(PoetTransactionBlockMessage, self).__init__(minfo)

        tinfo = minfo.get('TransactionBlock', {})
        self.TransactionBlock = PoetTransactionBlock(tinfo)


class PoetTransactionBlock(transaction_block.TransactionBlock):
    """A poet transaction block is a set of poet transactions to
    be applied to a ledger.

    Attributes:
        PoetTransactionBlock.TransactionBlockTypeName (str): The name of the
            transaction block type.
        PoetTransactionBlock.MessageType (type): The poet transaction block
            message class.
        PoetTransactionBlock.WaitTimer \
            (journal.consensus.poet.wait_timer.WaitTimer): The wait timer
            for the block.
        PoetTransactionBlock.WaitCertificate (wait_certificateWaitCertificate):
            The wait certificate for the block.
    """
    TransactionBlockTypeName = '/Lottery/PoetTransactionBlock'
    MessageType = PoetTransactionBlockMessage

    def __init__(self, minfo={}):
        """Constructor for the PoetTransactionBlock class.

        Args:
            minfo (dict): A dict of values for initializing
                PoetTransactionBlocks.
        """
        super(PoetTransactionBlock, self).__init__(minfo)

        self.WaitTimer = None
        self.WaitCertificate = None

        if 'WaitCertificate' in minfo:
            wc = minfo.get('WaitCertificate')
            serialized = wc.get('SerializedCert')
            signature = wc.get('Signature')
            self.WaitCertificate = \
                WaitCertificate.deserialize_wait_certificate(
                    serialized, signature)

    def __str__(self):
        return "{0}, {1}, {2}, {3:0.2f}, {4}".format(
            self.BlockNum, self.Identifier[:8], len(self.TransactionIDs),
            self.CommitTime, self.WaitCertificate)

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

        if self.TransactionDepth < other.TransactionDepth:
            return -1
        elif self.TransactionDepth > other.TransactionDepth:
            return 1
        else:
            return cmp(self.Identifier, other.Identifier)

    def is_valid(self, journal):
        """Verifies that the block received is valid.

        This includes checks for valid signature and a valid
        waitcertificate.

        Args:
            journal (PoetJorunal): Journal for pulling context.
        """
        if not super(PoetTransactionBlock, self).is_valid(journal):
            return False

        if not self.WaitCertificate:
            logger.info('not a valid block, no wait certificate')
            return False

        return self.WaitCertificate.is_valid_wait_certificate(
            self.OriginatorID,
            journal._build_certificate_list(self),
            self.TransactionIDs)

    def create_wait_timer(self, validator_address, certlist):
        """Creates a wait timer for the journal based on a list
        of wait certificates.

        Args:
            certlist (list): A list of wait certificates.
        """

        self.WaitTimer = WaitTimer.create_wait_timer(
            validator_address,
            certlist)

    def create_wait_certificate(self):
        """Create a wait certificate for the journal based on the
        wait timer.
        """
        hasher = hashlib.sha256()
        for tid in self.TransactionIDs:
            hasher.update(tid)
        block_hash = hasher.hexdigest()

        self.WaitCertificate = WaitCertificate.create_wait_certificate(
            self.WaitTimer,
            block_hash)
        if self.WaitCertificate:
            self.WaitTimer = None

    def wait_timer_is_expired(self, now):
        """Determines if the wait timer is expired.

        Returns:
            bool: Whether or not the wait timer is expired.
        """
        return self.WaitTimer.is_expired(now)

    def dump(self):
        """Returns a dict with information about the poet transaction
        block.

        Returns:
            dict: A dict containing information about the poet
                transaction block.
        """
        result = super(PoetTransactionBlock, self).dump()
        result['WaitCertificate'] = self.WaitCertificate.dump()

        return result

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

from gossip import message

logger = logging.getLogger(__name__)


def register_message_handlers(journal):
    """Registers the message handlers which are triggered when
    quorum ballot messages arrive.

    Args:
        journal (QuorumJournal): The journal to register the message
            handlers against.
    """
    journal.register_message_handler(QuorumBallotMessage,
                                     quorum_ballot_handler)
    journal.register_message_handler(QuorumInitiateVoteMessage,
                                     quorum_initiate_vote_handler)
    journal.register_message_handler(QuorumCompleteVoteMessage,
                                     quorum_complete_vote_handler)


class QuorumBallotMessage(message.Message):
    """Quorum ballot message represent the message format for
    exchanging quorum ballots.

    Attributes:
        MessageType (str): The class name of the message.
        IsSystemMessage (bool): Whether or not this message is a
            system message.
        IsForward (bool): Whether or not this message is forwarded.
        IsReliable (bool): Whether or not this message should use
            reliable delivery.
        Ballot (int): The ballot number.
        BlockNumber (int): The block number.
        TransactionIDs (list): The list of transactions to appear on
            the ballot.
    """
    MessageType = \
        "/journal.consensus.quorum.messages.QuorumBallot/Quorum/Ballot"

    def __init__(self, minfo={}):
        """Constructor for QuorumBallotMessage.

        Args:
            minfo (dict): A dict containing initial values for the
                new QuorumBallotMessages.
        """
        super(QuorumBallotMessage, self).__init__(minfo)

        self.IsSystemMessage = False
        self.IsForward = True
        self.IsReliable = True

        self.Ballot = minfo.get('Ballot', 0)
        self.BlockNumber = minfo.get('BlockNumber', 0)

        self.TransactionIDs = []
        if 'TransactionIDs' in minfo:
            for txnid in minfo['TransactionIDs']:
                self.TransactionIDs.append(str(txnid))

    def dump(self):
        """Returns a dict containing information about the quorum
        ballot message.

        Returns:
            dict: A dict containing information about the quorum
               ballot message.
        """
        result = super(QuorumBallotMessage, self).dump()

        result['Ballot'] = self.Ballot
        result['BlockNumber'] = self.BlockNumber

        result['TransactionIDs'] = []
        for txnid in self.TransactionIDs:
            result['TransactionIDs'].append(str(txnid))

        return result


def quorum_ballot_handler(msg, journal):
    """Function called when the journal receives a
    QuorumBallotMessage from one of its peers.

    Args:
        msg (QuorumBallotMessage): The received quorum ballot message.
        journal (QuorumJournal): The journal which received the message.
    """
    logger.info("unhandled quorum ballot message received from %s",
                journal._id2name(msg.OriginatorID))


class QuorumInitiateVoteMessage(message.Message):
    """Quorum initiate vote messages represent the message format for
    exchanging quorum advertisements.

    Attributes:
        MessageType (str): The class name of the message.
        IsSystemMessage (bool): Whether or not this message is a system
            message.
        IsForward (bool): Whether this message is forwarded.
        IsReliable (bool): Whether or not this message should use
            reliable delivery.
        BlockNumber (int): The number of the block.
    """
    MessageType = \
        "/journal.consensus.quorum.messages.QuorumBallot/Quorum/InitiateVote"

    def __init__(self, minfo={}):
        """Constructor for QuorumInitiateVoteMessage.

        Args:
            minfo (dict): A dict containing initial values for
                the new QuorumInitiateVoteMessage.
        """
        super(QuorumInitiateVoteMessage, self).__init__(minfo)

        self.IsSystemMessage = False
        self.IsForward = False
        self.IsReliable = True

        self.BlockNumber = minfo.get('BlockNumber', 0)

    def dump(self):
        result = super(QuorumInitiateVoteMessage, self).dump()
        result['BlockNumber'] = self.BlockNumber

        return result


def quorum_initiate_vote_handler(msg, journal):
    """Function called when the journal receives a
    QuorumInitiateVoteMessage from one of its peers.

    Args:
        msg (QuorumInitiateVoteMessage): The received quorum initiate
            vote message.
        journal (QuorumJournal): The journal which received the
            message.
    """
    logger.debug("quorum initiation request received from %s",
                 journal._id2name(msg.OriginatorID))

    if journal.handle_vote_initiation(msg.BlockNumber):
        journal.forward_message(msg,
                                exceptions=[msg.SenderID],
                                initialize=False)


class QuorumCompleteVoteMessage(message.Message):
    """Quorum complete vote messages represent the message format
    for exchanging information between peers when voting has completed.

    Attributes:
        MessageType (str): The class name of the message.
        IsSystemMessage (bool): Whether or not this message is
            a system message.
        IsForward (bool): Whether or not this message is forwarded.
        IsReliable (bool): Whether or not this message should
            use reliable delivery.
        BlockNumber (int): The block number.
        TransactionIDs (list): The list of transactions which are
            a part of the vote.
    """
    MessageType = \
        "/journal.consensus.quorum.messages.QuorumBallot/Quorum/CompleteVote"

    def __init__(self, minfo={}):
        """Constructor for QuorumCompleteVoteMessage.

        Args:
            minfo (dict): A dict containing initial values for the
                new QuorumCompleteVoteMessage.
        """
        super(QuorumCompleteVoteMessage, self).__init__(minfo)

        self.IsSystemMessage = False
        self.IsForward = False
        self.IsReliable = True

        self.BlockNumber = minfo.get('BlockNumber', 0)

        self.TransactionIDs = []
        if 'TransactionIDs' in minfo:
            for txnid in minfo['TransactionIDs']:
                self.TransactionIDs.append(str(txnid))

    def dump(self):
        """Returns a dict containing information about the quorum
        complete vote message.

        Returns:
            dict: A dict containing information about the quorum
                complete vote message.
        """
        result = super(QuorumCompleteVoteMessage, self).dump()
        result['BlockNumber'] = self.BlockNumber

        result['TransactionIDs'] = []
        for txnid in self.TransactionIDs:
            result['TransactionIDs'].append(str(txnid))

        return result


def quorum_complete_vote_handler(msg, journal):
    """Function called when the journal receives a
    QuorumCompleteVoteMessage from one of its peers.
    """
    logger.debug("quorum initiation request received from %s",
                 journal._id2name(msg.OriginatorID))

    if journal.complete_vote(msg.BlockNumber, msg.TransactionIDs):
        journal.forward_message(msg,
                                exceptions=[msg.SenderID],
                                initialize=False)

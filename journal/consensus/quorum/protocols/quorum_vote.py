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
from collections import OrderedDict

from journal.consensus.quorum.messages import quorum_ballot

logger = logging.getLogger(__name__)


class QuorumBallot(object):
    """Represents a voting ballot in the quorum consensus mechanism.

    Attributes:
        Votes (dict): An orderd dict of votes.
    """
    def __init__(self):
        """Constructor for the QuorumBallot class.
        """
        self.Votes = OrderedDict()

    def vote(self, validatorID, txnID):
        """Adds a vote.

        Args:
            validatorID (str): The id of a remote node.
            txnID (str): The id of a transaction that is being voted
                for.
        """
        if txnID not in self.Votes:
            self.Votes[txnID] = set()

        self.Votes[txnID].add(validatorID)

    def count_votes(self, threshhold):
        """Identifies transactions above a voting threshold.

        Args:
            threshold (int): The number of votes required to win.

        Returns:
            list: A list of transaction ids that won the vote.
        """
        txnlist = []
        for txnID, votes in self.Votes.iteritems():
            if len(votes) > threshhold:
                txnlist.append(txnID)

        return txnlist


class QuorumVote(object):
    """Represents the voting process in the quorum consensus mechanism.

    Attributes:
        VotingLedger (QuorumJournal): The ledger on which the voting is
            taking place.
        ValidatorID (str): The identifier of the local node.
        VotingQuorum (list): A list of node identifiers participating in
            the vote.
        Threshholds (list): A list of voting threshholds.
        BlockNumber (int): The block number.
        Ballot (int): The ballot number.
        LastBallot (int): The id of the previous ballot.
        QuorumVote (list): A list of ballots.
        OldBallotMessageHandler (EventHandler): The EventHandler tracking
            calls to make when ballot messages are received.
        OldCompleteMessageHandler (EventHandler): The EventHandler tracking
            calls to make when quorum complete vote messages are
            received.
    """
    def __init__(self, vledger, blocknum, txnlist):
        """Construtor for the QuorumVote class.

        Args:
            vledger (QuorumJournal): The journal on which the voting is
                taking place.
            blocknum (int): The block number.
            txnlist (list): A list of transactions to vote on.
        """
        self.VotingLedger = vledger
        self.ValidatorID = vledger.LocalNode.Identifier
        self.VotingQuorum = vledger.VotingQuorum
        self.Threshholds = vledger.VoteThreshholds
        self.BlockNumber = blocknum

        self.Ballot = 0
        self.LastBallot = len(self.Threshholds)
        self.QuorumVote = [QuorumBallot() for x in range(self.LastBallot)]

        for txnid in txnlist:
            self.QuorumVote[self.Ballot].vote(self.ValidatorID, txnid)

        self.OldBallotMessageHandler = self.VotingLedger.get_message_handler(
            quorum_ballot.QuorumBallotMessage)
        self.VotingLedger.register_message_handler(
            quorum_ballot.QuorumBallotMessage,
            self.quorum_ballot_handler)

        self.OldCompleteMessageHandler = self.VotingLedger.get_message_handler(
            quorum_ballot.QuorumCompleteVoteMessage)
        self.VotingLedger.register_message_handler(
            quorum_ballot.QuorumCompleteVoteMessage,
            self.quorum_complete_vote_handler)

    def close_current_ballot(self):
        """Stops accepting further votes for this ballot and move to
        the next one.

        If this is the last ballot then close the vote completely.
        """
        threshhold = self.Threshholds[self.Ballot] * len(self.VotingQuorum)
        txnlist = self.QuorumVote[self.Ballot].count_votes(threshhold)

        self.Ballot += 1
        if self.Ballot == self.LastBallot:
            self.close_vote(txnlist)
            return

        # send our vote
        msg = quorum_ballot.QuorumBallotMessage()
        msg.Ballot = self.Ballot
        msg.BlockNumber = self.BlockNumber
        msg.TransactionIDs = txnlist
        msg.sign_from_node(self.VotingLedger.LocalNode)

        self.VotingLedger.broadcast_message(msg)

    def quorum_ballot_handler(self, msg, vledger):
        """Function called when the vledger receives a
        QuorumBallotMessage from one of its peers.
        """
        sname = self.VotingLedger._id2name(msg.OriginatorID)

        if msg.OriginatorID not in self.VotingQuorum:
            logger.debug('received votes from %s, not in our quorum set',
                         sname)
            return

        if msg.BlockNumber != self.BlockNumber:
            logger.info('received votes from %s for block %d, expecting %d',
                        sname, msg.BlockNumber, self.BlockNumber)
            return

        if msg.Ballot < self.Ballot or self.LastBallot <= msg.Ballot:
            logger.info(
                'received votes from %s for ballot %d, currently '
                'processing %d',
                sname, msg.Ballot, self.Ballot)
            return

        logger.debug('add votes from %s to ballot %d', sname, self.Ballot)
        for txnid in msg.TransactionIDs:
            self.QuorumVote[msg.Ballot].vote(msg.OriginatorID, txnid)

    def quorum_complete_vote_handler(self, msg, vledger):
        pass

    def close_vote(self, txnlist):
        """The last ballot has been closed so all voting is complete.

        The only transactions left should be those voted by the
        largest value in the threshhold array.
        """
        # don't process any more vote messages
        self.VotingLedger.register_message_handler(
            quorum_ballot.QuorumBallotMessage,
            self.OldBallotMessageHandler)
        self.VotingLedger.register_message_handler(
            quorum_ballot.QuorumCompleteVoteMessage,
            self.OldCompleteMessageHandler)

        self.VotingLedger.complete_vote(self.BlockNumber, txnlist)

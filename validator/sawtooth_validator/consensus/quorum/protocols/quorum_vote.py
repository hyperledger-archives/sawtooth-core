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

from sawtooth_validator.consensus.quorum.messages import quorum_ballot
from ledger.transaction.endpoint_registry import \
    EndpointRegistryTransactionMessage

LOGGER = logging.getLogger(__name__)


class QuorumBallot(object):
    """Represents a voting ballot in the quorum consensus mechanism.

    Attributes:
        votes (dict): An orderd dict of votes.
    """
    def __init__(self):
        """Constructor for the QuorumBallot class.
        """
        self.votes = OrderedDict()

    def vote(self, validator_id, txn_id):
        """Adds a vote.

        Args:
            validator_id (str): The id of a remote node.
            txn_id (str): The id of a transaction that is being voted
                for.
        """
        if txn_id not in self.votes:
            self.votes[txn_id] = set()

        self.votes[txn_id].add(validator_id)

    def count_votes(self, threshhold):
        """Identifies transactions above a voting threshold.

        Args:
            threshold (int): The number of votes required to win.

        Returns:
            list: A list of transaction ids that won the vote.
        """
        txnlist = []
        for txn_id, votes in self.votes.iteritems():
            if len(votes) > threshhold:
                txnlist.append(txn_id)

        return txnlist


class QuorumVote(object):
    """Represents the voting process in the quorum consensus mechanism.

    Attributes:
        voting_ledger (QuorumJournal): The ledger on which the voting is
            taking place.
        validator_id (str): The identifier of the local node.
        voting_quorum (list): A list of node identifiers participating in
            the vote.
        threshholds (list): A list of voting threshholds.
        block_number (int): The block number.
        ballot (int): The ballot number.
        last_ballot (int): The id of the previous ballot.
        quorum_vote (list): A list of ballots.
        old_ballot_message_handler (EventHandler): The EventHandler tracking
            calls to make when ballot messages are received.
        old_complete_message_handler (EventHandler): The EventHandler tracking
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
        self.voting_ledger = vledger
        self.validator_id = vledger.LocalNode.Identifier
        self.voting_quorum = vledger.VotingQuorum
        self.threshholds = vledger.VoteThreshholds
        self.block_number = blocknum

        self.ballot = 0
        self.last_ballot = len(self.threshholds)
        self.quorum_vote = [QuorumBallot() for _ in range(self.last_ballot)]

        for txnid in txnlist:
            nd = vledger.LocalNode
            txn = vledger.TransactionStore[txnid]
            if (txn.TransactionTypeName == '/EndpointRegistryTransaction' and
                    nd.Identifier == txn.Update.NodeIdentifier):
                LOGGER.debug('validator broadcasting self-promotion %s', txnid)
                msg = EndpointRegistryTransactionMessage()
                msg.Transaction = txn
                msg.SenderID = str(nd.Identifier)
                msg.sign_from_node(nd)
                vledger.forward_message(msg)
            self.quorum_vote[self.ballot].vote(self.validator_id, txnid)
        LOGGER.debug('txnlist: %s', txnlist)

        self.old_ballot_message_handler = self.voting_ledger.\
            get_message_handler(quorum_ballot.QuorumBallotMessage)
        self.voting_ledger.register_message_handler(
            quorum_ballot.QuorumBallotMessage,
            self.quorum_ballot_handler)

        self.old_complete_message_handler = self.voting_ledger.\
            get_message_handler(quorum_ballot.QuorumCompleteVoteMessage)
        self.voting_ledger.register_message_handler(
            quorum_ballot.QuorumCompleteVoteMessage,
            self.quorum_complete_vote_handler)

    def close_current_ballot(self):
        """Stops accepting further votes for this ballot and move to
        the next one.

        If this is the last ballot then close the vote completely.
        """
        threshhold = self.threshholds[self.ballot] * len(self.voting_quorum)
        txnlist = self.quorum_vote[self.ballot].count_votes(threshhold)

        self.ballot += 1
        if self.ballot == self.last_ballot:
            self.close_vote(txnlist)
            return

        # send our vote
        msg = quorum_ballot.QuorumBallotMessage()
        msg.Ballot = self.ballot
        msg.BlockNumber = self.block_number
        msg.TransactionIDs = txnlist
        msg.sign_from_node(self.voting_ledger.LocalNode)

        self.voting_ledger.broadcast_message(msg)

    def quorum_ballot_handler(self, msg, vledger):
        """Function called when the vledger receives a
        QuorumBallotMessage from one of its peers.
        """
        sname = self.voting_ledger.gossip.node_id_to_name(msg.OriginatorID)

        if msg.OriginatorID not in self.voting_quorum:
            LOGGER.debug('received votes from %s, not in our quorum set',
                         sname)
            return

        if msg.BlockNumber != self.block_number:
            LOGGER.info('received votes from %s for block %d, expecting %d',
                        sname, msg.BlockNumber, self.block_number)
            return

        if msg.Ballot < self.ballot or self.last_ballot <= msg.Ballot:
            LOGGER.info(
                'received votes from %s for ballot %d, currently '
                'processing %d',
                sname, msg.Ballot, self.ballot)
            return

        LOGGER.debug('add votes from %s to ballot %d', sname, self.ballot)
        for txnid in msg.TransactionIDs:
            self.quorum_vote[msg.Ballot].vote(msg.OriginatorID, txnid)

    def quorum_complete_vote_handler(self, msg, vledger):
        pass

    def close_vote(self, txnlist):
        """The last ballot has been closed so all voting is complete.

        The only transactions left should be those voted by the
        largest value in the threshhold array.
        """
        # don't process any more vote messages
        self.voting_ledger.register_message_handler(
            quorum_ballot.QuorumBallotMessage,
            self.old_ballot_message_handler)
        self.voting_ledger.register_message_handler(
            quorum_ballot.QuorumCompleteVoteMessage,
            self.old_complete_message_handler)

        self.voting_ledger.complete_vote(self.block_number, txnlist)

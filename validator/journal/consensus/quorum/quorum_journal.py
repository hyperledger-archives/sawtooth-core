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
import random
import time
import socket

from gossip import common
from gossip import node
from journal.consensus.quorum import quorum_transaction_block
from journal.consensus.quorum.messages import quorum_debug
from journal.consensus.quorum.messages import quorum_ballot
from journal.consensus.quorum.protocols import quorum_vote
from journal.journal_core import Journal

logger = logging.getLogger(__name__)


class QuorumJournal(Journal):
    """Implements a journal based on participant voting.

    Attributes:
        VoteTimeInterval (float): The minimum time between votes, in
            seconds.
        VoteTimeFudgeFactor (float): The average fudge factor added to
            the vote interval, in seconds.  Used in conjunction with
            randomization functions to stagger network initiative.
        BallotTimeInterval (float): The minimum time between ballots on
            a vote, in seconds.
        BallotTimeFudgeFactor (float): The average fudge factor added
            to the ballot interval, in seconds.  Used in conjunction with
            randomization functions to stagger network initiative.
        VoteThreshholds (list): The minimum votes required for a
            transaction to proceed to the next ballot.
        VotingQuorumTargetSize (int): The target size for the local
            quorum set (note: this should be a function of network size).
        VotingQuorum (dict): The nodes in the quorum.
        CurrentQuorumVote (QuorumVote): The vote in progress.
        NextVoteTime (float): When the next vote will occur.
        NextBallotTime (float): When the next ballot will occur.
        onHeartBeatTimer (EventHandler): The EventHandler tracking calls
            to make when the heartbeat timer fires.
    """
    def __init__(self,
                 local_node,
                 gossip,
                 gossip_dispatcher,
                 stat_domains,
                 minimum_transactions_per_block=None,
                 max_transactions_per_block=None,
                 max_txn_age=None,
                 genesis_ledger=None,
                 data_directory=None,
                 store_type=None,
                 vote_time_interval=None,
                 ballot_time_interval=None,
                 voting_quorum_target_size=None):
        """Constructor for the QuorumJournal class.

        Args:
            nd (Node): The local node.
        """

        super(QuorumJournal, self).__init__(
            local_node,
            gossip,
            gossip_dispatcher,
            stat_domains,
            minimum_transactions_per_block,
            max_transactions_per_block,
            max_txn_age,
            genesis_ledger,
            data_directory,
            store_type)

        # minimum time between votes
        if vote_time_interval is not None:
            self.VoteTimeInterval = vote_time_interval
        else:
            self.VoteTimeInterval = 30.0

        # average fudge factor added to the vote interval
        self.VoteTimeFudgeFactor = 1.0

        # minimum time between ballots on a vote
        if ballot_time_interval is not None:
            self.BallotTimeInterval = ballot_time_interval
        else:
            self.BallotTimeInterval = 5.0

        # average fudge factor added to the time interval
        self.BallotTimeFudgeFactor = 0.1

        # minimum votes required for a txn to proceed to the next ballot
        self.VoteThreshholds = [0.0, 0.5, 0.7, 0.9]

        # target size for local quorum set, note this should be a function of
        # network size
        if voting_quorum_target_size is not None:
            self.VotingQuorumTargetSize = voting_quorum_target_size
        else:
            self.VotingQuorumTargetSize = 13

        self.QuorumMap = dict()
        self.VotingQuorum = dict()
        # we are always a member of our own quorum
        self.VotingQuorum[self.local_node.Identifier] = \
            self.local_node

        self.CurrentQuorumVote = None
        self.NextVoteTime = self._nextvotetime()
        self.NextBallotTime = 0

        self.dispatcher.on_heartbeat += self._triggervote

        quorum_ballot.register_message_handlers(self)
        quorum_debug.register_message_handlers(self)
        quorum_transaction_block.register_message_handlers(self)

    def initialize_quorum_map(self, quorum, nodes):
        q = quorum
        if self.local_node.Name not in q:
            logger.fatal("node must be in its own quorum")
            self.shutdown()
            return
        if len(q) < self.VotingQuorumTargetSize:
            logger.fatal('insufficient quorum configuration; need %s but " \
                         "specified %s', len(q), self.VotingQuorumTargetSize)
            self.shutdown()
            return
        self.QuorumMap = {}
        for nd_dict in nodes:
            if nd_dict["NodeName"] in q:
                addr = (socket.gethostbyname(nd_dict["Host"]), nd_dict["Port"])
                nd = node.Node(address=addr,
                               identifier=nd_dict["Identifier"],
                               name=nd_dict["NodeName"])
                nd.HttpPort = nd_dict["HttpPort"]
                self.QuorumMap[nd_dict["NodeName"]] = nd

    #
    # GENERAL JOURNAL API
    #

    def build_transaction_block(self, force=False):
        """Builds the next transaction block for the journal.

        Note:
            For the voting journal this operation is meaningful only
            for the initial block. All other blocks are created after
            voting completes.

        Args:
            force (boolean): Force creation of the initial block.

        Returns:
            QuorumTransactionBlock: The created transaction block.
        """

        logger.debug('build transaction block')

        if force:
            block = quorum_transaction_block.QuorumTransactionBlock()
            block.BlockNumber = 0
            block.sign_from_node(self.local_node)
            return block

        return None

    def handle_fork(self, tblock):
        """Handle the case where we are attempting to commit a block
        that is not connected to the current block chain. This is a
        no-op for the QuorumJournal.

        Args:
            tblock (QuorumTransactionBlock): The block to commit.
        """
        logger.info(
            'received a forked block %s from %s with previous id %s, '
            'expecting %s',
            tblock.Identifier[:8], self._id2name(tblock.OriginatorID),
            tblock.PreviousBlockID[:8], self.MostRecentCommittedBlockID[:8])

    #
    # CUSTOM JOURNAL API
    #

    def add_quorum_node(self, nd):
        """Adds a node to this node's quorum set.

        Args:
            nd (Node): The node to add to the quorum set.
        """
        logger.info('attempt to add quorum voting node %s to %s', str(nd),
                    str(self.local_node))

        if nd.Identifier in self.VotingQuorum:
            logger.info('attempt to add duplicate node to quorum')
            return

        logger.info('add node %s to voting quorum as %s', nd.Name,
                    nd.Identifier)
        self.VotingQuorum[nd.Identifier] = nd

    def initiate_vote(self):
        """Initiates a new vote.

        This method is called when the vote timer expires indicating
        that a new vote should be initiated.
        """
        logger.info('quorum, initiate, %s',
                    self.MostRecentCommittedBlockID[:8])

        # check alleged connectivity
        if not self._connected():
            self.NextVoteTime = self._nextvotetime()
            self.NextBallotTime = 0
            return

        # check that we have enough transactions
        txnlist = self._preparetransactionlist(
            maxcount=self.MaximumTransactionsPerBlock)
        if len(txnlist) < self.MinimumTransactionsPerBlock:
            logger.debug('insufficient transactions for vote; %d out of %d',
                         len(txnlist), self.MinimumTransactionsPerBlock)
            self.NextVoteTime = self._nextvotetime()
            self.NextBallotTime = 0
            return

        # we are initiating the vote, send the message to the world
        newblocknum = self.MostRecentCommittedBlock.BlockNumber + 1
        msg = quorum_ballot.QuorumInitiateVoteMessage()
        msg.BlockNumber = newblocknum
        self.forward_message(msg)

        # and get our own process rolling
        self.handle_vote_initiation(newblocknum)

    def handle_vote_initiation(self, blocknum):
        """Handles an incoming VoteInitiation message.

        Args:
            blocknum (int): The block number for the proposed vote.

        Returns:
            bool: True if this is a new, valid vote, false otherwise.
        """
        if not self._connected():
            return False
        if self.MostRecentCommittedBlockID == common.NullIdentifier:
            logger.warn('self.MostRecentCommittedBlockID is %s',
                        self.MostRecentCommittedBlockID)
            return False

        if blocknum != self.MostRecentCommittedBlock.BlockNumber + 1:
            logger.warn(
                'attempt initiate vote on block %d, expecting block %d',
                blocknum, self.MostRecentCommittedBlock.BlockNumber + 1)
            return False

        if self.CurrentQuorumVote:
            logger.debug(
                'received request to start a vote already in progress')
            return False

        logger.info('quorum, handle initiate, %s',
                    self.MostRecentCommittedBlockID[:8])

        txnlist = self._preparetransactionlist(
            maxcount=self.MaximumTransactionsPerBlock)
        self.CurrentQuorumVote = quorum_vote.QuorumVote(self, blocknum,
                                                        txnlist)
        self.NextVoteTime = 0
        self.NextBallotTime = self._nextballottime()

        return True

    def close_current_ballot(self):
        """Closes the current ballot.

        This method is called when the timer indicates that the vote for a
        particular ballot is complete.
        """
        logger.info('quorum, ballot, %s, %d',
                    self.MostRecentCommittedBlockID[:8],
                    self.CurrentQuorumVote.Ballot)

        self.NextBallotTime = self._nextballottime()
        self.CurrentQuorumVote.close_current_ballot()

    def complete_vote(self, blocknum, txnlist):
        """Close the current vote.

        This is called by the QuorumVote object after the last ballot has been
        closed. The specified transactions can be safely added to journal.

        Args:
            blocknum (int): The block identifier.
            txnlist (list): A list of transactions that nodes voted to
                include in the block.
        """

        logger.debug('complete the vote for block based on %s',
                     self.MostRecentCommittedBlockID)

        if len(txnlist) == 0:
            logger.warn('no transactions to commit')
            self.CurrentQuorumVote = None
            self.NextVoteTime = self._nextvotetime()
            self.NextBallotTime = 0
            return

        if blocknum != self.MostRecentCommittedBlock.BlockNumber + 1:
            logger.warn(
                'attempt complete vote on block %d, expecting block %d',
                blocknum, self.MostRecentCommittedBlock.BlockNumber + 1)
            return

        nblock = quorum_transaction_block.QuorumTransactionBlock()
        nblock.BlockNumber = blocknum
        nblock.PreviousBlockID = self.MostRecentCommittedBlockID
        nblock.TransactionIDs = txnlist[:]
        nblock.sign_from_node(self.local_node)

        logger.info('commit: %s', nblock.dump())

        self.commit_transaction_block(nblock)

        self.CurrentQuorumVote = None
        self.NextVoteTime = self._nextvotetime()
        self.NextBallotTime = 0

    def quorum_list(self):
        return [x for x in self.QuorumMap.itervalues()]

    #
    # UTILITY FUNCTIONS
    #

    def _connected(self):
        rslt = len(self.VotingQuorum.keys()) >= self.VotingQuorumTargetSize
        if rslt is False:
            logger.warn('not sufficiently connected')
        return rslt

    def _triggervote(self, now):
        """
        Handle timer events
        """

        if self.NextVoteTime != 0:
            if self.NextVoteTime < now:
                self.initiate_vote()

        elif self.NextBallotTime != 0:
            if self.NextBallotTime < now:
                self.close_current_ballot()

    def _nextvotetime(self, now=0):
        """
        Generate the time for the next vote to be initiated
        """
        if now == 0:
            now = time.time()
        return now + self.VoteTimeInterval + random.expovariate(
            1.0 / self.VoteTimeFudgeFactor)

    def _nextballottime(self, now=0):
        """
        Generate the time for the next ballot to be initiated
        """
        if now == 0:
            now = time.time()
        return now + self.BallotTimeInterval + random.expovariate(
            1.0 / self.BallotTimeFudgeFactor)

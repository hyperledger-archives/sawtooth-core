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
from sawtooth_validator.consensus.consensus_base import Consensus
from sawtooth_validator.consensus.quorum import quorum_transaction_block
from sawtooth_validator.consensus.quorum.messages import quorum_debug
from sawtooth_validator.consensus.quorum.messages import quorum_ballot
from sawtooth_validator.consensus.quorum.protocols import quorum_vote

LOGGER = logging.getLogger(__name__)


class QuorumConsensus(Consensus):
    """Implements a journal based on participant voting.

    Attributes:
        vote_time_interval (float): The minimum time between votes, in
            seconds.
        vote_time_fudge_factor (float): The average fudge factor added to
            the vote interval, in seconds.  Used in conjunction with
            randomization functions to stagger network initiative.
        ballot_time_interval (float): The minimum time between ballots on
            a vote, in seconds.
        ballot_time_fudge_factor (float): The average fudge factor added
            to the ballot interval, in seconds.  Used in conjunction with
            randomization functions to stagger network initiative.
        vote_threshholds (list): The minimum votes required for a
            transaction to proceed to the next ballot.
        voting_quorum_target_size (int): The target size for the local
            quorum set (note: this should be a function of network size).
        voting_quorum (dict): The nodes in the quorum.
        current_quorum_vote (QuorumVote): The vote in progress.
        next_vote_time (float): When the next vote will occur.
        next_ballot_time (float): When the next ballot will occur.
        onHeartBeatTimer (EventHandler): The EventHandler tracking calls
            to make when the heartbeat timer fires.
    """
    def __init__(self,
                 vote_time_interval=None,
                 ballot_time_interval=None,
                 voting_quorum_target_size=None,
                 quorum=None,
                 nodes=None):
        """Constructor for the QuorumJournal class.

        Args:
            nd (Node): The local node.
        """

        # minimum time between votes
        if vote_time_interval is not None:
            self.vote_time_interval = vote_time_interval
        else:
            self.vote_time_interval = 30.0

        # average fudge factor added to the vote interval
        self.vote_time_fudge_factor = 1.0

        # minimum time between ballots on a vote
        if ballot_time_interval is not None:
            self.ballot_time_interval = ballot_time_interval
        else:
            self.ballot_time_interval = 5.0

        # average fudge factor added to the time interval
        self.ballot_time_fudge_factor = 0.1

        # minimum votes required for a txn to proceed to the next ballot
        self.vote_threshholds = [0.0, 0.5, 0.7, 0.9]

        # target size for local quorum set, note this should be a function of
        # network size
        if voting_quorum_target_size is not None:
            self.voting_quorum_target_size = voting_quorum_target_size
        else:
            self.voting_quorum_target_size = 13

        self.quorum_map = dict()
        self.voting_quorum = dict()
        # we are always a member of our own quorum
        self.voting_quorum[self.local_node.Identifier] = \
            self.local_node

        self.current_quorum_vote = None
        self.next_vote_time = self._nextvotetime()
        self.next_ballot_time = 0
        self.initialize_quorum_map(quorum, nodes)

    def initialization_complete(self, journal):
        # initialize the block handlers
        quorum_ballot.register_message_handlers(self)
        quorum_debug.register_message_handlers(self)
        quorum_transaction_block.register_message_handlers(self)

    def initialize_quorum_map(self, quorum, nodes):
        q = quorum
        if self.local_node.Name not in q:
            LOGGER.fatal("node must be in its own quorum")
            self.shutdown()
            return
        if len(q) < self.voting_quorum_target_size:
            LOGGER.fatal('insufficient quorum configuration; need %s but " \
                         "specified %s', len(q),
                         self.voting_quorum_target_size)
            self.shutdown()
            return
        self.quorum_map = {}
        for nd_dict in nodes:
            if nd_dict["NodeName"] in q:
                addr = (socket.gethostbyname(nd_dict["Host"]), nd_dict["Port"])
                nd = node.Node(address=addr,
                               identifier=nd_dict["Identifier"],
                               name=nd_dict["NodeName"])
                nd.HttpPort = nd_dict["HttpPort"]
                self.quorum_map[nd_dict["NodeName"]] = nd

    #
    # GENERAL JOURNAL API
    #
    def create_block(self):
        return quorum_transaction_block.QuorumTransactionBlock()

    def initialize_block(self, journal, block):
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
        # initiate a vote...
        pass

    def handle_fork(self, tblock):
        """Handle the case where we are attempting to commit a block
        that is not connected to the current block chain. This is a
        no-op for the QuorumJournal.

        Args:
            tblock (QuorumTransactionBlock): The block to commit.
        """
        LOGGER.info(
            'received a forked block %s from %s with previous id %s, '
            'expecting %s',
            tblock.Identifier[:8], self._id2name(tblock.OriginatorID),
            tblock.PreviousBlockID[:8],
            self.most_recent_committed_block_id[:8])

    #
    # CUSTOM JOURNAL API
    #

    def add_quorum_node(self, q_node):
        """Adds a node to this node's quorum set.

        Args:
            q_node (Node): The node to add to the quorum set.
        """
        LOGGER.info('attempt to add quorum voting node %s to %s', str(q_node),
                    str(self.local_node))

        if q_node.Identifier in self.voting_quorum:
            LOGGER.info('attempt to add duplicate node to quorum')
            return

        LOGGER.info('add node %s to voting quorum as %s', q_node.Name,
                    q_node.Identifier)
        self.voting_quorum[q_node.Identifier] = q_node

    def initiate_vote(self):
        """Initiates a new vote.

        This method is called when the vote timer expires indicating
        that a new vote should be initiated.
        """
        LOGGER.info('quorum, initiate, %s',
                    self.most_recent_committed_block_id[:8])

        # check alleged connectivity
        if not self._connected():
            self.next_vote_time = self._nextvotetime()
            self.next_ballot_time = 0
            return

        # check that we have enough transactions
        txnlist = self._prepare_transaction_list(
            maxcount=self.maximum_transactions_per_block)
        if len(txnlist) < self.minimum_transactions_per_block:
            LOGGER.debug('insufficient transactions for vote; %d out of %d',
                         len(txnlist), self.minimum_transactions_per_block)
            self.next_vote_time = self._nextvotetime()
            self.next_ballot_time = 0
            return

        # we are initiating the vote, send the message to the world
        newblocknum = self.most_recent_committed_block.BlockNumber + 1
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
        if self.most_recent_committed_block_id == common.NullIdentifier:
            LOGGER.warn('self.MostRecentCommittedBlockID is %s',
                        self.most_recent_committed_block_id)
            return False

        if blocknum != self.most_recent_committed_block.BlockNumber + 1:
            LOGGER.warn(
                'attempt initiate vote on block %d, expecting block %d',
                blocknum, self.most_recent_committed_block.BlockNumber + 1)
            return False

        if self.current_quorum_vote:
            LOGGER.debug(
                'received request to start a vote already in progress')
            return False

        LOGGER.info('quorum, handle initiate, %s',
                    self.most_recent_committed_block_id[:8])

        txnlist = self._prepare_transaction_list(
            maxcount=self.maximum_transactions_per_block)
        self.current_quorum_vote = quorum_vote.QuorumVote(self, blocknum,
                                                          txnlist)
        self.next_vote_time = 0
        self.next_ballot_time = self._nextballottime()

        return True

    def close_current_ballot(self):
        """Closes the current ballot.

        This method is called when the timer indicates that the vote for a
        particular ballot is complete.
        """
        LOGGER.info('quorum, ballot, %s, %d',
                    self.most_recent_committed_block_id[:8],
                    self.current_quorum_vote.Ballot)

        self.next_ballot_time = self._nextballottime()
        self.current_quorum_vote.close_current_ballot()

    def complete_vote(self, blocknum, txnlist):
        """Close the current vote.

        This is called by the QuorumVote object after the last ballot has been
        closed. The specified transactions can be safely added to journal.

        Args:
            blocknum (int): The block identifier.
            txnlist (list): A list of transactions that nodes voted to
                include in the block.
        """

        LOGGER.debug('complete the vote for block based on %s',
                     self.most_recent_committed_block_id)

        if len(txnlist) == 0:
            LOGGER.warn('no transactions to commit')
            self.current_quorum_vote = None
            self.next_vote_time = self._nextvotetime()
            self.next_ballot_time = 0
            return

        if blocknum != self.most_recent_committed_block.BlockNumber + 1:
            LOGGER.warn(
                'attempt complete vote on block %d, expecting block %d',
                blocknum, self.most_recent_committed_block.BlockNumber + 1)
            return

        nblock = quorum_transaction_block.QuorumTransactionBlock()
        nblock.BlockNumber = blocknum
        nblock.PreviousBlockID = self.most_recent_committed_block_id
        nblock.TransactionIDs = txnlist[:]
        nblock.sign_from_node(self.local_node)

        LOGGER.info('commit: %s', nblock.dump())

        self.commit_transaction_block(nblock)

        self.current_quorum_vote = None
        self.next_vote_time = self._nextvotetime()
        self.next_ballot_time = 0

    def claim_block(self, journal, block):
        """Placeholder for when the block is complete. """
        pass

    def create_block_message(self, block):
        pass

    def quorum_list(self):
        return [x for x in self.quorum_map.itervalues()]

    #
    # UTILITY FUNCTIONS
    #

    def _connected(self):
        rslt = len(self.voting_quorum.keys()) >= self.voting_quorum_target_size
        if rslt is False:
            LOGGER.warn('not sufficiently connected')
        return rslt

    def check_claim_block(self, journal, block, now):
        """ Check if it is time to vote
        """

        if self.next_vote_time != 0:
            if self.next_vote_time < now:
                self.initiate_vote()

        elif self.next_ballot_time != 0:
            if self.next_ballot_time < now:
                self.close_current_ballot()

    def _nextvotetime(self, now=0):
        """
        Generate the time for the next vote to be initiated
        """
        if now == 0:
            now = time.time()
        return now + self.vote_time_interval + random.expovariate(
            1.0 / self.vote_time_fudge_factor)

    def _nextballottime(self, now=0):
        """
        Generate the time for the next ballot to be initiated
        """
        if now == 0:
            now = time.time()
        return now + self.ballot_time_interval + random.expovariate(
            1.0 / self.ballot_time_fudge_factor)

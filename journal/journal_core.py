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
import shelve
import time
from collections import OrderedDict

from gossip import common, event_handler, gossip_core, stats
from journal import transaction, transaction_block
from journal.global_store_manager import GlobalStoreManager
from journal.messages import journal_debug
from journal.messages import journal_transfer
from journal.messages import transaction_block_message
from journal.messages import transaction_message

logger = logging.getLogger(__name__)


class Journal(gossip_core.Gossip):
    """The base journal class.

    Attributes:
        MaximumBlocksToKeep (int): Maximum number of blocks to keep in cache.
        MinimumTransactionsPerBlock (int): Minimum number of transactions
            per block.
        MaximumTransactionsPerBlock (int): Maximum number of transactions
            per block.
        MissingRequestInterval (float): Time in seconds between sending
            requests for a missing transaction block.
        StartTime (float): The initialization time of the journal in
            seconds since the epoch.
        Initializing (bool): Whether or not the journal is in an
            initializing state.
        InitialTransactions (list): A list of initial transactions to
            process.
        InitialBlockList (list): A list of initial blocks to process.
        GenesisLedger (bool): Whether or not this journal is associated
            with a genesis node.
        Restore (bool): Whether or not to restore block data.
        onGenesisBlock (EventHandler): An EventHandler for functions
            to call when processing a genesis block.
        onBuildBlock (EventHandler): An EventHandler for functions
            to call when processing a build block.
        onClaimBlock (EventHandler): An EventHandler for functions
            to call when processing a claim block.
        onCommitBlock (EventHandler): An EventHandler for functions
            to call when processing a commit block.
        onDecommitBlock (EventHandler): An EventHandler for functions
            to call when processing a decommit block.
        onBlockTest (EventHandler): An EventHandler for functions
            to call when processing a block test.
        PendingTransactions (dict): A dict of pending, unprocessed
            transactions.
        TransactionStore (Shelf): A dict-like object representing
            the persisted copy of the transaction store.
        BlockStore (Shelf): A dict-like object representing the
            persisted copy of the block store.
        ChainStore (Shelf): A dict-like object representing the
            persisted copy of the chain store.
        RequestedTransactions (dict): A dict of transactions which are
            not in the local cache, the details of which have been
            requested from peers.
        RequestedBlocks (dict): A dict of blocks which are not in the
            local cache, the details of which have been requested
            from peers.
        MostRecentCommittedBlockID (str): The block ID of the most
            recently committed block.
        PendingTransactionBlock (TransactionBlock): The constructed
            pending transaction block.
        PendingBlockIDs (set): A set of pending block identifiers.
        InvalidBlockIDs (set): A set of invalid block identifiers.
        FrontierBlockIDs (set): A set of block identifiers for blocks
            which still need to be processed.
        GlobalStoreMap (GlobalStoreManager): Manages access to the
            various persistence stores.
    """

    # For storage management, minimum blocks to keep cached
    MaximumBlocksToKeep = 50

    # Minimum number of transactions per block
    MinimumTransactionsPerBlock = 10

    # Maximum number of transactions per block
    MaximumTransactionsPerBlock = 200

    # Time between sending requests for a missing transaction block
    MissingRequestInterval = 30.0

    def __init__(self, node, **kwargs):
        """Constructor for the Journal class.

        Args:
            node (Node): The local node.
            GenesisLedger (bool): Whether or not this journal is associated
                with a genesis node.
            Restore (bool): Whether or not to restore block data.
            DataDirectory (str):
        """
        super(Journal, self).__init__(node, **kwargs)

        self.StartTime = time.time()
        self.Initializing = True

        self.InitialTransactions = []
        self.InitialBlockList = []

        self.GenesisLedger = kwargs.get('GenesisLedger', False)
        self.Restore = kwargs.get('Restore', False)

        # set up the event handlers that the transaction families can use
        self.onGenesisBlock = event_handler.EventHandler('onGenesisBlock')
        self.onBuildBlock = event_handler.EventHandler('onBuildBlock')
        self.onClaimBlock = event_handler.EventHandler('onClaimBlock')
        self.onCommitBlock = event_handler.EventHandler('onCommitBlock')
        self.onDecommitBlock = event_handler.EventHandler('onDecommitBlock')
        self.onBlockTest = event_handler.EventHandler('onBlockTest')

        # this flag indicates whether we should create a completely new
        # database file or reuse an existing file
        shelveflag = 'c' if self.Restore else 'n'
        shelvedir = kwargs.get('DataDirectory', 'db')

        self.PendingTransactions = OrderedDict()

        dbprefix = shelvedir + "/" + str(self.LocalNode)
        self.TransactionStore = shelve.open(dbprefix + "_txn", shelveflag)
        self.BlockStore = shelve.open(dbprefix + "_cb", shelveflag)
        self.ChainStore = shelve.open(dbprefix + "_cs", shelveflag)

        self.RequestedTransactions = {}
        self.RequestedBlocks = {}

        self.MostRecentCommittedBlockID = common.NullIdentifier
        self.PendingTransactionBlock = None

        self.PendingBlockIDs = set()
        self.InvalidBlockIDs = set()

        # Set up the global store and transaction handlers
        self.GlobalStoreMap = GlobalStoreManager(dbprefix + "_gs", shelveflag)

        # initialize the ledger stats data structures
        self._initledgerstats()

        # connect the message handlers
        transaction_message.register_message_handlers(self)
        transaction_block_message.register_message_handlers(self)
        journal_transfer.register_message_handlers(self)
        journal_debug.register_message_handlers(self)

    @property
    def CommittedBlockCount(self):
        """Returns the block number of the most recently committed block.

        Returns:
            int: most recently committed block number.
        """
        return self.MostRecentCommittedBlock.BlockNum

    @property
    def CommittedTxnCount(self):
        """Returns the committed transaction count.

        Returns:
            int: the transaction depth based on the most recently
                committed block.
        """
        return self.MostRecentCommittedBlock.TransactionDepth

    @property
    def PendingBlockCount(self):
        """Returns the number of pending blocks.

        Returns:
            int: the number of pending blocks.
        """
        return len(self.PendingBlockIDs)

    @property
    def PendingTxnCount(self):
        """Returns the number of pending transactions.

        Returns:
            int: the number of pending transactions.
        """
        return len(self.PendingTransactions)

    def shutdown(self):
        """Shuts down the journal in an orderly fashion.
        """
        logger.info('close journal databases in preparation for shutdown')

        # Global store manager handles its own database
        self.GlobalStoreMap.close()

        self.TransactionStore.close()
        self.BlockStore.close()
        self.ChainStore.close()

        super(Journal, self).shutdown()

    def add_transaction_store(self, family):
        """Add a transaction type-specific store to the global store.

        Args:
            family (transaction.Transaction): The transaction family.
        """
        tname = family.TransactionTypeName
        tstore = family.TransactionStoreType()
        self.GlobalStoreMap.add_transaction_store(tname, tstore)

    @property
    def GlobalStore(self):
        """Returns a reference to the global store associated with the
        most recently committed block that this validator possesses.

        Returns:
            Shelf: The block store.
        """
        blkid = self.MostRecentCommittedBlockID

        return self.GlobalStoreMap.get_block_store(blkid)

    @property
    def MostRecentCommittedBlock(self):
        """Returns the most recently committed block.

        Returns:
            dict: the most recently committed block.
        """
        return self.BlockStore.get(self.MostRecentCommittedBlockID)

    def committed_block_ids(self, count=0):
        """Returns the list of block identifiers starting from the
        most recently committed block.

        Args:
            count (int): How many results should be returned.

        Returns:
            list: A list of committed block ids.
        """
        if count == 0:
            count = len(self.BlockStore)

        blockids = []

        blkid = self.MostRecentCommittedBlockID
        while blkid != common.NullIdentifier and len(blockids) < count:
            blockids.append(blkid)
            blkid = self.BlockStore[blkid].PreviousBlockID

        return blockids

    def compute_chain_root(self):
        """
        Compute the most reasonable candidate for the root of the chain. This
        is only called if we cannot determine the root from the previously
        saved state information.
        """

        # this function uses a little bit of dynamic programming to save depths
        # of chains for re-use in later probes. not pretty but its better than
        # the n^2 naive approach

        depths = dict()
        depths[common.NullIdentifier] = 0

        for blockid in self.BlockStore.iterkeys():
            count = 0
            blkid = blockid
            while blkid in self.BlockStore:
                if blkid in depths:
                    count += depths[blkid]
                    break

                blkid = self.BlockStore[blkid].PreviousBlockID
                count += 1

            depths[blockid] = count
            while blkid in self.BlockStore:
                blkid = self.BlockStore[blkid].PreviousBlockID
                if blkid in depths:
                    break

                count -= 1
                depths[blkid] = count

        blocklist = sorted(list(depths), key=lambda blkid: depths[blkid])
        return blocklist[-1]

    def initialization_complete(self):
        """Processes all invocations that arrived while the ledger was
        being initialized.
        """
        logger.info('process initial transactions and blocks')

        self.Initializing = False

        # this is a very special case where the ledger is started with an
        # existing database but no validation network. the situation can (and
        # has) occurred with deployments where all validators fail. so this is
        # really the solution of last resort, it assumes that all databases are
        # successfully restored
        if self.GenesisLedger and self.Restore:
            logger.warn('restore ledger state from the backup data stores')
            try:
                self.MostRecentCommittedBlockID = \
                    self.ChainStore['MostRecentBlockID']
            except KeyError:
                logger.warn('unable to load the most recent block id, '
                            'recomputing')
                self.MostRecentCommittedBlockID = self.compute_chain_root()

            return

        for txn in self.InitialTransactions:
            self.add_pending_transaction(txn)
        self.InitialTransactions = None

        for block in self.InitialBlockList:
            self.commit_transaction_block(block)
        self.InitialBlockList = None

        # generate a block, if none exists then generate and commit the root
        # block
        if self.GenesisLedger:
            logger.warn('node %s claims the genesis block',
                        self.LocalNode.Name)
            self.onGenesisBlock.fire(self)
            self.claim_transaction_block(self.build_transaction_block(True))
        else:
            if self.MostRecentCommittedBlockID == common.NullIdentifier:
                logger.critical('no ledger for a new network node')
                return

        logger.info('finished processing initial transactions and blocks')

    def add_pending_transaction(self, txn):
        """Adds a transaction to the list of candidates for commit.

        Args:
            txn (Transaction.Transaction): The newly arrived transaction
        """
        logger.debug('incoming transaction %s', txn.Identifier[:8])

        # nothing more to do, we are initializing
        if self.Initializing:
            self.InitialTransactions.append(txn)
            return

        # if we already have the transaction there is nothing to do
        if txn.Identifier in self.TransactionStore:
            assert self.TransactionStore[txn.Identifier]
            return

        # add it to the transaction store
        txn.Status = transaction.Status.pending
        self.TransactionStore[txn.Identifier] = txn
        if txn.add_to_pending():
            self.PendingTransactions[txn.Identifier] = True

        # if this is a transaction we requested, then remove it from the list
        # and look for any blocks that might be completed as a result of
        # processing the transaction
        if txn.Identifier in self.RequestedTransactions:
            logger.info('catching up on old transaction %s',
                        txn.Identifier[:8])
            del self.RequestedTransactions[txn.Identifier]

            blockids = []
            for blockid in self.PendingBlockIDs:
                if txn.Identifier in self.BlockStore[blockid].TransactionIDs:
                    blockids.append(blockid)

            for blockid in blockids:
                self._handleblock(self.BlockStore[blockid])

        # there is a chance the we deferred creating a transaction block
        # because there were insufficient transactions, this is where we check
        # to see if there are now enough to run the validation algorithm
        if not self.PendingTransactionBlock:
            self.PendingTransactionBlock = self.build_transaction_block()

    def commit_transaction_block(self, tblock):
        """Commits a block of transactions to the chain.

        Args:
            tblock (Transaction.TransactionBlock): A block of
                transactions which nodes agree to commit.
        """
        logger.debug('processing incoming transaction block %s',
                     tblock.Identifier[:8])

        # Make sure this is a valid block, for now this will just check the
        # signature... more later
        if not tblock.verify_signature():
            logger.warn('invalid block %s received from %s', tblock.Identifier,
                        tblock.OriginatorID)
            return

        # Don't do anything with incoming blocks if we are initializing, wait
        # for the connections to be fully established
        if self.Initializing:
            logger.debug('adding block %s to the pending queue',
                         tblock.Identifier[:8])

            # this is an ugly hack to ensure that we don't treat this as a
            # duplicate while processing the initial blocks; this can happen,
            # for example, when we are restoring from saved state. having it in
            # the block store means we didn't need to transfer it during ledger
            # transfer, a much better approach at a future time would be to
            # circumvent the commit logic and just add the block to the chain.
            # However that does mean that we have to TRUST our peer which is
            # not necessarily such a good thing...
            if tblock.Identifier in self.BlockStore:
                del self.BlockStore[tblock.Identifier]

            self.InitialBlockList.append(tblock)
            return

        # If this is a block we requested, then remove it from the list
        if tblock.Identifier in self.RequestedBlocks:
            del self.RequestedBlocks[tblock.Identifier]

        # Make sure that we have not already processed this block
        if tblock.Identifier in self.BlockStore:
            logger.info('found previously committed block %s',
                        tblock.Identifier[:8])
            return

        # Make sure we initialize the state of the block
        tblock.Status = transaction_block.Status.incomplete

        # Add this block to block pool, mark as orphaned until it is committed
        self.PendingBlockIDs.add(tblock.Identifier)
        self.BlockStore[tblock.Identifier] = tblock

        self._handleblock(tblock)

    def claim_transaction_block(self, block):
        """Fires the onClaimBlock event handler and locally commits the
        transaction block.

        Args:
            block (Transaction.TransactionBlock): A block of
                transactions to claim.
        """
        # fire the event handler for claiming the transaction block
        self.onClaimBlock.fire(self, block)
        self.commit_transaction_block(block)

    def request_missing_block(self, blockid, exceptions=[], request=None):
        """Requests neighbors to send a transaction block.

        This method is called when one block references another block
        that is not currently in the local cache. Only send the request
        periodically to avoid spamming the network with duplicate requests.

        Args:
            blockid (str): The identifier of the missing block.
            exceptions (list): Identifiers of nodes we know don't have
                the block.
            request (message.Message): A previously initialized message for
                sending the request; avoids duplicates.
        """
        now = time.time()

        if blockid in self.RequestedBlocks and now < self.RequestedBlocks[
                blockid]:
            return

        self.RequestedBlocks[blockid] = now + self.MissingRequestInterval

        # if the request for the missing block came from another node, then
        # we need to reuse the request or we'll process multiple copies
        if not request:
            request = transaction_block_message.BlockRequestMessage(
                {'BlockID': blockid})
            self.forward_message(request, exceptions=exceptions)
        else:
            self.forward_message(request,
                                 exceptions=exceptions,
                                 initialize=False)

    def request_missing_txn(self, txnid, exceptions=[], request=None):
        """Requests that neighbors send a transaction.

        This method is called when a block references a transaction
        that is not currently in the local cache. Only send the request
        periodically to avoid spamming the network with duplicate requests.

        Args:
            txnid (str): The identifier of the missing transaction.
            exceptions (list): Identifiers of nodes we know don't have
                the block.
            request (message.Message): A previously initialized message for
                sending the request; avoids duplicates.
        """
        logger.info('missing_txn called')

        now = time.time()

        if txnid in self.RequestedTransactions and now < \
                self.RequestedTransactions[txnid]:
            logger.info('missing txnid is already in RequestedTxn')
            return

        self.RequestedTransactions[txnid] = now + self.MissingRequestInterval
        logger.info('New Txn placed in RequestedTxn')

        self.JournalStats.MissingTxnRequestCount.increment()

        # if the request for the missing block came from another node, then
        # we need to reuse the request or we'll process multiple copies
        if not request:
            logger.info('new request from same node')
            request = transaction_message.TransactionRequestMessage(
                {'TransactionID': txnid})
            self.forward_message(request, exceptions=exceptions)
        else:
            logger.info('new request fr another node')
            self.forward_message(request,
                                 exceptions=exceptions,
                                 initialize=False)

    def build_transaction_block(self, force=False):
        """Builds the next transaction block for the ledger.

        Note:
            This method will generally be overridden by derived classes.

        Args:
            force (bool): Whether to force the creation of the
                initial block.
        """

        self.onBuildBlock.fire(self, None)

    def handle_advance(self, tblock):
        """Handles the case where we are attempting to commit a block that
        advances the current block chain.

        Args:
            tblock (Transaction.TransactionBlock): A block of
                transactions to advance.
        """
        assert tblock.Status == transaction_block.Status.valid

        pending = self.PendingTransactionBlock
        self.PendingTransactionBlock = None
        try:
            self._commitblock(tblock)
            self.PendingTransactionBlock = self.build_transaction_block()
        except Exception as e:
            logger.error("Error advancing block chain: %s", e)
            self.PendingTransactionBlock = pending
            raise

    def handle_fork(self, tblock):
        """Handle the case where we are attempting to commit a block
        that is not connected to the current block chain.

        Args:
            tblock (Transaction.TransactionBlock): A disconnected block.
        """

        pending = self.PendingTransactionBlock
        self.PendingTransactionBlock = None
        try:
            assert tblock.Status == transaction_block.Status.valid

            logger.info(
                'received a disconnected block %s from %s with previous id %s,'
                ' expecting %s',
                tblock.Identifier[:8], self._id2name(tblock.OriginatorID),
                tblock.PreviousBlockID[:8],
                self.MostRecentCommittedBlockID[:8])

            # First see if the chain rooted in tblock is the one we should use,
            # if it is not, then we are building on the correct block and
            # nothing needs to change

            assert self.MostRecentCommittedBlockID != common.NullIdentifier
            if cmp(tblock, self.MostRecentCommittedBlock) < 0:
                logger.info('existing chain is the valid one')
                self.PendingTransactionBlock = pending
                return

            logger.info('new chain is the valid one, replace the current '
                        'chain')

            # now find the root of the fork, first handle the common case of
            # not looking very deeply for the common block, then handle the
            # expensive case of searching the entire chain
            fork_id = self._findfork(tblock, 5)
            if not fork_id:
                fork_id = self._findfork(tblock, 0)

            assert fork_id

            # at this point we have a new chain that is longer than the current
            # one, need to move the blocks in the current chain that follow the
            # fork into the orphaned pool and then move the blocks from the new
            # chain into the committed pool and finally rebuild the global
            # store

            # move the previously committed blocks into the orphaned list
            self._decommitblockchain(fork_id)

            # move the new blocks from the orphaned list to the committed list
            self._commitblockchain(tblock.Identifier, fork_id)
            self.PendingTransactionBlock = self.build_transaction_block()
        except Exception as e:
            logger.error("Error resolving fork: %s", e)
            self.PendingTransactionBlock = pending
            raise
    #
    # UTILITY FUNCTIONS
    #

    def _handleblock(self, tblock):
        """
        Attempt to add a block to the chain.
        """

        assert tblock.Identifier in self.PendingBlockIDs

        # initialize the state of this block
        self.BlockStore[tblock.Identifier] = tblock

        # if this block is the genesis block then we can assume that
        # it meets all criteria for dependent blocks
        if tblock.PreviousBlockID != common.NullIdentifier:
            # first test... do we have the previous block, if not then this
            # block remains incomplete awaiting the arrival of the predecessor
            pblock = self.BlockStore.get(tblock.PreviousBlockID)
            if not pblock:
                self.request_missing_block(tblock.PreviousBlockID)
                return

            # second test... is the previous block invalid, if so then this
            # block will never be valid & can be completely removed from
            # consideration, for now I'm not removing the block from the
            # block store though we could substitute a check for the previous
            # block in the invalid block list
            if pblock.Status == transaction_block.Status.invalid:
                self.PendingBlockIDs.discard(tblock.Identifier)
                self.InvalidBlockIDs.add(tblock.Identifier)
                tblock.Status = transaction_block.Status.invalid
                self.BlockStore[tblock.Identifier] = tblock
                return

            # third test... is the previous block complete, if not then
            # this block cannot be complete and there is nothing else to do
            # until the missing transactions come in, note that we are not
            # requesting missing transactions at this point
            if pblock.Status == transaction_block.Status.incomplete:
                return

        # fourth test... check for missing transactions in this block, if
        # any are missing, request them and then save this block for later
        # processing
        missing = tblock.missing_transactions(self)
        if missing:
            for txnid in missing:
                self.request_missing_txn(txnid)
                self.JournalStats.MissingTxnFromBlockCount.increment()
            return

        # at this point we know that the block is complete
        tblock.Status = transaction_block.Status.complete
        self.BlockStore[tblock.Identifier] = tblock

        # fifth test... run the checks for a valid block, generally these are
        # specific to the various transaction families or consensus mechanisms
        if (not tblock.is_valid(self)
                or not self.onBlockTest.fire(self, tblock)):
            logger.debug('block test failed for %s', tblock.Identifier[:8])
            self.PendingBlockIDs.discard(tblock.Identifier)
            self.InvalidBlockIDs.add(tblock.Identifier)
            tblock.Status = transaction_block.Status.invalid
            self.BlockStore[tblock.Identifier] = tblock
            return

        # sixth test... verify that every transaction in the now complete
        # block is valid independently and build the new data store
        newstore = self._testandapplyblock(tblock)
        if newstore is None:
            logger.debug('transaction validity test failed for %s',
                         tblock.Identifier[:8])
            self.PendingBlockIDs.discard(tblock.Identifier)
            self.InvalidBlockIDs.add(tblock.Identifier)
            tblock.Status = transaction_block.Status.invalid
            self.BlockStore[tblock.Identifier] = tblock
            return

        # at this point we know that the block is valid
        tblock.Status = transaction_block.Status.valid
        tblock.CommitTime = time.time() - self.StartTime
        tblock.update_block_weight(self)

        # time to apply the transactions in the block to get a new state
        self.GlobalStoreMap.commit_block_store(tblock.Identifier,
                                               newstore)
        self.BlockStore[tblock.Identifier] = tblock

        # remove the block from the pending block list
        self.PendingBlockIDs.discard(tblock.Identifier)

        # and now check to see if we should start to use this block as the one
        # on which we build a new chain

        # handle the easy, common case here where the new block extends the
        # current chain
        if tblock.PreviousBlockID == self.MostRecentCommittedBlockID:
            self.handle_advance(tblock)
        else:
            self.handle_fork(tblock)

        self._cleantransactionblocks()

        # last thing is to check the other orphaned blocks to see if this
        # block connects one to the chain, if a new block is connected to
        # the chain then we need to go through the entire process again with
        # the newly connected block
        blockids = set()
        for blockid in self.PendingBlockIDs:
            if self.BlockStore[blockid].PreviousBlockID == tblock.Identifier:
                blockids.add(blockid)

        for blockid in blockids:
            self._handleblock(self.BlockStore[blockid])

    def _commitblockchain(self, blockid, forkid):
        """
        commit a chain of block starting with the forked block through the head
        of the chain

        Args:
            blockid (UUID) -- head of the chain to commit
            forkid (UUID) -- point where the fork occurred
        """
        chain = []
        b_id = blockid
        while b_id != forkid:
            block = self.BlockStore[b_id]
            chain.append(block)
            b_id = block.PreviousBlockID
        chain.reverse()
        for block in chain:
            self._commitblock(block)

    def _commitblock(self, tblock):
        """
        Add a block to the committed chain, this function extends the
        chain by updating the most recent committed block field

        Args:
             tblock (Transaction.TransactionBlock) -- block of transactions to
                 be committed
        """

        logger.info('commit block %s from %s with previous id %s',
                    tblock.Identifier[:8], self._id2name(tblock.OriginatorID),
                    tblock.PreviousBlockID[:8])

        assert tblock.Status == transaction_block.Status.valid

        # Remove all of the newly committed transactions from the pending list
        # and put them in the committed list
        for txnid in tblock.TransactionIDs:
            if txnid in self.PendingTransactions:
                del self.PendingTransactions[txnid]

            txn = self.TransactionStore[txnid]
            txn.Status = transaction.Status.committed
            txn.InBlock = tblock.Identifier
            self.TransactionStore[txnid] = txn

        # Update the head of the chain
        self.MostRecentCommittedBlockID = tblock.Identifier
        self.ChainStore['MostRecentBlockID'] = self.MostRecentCommittedBlockID

        # Update stats
        self.JournalStats.CommittedBlockCount.increment()
        self.JournalStats.CommittedTxnCount.increment(len(
            tblock.TransactionIDs))

        # fire the event handler for block commit
        self.onCommitBlock.fire(self, tblock)

    def _decommitblockchain(self, forkid):
        """
        decommit blocks from the head of the chain through the forked block

        Args:
            forkid (UUID) -- identifier of the block where the fork occurred
        """
        blockid = self.MostRecentCommittedBlockID
        while blockid != forkid:
            self._decommitblock()
            blockid = self.MostRecentCommittedBlockID

    def _decommitblock(self):
        """
        Move the head of the block chain from the committed pool to the
        orphaned pool and move all transactions in the block back into the
        pending transaction list.
        """
        blockid = self.MostRecentCommittedBlockID
        block = self.BlockStore[blockid]
        assert block.Status == transaction_block.Status.valid

        # fire the event handler for block decommit
        self.onDecommitBlock.fire(self, block)

        # move the head of the chain back
        self.MostRecentCommittedBlockID = block.PreviousBlockID
        self.ChainStore['MostRecentBlockID'] = self.MostRecentCommittedBlockID

        # this bizarre bit of code is intended to preserve the ordering of
        # transactions, where all committed transactions occur before pending
        # transactions
        pending = OrderedDict()
        for txnid in block.TransactionIDs:
            # there is a chance that this block is incomplete and some of the
            # transactions have not arrived, don't put transactions into
            # pending if we dont have the transaction
            txn = self.TransactionStore.get(txnid)
            if txn:
                txn.Status = transaction.Status.pending
                self.TransactionStore[txnid] = txn

                if txn.add_to_pending():
                    pending[txnid] = True

        pending.update(self.PendingTransactions)
        self.PendingTransactions = pending

        # update stats
        self.JournalStats.CommittedBlockCount.increment(-1)
        self.JournalStats.CommittedTxnCount.increment(-len(
            block.TransactionIDs))

    def _testandapplyblock(self, tblock):
        """Test and apply transactions to the previous block's global
        store to create a new version of the store

        Args:
            tblock (Transaction.TransactionBlock) -- block of transactions to
                apply
        Returns:
            GlobalStore
        """

        assert tblock.Status == transaction_block.Status.complete

        # make a copy of the store from the previous block, the previous
        # block must be complete if this block is complete
        teststore = self.GlobalStoreMap.get_block_store(
            tblock.PreviousBlockID).clone_block()

        # apply the transactions
        try:
            for txnid in tblock.TransactionIDs:
                txn = self.TransactionStore[txnid]
                txnstore = teststore.get_transaction_store(
                    txn.TransactionTypeName)
                if not txn.is_valid(txnstore):
                    return None

                txn.apply(txnstore)
        except:
            logger.exception('unexpected exception when testing'
                             ' transaction block validity')
            return None

        return teststore

    def _findfork(self, tblock, depth):
        """
        Find most recent predecessor of tblock that is in the committed
        chain, searching through at most depth blocks

        :param tblock PoetTransactionBlock:
        :param depth int: depth in the current chain to search, 0 implies all
        """

        blockids = set(self.committed_block_ids(depth))
        forkid = tblock.PreviousBlockID
        while True:
            if forkid == common.NullIdentifier or forkid in blockids:
                return forkid

            assert forkid in self.BlockStore
            forkid = self.BlockStore[forkid].PreviousBlockID

        return None

    def _preparetransactionlist(self, maxcount=0):
        """
        Prepare an ordered list of valid transactions that can be included in
        the next consensus round

        Returns:
            list of Transaction.Transaction
        """

        # generate a list of valid transactions to place in the new block
        addtxns = []
        deltxns = []
        store = self.GlobalStore.clone_block()
        for txnid in self.PendingTransactions.iterkeys():
            txn = self.TransactionStore[txnid]
            if txn:
                self._preparetransaction(addtxns, deltxns, store, txn)

            if maxcount and len(addtxns) >= maxcount:
                break

        # as part of the process, we may identify transactions that are invalid
        # so go ahead and get rid of them, since these had all dependencies met
        # we know that they will never be valid
        for txnid in deltxns:
            logger.info('found a transaction that will never apply; %s',
                        txnid[:8])
            if txnid in self.TransactionStore:
                del self.TransactionStore[txnid]
            if txnid in self.PendingTransactions:
                del self.PendingTransactions[txnid]

        return addtxns

    def _preparetransaction(self, addtxns, deltxns, store, txn):
        """
        Determine if a particular transaction is valid

        Args:
            addtxns (list of Transaction.Transaction) -- transaction to be
                added to the current block
            deltxns (list of Transaction.Transaction) -- invalid transactions
            store (GlobalStore) -- current global store
            txn -- the transaction to be tested
        Returns:
            True if the transaction is valid
        """

        logger.debug('add transaction %s with id %s', str(txn),
                     txn.Identifier[:8])

        # Because the dependencies may reorder transactions in the block
        # in a way that is different from the arrival order, this transaction
        # might already be in the block
        if txn.Identifier in addtxns:
            return True

        # First step in adding the transaction to the list is to make
        # sure that all dependent transactions are in the list already
        ready = True
        for dependencyID in txn.Dependencies:
            logger.debug('check dependency %s of transaction %s',
                         dependencyID[:8], txn.Identifier[:8])

            # check to see if the dependency has already been committed
            if (dependencyID in self.TransactionStore and
                    (self.TransactionStore[dependencyID].Status ==
                     transaction.Status.committed)):
                continue

            # check to see if the dependency is already in this block
            if dependencyID in addtxns:
                continue

            # check to see if the dependency is among the transactions to be
            # deleted, if so then this transaction will never be valid and we
            # can just get rid of it
            if dependencyID in deltxns:
                logger.info('transaction %s depends on deleted transaction %s',
                            txn.Identifier[:8], dependencyID[:8])
                deltxns.append(txn.Identifier)
                ready = False
                continue

            # recurse into the dependency, note that we need to make sure there
            # are no loops in the dependencies but not doing that right now
            deptxn = self.TransactionStore.get(dependencyID)
            if deptxn and self._preparetransaction(addtxns, deltxns, store,
                                                   deptxn):
                continue

            # at this point we cannot find the dependency so send out a request
            # for it and wait, we should set a timer on this transaction so we
            # can just throw it away if the dependencies cannot be met
            ready = False

            logger.info('calling missing Txn')
            self.request_missing_txn(dependencyID)
            self.JournalStats.MissingTxnDepCount.increment()

        # if all of the dependencies have not been met then there isn't any
        # point in continuing on so bail out
        if not ready:
            return False

        # after all that work... we know the dependencies are met, so see if
        # the transaction is valid, that is that all of the preconditions
        # encoded in the transaction itself are met
        txnstore = store.get_transaction_store(txn.TransactionTypeName)
        if txn.is_valid(txnstore):
            logger.debug('txn with id %s is valid, adding to block',
                         txn.Identifier[:8])
            addtxns.append(txn.Identifier)
            txn.apply(txnstore)
            return True

        # because we have all of the dependencies but the transaction is still
        # invalid we know that this transaction is broken and we can simply
        # throw it away
        logger.warn(
            'transaction %s with id %s is not valid for this block, dropping',
            str(txn), txn.Identifier[:8])
        logger.info(common.pretty_print_dict(txn.dump()))
        deltxns.append(txn.Identifier)
        return False

    def _cleantransactionblocks(self):
        """
        _cleantransactionblocks -- for blocks and transactions that are with
        high probability no longer going to change, clean out the bulk of the
        memory used to store the block and the corresponding transactions
        """
        self.ChainStore.sync()
        self.TransactionStore.sync()
        self.BlockStore.sync()

        # with the state storage, we can flatten old blocks to reduce memory
        # footprint, they can always be recovered from persistent storage
        # later on, however, the flattening process increases memory usage
        # so we don't want to do it too often, the code below keeps the number
        # of blocks kept in memory less than 2 * self.MaximumBlocksToKeep
        if self.MostRecentCommittedBlock.BlockNum \
                % self.MaximumBlocksToKeep == 0:
            logger.info('compress global state for block number %s',
                        self.MostRecentCommittedBlock.BlockNum)
            depth = 0
            blockid = self.MostRecentCommittedBlockID
            while (blockid != common.NullIdentifier and
                   depth < self.MaximumBlocksToKeep):
                blockid = self.BlockStore[blockid].PreviousBlockID
                depth += 1

            if blockid != common.NullIdentifier:
                logger.debug('flatten storage for block %s', blockid)
                self.GlobalStoreMap.flatten_block_store(blockid)

    def _initledgerstats(self):
        self.JournalStats = stats.Stats(self.LocalNode.Name, 'ledger')
        self.JournalStats.add_metric(stats.Counter('CommittedBlockCount'))
        self.JournalStats.add_metric(stats.Counter('CommittedTxnCount'))
        self.JournalStats.add_metric(stats.Counter('MissingTxnRequestCount'))
        self.JournalStats.add_metric(stats.Counter('MissingTxnFromBlockCount'))
        self.JournalStats.add_metric(stats.Counter('MissingTxnDepCount'))
        self.JournalStats.add_metric(stats.Sample(
            'PendingBlockCount', lambda: self.PendingBlockCount))
        self.JournalStats.add_metric(stats.Sample(
            'PendingTxnCount',
            lambda: self.PendingTxnCount))

        self.StatDomains['ledger'] = self.JournalStats

        self.JournalConfigStats = stats.Stats(self.LocalNode.Name,
                                              'ledgerconfig')
        self.JournalConfigStats.add_metric(
            stats.Sample('MinimumTransactionsPerBlock',
                         lambda: self.MinimumTransactionsPerBlock))
        self.JournalConfigStats.add_metric(
            stats.Sample('MaximumTransactionsPerBlock',
                         lambda: self.MaximumTransactionsPerBlock))

        self.StatDomains['ledgerconfig'] = self.JournalConfigStats

    def _id2name(self, nodeid):
        if nodeid in self.NodeMap:
            return str(self.NodeMap[nodeid])

        if nodeid == self.LocalNode.Identifier:
            return str(self.LocalNode)

        store = self.GlobalStore.TransactionStores[
            '/EndpointRegistryTransaction']
        if nodeid in store and 'Name' in store[nodeid]:
            return str(store[nodeid]['Name'])

        return nodeid[:8]

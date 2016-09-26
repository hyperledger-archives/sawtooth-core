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
from threading import RLock
import time
from collections import OrderedDict

from gossip import common
from gossip import event_handler
from gossip.message_dispatcher import MessageDispatcher
from gossip import stats

from journal import journal_store
from journal import transaction
from journal import transaction_block
from journal.global_store_manager import GlobalStoreManager
from journal.messages import journal_debug
from journal.messages import journal_transfer
from journal.messages import transaction_block_message
from journal.messages import transaction_message

from sawtooth.exceptions import NotAvailableException

logger = logging.getLogger(__name__)


class Journal(object):
    """The base journal class.

    Attributes:
        MaximumBlocksToKeep (int): Maximum number of blocks to keep in cache.
        MinimumTransactionsPerBlock (int): Minimum number of transactions
            per block.
        MaximumTransactionsPerBlock (int): Maximum number of transactions
            per block.
        MissingRequestInterval (float): Time in seconds between sending
            requests for a missing transaction block.
        BlockRetryInterval (float): Time in seconds between retrying
            block validations that
        StartTime (float): The initialization time of the journal in
            seconds since the epoch.
        Initializing (bool): Whether or not the journal is in an
            initializing state.
        InitialLoad (bool): Whether or not the journal is in an initial
            loading state.
        InitialTransactions (list): A list of initial transactions to
            process.
        InitialBlockList (list): A list of initial blocks to process.
        GenesisLedger (bool): Whether or not this journal is associated
            with a genesis node.
        Restore (bool): Whether or not to restore block data.
        onGenesisBlock (EventHandler): An EventHandler for functions
            to call when processing a genesis block.
        onPreBuildBlock (EventHandler): An EventHandler for functions
            to call when before processing a build block.
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
        TransactionStore (JournalStore): A dict-like object representing
            the persisted copy of the transaction store.
        BlockStore (JournalStore): A dict-like object representing the
            persisted copy of the block store.
        ChainStore (JournalStore): A dict-like object representing the
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
        PendingBlockIDs (builtin set): A set of pending block identifiers.
        InvalidBlockIDs (builtin set): A set of invalid block identifiers.
        FrontierBlockIDs (builtin set): A set of block identifiers for blocks
            which still need to be processed.
        GlobalStoreMap (GlobalStoreManager): Manages access to the
            various persistence stores.
    """

    def __init__(self, gossip, **kwargs):
        """Constructor for the Journal class.

        Args:
            node (Node): The local node.
            GenesisLedger (bool): Whether or not this journal is associated
                with a genesis node.
            Restore (bool): Whether or not to restore block data.
            DataDirectory (str):
        """
        self.gossip = gossip
        self.dispatcher = MessageDispatcher(self, gossip)

        self.StartTime = time.time()
        self.Initializing = True
        self.InitialLoad = False

        self.InitialTransactions = []
        self.InitialBlockList = []

        # For storage management, minimum blocks to keep cached
        self.MaximumBlocksToKeep = 50

        # Minimum number of transactions per block
        self.MinimumTransactionsPerBlock = kwargs\
            .get('MinTransactionsPerBlock', 1)

        # Amount of time(in sec) transactions can wait to meet the
        # MinimumTransactionsPerBlock before a block gets built with
        # less then the MinimumTransactionsPerBlock count.
        # This is a safety measure to allow the validator network to function
        # with low transaction volume, such as network start up.
        self.MaximumTransactionsWaitTime = 60

        # Maximum number of transactions per block
        self.MaximumTransactionsPerBlock = kwargs.\
            get('MaxTransactionsPerBlock', 1000)

        # Time between sending requests for a missing transaction block
        self.MissingRequestInterval = 30.0

        # Time between sending requests for a missing transaction block
        self.BlockRetryInterval = 10.0
        self.MaxTxnAge = kwargs.get("MaxTxnAge", 3)
        self.GenesisLedger = kwargs.get('GenesisLedger', False)
        self.Restore = kwargs.get('Restore', False)

        # set up the event handlers that the transaction families can use
        self.onGenesisBlock = event_handler.EventHandler('onGenesisBlock')
        self.onPreBuildBlock = event_handler.EventHandler('onPreBuildBlock')
        self.onBuildBlock = event_handler.EventHandler('onBuildBlock')
        self.onClaimBlock = event_handler.EventHandler('onClaimBlock')
        self.onCommitBlock = event_handler.EventHandler('onCommitBlock')
        self.onDecommitBlock = event_handler.EventHandler('onDecommitBlock')
        self.onBlockTest = event_handler.EventHandler('onBlockTest')

        # this flag indicates whether we should create a completely new
        # database file or reuse an existing file
        dbflag = 'c' if self.Restore else 'n'
        dbdir = kwargs.get('DataDirectory', 'db')
        store_type = kwargs.get('StoreType', 'shelf')

        self._txn_lock = RLock()
        self.PendingTransactions = OrderedDict()
        self.TransactionEnqueueTime = None

        dbprefix = dbdir + "/" + str(self.gossip.LocalNode)

        if store_type == 'shelf':
            from journal.database import shelf_database

            self.TransactionStore = journal_store.JournalStore(
                shelf_database.ShelfDatabase(dbprefix + "_txn" + ".shelf",
                                             dbflag))
            self.BlockStore = journal_store.JournalStore(
                shelf_database.ShelfDatabase(dbprefix + "_block" + ".shelf",
                                             dbflag))
            self.ChainStore = journal_store.JournalStore(
                shelf_database.ShelfDatabase(dbprefix + "_chain" + ".shelf",
                                             dbflag))
        elif store_type == 'lmdb':
            from journal.database import lmdb_database

            self.TransactionStore = journal_store.JournalStore(
                lmdb_database.LMDBDatabase(dbprefix + "_txn" + ".lmdb",
                                           dbflag))
            self.BlockStore = journal_store.JournalStore(
                lmdb_database.LMDBDatabase(dbprefix + "_block" + ".lmdb",
                                           dbflag))
            self.ChainStore = journal_store.JournalStore(
                lmdb_database.LMDBDatabase(dbprefix + "_chain" + ".lmdb",
                                           dbflag))
        else:
            raise KeyError("%s is not a supported StoreType", store_type)

        self.RequestedTransactions = {}
        self.RequestedBlocks = {}

        self.next_block_retry = time.time() + self.BlockRetryInterval

        self.dispatcher.on_heartbeat += self._trigger_retry_blocks

        self.MostRecentCommittedBlockID = common.NullIdentifier
        self.PendingTransactionBlock = None

        self.PendingBlockIDs = set()
        self.InvalidBlockIDs = set()

        # Set up the global store and transaction handlers
        self.GlobalStoreMap = GlobalStoreManager(dbprefix + "_state" + ".dbm",
                                                 dbflag)
        # initialize the ledger stats data structures
        self._initledgerstats()

        # connect the message handlers
        journal_debug.register_message_handlers(self)
        transaction_message.register_message_handlers(self)
        transaction_block_message.register_message_handlers(self)
        journal_transfer.register_message_handlers(self)

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

    def sign_and_send_message(self, msg):
        msg.SenderID = self.gossip.LocalNode.Identifier
        msg.sign_from_node(self.gossip.LocalNode)
        self.gossip.handle_message(msg)

    def forward_message(self, msg, exceptions=None, initialize=True):
        self.gossip.forward_message(msg, exceptions, initialize)

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

    @property
    def CommittedBlockIDCount(self):
        """Returns the count of blocks in the block store.

        Returns:
            int: count of blocks in the block store.
        """
        return len(self.BlockStore)

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
        self.InitialLoad = True

        if self.Restore:
            logger.info('restore ledger state from the backup data stores')
            try:
                self.MostRecentCommittedBlockID = \
                    self.ChainStore['MostRecentBlockID']
                logger.info('commit head: %s', self.MostRecentCommittedBlockID)
            except KeyError:
                logger.warn('unable to load the most recent block id, '
                            'recomputing')
                self.MostRecentCommittedBlockID = self.compute_chain_root()

            return

        for txn in self.InitialTransactions:
            self.add_pending_transaction(txn, build_block=False)
        self.InitialTransactions = None

        logger.debug('initial block list: %s', self.InitialBlockList)

        # Generate a unique list of initial blocks to process, sorted
        # by BlockNum
        initial_block_list = []
        seen = set()
        for block in self.InitialBlockList:
            if block.Identifier not in seen:
                initial_block_list.append(block)
                seen.add(block.Identifier)
        initial_block_list.sort(key=lambda x: x.BlockNum)

        for block in initial_block_list:
            logger.debug('initial block processing of block: %s', block)
            self.commit_transaction_block(block)
        self.InitialBlockList = None

        # generate a block, if none exists then generate and commit the root
        # block
        if self.GenesisLedger:
            logger.warn('node %s claims the genesis block',
                        self.gossip.LocalNode.Name)
            self.onGenesisBlock.fire(self)
            self.claim_transaction_block(self.build_transaction_block(True))
            self.GenesisLedger = False
        else:
            if self.MostRecentCommittedBlockID == common.NullIdentifier:
                logger.critical('no ledger for a new network node')
                return

        self.InitialLoad = False

        logger.info('finished processing initial transactions and blocks')

    def add_pending_transaction(self, txn, prepend=False, build_block=True):
        """Adds a transaction to the list of candidates for commit.

        Args:
            txn (Transaction.Transaction): The newly arrived transaction
        """
        with self._txn_lock:
            logger.debug('txnid: %s - add_pending_transaction',
                         txn.Identifier[:8])

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
                if prepend:
                    pending = OrderedDict()
                    pending[txn.Identifier] = True
                    pending.update(self.PendingTransactions)
                    self.PendingTransactions = pending
                else:
                    self.PendingTransactions[txn.Identifier] = True
                if self.TransactionEnqueueTime is None:
                    self.TransactionEnqueueTime = time.time()

            # if this is a transaction we requested, then remove it from
            # the list and look for any blocks that might be completed
            # as a result of processing the transaction
            if txn.Identifier in self.RequestedTransactions:
                logger.info('txnid %s - catching up',
                            txn.Identifier[:8])
                del self.RequestedTransactions[txn.Identifier]
                txn.InBlock = "Uncommitted"
                self.TransactionStore[txn.Identifier] = txn

                blockids = []
                for blockid in self.PendingBlockIDs:
                    if txn.Identifier in \
                            self.BlockStore[blockid].TransactionIDs:
                        blockids.append(blockid)

                for blockid in blockids:
                    self._handleblock(self.BlockStore[blockid])

            # there is a chance the we deferred creating a transaction block
            # because there were insufficient transactions, this is where
            # we check to see if there are now enough to run the validation
            # algorithm
            if not self.PendingTransactionBlock and build_block:
                self.PendingTransactionBlock = self.build_transaction_block()

    def commit_transaction_block(self, tblock):
        """Commits a block of transactions to the chain.

        Args:
            tblock (Transaction.TransactionBlock): A block of
                transactions which nodes agree to commit.
        """
        logger.debug('blkid: %s - processing incoming transaction block',
                     tblock.Identifier[:8])

        # Make sure this is a valid block, for now this will just check the
        # signature... more later
        if not tblock.verify_signature():
            logger.warn('blkid: %s - invalid block received from %s',
                        tblock.Identifier,
                        tblock.OriginatorID)
            return

        # Don't do anything with incoming blocks if we are initializing, wait
        # for the connections to be fully established
        if self.Initializing:
            logger.debug('blkid: %s - adding block to the pending queue',
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
            logger.info('blkid: %s - previously committed block',
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

    def request_missing_block(self, blockid, exceptions=None, request=None):
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
        if exceptions is None:
            exceptions = []
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

    def request_missing_txn(self, txnid, exceptions=None, request=None):
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
        if exceptions is None:
            exceptions = []
        logger.info('txnid: %s - missing_txn called', txnid[:8])

        now = time.time()

        if txnid in self.RequestedTransactions and now < \
                self.RequestedTransactions[txnid]:
            logger.info('txnid: %s - already in RequestedTxn', txnid[:8])
            return

        self.RequestedTransactions[txnid] = now + self.MissingRequestInterval

        self.JournalStats.MissingTxnRequestCount.increment()

        # if the request for the missing block came from another node, then
        # we need to reuse the request or we'll process multiple copies
        if not request:
            logger.info('txnid: %s - new request from same node(%s)',
                        txnid[:8], self.gossip.LocalNode.Name)
            request = transaction_message.TransactionRequestMessage(
                {'TransactionID': txnid})
            self.forward_message(request, exceptions=exceptions)
        else:
            logger.info('txnid: %s - new request from another node(%s)  ',
                        txnid[:8], self._id2name(request.SenderID))
            self.forward_message(request,
                                 exceptions=exceptions,
                                 initialize=False)

    def build_transaction_block(self, genesis=False):
        """Builds the next transaction block for the ledger.

        Note:
            This method will generally be overridden by derived classes.

        Args:
            genesis (bool): Whether to force the creation of the
                initial block.
        """

        self.onPreBuildBlock.fire(self, None)
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
            if not self.InitialLoad:
                self.PendingTransactionBlock = self.build_transaction_block()
        except Exception as e:
            logger.error("blkid: %s - Error advancing block chain: %s",
                         tblock.Identifier[:8], e)
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
                'blkid: %s - (fork) received disconnected from %s with'
                ' previous id %s, expecting %s',
                tblock.Identifier[:8],
                self._id2name(tblock.OriginatorID),
                tblock.PreviousBlockID[:8],
                self.MostRecentCommittedBlockID[:8])

            # First see if the chain rooted in tblock is the one we should use,
            # if it is not, then we are building on the correct block and
            # nothing needs to change

            assert self.MostRecentCommittedBlockID != common.NullIdentifier
            if cmp(tblock, self.MostRecentCommittedBlock) < 0:
                logger.info('blkid: %s - (fork) existing chain is the '
                            'valid one, discarding blkid: %s',
                            self.MostRecentCommittedBlockID[:8],
                            tblock.Identifier[:8],
                            )
                self.PendingTransactionBlock = pending
                return

            logger.info('blkid: %s - (fork) new chain is the valid one, '
                        ' replace the current chain blkid: %s',
                        tblock.Identifier[:8],
                        self.MostRecentCommittedBlockID[:8]
                        )

            # now find the root of the fork
            fork_id = self._findfork(tblock)

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
            logger.exception("blkid: %s - (fork) error resolving fork",
                             tblock.Identifier[:8])
            self.PendingTransactionBlock = pending
            raise
    #
    # UTILITY FUNCTIONS
    #

    def _handleblock(self, tblock):
        # pylint: disable=redefined-variable-type
        """
        Attempt to add a block to the chain.
        """

        assert tblock.Identifier in self.PendingBlockIDs

        with self._txn_lock:
            # initialize the state of this block
            self.BlockStore[tblock.Identifier] = tblock

            # if this block is the genesis block then we can assume that
            # it meets all criteria for dependent blocks
            if tblock.PreviousBlockID != common.NullIdentifier:
                # first test... do we have the previous block, if not then this
                # block remains incomplete awaiting the arrival of the
                # predecessor
                pblock = self.BlockStore.get(tblock.PreviousBlockID)
                if not pblock:
                    self.request_missing_block(tblock.PreviousBlockID)
                    return

                # second test... is the previous block invalid, if so then this
                # block will never be valid & can be completely removed from
                # consideration, for now I'm not removing the block from the
                # block store though we could substitute a check for the
                # previous block in the invalid block list
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
                logger.info("blkid: %s - missing transactions: %s",
                            tblock.Identifier, repr(missing))
                for txnid in missing:
                    self.request_missing_txn(txnid)
                    self.JournalStats.MissingTxnFromBlockCount.increment()
                return

            # at this point we know that the block is complete
            tblock.Status = transaction_block.Status.complete
            self.BlockStore[tblock.Identifier] = tblock

            # fifth test... run the checks for a valid block, generally
            # these are specific to the various transaction families or
            # consensus mechanisms
            try:
                if (not tblock.is_valid(self)
                        or not self.onBlockTest.fire(self, tblock)):
                    logger.debug('blkid: %s - block test failed',
                                 tblock.Identifier[:8])
                    self.PendingBlockIDs.discard(tblock.Identifier)
                    self.InvalidBlockIDs.add(tblock.Identifier)
                    tblock.Status = transaction_block.Status.invalid
                    self.BlockStore[tblock.Identifier] = tblock
                    return
            except NotAvailableException:
                tblock.Status = transaction_block.Status.retry
                self.BlockStore[tblock.Identifier] = tblock
                logger.debug('blkid: %s - NotAvailableException - not able to '
                             'verify, will retry later',
                             tblock.Identifier[:8])
                return

            # sixth test... verify that every transaction in the now complete
            # block is valid independently and build the new data store
            newstore = self._testandapplyblock(tblock)
            if newstore is None:
                logger.debug('blkid: %s - transaction validity test failed',
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

            if hasattr(tblock, 'AggregateLocalMean'):
                self.JournalStats.AggregateLocalMean.Value = \
                    tblock.AggregateLocalMean

            # time to apply the transactions in the block to get a new state
            self.GlobalStoreMap.commit_block_store(tblock.Identifier, newstore)
            self.BlockStore[tblock.Identifier] = tblock

            # remove the block from the pending block list
            self.PendingBlockIDs.discard(tblock.Identifier)

            # and now check to see if we should start to use this block as the
            # one on which we build a new chain

            # handle the easy, common case here where the new block extends the
            # current chain
            if tblock.PreviousBlockID == self.MostRecentCommittedBlockID:
                self.handle_advance(tblock)
            else:
                self.handle_fork(tblock)

            self._cleantransactionblocks()

            # check the other orphaned blocks to see if this
            # block connects one to the chain, if a new block is connected to
            # the chain then we need to go through the entire process again
            # with the newly connected block
            # Also checks if we have pending blocks that need to be retried. If
            # so adds them to the list to be handled.
            blockids = set()
            for blockid in self.PendingBlockIDs:
                if self.BlockStore[blockid].PreviousBlockID ==\
                        tblock.Identifier:
                    blockids.add(blockid)

            for blockid in blockids:
                self._handleblock(self.BlockStore[blockid])

            self.retry_blocks()

    def retry_blocks(self):
        # check the orphaned blocks to see if any had a recoverable validation
        # failure, if the did and the retry time has expired then send the
        # block to be revalidated. We only process the first expired block
        # in the list, as that will call this function that will process
        # the next block ready for retry. The retry will modify the
        # PendingBlockIDs set, so we can not be iterating the set as
        # the retry happens.
        retry_block = None
        for blockid in self.PendingBlockIDs:
            block = self.BlockStore[blockid]
            if block.Status == transaction_block.Status.retry:
                retry_block = block
                break

        if retry_block:
            logger.debug('blkid: %s - Retrying block validation.',
                         retry_block.Identifier[:8])
            self._handleblock(retry_block)

    def _trigger_retry_blocks(self, now):
        if time.time() > self.next_block_retry:
            self.next_block_retry = time.time() + self.BlockRetryInterval
            msg = transaction_block_message.BlockRetryMessage()
            self.sign_and_send_message(msg)

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

        with self._txn_lock:
            logger.info('blkid: %s - commit block from %s with previous '
                        'blkid: %s',
                        tblock.Identifier[:8],
                        self._id2name(tblock.OriginatorID),
                        tblock.PreviousBlockID[:8])

            assert tblock.Status == transaction_block.Status.valid

            # Remove all of the newly committed transactions from the
            # pending list and put them in the committed list
            for txnid in tblock.TransactionIDs:
                assert txnid in self.TransactionStore
                if txnid in self.PendingTransactions:
                    del self.PendingTransactions[txnid]

                txn = self.TransactionStore[txnid]
                txn.Status = transaction.Status.committed
                txn.InBlock = tblock.Identifier
                self.TransactionStore[txnid] = txn

            # Update the head of the chain
            self.MostRecentCommittedBlockID = tblock.Identifier
            self.ChainStore['MostRecentBlockID'] = \
                self.MostRecentCommittedBlockID
            self.JournalStats.PreviousBlockID.Value = \
                self.MostRecentCommittedBlockID
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

        with self._txn_lock:
            blockid = self.MostRecentCommittedBlockID
            block = self.BlockStore[blockid]
            assert block.Status == transaction_block.Status.valid

            # fire the event handler for block decommit
            self.onDecommitBlock.fire(self, block)

            # move the head of the chain back
            self.MostRecentCommittedBlockID = block.PreviousBlockID
            self.ChainStore['MostRecentBlockID'] = \
                self.MostRecentCommittedBlockID

            # this bizarre bit of code is intended to preserve the ordering of
            # transactions, where all committed transactions occur before
            # pending transactions
            pending = OrderedDict()
            for txnid in block.TransactionIDs:
                # there is a chance that this block is incomplete and some
                # of the transactions have not arrived, don't put
                # transactions into pending if we dont have the transaction
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

        with self._txn_lock:
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
                logger.exception('txnid: %s - unexpected exception '
                                 'when testing transaction block '
                                 'validity.',
                                 txnid[:8])
                return None

            return teststore

    def _findfork(self, tblock):
        """
        Find most recent predecessor of tblock that is in the committed
        chain, searching through at most depth blocks

        :param tblock PoetTransactionBlock:
        :param depth int: depth in the current chain to search, 0 implies all
        """

        blockids = set(self.committed_block_ids(0))
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

        with self._txn_lock:
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

            # as part of the process, we may identify transactions that
            # are invalid so go ahead and get rid of them, since these
            # had all dependencies met we know that they will never be valid
            for txnid in deltxns:
                self.JournalStats.InvalidTxnCount.increment()
                if txnid in self.TransactionStore:
                    txn = self.TransactionStore[txnid]
                    if txn.InBlock is None:
                        logger.debug("txnid: %s - deleting from transaction "
                                     "store", txnid)
                        del self.TransactionStore[txnid]
                if txnid in self.PendingTransactions:
                    logger.debug("txnid: %s - deleting from pending "
                                 "transactions", txnid)
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

        with self._txn_lock:
            logger.debug('txnid: %s - add transaction %s',
                         txn.Identifier[:8],
                         str(txn))

            # Because the dependencies may reorder transactions in the block
            # in a way that is different from the arrival order, this
            # transaction might already be in the block
            if txn.Identifier in addtxns:
                return True

            # First step in adding the transaction to the list is to make
            # sure that all dependent transactions are in the list already
            ready = True
            for dependencyID in txn.Dependencies:
                logger.debug('txnid: %s - check dependency %s',
                             txn.Identifier[:8], dependencyID[:8])

                # check to see if the dependency has already been committed
                if (dependencyID in self.TransactionStore and
                        (self.TransactionStore[dependencyID].Status ==
                         transaction.Status.committed)):
                    continue

                # check to see if the dependency is already in this block
                if dependencyID in addtxns:
                    continue

                # check to see if the dependency is among the transactions to
                # be deleted, if so then this transaction will never be valid
                # and we can just get rid of it
                if dependencyID in deltxns:
                    logger.info('txnid: %s - depends on deleted '
                                'transaction %s',
                                txn.Identifier[:8], dependencyID[:8])
                    deltxns.append(txn.Identifier)
                    ready = False
                    continue

                # recurse into the dependency, note that we need to make sure
                # there are no loops in the dependencies but not doing that
                # right now
                deptxn = self.TransactionStore.get(dependencyID)
                if deptxn and self._preparetransaction(addtxns, deltxns, store,
                                                       deptxn):
                    continue

                # at this point we cannot find the dependency so send out a
                # request for it and wait, we should set a timer on this
                # transaction so we can just throw it away if the dependencies
                # cannot be met
                ready = False

                logger.info('txnid: %s - missing %s, '
                            'calling request_missing_txn',
                            txn.Identifier[:8], dependencyID[:8])
                self.request_missing_txn(dependencyID)
                self.JournalStats.MissingTxnDepCount.increment()

            # if all of the dependencies have not been met then there isn't any
            # point in continuing on so bail out
            if not ready:
                txn.increment_age()
                self.TransactionStore[txn.Identifier] = txn
                logger.info('txnid: %s - not ready (age %s)',
                            txn.Identifier[:8], txn.age)
                if txn.age > self.MaxTxnAge:
                    logger.warn('txnid: %s - too old, dropping - %s',
                                txn.Identifier[:8], str(txn))
                    deltxns.append(txn.Identifier)
                return False

            # after all that work... we know the dependencies are met, so
            # see if # the transaction is valid, that is that all of the
            # preconditions encoded in the transaction itself are met
            txnstore = store.get_transaction_store(txn.TransactionTypeName)
            if txn.is_valid(txnstore):
                logger.debug('txnid: %s - is valid, adding to block',
                             txn.Identifier[:8])
                addtxns.append(txn.Identifier)
                txn.apply(txnstore)
                return True

            # because we have all of the dependencies but the transaction is
            # still invalid we know that this transaction is broken and we
            # can simply throw it away
            logger.warn(
                'txnid: %s - is not valid for this block, dropping - %s',
                txn.Identifier[:8], str(txn))
            logger.info(common.pretty_print_dict(txn.dump()))
            deltxns.append(txn.Identifier)
            return False

    def _cleantransactionblocks(self):
        """
        _cleantransactionblocks -- for blocks and transactions that are with
        high probability no longer going to change, clean out the bulk of the
        memory used to store the block and the corresponding transactions
        """
        with self._txn_lock:
            self.ChainStore.sync()
            self.TransactionStore.sync()
            self.BlockStore.sync()

            # with the state storage, we can flatten old blocks to reduce
            # memory footprint, they can always be recovered from
            # persistent storage later on, however, the flattening
            # process increases memory usage so we don't want to do
            # it too often, the code below keeps the number of blocks
            # kept in memory less than 2 * self.MaximumBlocksToKeep
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
        self.JournalStats = stats.Stats(self.gossip.LocalNode.Name, 'ledger')
        self.JournalStats.add_metric(stats.Counter('BlocksClaimed'))
        self.JournalStats.add_metric(stats.Value('PreviousBlockID', '0'))
        self.JournalStats.add_metric(stats.Counter('CommittedBlockCount'))
        self.JournalStats.add_metric(stats.Counter('CommittedTxnCount'))
        self.JournalStats.add_metric(stats.Counter('InvalidTxnCount'))
        self.JournalStats.add_metric(stats.Counter('MissingTxnRequestCount'))
        self.JournalStats.add_metric(stats.Counter('MissingTxnFromBlockCount'))
        self.JournalStats.add_metric(stats.Counter('MissingTxnDepCount'))
        self.JournalStats.add_metric(stats.Sample(
            'PendingBlockCount', lambda: self.PendingBlockCount))
        self.JournalStats.add_metric(stats.Sample(
            'PendingTxnCount',
            lambda: self.PendingTxnCount))

        self.gossip.StatDomains['ledger'] = self.JournalStats

        self.JournalConfigStats = stats.Stats(self.gossip.LocalNode.Name,
                                              'ledgerconfig')
        self.JournalConfigStats.add_metric(
            stats.Sample('MinimumTransactionsPerBlock',
                         lambda: self.MinimumTransactionsPerBlock))
        self.JournalConfigStats.add_metric(
            stats.Sample('MaximumTransactionsPerBlock',
                         lambda: self.MaximumTransactionsPerBlock))

        self.gossip.StatDomains['ledgerconfig'] = self.JournalConfigStats

    def _id2name(self, nodeid):
        if nodeid in self.gossip.NodeMap:
            return str(self.gossip.NodeMap[nodeid])

        if nodeid == self.gossip.LocalNode.Identifier:
            return str(self.gossip.LocalNode)

        store = self.GlobalStore.TransactionStores[
            '/EndpointRegistryTransaction']
        if nodeid in store and 'Name' in store[nodeid]:
            return str(store[nodeid]['Name'])

        return nodeid[:8]

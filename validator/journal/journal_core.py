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
import os

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
from sawtooth_signing import pbct_nativerecover as signing
from sawtooth_validator.consensus.consensus_base import Consensus

logger = logging.getLogger(__name__)


class Journal(object):
    """The base journal class.

    Attributes:
        maximum_blocks_to_keep (int): Maximum number of blocks to keep in
        cache.
        minimum_transactions_per_block (int): Minimum number of transactions
            per block.
        maximum_transactions_per_block (int): Maximum number of transactions
            per block.
        missing_request_interval (float): Time in seconds between sending
            requests for a missing transaction block.
        block_retry_interval (float): Time in seconds between retrying
            block validations that
        start_time (float): The initialization time of the journal in
            seconds since the epoch.
        initializing (bool): Whether or not the journal is in an
            initializing state.
        initial_load (bool): Whether or not the journal is in an initial
            loading state.
        initial_transactions (list): A list of initial transactions to
            process.
        initial_block_list (list): A list of initial blocks to process.
        onGenesisBlock (EventHandler): An EventHandler for functions
            to call when processing a genesis block.
        on_pre_build_block (EventHandler): An EventHandler for functions
            to call when before processing a build block.
        on_build_block (EventHandler): An EventHandler for functions
            to call when processing a build block.
        on_claim_block (EventHandler): An EventHandler for functions
            to call when processing a claim block.
        on_commit_block (EventHandler): An EventHandler for functions
            to call when processing a commit block.
        on_decommit_block (EventHandler): An EventHandler for functions
            to call when processing a decommit block.
        on_block_test (EventHandler): An EventHandler for functions
            to call when processing a block test.
        pending_transactions (dict): A dict of pending, unprocessed
            transactions.
        transaction_store (JournalStore): A dict-like object representing
            the persisted copy of the transaction store.
        block_store (JournalStore): A dict-like object representing the
            persisted copy of the block store.
        chain_store (JournalStore): A dict-like object representing the
            persisted copy of the chain store.
        local_store (JournalStore): A dict-like object representing the
            persisted local state of the journal.
        requested_transactions (dict): A dict of transactions which are
            not in the local cache, the details of which have been
            requested from peers.
        requested_blocks (dict): A dict of blocks which are not in the
            local cache, the details of which have been requested
            from peers.
        most_recent_committed_block_id (str): The block ID of the most
            recently committed block.
        pending_block (TransactionBlock): The constructed
            candidate transaction block to claim.
        pending_block_ids (builtin set): A set of pending block identifiers.
        invalid_block_ids (builtin set): A set of invalid block identifiers.
        FrontierBlockIDs (builtin set): A set of block identifiers for blocks
            which still need to be processed.
        global_store_map (GlobalStoreManager): Manages access to the
            various persistence stores.
    """

    def __init__(self,
                 local_node,
                 gossip,
                 gossip_dispatcher,
                 consensus,
                 permissioned_validators=None,
                 stat_domains=None,
                 minimum_transactions_per_block=None,
                 max_transactions_per_block=None,
                 max_txn_age=None,
                 data_directory=None,
                 store_type=None):
        """Constructor for the Journal class.

        Args:
            node (Node): The local node.
            DataDirectory (str):
        """
        self.local_node = local_node
        self.gossip = gossip
        self.dispatcher = MessageDispatcher(self, gossip_dispatcher)
        if not isinstance(consensus, Consensus):
            raise TypeError("Expected consensus to be subclass of the "
                            "Consensus abstract base class")
        self.consensus = consensus

        self.start_time = time.time()
        self.initializing = True
        self.initial_load = False

        self.initial_transactions = []
        self.initial_block_list = []

        # For storage management, minimum blocks to keep cached
        self.maximum_blocks_to_keep = 50

        # Minimum number of transactions per block
        if minimum_transactions_per_block is not None:
            self.minimum_transactions_per_block = \
                int(minimum_transactions_per_block)
        else:
            self.minimum_transactions_per_block = 1

        # Amount of time(in sec) transactions can wait to meet the
        # MinimumTransactionsPerBlock before a block gets built with
        # less then the MinimumTransactionsPerBlock count.
        # This is a safety measure to allow the validator network to function
        # with low transaction volume, such as network start up.
        self._maximum_transaction_wait_time = 60

        # Maximum number of transactions per block
        if max_transactions_per_block is not None:
            self.maximum_transactions_per_block = \
                int(max_transactions_per_block)
        else:
            self.maximum_transactions_per_block = 1000

        # Time between sending requests for a missing transaction block
        self.missing_request_interval = 30.0

        # Time between sending requests for a missing transaction block
        self.block_retry_interval = 10.0

        if max_txn_age is not None:
            self.max_txn_age = max_txn_age
        else:
            self.max_txn_age = 3

        self.restored = False

        # set up the event handlers that the transaction families can use
        self.on_genesis_block = event_handler.EventHandler('onGenesisBlock')
        self.on_pre_build_block = event_handler.EventHandler('onPreBuildBlock')
        self.on_build_block = event_handler.EventHandler('onBuildBlock')
        self.on_claim_block = event_handler.EventHandler('onClaimBlock')
        self.on_commit_block = event_handler.EventHandler('onCommitBlock')
        self.on_decommit_block = event_handler.EventHandler('onDecommitBlock')
        self.on_block_test = event_handler.EventHandler('onBlockTest')

        self._txn_lock = RLock()
        self.pending_transactions = OrderedDict()
        self.transaction_enqueue_time = None

        self.transaction_store = None
        self.block_store = None
        self.chain_store = None
        self.local_store = None
        self.global_store_map = None
        self.open_databases(store_type, data_directory)

        self.requested_transactions = {}
        self.requested_blocks = {}

        self.next_block_retry = time.time() + self.block_retry_interval

        self.dispatcher.on_heartbeat += self._trigger_retry_blocks
        self.dispatcher.on_heartbeat += self._check_claim_block

        self.most_recent_committed_block_id = common.NullIdentifier
        self.pending_block = None

        self.pending_block_ids = set()
        self.invalid_block_ids = set()

        # initialize the ledger stats data structures
        self._init_ledger_stats(stat_domains)

        # connect the message handlers
        journal_debug.register_message_handlers(self)
        transaction_message.register_message_handlers(self)
        transaction_block_message.register_message_handlers(self)
        journal_transfer.register_message_handlers(self)
        self.consensus.initialization_complete(self)
        self.permissioned_validators = permissioned_validators

    @classmethod
    def get_store_file(cls, node_name, store_name, data_dir,
                       store_type=None):
        store_type = 'shelf' if store_type is None else store_type
        dir = 'db' if data_dir is None else data_dir
        prefix = os.path.join(dir, str(node_name))
        postfix = '.shelf'
        if store_type in ['lmdb', 'cached-lmdb']:
            postfix = '.lmdb'
        if store_type in ['dbm']:
            postfix = '.dbm'
        return prefix + '_' + store_name + postfix

    def open_databases(self, store_type, data_directory):
        # this flag indicates whether we should create a completely new
        # database file or reuse an existing file
        store_type = 'shelf' if store_type is None else store_type
        if store_type in ['shelf', 'cached-shelf', 'lmdb', 'cached-lmdb']:
            def get_store(db_name, db_type):
                file_name = self.get_store_file(self.local_node, db_name,
                                                data_directory, db_type)
                db_flag = 'c' if os.path.isfile(file_name) else 'n'
                db_cls = None
                if db_type in ['shelf', 'cached-shelf']:
                    from sawtooth_validator.database import shelf_database
                    db_cls = shelf_database.ShelfDatabase
                elif db_type in ['lmdb', 'cached-lmdb']:
                    from sawtooth_validator.database import lmdb_database
                    db_cls = lmdb_database.LMDBDatabase
                db = db_cls(file_name, db_flag)
                if db_type in ['cached-shelf', 'cached-lmdb']:
                    from sawtooth_validator.database.database \
                        import CachedDatabase
                    db = CachedDatabase(db)
                return journal_store.JournalStore(db)

            self.transaction_store = get_store('txn', store_type)
            self.block_store = get_store('block', store_type)
            self.chain_store = get_store('chain', store_type)
            self.local_store = get_store('local', store_type)
        else:
            raise KeyError("%s is not a supported StoreType", store_type)

        # Set up the global store and transaction handlers
        gsm_fname = self.get_store_file(self.local_node, 'state',
                                        data_directory, 'dbm')
        db_flag = 'c' if os.path.isfile(gsm_fname) else 'n'
        self.global_store_map = GlobalStoreManager(gsm_fname, db_flag)

    @property
    def committed_block_count(self):
        """Returns the block number of the most recently committed block.

        Returns:
            int: most recently committed block number.
        """
        if self.most_recent_committed_block is not None:
            return self.most_recent_committed_block.BlockNum
        return 0

    @property
    def committed_txn_count(self):
        """Returns the committed transaction count.

        Returns:
            int: the transaction depth based on the most recently
                committed block.
        """
        return self.most_recent_committed_block.TransactionDepth

    @property
    def pending_block_count(self):
        """Returns the number of pending blocks.

        Returns:
            int: the number of pending blocks.
        """
        return len(self.pending_block_ids)

    @property
    def pending_txn_count(self):
        """Returns the number of pending transactions.

        Returns:
            int: the number of pending transactions.
        """
        return len(self.pending_transactions)

    def shutdown(self):
        """Shuts down the journal in an orderly fashion.
        """
        logger.info('close journal databases in preparation for shutdown')

        # Global store manager handles its own database
        self.global_store_map.close()

        self.transaction_store.close()
        self.block_store.close()
        self.chain_store.close()
        self.local_store.close()

    def add_transaction_store(self, family):
        """Add a transaction type-specific store to the global store.

        Args:
            family (transaction.Transaction): The transaction family.
        """
        tname = family.TransactionTypeName
        tstore = family.TransactionStoreType()
        self.global_store_map.add_transaction_store(tname, tstore)

    def get_transaction_store(self, family, block_id):
        """Retrieve a transaction-family-specific store from the global store

        Args:
            family (transaction.Transaction): The transaction family for which
                the store will be retrieved.
            block_id (str): Identifier for block for which the  store will be
                retrieved.
        """
        return \
            self.global_store_map.get_transaction_store(
                family.TransactionTypeName,
                block_id)

    @property
    def global_store(self):
        """Returns a reference to the global store associated with the
        most recently committed block that this validator possesses.

        Returns:
            Shelf: The block store.
        """
        blkid = self.most_recent_committed_block_id

        return self.global_store_map.get_block_store(blkid)

    @property
    def most_recent_committed_block(self):
        """Returns the most recently committed block.

        Returns:
            dict: the most recently committed block.
        """
        return self.block_store.get(self.most_recent_committed_block_id)

    def committed_block_ids(self, count=0):
        """Returns the list of block identifiers starting from the
        most recently committed block.

        Args:
            count (int): How many results should be returned.

        Returns:
            list: A list of committed block ids.
        """
        if count == 0:
            count = len(self.block_store)

        block_ids = []

        blkid = self.most_recent_committed_block_id
        while blkid != common.NullIdentifier and len(block_ids) < count:
            block_ids.append(blkid)
            blkid = self.block_store[blkid].PreviousBlockID

        return block_ids

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

        for block_id in self.block_store.iterkeys():
            count = 0
            blkid = block_id
            while blkid in self.block_store:
                if blkid in depths:
                    count += depths[blkid]
                    break

                blkid = self.block_store[blkid].PreviousBlockID
                count += 1

            depths[block_id] = count
            while blkid in self.block_store:
                blkid = self.block_store[blkid].PreviousBlockID
                if blkid in depths:
                    break

                count -= 1
                depths[blkid] = count

        block_list = sorted(list(depths), key=lambda blkid: depths[blkid])
        return block_list[-1]

    def restore(self):
        logger.info('restore ledger state from persistence')
        head = None
        try:
            head = self.chain_store['MostRecentBlockID']
        except KeyError:
            if len(self.block_store) > 0:
                logger.warn('unable to load the most recent block id; '
                            'recomputing')
                head = self.compute_chain_root()
        if head is not None:
            self.most_recent_committed_block_id = head
            self.global_store_map.get_block_store(head)
            logger.info('commit head: %s', head)
            self.restored = True
        else:
            logger.warn('unable to restore ledger state')

    def initialization_complete(self):
        """Processes all invocations that arrived while the ledger was
        being initialized.
        """
        logger.info('process initial transactions and blocks')

        self.initializing = False
        self.initial_load = True

        if self.restored is True:
            return

        for txn in self.initial_transactions:
            self.add_pending_transaction(txn, build_block=False)
        self.initial_transactions = None

        logger.debug('initial block list: %s', self.initial_block_list)

        # Generate a unique list of initial blocks to process, sorted
        # by BlockNum
        initial_block_list = []
        seen = set()
        for block in self.initial_block_list:
            if block.Identifier not in seen:
                initial_block_list.append(block)
                seen.add(block.Identifier)
        initial_block_list.sort(key=lambda x: x.BlockNum)

        for block in initial_block_list:
            logger.debug('initial block processing of block: %s', block)
            self.commit_transaction_block(block)
        self.initial_block_list = None

        # verify root block exits
        if self.most_recent_committed_block_id == common.NullIdentifier:
            logger.critical('no ledger for a new network node')
            return

        self.initial_load = False
        logger.info('finished processing initial transactions and blocks')

    def add_pending_transaction(self, txn, prepend=False, build_block=True):
        """Adds a transaction to the list of candidates for commit.

        Args:
            txn (Transaction.Transaction): The newly arrived transaction
            prepend - add to front of list
            build_block - force build of transaction block
        """
        with self._txn_lock:
            logger.debug('txnid: %s - add_pending_transaction',
                         txn.Identifier[:8])

            # nothing more to do, we are initializing
            if self.initializing:
                self.initial_transactions.append(txn)
                return

            # if we already have the transaction there is nothing to do
            if txn.Identifier in self.transaction_store:
                assert self.transaction_store[txn.Identifier]
                return

            # add it to the transaction store
            txn.Status = transaction.Status.pending
            self.transaction_store[txn.Identifier] = txn
            if txn.add_to_pending():
                if prepend:
                    pending = OrderedDict()
                    pending[txn.Identifier] = True
                    pending.update(self.pending_transactions)
                    self.pending_transactions = pending
                else:
                    self.pending_transactions[txn.Identifier] = True
                if self.transaction_enqueue_time is None:
                    self.transaction_enqueue_time = time.time()

            # if this is a transaction we requested, then remove it from
            # the list and look for any blocks that might be completed
            # as a result of processing the transaction
            if txn.Identifier in self.requested_transactions:
                logger.info('txnid %s - catching up',
                            txn.Identifier[:8])
                del self.requested_transactions[txn.Identifier]
                txn.InBlock = "Uncommitted"
                self.transaction_store[txn.Identifier] = txn

                block_ids = []
                for block_id in self.pending_block_ids:
                    if txn.Identifier in \
                            self.block_store[block_id].TransactionIDs:
                        block_ids.append(block_id)

                for block_id in block_ids:
                    self._handleblock(self.block_store[block_id])

            # there is a chance the we deferred creating a transaction block
            # because there were insufficient transactions, this is where
            # we check to see if there are now enough to run the validation
            # algorithm
            if not self.pending_block and build_block:
                self.pending_block = self.build_block()

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
        if self.initializing:
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
            if tblock.Identifier in self.block_store:
                del self.block_store[tblock.Identifier]

            self.initial_block_list.append(tblock)
            return

        # If this is a block we requested, then remove it from the list
        if tblock.Identifier in self.requested_blocks:
            del self.requested_blocks[tblock.Identifier]

        # Make sure that we have not already processed this block
        if tblock.Identifier in self.block_store:
            logger.info('blkid: %s - previously committed block',
                        tblock.Identifier[:8])
            return

        # Make sure we initialize the state of the block
        tblock.Status = transaction_block.Status.incomplete

        # Add this block to block pool, mark as orphaned until it is committed
        self.pending_block_ids.add(tblock.Identifier)
        self.block_store[tblock.Identifier] = tblock

        self._handleblock(tblock)

    def claim_block(self, block=None):
        """Fires the on_claim_block event handler and locally commits the
        transaction block.

        Args:
            block (Transaction.TransactionBlock): A block of
                transactions to claim.
        """
        with self._txn_lock:
            if block is None:
                if self.pending_block is not None:
                    block = self.pending_block
                    self.pending_block = None
                else:
                    return  # No block to claim

            # fire the event handler for claiming the transaction block
            logger.info('node %s validates block with %d transactions',
                        self.local_node.Name, len(block.TransactionIDs))

            # Claim the block
            self.consensus.claim_block(self, block)
            block.sign_from_node(self.local_node)
            self.JournalStats.BlocksClaimed.increment()

            # Fire the event handler for block claim
            self.on_claim_block.fire(self, block)

            # And send out the message that we won
            msg = self.consensus.create_block_message(block)
            self.gossip.broadcast_message(msg)

    def request_missing_block(self, block_id, exceptions=None, request=None):
        """Requests neighbors to send a transaction block.

        This method is called when one block references another block
        that is not currently in the local cache. Only send the request
        periodically to avoid spamming the network with duplicate requests.

        Args:
            block_id (str): The identifier of the missing block.
            exceptions (list): Identifiers of nodes we know don't have
            the block.
            request (message.Message): A previously initialized message for
                sending the request; avoids duplicates.
        """
        if exceptions is None:
            exceptions = []
        now = time.time()

        if block_id in self.requested_blocks and now < self.requested_blocks[
                block_id]:
            return

        self.requested_blocks[block_id] = now + self.missing_request_interval

        # if the request for the missing block came from another node, then
        # we need to reuse the request or we'll process multiple copies
        if not request:
            request = transaction_block_message.BlockRequestMessage(
                {'BlockID': block_id})
            self.gossip.forward_message(request, exceptions=exceptions)
        else:
            self.gossip.forward_message(request,
                                        exceptions=exceptions,
                                        initialize=False)

    def request_missing_txn(self, txn_id, exceptions=None, request=None):
        """Requests that neighbors send a transaction.

        This method is called when a block references a transaction
        that is not currently in the local cache. Only send the request
        periodically to avoid spamming the network with duplicate requests.

        Args:
            txn_id (str): The identifier of the missing transaction.
            exceptions (list): Identifiers of nodes we know don't have
                the block.
            request (message.Message): A previously initialized message for
                sending the request; avoids duplicates.
        """
        logger.info('txnid: %s - missing_txn called', txn_id[:8])

        now = time.time()

        if txn_id in self.requested_transactions and now < \
                self.requested_transactions[txn_id]:
            logger.info('txnid: %s - already in RequestedTxn', txn_id[:8])
            return

        self.requested_transactions[txn_id] = now + \
            self.missing_request_interval

        self.JournalStats.MissingTxnRequestCount.increment()

        # if the request for the missing block came from another node, then
        # we need to reuse the request or we'll process multiple copies
        if not request:
            logger.info('txnid: %s - new request from same node(%s)',
                        txn_id[:8], self.local_node.Name)
            request = transaction_message.TransactionRequestMessage(
                {'TransactionID': txn_id})
            self.gossip.forward_message(request, exceptions=exceptions)
        else:
            logger.info('txnid: %s - new request from another node(%s)  ',
                        txn_id[:8],
                        self.gossip.node_id_to_name(request.SenderID))
            self.gossip.forward_message(request,
                                        exceptions=exceptions,
                                        initialize=False)

    def build_block(self, genesis=False):
        """Builds the next transaction block for the ledger.

        Note:
            This method will generally be overridden by derived classes.

        Args:
            genesis (bool): Whether to force the creation of the
                initial block. Used during genesis block creation
        """
        assert self.local_node.SigningKey
        pub_key = signing.encode_pubkey(
            signing.generate_pubkey(self.local_node.SigningKey), "hex")
        new_block = self.consensus.create_block(pub_key)

        # in some cases the consensus will not build candidate blocks.
        # for example devmode non block publishing nodes.
        if new_block is None:
            return

        if not genesis and len(self.pending_transactions) == 0:
            return None

        logger.debug('attempt to build transaction block extending %s',
                     self.most_recent_committed_block_id[:8])

        # Create a new block from all of our pending transactions
        new_block.BlockNum = self.most_recent_committed_block.BlockNum \
            + 1 if self.most_recent_committed_block is not None else 0
        new_block.PreviousBlockID = self.most_recent_committed_block_id
        self.on_pre_build_block.fire(self, new_block)

        logger.debug('created new pending block')

        txn_list = self._prepare_transaction_list(
            self.maximum_transactions_per_block)
        logger.info('build transaction block to extend %s with %s '
                    'transactions',
                    self.most_recent_committed_block_id[:8], len(txn_list))

        if len(txn_list) == 0 and not genesis:
            return None

        new_block.TransactionIDs = txn_list

        self.consensus.initialize_block(self, new_block)

        # fire the build block event handlers
        self.on_build_block.fire(self, new_block)

        for txn_id in new_block.TransactionIDs:
            txn = self.transaction_store[txn_id]
            txn.InBlock = "Uncommitted"
            self.transaction_store[txn_id] = txn

        return new_block

    def handle_advance(self, tblock):
        """Handles the case where we are attempting to commit a block that
        advances the current block chain.

        Args:
            tblock (Transaction.TransactionBlock): A block of
                transactions to advance.
        """
        assert tblock.Status == transaction_block.Status.valid

        pending = self.pending_block
        self.pending_block = None
        try:
            self._commit_block(tblock)
            if not self.initial_load:
                self.pending_block = self.build_block()
        except Exception as e:
            logger.error("blkid: %s - Error advancing block chain: %s",
                         tblock.Identifier[:8], e)
            self.pending_block = pending
            raise

    def handle_fork(self, tblock):
        """Handle the case where we are attempting to commit a block
        that is not connected to the current block chain.

        Args:
            tblock (Transaction.TransactionBlock): A disconnected block.
        """

        pending = self.pending_block
        self.pending_block = None
        try:
            assert tblock.Status == transaction_block.Status.valid

            logger.info(
                'blkid: %s - (fork) received disconnected from %s with'
                ' previous id %s, expecting %s',
                tblock.Identifier[:8],
                self.gossip.node_id_to_name(tblock.OriginatorID),
                tblock.PreviousBlockID[:8],
                self.most_recent_committed_block_id[:8])

            # First see if the chain rooted in tblock is the one we should use,
            # if it is not, then we are building on the correct block and
            # nothing needs to change

            assert self.most_recent_committed_block_id != common.NullIdentifier
            if cmp(tblock, self.most_recent_committed_block) < 0:
                logger.info('blkid: %s - (fork) existing chain is the '
                            'valid one, discarding blkid: %s',
                            self.most_recent_committed_block_id[:8],
                            tblock.Identifier[:8],
                            )
                self.pending_block = pending
                return

            logger.info('blkid: %s - (fork) new chain is the valid one, '
                        ' replace the current chain blkid: %s',
                        tblock.Identifier[:8],
                        self.most_recent_committed_block_id[:8]
                        )

            # now find the root of the fork
            fork_id = self._find_fork(tblock)

            assert fork_id

            # at this point we have a new chain that is longer than the current
            # one, need to move the blocks in the current chain that follow the
            # fork into the orphaned pool and then move the blocks from the new
            # chain into the committed pool and finally rebuild the global
            # store

            # move the previously committed blocks into the orphaned list
            self._decommit_block_chain(fork_id)

            # move the new blocks from the orphaned list to the committed list
            self._commit_block_chain(tblock.Identifier, fork_id)
            self.pending_block = self.build_block()
        except Exception as e:
            logger.exception("blkid: %s - (fork) error resolving fork",
                             tblock.Identifier[:8])
            self.pending_block = pending
            raise

    #
    # UTILITY FUNCTIONS
    #
    def _handleblock(self, tblock):
        # pylint: disable=redefined-variable-type
        """
        Attempt to add a block to the chain.
        """

        assert tblock.Identifier in self.pending_block_ids

        with self._txn_lock:
            # initialize the state of this block
            self.block_store[tblock.Identifier] = tblock

            # if this block is the genesis block then we can assume that
            # it meets all criteria for dependent blocks
            if tblock.PreviousBlockID != common.NullIdentifier:
                # first test... do we have the previous block, if not then this
                # block remains incomplete awaiting the arrival of the
                # predecessor
                pblock = self.block_store.get(tblock.PreviousBlockID)
                if not pblock:
                    self.request_missing_block(tblock.PreviousBlockID)
                    return

                # second test... is the previous block invalid, if so then this
                # block will never be valid & can be completely removed from
                # consideration, for now I'm not removing the block from the
                # block store though we could substitute a check for the
                # previous block in the invalid block list
                if pblock.Status == transaction_block.Status.invalid:
                    self.pending_block_ids.discard(tblock.Identifier)
                    self.invalid_block_ids.add(tblock.Identifier)
                    tblock.Status = transaction_block.Status.invalid
                    self.block_store[tblock.Identifier] = tblock
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
            self.block_store[tblock.Identifier] = tblock

            # fifth test... run the checks for a valid block, generally
            # these are specific to the various transaction families or
            # consensus mechanisms
            try:
                if (not tblock.is_valid(self)
                        or not self.on_block_test.fire(self, tblock)):
                    logger.debug('blkid: %s - block test failed',
                                 tblock.Identifier[:8])
                    self.pending_block_ids.discard(tblock.Identifier)
                    self.invalid_block_ids.add(tblock.Identifier)
                    tblock.Status = transaction_block.Status.invalid
                    self.block_store[tblock.Identifier] = tblock
                    return
            except NotAvailableException:
                tblock.Status = transaction_block.Status.retry
                self.block_store[tblock.Identifier] = tblock
                logger.debug('blkid: %s - NotAvailableException - not able to '
                             'verify, will retry later',
                             tblock.Identifier[:8])
                return

            # sixth test... verify that every transaction in the now complete
            # block is valid independently and build the new data store
            newstore = self._test_and_apply_block(tblock)
            if newstore is None:
                logger.debug('blkid: %s - transaction validity test failed',
                             tblock.Identifier[:8])
                self.pending_block_ids.discard(tblock.Identifier)
                self.invalid_block_ids.add(tblock.Identifier)
                tblock.Status = transaction_block.Status.invalid
                self.block_store[tblock.Identifier] = tblock
                return

            # at this point we know that the block is valid
            tblock.Status = transaction_block.Status.valid
            tblock.CommitTime = time.time() - self.start_time
            tblock.update_block_weight(self)

            if hasattr(tblock, 'AggregateLocalMean') or \
                    hasattr(tblock, 'aggregate_local_mean'):
                self.JournalStats.AggregateLocalMean.Value = \
                    tblock.aggregate_local_mean

            # time to apply the transactions in the block to get a new state
            self.global_store_map.commit_block_store(tblock.Identifier,
                                                     newstore)
            self.block_store[tblock.Identifier] = tblock

            # remove the block from the pending block list
            self.pending_block_ids.discard(tblock.Identifier)

            # and now check to see if we should start to use this block as the
            # one on which we build a new chain

            # handle the easy, common case here where the new block extends the
            # current chain
            if tblock.PreviousBlockID == self.most_recent_committed_block_id:
                self.handle_advance(tblock)
            else:
                self.handle_fork(tblock)

            self._clean_transaction_blocks()

            # check the other orphaned blocks to see if this
            # block connects one to the chain, if a new block is connected to
            # the chain then we need to go through the entire process again
            # with the newly connected block
            # Also checks if we have pending blocks that need to be retried. If
            # so adds them to the list to be handled.
            blockids = set()
            for blockid in self.pending_block_ids:
                if self.block_store[blockid].PreviousBlockID ==\
                        tblock.Identifier:
                    blockids.add(blockid)

            for blockid in blockids:
                self._handleblock(self.block_store[blockid])

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
        for blockid in self.pending_block_ids:
            block = self.block_store[blockid]
            if block.Status == transaction_block.Status.retry:
                retry_block = block
                break

        if retry_block:
            logger.debug('blkid: %s - Retrying block validation.',
                         retry_block.Identifier[:8])
            self._handleblock(retry_block)

    def _trigger_retry_blocks(self, now):
        if time.time() > self.next_block_retry:
            self.next_block_retry = time.time() + self.block_retry_interval
            msg = transaction_block_message.BlockRetryMessage()
            self.gossip.broadcast_message(msg)

    def _commit_block_chain(self, blockid, forkid):
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
            block = self.block_store[b_id]
            chain.append(block)
            b_id = block.PreviousBlockID
        chain.reverse()
        for block in chain:
            self._commit_block(block)

    def _commit_block(self, tblock):
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
                        self.gossip.node_id_to_name(tblock.OriginatorID),
                        tblock.PreviousBlockID[:8])

            assert tblock.Status == transaction_block.Status.valid

            # Remove all of the newly committed transactions from the
            # pending list and put them in the committed list
            for txnid in tblock.TransactionIDs:
                assert txnid in self.transaction_store
                if txnid in self.pending_transactions:
                    del self.pending_transactions[txnid]

                txn = self.transaction_store[txnid]
                txn.Status = transaction.Status.committed
                txn.InBlock = tblock.Identifier
                self.transaction_store[txnid] = txn

            # Update the head of the chain
            self.most_recent_committed_block_id = tblock.Identifier
            self.chain_store['MostRecentBlockID'] = \
                self.most_recent_committed_block_id
            self.JournalStats.PreviousBlockID.Value = \
                self.most_recent_committed_block_id

            # Update stats
            self.JournalStats.CommittedTxnCount.increment(len(
                tblock.TransactionIDs))
            self.JournalStats.CommittedBlockCount.Value = \
                self.committed_block_count + 1

            # fire the event handler for block commit
            self.on_commit_block.fire(self, tblock)

    def _decommit_block_chain(self, forkid):
        """
        decommit blocks from the head of the chain through the forked block

        Args:
            forkid (UUID) -- identifier of the block where the fork occurred
        """
        blockid = self.most_recent_committed_block_id
        while blockid != forkid:
            self._decommit_block()
            blockid = self.most_recent_committed_block_id

    def _decommit_block(self):
        """
        Move the head of the block chain from the committed pool to the
        orphaned pool and move all transactions in the block back into the
        pending transaction list.
        """

        with self._txn_lock:
            blockid = self.most_recent_committed_block_id
            block = self.block_store[blockid]
            assert block.Status == transaction_block.Status.valid

            # fire the event handler for block decommit
            self.on_decommit_block.fire(self, block)

            # move the head of the chain back
            self.most_recent_committed_block_id = block.PreviousBlockID
            self.chain_store['MostRecentBlockID'] = \
                self.most_recent_committed_block_id

            # this bizarre bit of code is intended to preserve the ordering of
            # transactions, where all committed transactions occur before
            # pending transactions
            pending = OrderedDict()
            for txnid in block.TransactionIDs:
                # there is a chance that this block is incomplete and some
                # of the transactions have not arrived, don't put
                # transactions into pending if we dont have the transaction
                txn = self.transaction_store.get(txnid)
                if txn:
                    txn.Status = transaction.Status.pending
                    self.transaction_store[txnid] = txn

                    if txn.add_to_pending():
                        pending[txnid] = True

            pending.update(self.pending_transactions)
            self.pending_transactions = pending

            # update stats
            self.JournalStats.CommittedBlockCount.Value = \
                self.committed_block_count + 1
            self.JournalStats.CommittedTxnCount.increment(-len(
                block.TransactionIDs))

    def _test_and_apply_block(self, tblock):
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
            teststore = self.global_store_map.get_block_store(
                tblock.PreviousBlockID).clone_block()

            # apply the transactions
            try:
                for txnid in tblock.TransactionIDs:
                    txn = self.transaction_store[txnid]
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

    def _find_fork(self, tblock):
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

            assert forkid in self.block_store
            forkid = self.block_store[forkid].PreviousBlockID

        return None

    def _prepare_transaction_list(self, maxcount=0):
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
            store = self.global_store.clone_block()
            for txnid in self.pending_transactions.iterkeys():
                txn = self.transaction_store[txnid]
                if txn:
                    self._prepare_transaction(addtxns, deltxns, store, txn)

                if maxcount and len(addtxns) >= maxcount:
                    break

            # as part of the process, we may identify transactions that
            # are invalid so go ahead and get rid of them, since these
            # had all dependencies met we know that they will never be valid
            for txnid in deltxns:
                self.JournalStats.InvalidTxnCount.increment()
                if txnid in self.transaction_store:
                    txn = self.transaction_store[txnid]
                    if txn.InBlock is None:
                        logger.debug("txnid: %s - deleting from transaction "
                                     "store", txnid)
                        del self.transaction_store[txnid]
                if txnid in self.pending_transactions:
                    logger.debug("txnid: %s - deleting from pending "
                                 "transactions", txnid)
                    del self.pending_transactions[txnid]

            return addtxns

    def _prepare_transaction(self, addtxns, deltxns, store, txn):
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
                if (dependencyID in self.transaction_store and
                        (self.transaction_store[dependencyID].Status ==
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
                deptxn = self.transaction_store.get(dependencyID)
                if deptxn and self._prepare_transaction(addtxns,
                                                        deltxns,
                                                        store,
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
                self.transaction_store[txn.Identifier] = txn
                logger.info('txnid: %s - not ready (age %s)',
                            txn.Identifier[:8], txn.age)
                if txn.age > self.max_txn_age:
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

    def _clean_transaction_blocks(self):
        """
        _clean_transaction_blocks -- for blocks and transactions that are with
        high probability no longer going to change, clean out the bulk of the
        memory used to store the block and the corresponding transactions
        """
        with self._txn_lock:
            self.chain_store.sync()
            self.transaction_store.sync()
            self.block_store.sync()

            # with the state storage, we can flatten old blocks to reduce
            # memory footprint, they can always be recovered from
            # persistent storage later on, however, the flattening
            # process increases memory usage so we don't want to do
            # it too often, the code below keeps the number of blocks
            # kept in memory less than 2 * self.MaximumBlocksToKeep
            if self.most_recent_committed_block.BlockNum \
                    % self.maximum_blocks_to_keep == 0:
                logger.info('compress global state for block number %s',
                            self.most_recent_committed_block.BlockNum)
                depth = 0
                blockid = self.most_recent_committed_block_id
                while (blockid != common.NullIdentifier and
                       depth < self.maximum_blocks_to_keep):
                    blockid = self.block_store[blockid].PreviousBlockID
                    depth += 1

                if blockid != common.NullIdentifier:
                    logger.debug('flatten storage for block %s', blockid)
                    self.global_store_map.flatten_block_store(blockid)

    def _init_ledger_stats(self, stat_domains):
        self.JournalStats = stats.Stats(self.local_node.Name, 'ledger')
        self.JournalStats.add_metric(stats.Counter('BlocksClaimed'))
        self.JournalStats.add_metric(stats.Value('PreviousBlockID', '0'))
        self.JournalStats.add_metric(stats.Value('CommittedBlockCount', 0))
        self.JournalStats.add_metric(stats.Counter('CommittedTxnCount'))
        self.JournalStats.add_metric(stats.Counter('InvalidTxnCount'))
        self.JournalStats.add_metric(stats.Counter('MissingTxnRequestCount'))
        self.JournalStats.add_metric(stats.Counter('MissingTxnFromBlockCount'))
        self.JournalStats.add_metric(stats.Counter('MissingTxnDepCount'))
        self.JournalStats.add_metric(stats.Sample(
            'PendingBlockCount', lambda: self.pending_block_count))
        self.JournalStats.add_metric(stats.Sample(
            'PendingTxnCount',
            lambda: self.pending_txn_count))
        self.JournalConfigStats = stats.Stats(self.local_node.Name,
                                              'ledgerconfig')
        self.JournalConfigStats.add_metric(
            stats.Sample('MinimumTransactionsPerBlock',
                         lambda: self.minimum_transactions_per_block))
        self.JournalConfigStats.add_metric(
            stats.Sample('MaximumTransactionsPerBlock',
                         lambda: self.maximum_transactions_per_block))
        if stat_domains is not None:
            stat_domains['journal'] = self.JournalStats
            stat_domains['journalconfig'] = self.JournalConfigStats

    def _check_claim_block(self, now):
        with self._txn_lock:
            if not self.pending_block:
                if self.transaction_enqueue_time is not None:
                    transaction_time_waiting = \
                        now - self.transaction_enqueue_time
                else:
                    transaction_time_waiting = 0
                txn_list = self._prepare_transaction_list()
                txn_count = len(txn_list)
                build_block = (
                    txn_count > self.minimum_transactions_per_block or
                    (txn_count > 0 and
                        transaction_time_waiting >
                        self._maximum_transaction_wait_time))
                if build_block:
                    self.pending_block = self.build_block()
                    # we know that the transaction list is a subset of the
                    # pending transactions, if it is less then all of them
                    # then set the TransactionEnqueueTime we can track these
                    # transactions wait time.
                    remaining_transactions = \
                        len(self.pending_transactions) - txn_count
                    self.transaction_enqueue_time =\
                        time.time() if remaining_transactions > 0 else None

        with self._txn_lock:
            if self.pending_block and \
                    self.consensus.check_claim_block(
                        self,
                        self.pending_block,
                        now):
                self.claim_block()

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

import anydbm
import logging
import copy

import cbor

from gossip.common import cbor2dict, dict2cbor, NullIdentifier

logger = logging.getLogger(__name__)


class ReadOnlyException(BaseException):
    """An exception thrown when an update is attempted on a read-only store.
    """
    pass


class GlobalStoreManager(object):
    """The GlobalStoreManager class encapsulates persistent management
    of state associated with blocks in the ledger.

    To use the the class, first create a BlockStore that is initialized with
    an empty store (which should be a subclass of the KeyValueStore class)
    for each transaction family in the ledger. Commit the initial block
    with the method CommitRootBlock. This step is necessary whether or not
    this is the first time the validator is run.

    Attributes:
        RootBlockID (str): The ID of the root block.
    """

    RootBlockID = NullIdentifier

    def __init__(self, blockstorefile='blockstore', dbmode='c'):
        """Initialize a GlobalStoreManager, opening the database file.

        Args:
            blockstorefile (str): The name of the file to use for
                persistent data.
            dbmode (str): The mode used to open the file (see anydbm
                parameters).
        """
        logger.info('create blockstore from file %s with flag %s',
                    blockstorefile, dbmode)

        self._blockmap = {}
        self._persistmap = anydbm.open(blockstorefile, dbmode)

        rootstore = BlockStore()
        rootstore.commit_block(self.RootBlockID, )
        self._blockmap[self.RootBlockID] = rootstore
        self._persistmap[self.RootBlockID] = \
            dict2cbor(rootstore.dump_block(True))
        self._persistmap.sync()

        logger.debug('the persistent block store has %s keys',
                     len(self._persistmap))

    def close(self):
        """Close the database file.
        """
        self._persistmap.close()

    def add_transaction_store(self, tname, tstore):
        """Registers a data store type with a particular transaction type.

        Args:
           tname (str): The name of the transaction type.
           tstore (KeyValueStore): The data store to associate with the
               transaction type.
        """

        # we should really only be adding transaction stores to the
        # root block, if this fails we need to think more about the
        # initialization
        assert len(self._blockmap) == 1

        rootstore = self._blockmap[self.RootBlockID]
        rootstore.add_transaction_store(tname, tstore)

        rootstore.commit_block(self.RootBlockID)
        self._blockmap[self.RootBlockID] = rootstore
        self._persistmap[self.RootBlockID] = \
            dict2cbor(rootstore.dump_block(True))
        self._persistmap.sync()

    def commit_block_store(self, blockid, blockstore):
        """Associates the blockstore with the blockid and commits
        the blockstore to disk.

        Marks the blockstore read only as part of the process.

        Args:
            blockid (str): The identifier to associate with the block.
            blockstore (global_store_manager.BlockStore): An initialized
                blockstore to be used as the root store.
        """

        # if we commit a block then we know that either this is the genesis
        # block or that the previous block is committed already
        assert blockstore.PreviousBlockID in self._persistmap

        blockstore.commit_block(blockid)
        self._blockmap[blockid] = blockstore
        self._persistmap[blockid] = dict2cbor(blockstore.dump_block(True))
        self._persistmap.sync()

    def require_store(self, blockid):
        """Ensure that the store for this block (including all dependent
        blocks) is loaded into the _blockmap
        :param str blockid: identifier to associate with the block
        """

        # this is all about removing recursion... yes, recursion is a useful
        # thing... however python is not really very friendly to deep recursion
        # and since this might go through the entire chain of blocks... seems
        # like avoiding recursion is a very useful thing

        # pass 1... build the list of blocks that we need to load in order
        # to load the current block
        blocklist = []
        while blockid not in self._blockmap:
            logger.info('add block %s to the queue for loading', blockid)
            blocklist.insert(0, blockid)

            if blockid not in self._persistmap:
                raise KeyError('unknown block', blockid)

            blockinfo = cbor2dict(self._persistmap[blockid])
            blockid = blockinfo['PreviousBlockID']

        # pass 2... starting with the oldest block, begin to load
        # the stores
        for blockid in blocklist:
            logger.info('load block %s from storage', blockid)
            blockinfo = cbor.loads(self._persistmap[blockid])
            prevstore = self._blockmap[blockinfo['PreviousBlockID']]
            blockstore = prevstore.clone_block(blockinfo, True)
            blockstore.commit_block(blockid)
            self._blockmap[blockid] = blockstore

    def get_block_store(self, blockid):
        """Gets the blockstore associated with a particular blockid.

        This method will ensure that all previous block stores are
        loaded as well.

        Args:
            blockid (str): Identifier associated with the block.

        Returns:
            global_store_manager.BlockStore: The blockstore associated with
                the identifier.
        """

        self.require_store(blockid)
        return self._blockmap[blockid]

    def flush_block_store(self, blockid):
        """Removes the memory copy of this block and all predecessors.

        Note:
            Generally this is done through the FlattenBlockStore method.

        Args:
            blockid (str): Identifier associated with the block.
        """

        blocklist = []
        while blockid != self.RootBlockID:
            blockstore = self._blockmap.get(blockid)
            if blockstore is None:
                break
            blocklist.insert(0, blockid)
            blockid = blockstore.PreviousBlockID

        for blockid in blocklist:
            del self._blockmap[blockid]

    def flatten_block_store(self, blockid):
        """Collapses the history of this blockstore into a single blockstore.

        Flattening creates duplicate copies of the objects so it is
        important to release the history of the blockstore from memory.
        It is best if this is called only for relatively old blocks
        that are unlikely to be rolled back.

        Args:
            blockid (str): Identifier associated with the block.
        """

        blockstore = self.get_block_store(blockid)
        blockstore.flatten()

        self.flush_block_store(blockstore.PreviousBlockID)


class BlockStore(object):
    """The BlockManager class captures the ledger state associated with
    a single block.

    The ledger consists of a copy of the data store associated with
    each transaction family as it exists after all transactions in the
    block have been applied to the state from the preceding block.

    With the exception of the root block, all others should be created
    through the clone_block method which will preserve the ordering of
    the stores.

    Attributes:
        PrevBlock (global_store_manager.BlockStore): The previous block.
        BlockID (str): The ID of the root block.
        TransactionStores (dict): The transaction stores associated with
            this block store.
    """

    def __init__(self, prevblock=None, blockinfo=None, readonly=False):
        """Initializes a new BlockStore.

        Args:
            prevblock (global_store_manager.BlockStore): Optional parameter
                to initialize previous block pointer, required for all but the
                root block.
            blockinfo (dict): Optional initial data for the block.
        """

        self.PrevBlock = prevblock

        self.BlockID = GlobalStoreManager.RootBlockID
        self.TransactionStores = {}

        if self.PrevBlock:
            for tname, tstore in self.PrevBlock.TransactionStores.iteritems():
                storeinfo = blockinfo['TransactionStores'][
                    tname] if blockinfo else None
                self.add_transaction_store(
                    tname, tstore.clone_store(storeinfo, readonly))

    @property
    def PreviousBlockID(self):
        """
        Return the identifier associated with the previous block,
        NullIdentifier if this is the root block (ie there is no previous
        block)
        """
        return self.PrevBlock.BlockID if self.PrevBlock else NullIdentifier

    def add_transaction_store(self, tname, tstore):
        """Register a data store type with a particular transaction type.

        Args:
            tname (str): The name of the transaction type
            tstore (KeyValueStore): The data store to associate with the
                transaction type
        """
        self.TransactionStores[tname] = tstore

    def get_transaction_store(self, tname):
        """Return the transaction store associated with a particular
        transaction family.

        Args:
            tname (str): The name of the transaction family

        Returns:
            KeyValueStore: The store associated with the family.
        """
        return self.TransactionStores[tname]

    def clone_block(self, blockinfo=None, readonly=False):
        """Create a copy of the ledger by creating and registering a copy
        of each store in the current ledger.

        Args:
            blockinfo (dict): Optional output of the dump() method.
        """
        return BlockStore(self, blockinfo, readonly)

    def commit_block(self, blockid):
        """Persist the state of the store to disk.

        This should be called when the block is committed so we know
        that the state will not change.

        Args:
            blockid (str): The identifier associated with the block.
        """
        self.BlockID = blockid
        for tstore in self.TransactionStores.itervalues():
            tstore.commit()

    def flatten(self):
        """Flatten the store at this point.
        """
        for tstore in self.TransactionStores.itervalues():
            tstore.flatten()

    def dump_block(self, readonly=True):
        """Serialize the stores associated with this block.

        Returns:
            dict: Information about the stores associated with this
                block.
        """
        result = dict()
        result['BlockID'] = self.BlockID
        result['PreviousBlockID'] = self.PreviousBlockID
        result['TransactionStores'] = {}
        for tname, tstore in self.TransactionStores.iteritems():
            result['TransactionStores'][tname] = tstore.dump(readonly)

        return result


class KeyValueStore(object):
    """
    The KeyValueStore class implements a journaling dictionary that
    enables rollback through generational updates.

    For optimization the chain of stores can be flattened to limit
    traversal of the chain.

    Attributes:
        ReadOnly (bool): Whether or not the store is read only.
        PrevStore (KeyValueStore): The previous checkpoint of the store.
    """

    def __init__(self, prevstore=None, storeinfo=None, readonly=False):
        """Initialize a new KeyValueStore object.

        Args:
            prevstore (KeyValueStore): A reference to the previous
                checkpoint of the store.
            storeinfo (dict): Optional output of the dump() method,
                forces committed state.
        """

        self.ReadOnly = False
        self.PrevStore = prevstore
        copyfn = copy.copy if readonly else copy.deepcopy

        if storeinfo:
            self._store = copyfn(storeinfo['Store'])
            self._deletedkeys = set(storeinfo['DeletedKeys'])
        else:
            self._store = dict()
            self._deletedkeys = set()

    def clone_store(self, storeinfo=None, readonly=False):
        """Creates a new checkpoint that can be modified.

        Args:
            storeinfo (dict): Information about the store to clone.

        Returns:
            KeyValueStore: A new checkpoint that extends the current
                store.
        """
        return KeyValueStore(self, storeinfo, readonly)

    def commit(self):
        """Marks the store as read only.

        Do not allow any further modifications to this store or
        through this store to previous checkpoints.
        """
        self.ReadOnly = True

    def compose(self, readonly=True):
        """Creates a dictionary that is the composition of all
        previous stores.

        The dictionary that is created contains a copy of the
        dictionary entries.

        Args:
            readonly (bool): Whether or not the copy will be read only,
                in which case a deep copy is not performed.

        Returns:
            dict: A dictionary with a copy of all items in the store.
        """
        copyfn = copy.copy if readonly else copy.deepcopy

        storelist = []
        store = self
        while store:
            storelist.insert(0, store)
            store = store.PrevStore

        result = dict()
        for store in storelist:
            # copy our dictionary into the result
            result.update(copyfn(store._store))
            # remove the deleted keys from the store
            for k in store._deletedkeys:
                result.pop(k, None)

        # it would be possible to flatten the store here since
        # we've already done all the work; however, that would still
        # use too much memory. we only want to flatten if we are
        # flushing previous state

        return result

    def flatten(self):
        """Truncates the journal history at this point.

        Collapse all previous stores into this one and remove any
        reverse references.
        """
        if self.ReadOnly:
            self._store = self.compose(readonly=True)
            self._deletedkeys = set()
            self.PrevStore = None

    def get(self, key):
        """Gets the value associated with a key, cascading the
        request through the chain of stores.

        Args:
            key (str): The key to lookup.

        Returns:
            object: The value associated with the key.
        """
        if key in self._store:
            return copy.deepcopy(self._store[key])

        if self.PrevStore and key not in self._deletedkeys:
            return self.PrevStore.get(key)

        raise KeyError('attempt to access missing key', key)

    def __getitem__(self, key):
        return self.get(key)

    def set(self, key, value):
        """Sets the value associated with a key.

        Note:
            This change only occurs in the current checkpoint.

        Args:
            key (str): The key to set.
            value (str): The value to bind to the key. A deepcopy is
                made.
        """
        if self.ReadOnly:
            raise ReadOnlyException("Attempt to modify readonly store")

        self._store[key] = copy.deepcopy(value)
        self._deletedkeys.discard(key)

    def __setitem__(self, key, value):
        self.set(key, value)

    def delete(self, key):
        """Removes the key from the current store if it exists and
        adds it to the deleted keys list if it exists in previous
        checkpoints.

        Args:
            key (str): The key to delete.
        """

        if self.ReadOnly:
            raise ReadOnlyException("Attempt to modify readonly store")

        self._store.pop(key, None)
        self._deletedkeys.add(key)

    def __delitem__(self, key):
        self.delete(key)

    def has_key(self, key):
        """Walks the chain to determine if the key exists in the store.

        Args:
            key (str): The key to search for.

        Returns:
            bool: Whether or not the key exists in the store.
        """
        if key in self._store:
            return True

        if self.PrevStore and key not in self._deletedkeys:
            return key in self.PrevStore

        return False

    def _keys(self):
        """Computes the set of valid keys used in the store.

        Returns:
            set: The set of valid keys in the store.
        """
        kset = self.PrevStore._keys() if self.PrevStore else set()
        kset -= self._deletedkeys
        kset |= set(self._store.keys())

        return kset

    def keys(self):
        """Computes the set of valid keys used in the store.

        Returns:
            list: A list of valid keys in the store.
        """
        return list(self._keys())

    def __iter__(self):
        """Create an iterator for the keys.
        """
        for k in self.keys():
            yield k

    def iteritems(self):
        """Creates an iterator for items in the store.
        """
        for k in self.keys():
            yield k, self.get(k)

    def __contains__(self, key):
        """Determines whether a key occurs in the store.

        Args:
            key (str): A key to test.

        Returns:
            bool: Whether the key exists in the store.
        """

        if key in self._store:
            return True

        if key in self._deletedkeys:
            return False

        return self.PrevStore and self.PrevStore.__contains__(key)

    def dump(self, readonly=False):
        """Returns a dict containing information about the store.

        Returns:
            dict: A dict containing information about the store.
        """
        copyfn = copy.copy if readonly else copy.deepcopy

        result = dict()
        result['Store'] = copyfn(self._store)
        result['DeletedKeys'] = list(self._deletedkeys)

        return result

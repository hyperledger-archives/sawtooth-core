# Copyright 2017 Intel Corporation
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

from sawtooth_validator.journal.block_wrapper import NULL_BLOCK_IDENTIFIER
from sawtooth_validator.protobuf.transaction_pb2 import TransactionHeader


class MissingDependency(Exception):
    def __init__(self, txn_id):
        super().__init__("Missing dependency: {}".format(txn_id))
        self.transaction_id = txn_id


class DuplicateTransaction(Exception):
    def __init__(self, txn_id):
        super().__init__("Duplicate transaction: {}".format(txn_id))
        self.transaction_id = txn_id


class DuplicateBatch(Exception):
    def __init__(self, batch_id):
        super().__init__("Duplicate batch: {}".format(batch_id))
        self.batch_id = batch_id


class ChainCommitState:
    """Checking to see if a batch or transaction in a block has already been
    committed is somewhat difficult because of the presence of forks. While
    the block store is the definitive source for all batches and transactions
    that have been committed on the current chain, validation of blocks on
    another fork requires determing what blocks would actually be in the chain
    if that block were to be committed and only checking the batches and
    transactions contained within. ChainCommitState abstracts this process.
    """
    def __init__(self, head_id, block_cache, block_store):
        """The constructor should be passed the previous block id of the block
        being validated."""
        uncommitted_block_ids = list()
        uncommitted_batch_ids = set()
        uncommitted_txn_ids = set()

        # Find the most recent ancestor of this block that is in the block
        # store. Batches and transactions that are in a block that is in the
        # block store and that has a greater block number than this block must
        # be ignored.
        if head_id != NULL_BLOCK_IDENTIFIER:
            head = block_cache[head_id]
            ancestor = head
            while ancestor.header_signature not in block_store:
                # For every block not in the block store, we need to track all
                # its batch ids and transaction ids separately to ensure there
                # are no duplicates.
                for batch in ancestor.batches:
                    uncommitted_batch_ids.add(batch.header_signature)

                    for txn in batch.transactions:
                        uncommitted_txn_ids.add(txn.header_signature)

                uncommitted_block_ids.append(ancestor.header_signature)

                previous_block_id = ancestor.previous_block_id
                if previous_block_id == NULL_BLOCK_IDENTIFIER:
                    break

                ancestor = block_cache[previous_block_id]
        else:
            ancestor = None

        self.block_store = block_store
        self.common_ancestor = ancestor
        self.uncommitted_block_ids = uncommitted_block_ids
        self.uncommitted_batch_ids = uncommitted_batch_ids
        self.uncommitted_txn_ids = uncommitted_txn_ids

    def _block_in_chain(self, block):
        if self.common_ancestor is not None:
            return block.block_num <= self.common_ancestor.block_num
        return False

    @staticmethod
    def _check_for_duplicates_within(key_fn, items):
        """Checks that for any two items in `items`, calling `key_fn` on both
        does not return equal values."""
        for i, item_i in enumerate(items):
            for item_j in items[i + 1:]:
                if key_fn(item_i) == key_fn(item_j):
                    return key_fn(item_i)
        return None

    def check_for_duplicate_transactions(self, transactions):
        """Check that none of the transactions passed in have already been
        committed in the chain. Also checks that the list of transactions
        passed contains no duplicates."""
        # Same as for batches
        duplicate = self._check_for_duplicates_within(
            lambda txn: txn.header_signature, transactions)
        if duplicate is not None:
            raise DuplicateTransaction(duplicate)

        for txn in transactions:
            txn_id = txn.header_signature
            if txn_id in self.uncommitted_txn_ids:
                raise DuplicateTransaction(txn_id)

            if self.block_store.has_transaction(txn_id):
                committed_block =\
                    self.block_store.get_block_by_transaction_id(txn_id)

                if self._block_in_chain(committed_block):
                    raise DuplicateTransaction(txn_id)

    def check_for_duplicate_batches(self, batches):
        """Check that none of the batches passed in have already been committed
        in the chain. Also checks that the list of batches passed contains no
        duplicates."""
        # Check for duplicates within the given list
        duplicate = self._check_for_duplicates_within(
            lambda batch: batch.header_signature, batches)
        if duplicate is not None:
            raise DuplicateBatch(duplicate)

        for batch in batches:
            batch_id = batch.header_signature

            # Make sure the batch isn't in one of the uncommitted block
            if batch_id in self.uncommitted_batch_ids:
                raise DuplicateBatch(batch_id)

            # Check if the batch is in one of the committed blocks
            if self.block_store.has_batch(batch_id):
                committed_block =\
                    self.block_store.get_block_by_batch_id(batch_id)

                # This is only a duplicate batch if the batch is in a block
                # that would stay committed if this block were committed. This
                # is equivalent to asking if the number of the block that this
                # batch is in is less than or equal to the number of the common
                # ancestor block.
                if self._block_in_chain(committed_block):
                    raise DuplicateBatch(batch_id)

    def check_for_transaction_dependencies(self, transactions):
        """Check that all explicit dependencies in all transactions passed have
        been satisfied."""
        dependencies = []
        txn_ids = []
        for txn in transactions:
            txn_ids.append(txn.header_signature)
            txn_hdr = TransactionHeader()
            txn_hdr.ParseFromString(txn.header)
            dependencies.extend(txn_hdr.dependencies)

        for dep in dependencies:
            # Check for dependency within the given block's batches
            if dep in txn_ids:
                continue

            # Check for dependency in the uncommitted blocks
            if dep in self.uncommitted_txn_ids:
                continue

            # Check for dependency in the committe blocks
            if self.block_store.has_transaction(dep):
                committed_block =\
                    self.block_store.get_block_by_transaction_id(dep)

                # Make sure the block wouldn't be uncomitted if the given block
                # were uncommitted
                if self._block_in_chain(committed_block):
                    continue

            raise MissingDependency(dep)


class _CommitCache:
    """Tracks the commit status of a set of identifiers and these identifiers
    are either explicitly committed, or explicitly uncommitted. If they fall in
    to neither of these cases then the fallback is to look in the BlockStore to
    see if they are there. Explicit committed ids take priority over
    uncommitted since one of the common use cases we have is to simulate the
    committed state at a previous state of the BlockStore and we allow for the
    identifiers to be re-committed.
    """

    def __init__(self, block_store_check):
        self.block_store_check = block_store_check
        self._committed = set()  # the set of items
        # committed by this chain
        self._uncommitted = set()  # the set of items
        # uncommitted by the current chain when it is rolled back.

    def add(self, identifier):
        self._committed.add(identifier)

    def remove(self, identifier):
        self._committed.discard(identifier)

    def uncommit(self, identifier):
        self._uncommitted.add(identifier)

    def __contains__(self, identifier):
        if identifier in self._committed:
            return True
        if identifier in self._uncommitted:
            return False
        return self.block_store_check(identifier)


class TransactionCommitCache(_CommitCache):
    """Tracks the set of Transactions that are committed to a hypothetical
    blockchain. This is used to detect duplicate transactions or missing
    dependencies when building a block.
    """

    def __init__(self, block_store):
        super(TransactionCommitCache, self).__init__(
            block_store.has_transaction)

    def add_batch(self, batch):
        for txn in batch.transactions:
            self._committed.add(txn.header_signature)

    def remove_batch(self, batch):
        for txn in batch.transactions:
            self._committed.discard(txn.header_signature)

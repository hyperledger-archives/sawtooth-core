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


class _CommitCache(object):
    """Tracks the committment status of a set of identifiers in these
    identifiers are either explicitly committed, explicity uncommitted, if
    they fall in to neither of these cases then the fallback is to look in
    the BlockStore to see if they are there. Explicit committed ids
    take priority over uncommitted since one of the common use cases we have
    is to simulate the committed state at a previous state of the BlockStore
    and we allow for the identifiers to be re-committed.
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
        elif identifier in self._uncommitted:
            return False
        return self.block_store_check(identifier)


class ChainCommitState(object):
    """Tracks the set of Batches and Transactions that are committed to a
    hypothetical chain. This is used to to detect duplicate batches, duplicate
    transactions, and missing transactions dependencies when evaluating a new
    chain.
    """
    def __init__(self, block_store, uncommitted_blocks):
        self._batch_commit_state = _CommitCache(block_store.has_batch)
        self._transaction_commit_state = _CommitCache(
            block_store.has_transaction)

        for block in uncommitted_blocks:
            self._uncommit_block(block)

    def _uncommit_block(self, block):
        for batch in block.batches:
            self._batch_commit_state.uncommit(batch.header_signature)

            for txn in batch.transactions:
                self._transaction_commit_state.uncommit(txn.header_signature)

    def add_txn(self, txn_id):
        self._transaction_commit_state.add(txn_id)

    def add_batch(self, batch, add_transactions=True):
        self._batch_commit_state.add(batch.header_signature)
        if add_transactions:
            for txn in batch.transactions:
                self._transaction_commit_state.add(txn.header_signature)

    def remove_batch(self, batch):
        self._batch_commit_state.remove(batch.header_signature)
        for txn in batch.transactions:
            self._transaction_commit_state.remove(txn.header_signature)

    def has_batch(self, batch_id):
        return batch_id in self._batch_commit_state

    def has_transaction(self, txn_id):
        return txn_id in self._transaction_commit_state


class TransactionCommitState(_CommitCache):
    """Tracks the set of Transactions that are committed to a hypothetical
    blockchain. This is used to to detect duplicate transactions or missing
    dependencies when building a block.
    """
    def __init__(self, block_store):
        super(TransactionCommitState, self).__init__(
            block_store.has_transaction)

    def add_batch(self, batch, add_transactions=True):
        for txn in batch.transactions:
            self._committed.add(txn.header_signature)

    def remove_batch(self, batch):
        for txn in batch.transactions:
            self._committed.discard(txn.header_signature)

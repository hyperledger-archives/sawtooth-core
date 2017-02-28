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


class TransactionCache(object):
    """Class to track set of committed transactions, falls back to using the
    Block store if transactions are not in the local cache. Has the ability
    to track a set of uncommited transactions, so we can simulate the
    committed transaction set at a point previously on the chain.
    """
    def __init__(self, block_store):
        self._block_store = block_store
        self._committed_transactions = set()  # the set of transactions
        # committed by this chain
        self._uncommitted_transactions = set()  # the set of transactions
        # uncommitted by the current chain when it is rolled back.

    def add_txn(self, txn_id):
        self._committed_transactions.add(txn_id)

    def add_batch(self, batch):
        for txn in batch.transactions:
            self._committed_transactions.add(txn.header_signature)

    def remove_batch(self, batch):
        for txn in batch.transactions:
            self._committed_transactions.discard(txn.header_signature)

    def uncommit_batch(self, batch):
        for txn in batch.transactions:
            self._uncommitted_transactions.add(txn.header_signature)

    def __contains__(self, txn_id):
        if txn_id in self._committed_transactions:
            return True
        elif txn_id in self._uncommitted_transactions:
            return False
        return self._block_store.has_transaction(txn_id)

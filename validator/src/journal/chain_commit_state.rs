/*
 * Copyright 2018 Intel Corporation
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * ------------------------------------------------------------------------------
 */

use std::collections::HashSet;

use cpython;
use cpython::ObjectProtocol;

use batch::Batch;
use block::Block;
use journal::block_manager::BlockManager;
use journal::block_store::{BatchIndex, BlockStore, TransactionIndex};
use journal::NULL_BLOCK_IDENTIFIER;
use transaction::Transaction;

#[derive(Debug, PartialEq)]
pub enum ChainCommitStateError {
    MissingDependency(String),
    DuplicateTransaction(String),
    DuplicateBatch(String),
    BlockStoreUpdated,
    Error(String),
}

pub struct ChainCommitState<B: BatchIndex, T: TransactionIndex> {
    batch_index: B,
    transaction_index: T,
    ancestor: Option<Block>,
    uncommitted_batch_ids: Vec<String>,
    uncommitted_txn_ids: Vec<String>,
}

fn check_no_duplicates(ids: &[String]) -> Option<String> {
    for (i, id1) in ids.iter().enumerate() {
        if ids[i + 1..ids.len()].contains(id1) {
            return Some(id1.to_string());
        }
    }
    None
}

impl<B: BatchIndex, T: TransactionIndex> ChainCommitState<B, T> {
    pub fn new<BS: BlockStore>(
        branch_head_id: &str,
        block_manager: &BlockManager,
        batch_index: B,
        transaction_index: T,
        block_store: BS,
    ) -> Result<Self, ChainCommitStateError> {
        let current_chain_head_id = block_store
            .iter()
            .map_err(|err| {
                ChainCommitStateError::Error(format!(
                    "Getting chain head in ChainCommitState: {:?}",
                    err
                ))
            })?
            .nth(0)
            .map(|block| block.header_signature.clone());

        let (batch_ids, txn_ids, common_ancestor) = if branch_head_id != NULL_BLOCK_IDENTIFIER {
            if let Some(ref chain_head_id) = current_chain_head_id {
                let uncommitted_branch = block_manager
                    .branch_diff(branch_head_id, chain_head_id)
                    .map_err(|err| ChainCommitStateError::Error(format!("{:?}", err)))?;

                Self::return_ids_for_blocks_batches_txns(uncommitted_branch)
            } else {
                let uncommitted_branch = block_manager
                    .branch(branch_head_id)
                    .map_err(|err| ChainCommitStateError::Error(format!("{:?}", err)))?;
                let (batch_ids, txn_ids, _) =
                    Self::return_ids_for_blocks_batches_txns(uncommitted_branch);
                (batch_ids, txn_ids, None)
            }
        } else {
            (vec![], vec![], None)
        };
        Ok(ChainCommitState {
            batch_index,
            transaction_index,
            ancestor: common_ancestor,
            uncommitted_batch_ids: batch_ids,
            uncommitted_txn_ids: txn_ids,
        })
    }

    fn return_ids_for_blocks_batches_txns(
        uncommitted_branch: Box<Iterator<Item = Block>>,
    ) -> (Vec<String>, Vec<String>, Option<Block>) {
        let mut batch_ids = vec![];
        let mut txn_ids = vec![];
        let mut blocks = vec![];
        for block in uncommitted_branch {
            for batch in &block.batches {
                batch_ids.push(batch.header_signature.clone());
                for transaction in &batch.transactions {
                    txn_ids.push(transaction.header_signature.clone());
                }
            }
            blocks.push(block);
        }
        let last_block = blocks.last().cloned();
        (batch_ids, txn_ids, last_block)
    }

    fn block_in_chain(&self, block: &Block) -> bool {
        if let Some(ref common) = self.ancestor {
            return block.block_num <= common.block_num;
        }
        false
    }

    pub fn validate_no_duplicate_batches(
        &self,
        batch_ids: Vec<String>,
    ) -> Result<(), ChainCommitStateError> {
        if let Some(batch_id) = check_no_duplicates(batch_ids.as_slice()) {
            return Err(ChainCommitStateError::DuplicateBatch(batch_id));
        }
        for id in batch_ids {
            if self.uncommitted_batch_ids.contains(&id) {
                return Err(ChainCommitStateError::DuplicateBatch((*id).into()));
            }

            if self.batch_index.contains(&id).map_err(|err| {
                ChainCommitStateError::Error(format!("Reading contains on BatchIndex: {:?}", err))
            })? {
                if let Some(ref block) = self
                    .batch_index
                    .get_block_by_id(&id)
                    .map_err(|err| ChainCommitStateError::BlockStoreUpdated)?
                {
                    if self.block_in_chain(block) {
                        return Err(ChainCommitStateError::DuplicateBatch(id));
                    }
                }
            }
        }

        Ok(())
    }

    pub fn validate_no_duplicate_transactions(
        &self,
        transaction_ids: Vec<String>,
    ) -> Result<(), ChainCommitStateError> {
        if let Some(txn_id) = check_no_duplicates(transaction_ids.as_slice()) {
            return Err(ChainCommitStateError::DuplicateTransaction(txn_id));
        }

        for id in transaction_ids {
            if self.uncommitted_txn_ids.contains(&(*id).into()) {
                return Err(ChainCommitStateError::DuplicateTransaction(id));
            }

            if self
                .transaction_index
                .contains(&id)
                .map_err(|err| ChainCommitStateError::Error(format!("{:?}", err)))?
            {
                if let Some(ref block) = self
                    .transaction_index
                    .get_block_by_id(&id)
                    .map_err(|err| ChainCommitStateError::BlockStoreUpdated)?
                {
                    if self.block_in_chain(block) {
                        return Err(ChainCommitStateError::DuplicateTransaction(id));
                    }
                }
            }
        }
        Ok(())
    }

    pub fn validate_transaction_dependencies(
        self,
        transactions: &[Transaction],
    ) -> Result<(), ChainCommitStateError> {
        let mut dependencies = vec![];
        let mut txn_ids = vec![];
        for txn in transactions {
            txn_ids.push(txn.header_signature.clone());

            for dep in &txn.dependencies {
                dependencies.push(dep.clone());
            }
        }
        for dep in dependencies {
            // Check for dependencies within the given block's batches
            if txn_ids.contains(&dep) {
                continue;
            }

            // Check for dependencies within the uncommitted blocks
            if self.uncommitted_txn_ids.contains(&dep) {
                continue;
            }

            // Check for the dependency in the committed blocks
            if self
                .transaction_index
                .contains(&dep)
                .map_err(|err| ChainCommitStateError::Error(format!("{:?}", err)))?
            {
                if let Some(ref block) = self
                    .transaction_index
                    .get_block_by_id(&dep)
                    .map_err(|err| ChainCommitStateError::BlockStoreUpdated)?
                {
                    if self.block_in_chain(block) {
                        continue;
                    }
                }
            }
            return Err(ChainCommitStateError::MissingDependency(dep));
        }
        Ok(())
    }
}

pub struct TransactionCommitCache {
    committed: HashSet<String>,

    transaction_committed: cpython::PyObject,
}

impl TransactionCommitCache {
    pub fn new(transaction_committed: cpython::PyObject) -> Self {
        TransactionCommitCache {
            committed: HashSet::new(),
            transaction_committed,
        }
    }

    pub fn add(&mut self, transaction_id: String) {
        self.committed.insert(transaction_id);
    }

    pub fn add_batch(&mut self, batch: &Batch) {
        batch
            .transactions
            .iter()
            .for_each(|txn| self.add(txn.header_signature.clone()));
    }

    pub fn remove(&mut self, transaction_id: &str) {
        self.committed.remove(transaction_id);
    }

    pub fn remove_batch(&mut self, batch: &Batch) {
        batch
            .transactions
            .iter()
            .for_each(|txn| self.remove(txn.header_signature.as_str()));
    }

    pub fn contains(&self, transaction_id: &str) -> bool {
        self.committed.contains(transaction_id) || self.blockstore_has_txn(transaction_id)
    }

    fn blockstore_has_txn(&self, transaction_id: &str) -> bool {
        let gil = cpython::Python::acquire_gil();
        let py = gil.python();
        self.transaction_committed
            .call(py, (transaction_id,), None)
            .expect("Call to determine if transaction is committed failed")
            .extract::<bool>(py)
            .unwrap()
    }
}

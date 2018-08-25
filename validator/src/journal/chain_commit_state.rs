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

pub struct ChainCommitState<'b, 't, B: BatchIndex + 'b, T: TransactionIndex + 't> {
    batch_index: &'b B,
    transaction_index: &'t T,
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

impl<'b, 't, B: BatchIndex + 'b, T: TransactionIndex + 't> ChainCommitState<'b, 't, B, T> {
    pub fn new<BS: BlockStore>(
        branch_head_id: &str,
        block_manager: &BlockManager,
        batch_index: &'b B,
        transaction_index: &'t T,
        block_store: &BS,
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

#[cfg(test)]
mod test {
    use super::*;
    use block::Block;
    use journal::block_store::InMemoryBlockStore;
    use journal::NULL_BLOCK_IDENTIFIER;
    use transaction::Transaction;

    /// Creates Chains of blocks that match this diagram
    /// chain4                    B4-4  - B5-4
    ///                         /
    /// chain1          B2-1 - B3-1- B4-1 -- B5-1
    ///               /
    /// chain0    B0-B1-B2 - B3 -- B4 ---  B5
    ///                    \
    /// chain2               B3-2 - B4-2 -- B5-2
    ///                          \
    /// chain3                      B4-3 -- B5-3
    ///
    ///  the batches in B2-1, for example, are B2-1b0 and B2-1b1
    ///  the transactions in b0, are B2-1b0t0, B2'b0t1, and B2-1b0t2
    ///
    fn create_chains_to_put_in_block_manager() -> Vec<Vec<Block>> {
        let mut previous_block_id = ::journal::NULL_BLOCK_IDENTIFIER;
        let mut block_num = 0;
        let chain0 = ["B0", "B1", "B2", "B3", "B4", "B5"]
            .iter()
            .map(|ref mut block_id| {
                let block = create_block_w_batches_txns(block_id, previous_block_id, block_num);
                previous_block_id = block_id;
                block_num += 1;
                block
            })
            .collect();

        let mut previous_block_id = "B1";
        let mut block_num = 2;
        let chain1 = ["B2-1", "B3-1", "B4-1", "B5-1"]
            .iter()
            .map(|ref mut block_id| {
                let block = create_block_w_batches_txns(block_id, previous_block_id, block_num);
                previous_block_id = block_id;
                block_num += 1;
                block
            })
            .collect();

        let mut previous_block_id = "B3-1";
        let mut block_num = 4;
        let chain4 = ["B4-4", "B5-4"]
            .iter()
            .map(|ref mut block_id| {
                let block = create_block_w_batches_txns(block_id, previous_block_id, block_num);
                previous_block_id = block_id;
                block_num += 1;
                block
            })
            .collect();

        let mut previous_block_id = "B2";
        let mut block_num = 3;
        let chain2 = ["B3-2", "B4-2", "B5-2"]
            .iter()
            .map(|ref mut block_id| {
                let block = create_block_w_batches_txns(block_id, previous_block_id, block_num);
                previous_block_id = block_id;
                block
            })
            .collect();

        let mut previous_block_id = "B3-2";
        let mut block_num = 4;
        let chain3 = ["B4-3", "B5-3"]
            .iter()
            .map(|ref mut block_id| {
                let block = create_block_w_batches_txns(block_id, previous_block_id, block_num);
                previous_block_id = block_id;
                block
            })
            .collect();
        vec![chain0, chain1, chain4, chain2, chain3]
    }

    #[test]
    fn test_no_duplicates() {
        assert_eq!(
            check_no_duplicates(&["1".into(), "2".into(), "3".into()]),
            None
        );
    }

    #[test]
    fn test_duplicates1() {
        assert_eq!(
            check_no_duplicates(&["1".into(), "2".into(), "1".into()]),
            Some("1".into())
        );
    }

    #[test]
    fn test_duplicates2() {
        assert_eq!(
            check_no_duplicates(&["1".into(), "1".into(), "2".into()]),
            Some("1".into())
        );
    }

    #[test]
    fn test_dependency_in_other_fork() {
        let (block_manager, block_store) = setup_state();

        let transactions: Vec<Transaction> = ["B6b0t0", "B6b0t1", "B6b0t2"]
            .into_iter()
            .map(|t_id| create_transaction((*t_id).into(), vec!["B2b0t0".into()]))
            .collect();

        block_manager
            .persist("B5", "commit")
            .expect("The block manager is able to persist all blocks known to it");

        let chain_commit_state = ChainCommitState::new(
            "B5-1",
            &block_manager,
            &block_store,
            &block_store,
            &block_store,
        ).expect("There was no error creating ChainCommitState");

        assert_eq!(
            chain_commit_state.validate_transaction_dependencies(&transactions),
            Err(ChainCommitStateError::MissingDependency("B2b0t0".into()))
        );
    }

    #[test]
    fn test_dependency_in_chain() {
        let (block_manager, block_store) = setup_state();

        let transactions: Vec<Transaction> = ["B6b0t0", "B6b0t1", "B6b0t2"]
            .into_iter()
            .map(|t_id| create_transaction((*t_id).into(), vec!["B1b0t0".into()]))
            .collect();

        block_manager
            .persist("B5", "commit")
            .expect("The block manager is able to persist all blocks known to it");

        let chain_commit_state = ChainCommitState::new(
            "B5-1",
            &block_manager,
            &block_store,
            &block_store,
            &block_store,
        ).expect("There was no error creating ChainCommitState");

        assert_eq!(
            chain_commit_state.validate_transaction_dependencies(&transactions),
            Ok(())
        );
    }

    #[test]
    fn test_dependency_in_chain_chain_head_greater() {
        let (block_manager, block_store) = setup_state();

        let transactions: Vec<Transaction> = ["B3-1b0t0", "B3-1b0t1", "B3-1b0t2"]
            .into_iter()
            .map(|t_id| create_transaction((*t_id).into(), vec!["B1b0t0".into()]))
            .collect();

        block_manager
            .persist("B5", "commit")
            .expect("The block manager is able to persist all blocks known to it");

        let chain_commit_state = ChainCommitState::new(
            "B2",
            &block_manager,
            &block_store,
            &block_store,
            &block_store,
        ).expect("There was no error creating ChainCommitState");

        assert_eq!(
            chain_commit_state.validate_transaction_dependencies(&transactions),
            Ok(())
        );
    }

    #[test]
    fn test_dependency_in_uncommitted() {
        let (block_manager, block_store) = setup_state();

        let transactions: Vec<Transaction> = ["B6b0t0", "B6b0t1", "B6b0t2"]
            .into_iter()
            .map(|t_id| create_transaction((*t_id).into(), vec!["B4-3b0t0".into()]))
            .collect();

        block_manager
            .persist("B1", "commit")
            .expect("The block manager is able to persist all blocks known to it");

        let chain_commit_state = ChainCommitState::new(
            "B5-3",
            &block_manager,
            &block_store,
            &block_store,
            &block_store,
        ).expect("There was no error creating ChainCommitState");

        assert_eq!(
            chain_commit_state.validate_transaction_dependencies(&transactions),
            Ok(())
        );
    }

    #[test]
    fn test_no_duplicate_batches() {
        let (block_manager, block_store) = setup_state();

        let batches = vec!["B6b0".into(), "B6b1".into()];

        block_manager
            .persist("B4", "commit")
            .expect("The block manager is able to persist all blocks known to it");
        let chain_commit_state = ChainCommitState::new(
            "B5",
            &block_manager,
            &block_store,
            &block_store,
            &block_store,
        ).expect("There was no error creating ChainCommitState");

        assert_eq!(
            chain_commit_state.validate_no_duplicate_batches(batches),
            Ok(())
        );
    }

    #[test]
    fn test_no_duplicates_because_batches_in_other_fork() {
        let (block_manager, block_store) = setup_state();

        let batches = vec!["B3b0".into(), "B3b1".into()];

        block_manager
            .persist("B5", "commit")
            .expect("The block manager is able to persist all blocks known to it");

        let chain_commit_state = ChainCommitState::new(
            "B5-2",
            &block_manager,
            &block_store,
            &block_store,
            &block_store,
        ).expect("There was no error creating ChainCommitState");

        assert_eq!(
            chain_commit_state.validate_no_duplicate_batches(batches),
            Ok(())
        );
    }

    #[test]
    fn test_no_duplicate_batches_duplicate_in_branch() {
        let (block_manager, block_store) = setup_state();

        let batches = vec!["B2b0".into(), "B2b1".into()];

        block_manager
            .persist("B5", "commit")
            .expect("The block manage is able to persist all blocks known to it");

        let chain_commit_state = ChainCommitState::new(
            "B5-2",
            &block_manager,
            &block_store,
            &block_store,
            &block_store,
        ).expect("There was no error creating ChainCommitState");

        assert_eq!(
            chain_commit_state.validate_no_duplicate_batches(batches),
            Err(ChainCommitStateError::DuplicateBatch("B2b0".into()))
        );
    }

    #[test]
    fn test_no_duplicate_batches_duplicate_in_uncommitted() {
        let (block_manager, block_store) = setup_state();

        let batches = vec!["B5-2b0".into(), "B5-2b1".into()];

        block_manager
            .persist("B5", "commit")
            .expect("The block manager is able to persist all blocks known to it");

        let chain_commit_state = ChainCommitState::new(
            "B5-2",
            &block_manager,
            &block_store,
            &block_store,
            &block_store,
        ).expect("There was no error creating ChainCommitState");

        assert_eq!(
            chain_commit_state.validate_no_duplicate_batches(batches),
            Err(ChainCommitStateError::DuplicateBatch("B5-2b0".into()))
        );
    }

    #[test]
    fn test_no_duplicate_batches_duplicate_in_other_fork() {
        let (block_manager, block_store) = setup_state();

        let batches = vec!["B2b0".into(), "B2b1".into()];

        block_manager
            .persist("B5", "commit")
            .expect("The block manager is able to persist all blocks known to it");

        let chain_commit_state = ChainCommitState::new(
            "B5-1",
            &block_manager,
            &block_store,
            &block_store,
            &block_store,
        ).expect("There was no error creating ChainCommitState");

        assert_eq!(
            chain_commit_state.validate_no_duplicate_batches(batches),
            Ok(())
        );
    }

    #[test]
    fn test_no_duplicate_transactions() {
        let (block_manager, block_store) = setup_state();

        let transactions = vec![
            "B6b0t0".into(),
            "B6b0t1".into(),
            "B6b0t2".into(),
            "B6b1t0".into(),
            "B6b1t1".into(),
            "B6b1t2".into(),
        ];

        block_manager
            .persist("B5", "commit")
            .expect("The block manager is able to persist all blocks known to it");

        let chain_commit_state = ChainCommitState::new(
            "B5",
            &block_manager,
            &block_store,
            &block_store,
            &block_store,
        ).expect("There was no error creating ChainCommitState");

        assert_eq!(
            chain_commit_state.validate_no_duplicate_transactions(transactions),
            Ok(())
        );
    }

    #[test]
    fn test_no_duplicate_transactions_duplicate_in_branch() {
        let (block_manager, block_store) = setup_state();

        let transactions = vec!["B6b0t0".into(), "B6b0t1".into(), "B2b0t2".into()];

        block_manager
            .persist("B5-3", "commit")
            .expect("The block manager is able to persist all blocks known to it");

        let chain_commit_state = ChainCommitState::new(
            "B5-2",
            &block_manager,
            &block_store,
            &block_store,
            &block_store,
        ).expect("There was no error creating ChainCommitState");

        assert_eq!(
            chain_commit_state.validate_no_duplicate_transactions(transactions),
            Err(ChainCommitStateError::DuplicateTransaction("B2b0t2".into())),
        )
    }

    #[test]
    fn test_no_duplicate_transactions_duplicate_in_uncommitted() {
        let (block_manager, block_store) = setup_state();

        let transactions = vec!["B6b0t0".into(), "B6b0t1".into(), "B2-1b0t1".into()];

        block_manager
            .persist("B5-3", "commit")
            .expect("The block manager is able to persist all blocks known to it");

        let chain_commit_state = ChainCommitState::new(
            "B5-4",
            &block_manager,
            &block_store,
            &block_store,
            &block_store,
        ).expect("There was no error creating ChainCommitState");

        assert_eq!(
            chain_commit_state.validate_no_duplicate_transactions(transactions),
            Err(ChainCommitStateError::DuplicateTransaction(
                "B2-1b0t1".into()
            ))
        );
    }

    #[test]
    fn test_no_duplicate_transactions_duplicate_in_other_fork() {
        let (block_manager, block_store) = setup_state();

        let transactions = vec!["B6b0t0".into(), "B6b0t1".into(), "B2b0t1".into()];

        block_manager
            .persist("B5", "commit")
            .expect("The block manager is able to persist all blocks known to it");

        let chain_commit_state = ChainCommitState::new(
            "B5-1",
            &block_manager,
            &block_store,
            &block_store,
            &block_store,
        ).expect("There was no error creating ChainCommitState");

        assert_eq!(
            chain_commit_state.validate_no_duplicate_transactions(transactions),
            Ok(())
        );
    }

    #[test]
    fn test_before_genesis() {
        let (block_manager, block_store) = setup_state();

        let transactions = vec!["B0b0t0".into(), "B0b0t1".into(), "B0b0t2".into()];
        let batches = vec!["B0b0".into(), "B0b1".into()];
        let block_store_clone = block_store.clone();
        let chain_commit_state = ChainCommitState::new(
            NULL_BLOCK_IDENTIFIER,
            &block_manager,
            &block_store,
            &block_store,
            &block_store,
        ).expect("There was no error creating ChainCommitState");

        assert_eq!(
            chain_commit_state.validate_no_duplicate_batches(batches),
            Ok(())
        );

        assert_eq!(
            chain_commit_state.validate_no_duplicate_transactions(transactions),
            Ok(())
        );

        let transactions = vec!["B3b0t0".into(), "B3b0t1".into(), "B3b0t2".into()];
        let batches = vec!["B3b0".into(), "B3b1".into()];
        let chain_commit_state = ChainCommitState::new(
            "B2",
            &block_manager,
            &block_store,
            &block_store,
            &block_store,
        ).expect("There was no error creating ChainCommitState");

        assert_eq!(
            chain_commit_state.validate_no_duplicate_batches(batches),
            Ok(())
        );

        assert_eq!(
            chain_commit_state.validate_no_duplicate_transactions(transactions),
            Ok(())
        );

        let transactions = vec!["B3b0t0".into(), "B3b0t1".into(), "B3b0t2".into()];
        let batches = vec!["B3b0".into(), "B3b1".into()];

        let chain_commit_state = ChainCommitState::new(
            "B3",
            &block_manager,
            &block_store,
            &block_store,
            &block_store,
        ).expect("There was no error creating ChainCommitState");

        assert_eq!(
            chain_commit_state.validate_no_duplicate_batches(batches),
            Err(ChainCommitStateError::DuplicateBatch("B3b0".into()))
        );
        assert_eq!(
            chain_commit_state.validate_no_duplicate_transactions(transactions),
            Err(ChainCommitStateError::DuplicateTransaction("B3b0t0".into()))
        );
    }

    fn create_block_w_batches_txns(
        block_id: &str,
        previous_block_id: &str,
        block_num: u64,
    ) -> Block {
        let batches = vec!["b0", "b1"]
            .into_iter()
            .map(|batch_id: &str| {
                let batch_header_signature = format!("{}{}", block_id, batch_id);
                let txns = vec!["t0", "t1", "t2"]
                    .into_iter()
                    .map(|t_id: &str| {
                        let txn_id = format!("{}{}", batch_header_signature, t_id);
                        create_transaction(txn_id, vec![])
                    })
                    .collect();
                create_batch(batch_header_signature, txns)
            })
            .collect();

        let block = create_block(block_id, previous_block_id, block_num, batches);

        block
    }

    fn create_block(
        block_id: &str,
        previous_id: &str,
        block_num: u64,
        batches: Vec<Batch>,
    ) -> Block {
        let batch_ids = batches.iter().map(|b| b.header_signature.clone()).collect();
        Block {
            header_signature: block_id.into(),
            batches,
            state_root_hash: "".into(),
            consensus: vec![],
            batch_ids,
            signer_public_key: "".into(),
            previous_block_id: previous_id.into(),
            block_num: block_num,
            header_bytes: vec![],
        }
    }

    fn create_batch(batch_id: String, transactions: Vec<Transaction>) -> Batch {
        let transaction_ids = transactions
            .iter()
            .map(|t| t.header_signature.clone())
            .collect();
        Batch {
            header_signature: batch_id,
            transactions,
            signer_public_key: "".into(),
            transaction_ids,
            trace: false,
            header_bytes: vec![],
        }
    }

    fn create_transaction(txn_id: String, dependencies: Vec<String>) -> Transaction {
        Transaction {
            header_signature: txn_id,
            payload: vec![],
            batcher_public_key: "".into(),
            dependencies,
            family_name: "".into(),
            family_version: "".into(),
            inputs: vec![],
            outputs: vec![],
            nonce: "".into(),
            payload_sha512: "".into(),
            signer_public_key: "".into(),
            header_bytes: vec![],
        }
    }

    fn setup_state() -> (BlockManager, InMemoryBlockStore) {
        let mut block_manager = BlockManager::new();

        for branch in create_chains_to_put_in_block_manager() {
            block_manager
                .put(branch)
                .expect("The branches were created to be `put` in the block manager without error");
        }
        let block_store = Box::new(InMemoryBlockStore::new());
        block_manager
            .add_store("commit", block_store.clone())
            .expect("The block manager failed to add a blockstore");

        (block_manager, *block_store)
    }

}

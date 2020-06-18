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

use batch::Batch;
use journal::block_manager::BlockManager;
use journal::commit_store::CommitStore;
use transaction::Transaction;

#[derive(Debug, PartialEq)]
pub enum ChainCommitStateError {
    MissingDependency(String),
    DuplicateTransaction(String),
    DuplicateBatch(String),
    BlockStoreUpdated,
    Error(String),
}

fn check_no_duplicates(ids: &[&String]) -> Option<String> {
    for (i, id1) in ids.iter().enumerate() {
        if ids[i + 1..ids.len()].contains(id1) {
            return Some(id1.to_string());
        }
    }
    None
}

pub fn validate_no_duplicate_batches(
    block_manager: &BlockManager,
    branch_head_id: &str,
    batch_ids: &[&String],
) -> Result<(), ChainCommitStateError> {
    if let Some(batch_id) = check_no_duplicates(batch_ids) {
        return Err(ChainCommitStateError::DuplicateBatch(batch_id));
    }

    if let Some(batch_id) = block_manager
        .contains_any_batches(branch_head_id, batch_ids)
        .map_err(|err| {
            ChainCommitStateError::Error(format!("During validate_no_duplicate_batches: {:?}", err))
        })?
    {
        return Err(ChainCommitStateError::DuplicateBatch(batch_id));
    }
    Ok(())
}

pub fn validate_no_duplicate_transactions(
    block_manager: &BlockManager,
    branch_head_id: &str,
    transaction_ids: &[&String],
) -> Result<(), ChainCommitStateError> {
    if let Some(txn_id) = check_no_duplicates(transaction_ids) {
        return Err(ChainCommitStateError::DuplicateTransaction(txn_id));
    }

    if let Some(transaction_id) = block_manager
        .contains_any_transactions(branch_head_id, transaction_ids)
        .map_err(|err| {
            ChainCommitStateError::Error(format!(
                "During validate_no_duplicate_transactions: {:?}",
                err
            ))
        })?
    {
        return Err(ChainCommitStateError::DuplicateTransaction(transaction_id));
    }

    Ok(())
}

pub fn validate_transaction_dependencies(
    block_manager: &BlockManager,
    branch_head_id: &str,
    transactions: &[Transaction],
) -> Result<(), ChainCommitStateError> {
    let mut dependencies = vec![];
    let mut txn_ids = vec![];
    for txn in transactions {
        txn_ids.push(txn.header_signature.clone());

        for dep in &txn.dependencies {
            if !dependencies.contains(&dep) {
                dependencies.push(&dep);
            }
        }
    }
    for dep in &dependencies {
        // Check for dependencies within the given block's batches
        if txn_ids.contains(dep) {
            continue;
        }

        let block_manager_contains_transaction = block_manager
            .contains_any_transactions(branch_head_id, &[dep])
            .map_err(|err| {
                ChainCommitStateError::Error(format!(
                    "During validate transaction dependencies: {:?}",
                    err
                ))
            })?
            .is_some();

        if block_manager_contains_transaction {
            continue;
        }
        return Err(ChainCommitStateError::MissingDependency(dep.to_string()));
    }
    Ok(())
}

pub struct TransactionCommitCache {
    committed: HashSet<String>,
    commit_store: CommitStore,
}

impl TransactionCommitCache {
    pub fn new(commit_store: CommitStore) -> Self {
        TransactionCommitCache {
            committed: HashSet::new(),
            commit_store,
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
        // Shouldn't expect here
        self.committed.contains(transaction_id)
            || self
                .commit_store
                .contains_transaction(transaction_id)
                .expect("Couldn't check commit store for txn")
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
        let block_num = 3;
        let chain2 = ["B3-2", "B4-2", "B5-2"]
            .iter()
            .map(|ref mut block_id| {
                let block = create_block_w_batches_txns(block_id, previous_block_id, block_num);
                previous_block_id = block_id;
                block
            })
            .collect();

        let mut previous_block_id = "B3-2";
        let block_num = 4;
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
            check_no_duplicates(&[&"1".into(), &"2".into(), &"3".into()]),
            None
        );
    }

    #[test]
    fn test_duplicates1() {
        assert_eq!(
            check_no_duplicates(&[&"1".into(), &"2".into(), &"1".into()]),
            Some("1".into())
        );
    }

    #[test]
    fn test_duplicates2() {
        assert_eq!(
            check_no_duplicates(&[&"1".into(), &"1".into(), &"2".into()]),
            Some("1".into())
        );
    }

    #[test]
    fn test_dependency_in_other_fork() {
        let block_manager = setup_state();

        let transactions: Vec<Transaction> = ["B6b0t0", "B6b0t1", "B6b0t2"]
            .iter()
            .map(|t_id| create_transaction((*t_id).into(), vec!["B2b0t0".into()]))
            .collect();

        block_manager
            .persist("B5", "commit")
            .expect("The block manager is able to persist all blocks known to it");

        assert_eq!(
            validate_transaction_dependencies(&block_manager, "B5-1", &transactions),
            Err(ChainCommitStateError::MissingDependency("B2b0t0".into()))
        );
    }

    #[test]
    fn test_dependency_in_chain() {
        let block_manager = setup_state();

        let transactions: Vec<Transaction> = ["B6b0t0", "B6b0t1", "B6b0t2"]
            .iter()
            .map(|t_id| create_transaction((*t_id).into(), vec!["B1b0t0".into()]))
            .collect();

        block_manager
            .persist("B5", "commit")
            .expect("The block manager is able to persist all blocks known to it");

        assert_eq!(
            validate_transaction_dependencies(&block_manager, "B5-1", &transactions),
            Ok(())
        );
    }

    #[test]
    fn test_dependency_in_chain_chain_head_greater() {
        let block_manager = setup_state();

        let transactions: Vec<Transaction> = ["B3-1b0t0", "B3-1b0t1", "B3-1b0t2"]
            .iter()
            .map(|t_id| create_transaction((*t_id).into(), vec!["B1b0t0".into()]))
            .collect();

        block_manager
            .persist("B5", "commit")
            .expect("The block manager is able to persist all blocks known to it");

        assert_eq!(
            validate_transaction_dependencies(&block_manager, "B2", &transactions),
            Ok(())
        );
    }

    #[test]
    fn test_dependency_in_uncommitted() {
        let block_manager = setup_state();

        let transactions: Vec<Transaction> = ["B6b0t0", "B6b0t1", "B6b0t2"]
            .iter()
            .map(|t_id| create_transaction((*t_id).into(), vec!["B4-3b0t0".into()]))
            .collect();

        block_manager
            .persist("B1", "commit")
            .expect("The block manager is able to persist all blocks known to it");

        assert_eq!(
            validate_transaction_dependencies(&block_manager, "B5-3", &transactions),
            Ok(())
        );
    }

    #[test]
    fn test_no_duplicate_batches() {
        let block_manager = setup_state();

        let batches = ["B6b0".into(), "B6b1".into()];

        block_manager
            .persist("B4", "commit")
            .expect("The block manager is able to persist all blocks known to it");

        assert_eq!(
            validate_no_duplicate_batches(
                &block_manager,
                "B5",
                &batches.iter().collect::<Vec<&String>>()
            ),
            Ok(())
        );
    }

    #[test]
    fn test_no_duplicates_because_batches_in_other_fork() {
        let block_manager = setup_state();

        let batches = ["B3b0".into(), "B3b1".into()];

        block_manager
            .persist("B5", "commit")
            .expect("The block manager is able to persist all blocks known to it");

        assert_eq!(
            validate_no_duplicate_batches(
                &block_manager,
                "B5-2",
                &batches.iter().collect::<Vec<&String>>()
            ),
            Ok(())
        );
    }

    #[test]
    fn test_no_duplicate_batches_duplicate_in_branch() {
        let block_manager = setup_state();

        let batches = ["B2b0".into(), "B2b1".into()];

        block_manager
            .persist("B5", "commit")
            .expect("The block manage is able to persist all blocks known to it");

        assert!(validate_no_duplicate_batches(
            &block_manager,
            "B5-2",
            &batches.iter().collect::<Vec<&String>>(),
        )
        .is_err(),);
    }

    #[test]
    fn test_no_duplicate_batches_duplicate_in_uncommitted() {
        let block_manager = setup_state();

        let batches = ["B5-2b0".into(), "B5-2b1".into()];

        block_manager
            .persist("B5", "commit")
            .expect("The block manager is able to persist all blocks known to it");

        assert!(validate_no_duplicate_batches(
            &block_manager,
            "B5-2",
            &batches.iter().collect::<Vec<&String>>(),
        )
        .is_err(),);
    }

    #[test]
    fn test_no_duplicate_batches_duplicate_in_other_fork() {
        let block_manager = setup_state();

        let batches = ["B2b0".into(), "B2b1".into()];

        block_manager
            .persist("B5", "commit")
            .expect("The block manager is able to persist all blocks known to it");

        assert_eq!(
            validate_no_duplicate_batches(
                &block_manager,
                "B5-1",
                &batches.iter().collect::<Vec<&String>>()
            ),
            Ok(())
        );
    }

    #[test]
    fn test_no_duplicate_transactions() {
        let block_manager = setup_state();

        let transactions = [
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

        assert_eq!(
            validate_no_duplicate_transactions(
                &block_manager,
                "B5",
                &transactions.iter().collect::<Vec<&String>>()
            ),
            Ok(())
        );
    }

    #[test]
    fn test_no_duplicate_transactions_duplicate_in_branch() {
        let block_manager = setup_state();

        let transactions = ["B6b0t0".into(), "B6b0t1".into(), "B2b0t2".into()];

        block_manager
            .persist("B5-3", "commit")
            .expect("The block manager is able to persist all blocks known to it");

        assert!(validate_no_duplicate_transactions(
            &block_manager,
            "B5-2",
            &transactions.iter().collect::<Vec<&String>>(),
        )
        .is_err(),)
    }

    #[test]
    fn test_no_duplicate_transactions_duplicate_in_uncommitted() {
        let block_manager = setup_state();

        let transactions = ["B6b0t0".into(), "B6b0t1".into(), "B2-1b0t1".into()];

        block_manager
            .persist("B5-3", "commit")
            .expect("The block manager is able to persist all blocks known to it");

        assert!(validate_no_duplicate_transactions(
            &block_manager,
            "B5-4",
            &transactions.iter().collect::<Vec<&String>>(),
        )
        .is_err(),);
    }

    #[test]
    fn test_no_duplicate_transactions_duplicate_in_other_fork() {
        let block_manager = setup_state();

        let transactions = ["B6b0t0".into(), "B6b0t1".into(), "B2b0t1".into()];

        block_manager
            .persist("B5", "commit")
            .expect("The block manager is able to persist all blocks known to it");

        assert_eq!(
            validate_no_duplicate_transactions(
                &block_manager,
                "B5-1",
                &transactions.iter().collect::<Vec<&String>>()
            ),
            Ok(())
        );
    }

    #[test]
    fn test_before_genesis() {
        let block_manager = setup_state();

        let transactions = ["B0b0t0".into(), "B0b0t1".into(), "B0b0t2".into()];
        let batches = ["B0b0".into(), "B0b1".into()];

        assert_eq!(
            validate_no_duplicate_batches(
                &block_manager,
                NULL_BLOCK_IDENTIFIER,
                &batches.iter().collect::<Vec<&String>>()
            ),
            Ok(())
        );

        assert_eq!(
            validate_no_duplicate_transactions(
                &block_manager,
                NULL_BLOCK_IDENTIFIER,
                &transactions.iter().collect::<Vec<&String>>()
            ),
            Ok(())
        );

        let transactions = ["B3b0t0".into(), "B3b0t1".into(), "B3b0t2".into()];
        let batches = ["B3b0".into(), "B3b1".into()];

        assert_eq!(
            validate_no_duplicate_batches(
                &block_manager,
                "B2",
                &batches.iter().collect::<Vec<&String>>()
            ),
            Ok(())
        );

        assert_eq!(
            validate_no_duplicate_transactions(
                &block_manager,
                "B2",
                &transactions.iter().collect::<Vec<&String>>()
            ),
            Ok(())
        );

        let transactions = ["B3b0t0".into(), "B3b0t1".into(), "B3b0t2".into()];
        let batches = ["B3b0".into(), "B3b1".into()];

        assert!(validate_no_duplicate_batches(
            &block_manager,
            "B3",
            &batches.iter().collect::<Vec<&String>>(),
        )
        .is_err(),);
        assert!(validate_no_duplicate_transactions(
            &block_manager,
            "B3",
            &transactions.iter().collect::<Vec<&String>>(),
        )
        .is_err(),);
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
            block_num,
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

    fn setup_state() -> BlockManager {
        let block_manager = BlockManager::new();

        for branch in create_chains_to_put_in_block_manager() {
            block_manager
                .put(branch)
                .expect("The branches were created to be `put` in the block manager without error");
        }
        let block_store = Box::new(InMemoryBlockStore::new());
        block_manager
            .add_store("commit", block_store.clone())
            .expect("The block manager failed to add a blockstore");

        block_manager
    }
}

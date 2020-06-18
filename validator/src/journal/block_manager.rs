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

#![allow(unknown_lints)]

use std::collections::{HashMap, HashSet};
use std::iter::{FromIterator, Peekable};
use std::sync::{Arc, RwLock};

use block::Block;
use journal::block_store::{BatchIndex, BlockStoreError, IndexedBlockStore, TransactionIndex};
use journal::NULL_BLOCK_IDENTIFIER;
use metrics;

lazy_static! {
    static ref COLLECTOR: metrics::MetricsCollectorHandle =
        metrics::get_collector("sawtooth_validator.block_manager");
}

#[derive(Debug, PartialEq)]
pub enum BlockManagerError {
    MissingPredecessor(String),
    MissingPredecessorInBranch(String),
    MissingInput,
    UnknownBlock,
    UnknownBlockStore,
    BlockStoreError,
}

impl From<BlockStoreError> for BlockManagerError {
    fn from(_other: BlockStoreError) -> Self {
        BlockManagerError::BlockStoreError
    }
}

/// An external block reference that is owned by and can be passed between validator components.
/// Implements the `Drop` trait to allow for automatically decrementing the external reference
/// count for the block ID in the block manager.
pub struct BlockRef {
    block_id: String,
    block_manager: BlockManager,
}

impl BlockRef {
    fn new(block_id: String, block_manager: BlockManager) -> Self {
        BlockRef {
            block_id,
            block_manager,
        }
    }

    pub fn block_id(&self) -> &str {
        &self.block_id
    }
}

impl Drop for BlockRef {
    fn drop(&mut self) {
        // This will be the only place unref_block is called
        self.block_manager
            .unref_block(self.block_id.as_str())
            .unwrap_or_else(|err| {
                error!(
                    "Failed to unref block {} on drop due to error: {:?}",
                    self.block_id, err
                );
                false
            });
    }
}

struct RefCount {
    pub block_id: String,
    pub previous_block_id: String,
    pub external_ref_count: u64,
    pub internal_ref_count: u64,
}

impl RefCount {
    fn new_reffed_block(block_id: String, previous_id: String) -> Self {
        RefCount {
            block_id,
            previous_block_id: previous_id,
            external_ref_count: 0,
            internal_ref_count: 1,
        }
    }

    fn new_unreffed_block(block_id: String, previous_id: String) -> Self {
        RefCount {
            block_id,
            previous_block_id: previous_id,
            external_ref_count: 1,
            internal_ref_count: 0,
        }
    }

    fn increase_internal_ref_count(&mut self) {
        self.internal_ref_count += 1;
    }

    fn decrease_internal_ref_count(&mut self) {
        match self.internal_ref_count.checked_sub(1) {
            Some(ref_count) => self.internal_ref_count = ref_count,
            None => panic!(
                "The internal ref-count for {} fell below zero, its lowest possible value",
                self.block_id
            ),
        }
    }

    fn increase_external_ref_count(&mut self) {
        self.external_ref_count += 1;
    }

    fn decrease_external_ref_count(&mut self) {
        match self.external_ref_count.checked_sub(1) {
            Some(ref_count) => self.external_ref_count = ref_count,
            None => panic!(
                "The external ref-count for {} fell below zero, its lowest possible value",
                self.block_id
            ),
        }
    }
}

/// An Enum describing where a block is found within the BlockManager.
/// This is used by iterators calling private methods.
enum BlockLocation {
    MainCache(Block),
    InStore(String),
    Unknown,
}

#[derive(Default)]
struct BlockManagerState {
    block_by_block_id: RwLock<HashMap<String, Block>>,

    blockstore_by_name: RwLock<HashMap<String, Box<IndexedBlockStore>>>,

    references_by_block_id: RwLock<HashMap<String, RefCount>>,
}

impl BlockManagerState {
    fn contains(
        references_block_id: &HashMap<String, RefCount>,
        blockstore_by_name: &HashMap<String, Box<IndexedBlockStore>>,
        block_id: &str,
    ) -> Result<bool, BlockManagerError> {
        let block_is_null_block = block_id == NULL_BLOCK_IDENTIFIER;
        if block_is_null_block {
            return Ok(true);
        }

        let block_has_been_put = references_block_id.contains_key(block_id);
        if block_has_been_put {
            return Ok(true);
        }

        let block_in_some_store = blockstore_by_name
            .iter()
            .any(|(_, store)| store.get(&[block_id]).map(|res| res.count()).unwrap_or(0) > 0);

        if block_in_some_store {
            return Ok(true);
        }

        Ok(false)
    }

    /// Checks that every block is preceded by the block referenced by block.previous_block_id except the
    /// zeroth block in tail, which references head.
    fn check_predecessor_relationship(
        &self,
        tail: &[Block],
        head: &Block,
    ) -> Result<(), BlockManagerError> {
        let mut previous = None;
        for block in tail {
            match previous {
                Some(previous_block_id) => {
                    if block.previous_block_id != previous_block_id {
                        return Err(BlockManagerError::MissingPredecessorInBranch(format!(
                            "During Put, missing predecessor of block {}: {}",
                            block.header_signature, block.previous_block_id
                        )));
                    }
                    previous = Some(block.header_signature.as_str());
                }
                None => {
                    if block.previous_block_id != head.header_signature {
                        return Err(BlockManagerError::MissingPredecessorInBranch(format!(
                            "During Put, missing predecessor of block {}: {}",
                            block.previous_block_id, head.header_signature
                        )));
                    }

                    previous = Some(block.header_signature.as_str());
                }
            }
        }
        Ok(())
    }

    fn put(&self, branch: Vec<Block>) -> Result<(), BlockManagerError> {
        let mut references_by_block_id = self
            .references_by_block_id
            .write()
            .expect("Acquiring reference write lock; lock poisoned");
        let mut block_by_block_id = self
            .block_by_block_id
            .write()
            .expect("Acquiring block pool write lock; lock poisoned");
        let blockstore_by_name = self
            .blockstore_by_name
            .read()
            .expect("Acquiring blockstore name lock; lock poisoned");
        match branch.split_first() {
            Some((head, tail)) => {
                if !Self::contains(
                    &references_by_block_id,
                    &blockstore_by_name,
                    &head.previous_block_id,
                )? {
                    return Err(BlockManagerError::MissingPredecessor(format!(
                        "During Put, missing predecessor of block {}: {}",
                        head.header_signature, head.previous_block_id
                    )));
                }

                self.check_predecessor_relationship(tail, head)?;
                if !Self::contains(
                    &references_by_block_id,
                    &blockstore_by_name,
                    &head.header_signature,
                )? {
                    if let Some(r) = references_by_block_id.get_mut(&head.previous_block_id) {
                        r.increase_internal_ref_count();
                    }
                }
            }
            None => return Err(BlockManagerError::MissingInput),
        }
        let mut blocks_not_added_yet: Vec<Block> = Vec::new();
        for block in branch {
            if !Self::contains(
                &references_by_block_id,
                &blockstore_by_name,
                &block.header_signature,
            )? {
                blocks_not_added_yet.push(block);
            }
        }
        if let Some((last_block, blocks_with_references)) = blocks_not_added_yet.split_last() {
            references_by_block_id.insert(
                last_block.header_signature.clone(),
                RefCount::new_unreffed_block(
                    last_block.header_signature.clone(),
                    last_block.previous_block_id.clone(),
                ),
            );
            block_by_block_id.insert(last_block.header_signature.clone(), last_block.clone());

            blocks_with_references.into_iter().for_each(|block| {
                block_by_block_id.insert(block.header_signature.clone(), block.clone());

                references_by_block_id.insert(
                    block.header_signature.clone(),
                    RefCount::new_reffed_block(
                        block.header_signature.clone(),
                        block.previous_block_id.clone(),
                    ),
                );
            })
        };

        COLLECTOR
            .gauge("BlockManager.pool_size", None, None)
            .set_value(block_by_block_id.len());

        Ok(())
    }

    fn get_block_from_main_cache_or_blockstore_name(&self, block_id: &str) -> BlockLocation {
        let block_by_block_id = self
            .block_by_block_id
            .read()
            .expect("Acquiring block pool read lock; lock poisoned");
        let blockstore_by_name = self
            .blockstore_by_name
            .read()
            .expect("Acquiring blockstore by name read lock; lock poisoned");
        let block = block_by_block_id.get(block_id).cloned();
        if block.is_some() {
            BlockLocation::MainCache(block.unwrap())
        } else {
            let name: Option<String> = blockstore_by_name
                .iter()
                .find(|(_, store)| store.get(&[block_id]).map(|res| res.count()).unwrap_or(0) > 0)
                .map(|(name, _)| name.clone());

            name.map(BlockLocation::InStore)
                .unwrap_or(BlockLocation::Unknown)
        }
    }

    fn get_block_from_blockstore(
        &self,
        block_id: &str,
        store_name: &str,
    ) -> Result<Option<Block>, BlockManagerError> {
        let blockstore_by_name = self
            .blockstore_by_name
            .read()
            .expect("Acquiring blockstore by name read lock; lock poisoned");
        let blockstore = blockstore_by_name.get(store_name);
        let block = blockstore
            .ok_or(BlockManagerError::UnknownBlockStore)?
            .get(&[block_id])?
            .nth(0);
        Ok(block)
    }

    fn ref_block(&self, block_id: &str) -> Result<(), BlockManagerError> {
        let mut references_by_block_id = self
            .references_by_block_id
            .write()
            .expect("Acquiring references write lock; lock poisoned");

        if let Some(r) = references_by_block_id.get_mut(block_id) {
            r.increase_external_ref_count();
            return Ok(());
        }

        let blockstore_by_name = self
            .blockstore_by_name
            .read()
            .expect("Acquiring blockstore by name read lock; lock poisoned");

        let block = blockstore_by_name
            .iter()
            .filter_map(|(_, store)| {
                store
                    .get(&[block_id])
                    .expect("Failed to get from blockstore")
                    .next()
            })
            .next();

        if let Some(block) = block {
            let mut rc = RefCount::new_reffed_block(
                block.header_signature.clone(),
                block.previous_block_id.clone(),
            );
            rc.increase_external_ref_count();
            references_by_block_id.insert(block.header_signature.clone(), rc);
            return Ok(());
        }

        Err(BlockManagerError::UnknownBlock)
    }

    fn unref_block(&self, tip: &str) -> Result<bool, BlockManagerError> {
        let mut references_by_block_id = self
            .references_by_block_id
            .write()
            .expect("Acquiring references write lock; lock poisoned");

        let (external_ref_count, internal_ref_count, block_id) =
            self.lower_tip_blocks_refcount(&mut references_by_block_id, tip)?;

        let mut blocks_to_remove = vec![];

        let mut optional_new_tip = None;

        let dropped = if external_ref_count == 0 && internal_ref_count == 0 {
            if let Some(block_id) = block_id {
                let (mut predecesors_to_remove, new_tip) = self
                    .find_block_ids_for_blocks_with_refcount_1_or_less(
                        &references_by_block_id,
                        &block_id,
                    );
                blocks_to_remove.append(&mut predecesors_to_remove);
                debug!("Removing block {}", tip);
                self.block_by_block_id
                    .write()
                    .expect("Acquiring block pool write lock; lock poisoned")
                    .remove(tip);
                references_by_block_id.remove(tip);
                optional_new_tip = new_tip;
            }
            true
        } else {
            false
        };

        COLLECTOR
            .counter("BlockManager.expired", None, None)
            .inc_n(blocks_to_remove.len());

        blocks_to_remove.iter().for_each(|block_id| {
            debug!("Removing block {}", block_id);
            self.block_by_block_id
                .write()
                .expect("Acquiring block pool write lock; lock poisoned")
                .remove(block_id);
            references_by_block_id.remove(block_id);
        });

        if let Some(block_id) = optional_new_tip {
            if let Some(ref mut new_tip) = references_by_block_id.get_mut(block_id.as_str()) {
                new_tip.decrease_internal_ref_count();
            };
        };

        Ok(dropped)
    }

    fn lower_tip_blocks_refcount(
        &self,
        references_by_block_id: &mut HashMap<String, RefCount>,
        tip: &str,
    ) -> Result<(u64, u64, Option<String>), BlockManagerError> {
        match references_by_block_id.get_mut(tip) {
            Some(ref mut ref_block) => {
                ref_block.decrease_external_ref_count();
                Ok((
                    ref_block.external_ref_count,
                    ref_block.internal_ref_count,
                    Some(ref_block.block_id.clone()),
                ))
            }
            None => Err(BlockManagerError::UnknownBlock),
        }
    }

    /// Starting from some `tip` block_id, walk back until finding a block that has a
    /// internal ref_count >= 2 or an external_ref_count > 0.
    fn find_block_ids_for_blocks_with_refcount_1_or_less(
        &self,
        references_by_block_id: &HashMap<String, RefCount>,
        tip: &str,
    ) -> (Vec<String>, Option<String>) {
        let mut blocks_to_remove = vec![];
        let mut block_id = tip;
        let pointed_to;
        loop {
            if let Some(ref ref_block) = references_by_block_id.get(block_id) {
                if ref_block.internal_ref_count >= 2 || ref_block.external_ref_count >= 1 {
                    pointed_to = Some(block_id.into());
                    break;
                } else if ref_block.previous_block_id == NULL_BLOCK_IDENTIFIER {
                    blocks_to_remove.push(block_id.into());
                    pointed_to = None;
                    break;
                } else {
                    blocks_to_remove.push(block_id.into());
                }
                block_id = &ref_block.previous_block_id;
            }
        }
        (blocks_to_remove, pointed_to)
    }

    fn add_store(
        &self,
        store_name: &str,
        store: Box<IndexedBlockStore>,
    ) -> Result<(), BlockManagerError> {
        let mut references_by_block_id = self
            .references_by_block_id
            .write()
            .expect("Acquiring references_by_block_id lock; lock poisoned");

        let mut stores = self
            .blockstore_by_name
            .write()
            .expect("Acquiring blockstore write lock; lock poisoned");

        if let Some(head) = store.iter().expect("Failed to get store iterator").next() {
            if !references_by_block_id.contains_key(&head.header_signature) {
                references_by_block_id.insert(
                    head.header_signature.clone(),
                    RefCount::new_unreffed_block(
                        head.header_signature.clone(),
                        head.previous_block_id.clone(),
                    ),
                );
            }
        }

        stores.insert(store_name.into(), store);
        Ok(())
    }
}

/// The BlockManager maintains integrity of all the blocks it contains,
/// such that for any Block within the BlockManager,
/// that Block's predecessor is also within the BlockManager.
#[derive(Default, Clone)]
pub struct BlockManager {
    state: Arc<BlockManagerState>,
    persist_lock: Arc<RwLock<()>>,
}

impl BlockManager {
    pub fn new() -> Self {
        BlockManager::default()
    }

    /// Returns whether the transaction id `id` is in the TransactionIndex of
    /// the IndexedBlockStore and supposing the Block `block_id` is in the block store,
    /// whether the transaction is <= the block
    ///
    /// Note:
    /// transaction_index_contains requires the indexed blockstore under
    /// consideration to be exclusive with respect to writes.
    fn transaction_index_contains(
        &self,
        index: &IndexedBlockStore,
        block_id: &str,
        id: &str,
    ) -> Result<bool, BlockManagerError> {
        if let Some(block) = TransactionIndex::get_block_by_id(index, id)? {
            let head = index
                .get(&[block_id])?
                .next()
                .expect("BlockStore updated during transaction index check");
            Ok(block.block_num <= head.block_num)
        } else {
            Ok(false)
        }
    }

    /// Returns whether the batch id `id` is in the BatchIndex of
    /// the IndexedBlockStore and supposing the Block `block_id` is in the block store,
    /// whether the batch is <= the block
    ///
    /// Note:
    /// transaction_index_contains requires the indexed blockstore under
    /// consideration to be exclusive with respect to writes.
    fn batch_index_contains(
        &self,
        index: &IndexedBlockStore,
        block_id: &str,
        id: &str,
    ) -> Result<bool, BlockManagerError> {
        if let Some(block) = BatchIndex::get_block_by_id(index, id)? {
            let head = index
                .get(&[block_id])?
                .next()
                .expect("BlockStore updated during batch index check");
            Ok(block.block_num <= head.block_num)
        } else {
            Ok(false)
        }
    }

    pub fn contains_any_transactions(
        &self,
        block_id: &str,
        ids: &[&String],
    ) -> Result<Option<String>, BlockManagerError> {
        let _lock = self
            .persist_lock
            .read()
            .expect("The persist RwLock is poisoned");
        let blockstore_by_name = self
            .state
            .blockstore_by_name
            .read()
            .expect("The blockstore RwLock is poisoned");
        if let Some(store) = self.persisted_branch_contains_block(&blockstore_by_name, block_id)? {
            self.persisted_branch_contains_any_transactions(store, block_id, ids)
        } else {
            if block_id != NULL_BLOCK_IDENTIFIER {
                for pool_block in self.branch(block_id)? {
                    if let Some(store) = self.persisted_branch_contains_block(
                        &blockstore_by_name,
                        &pool_block.header_signature,
                    )? {
                        return self.persisted_branch_contains_any_transactions(
                            store,
                            &pool_block.header_signature,
                            ids,
                        );
                    }
                    if let Some(transaction_id) =
                        self.block_contains_any_transaction(&pool_block, ids)
                    {
                        return Ok(Some(transaction_id));
                    }
                }
            }

            Ok(None)
        }
    }

    pub fn contains_any_batches(
        &self,
        block_id: &str,
        ids: &[&String],
    ) -> Result<Option<String>, BlockManagerError> {
        let _lock = self
            .persist_lock
            .read()
            .expect("The persist RwLock is poisoned");
        let blockstore_by_name = self
            .state
            .blockstore_by_name
            .read()
            .expect("The blockstore RwLock is poisoned");
        if let Some(store) = self.persisted_branch_contains_block(&blockstore_by_name, block_id)? {
            self.persisted_branch_contains_any_batches(store, block_id, ids)
        } else {
            if block_id != NULL_BLOCK_IDENTIFIER {
                for pool_block in self.branch(block_id)? {
                    if let Some(store) = self.persisted_branch_contains_block(
                        &blockstore_by_name,
                        &pool_block.header_signature,
                    )? {
                        return self.persisted_branch_contains_any_batches(
                            store,
                            &pool_block.header_signature,
                            ids,
                        );
                    }

                    if let Some(batch_id) = self.block_contains_any_batch(&pool_block, ids) {
                        return Ok(Some(batch_id));
                    }
                }
            }
            Ok(None)
        }
    }

    fn block_contains_any_transaction(&self, block: &Block, ids: &[&String]) -> Option<String> {
        let transaction_ids: HashSet<&String> = HashSet::from_iter(
            block
                .batches
                .iter()
                .fold(vec![], |mut arr, b| {
                    for transaction in &b.transactions {
                        arr.push(&transaction.header_signature)
                    }
                    arr
                })
                .into_iter(),
        );
        let comparison_transaction_ids: HashSet<&String> = HashSet::from_iter(ids.iter().cloned());
        transaction_ids
            .intersection(&comparison_transaction_ids)
            .next()
            .map(|t| t.to_string())
    }

    fn block_contains_any_batch(&self, block: &Block, ids: &[&String]) -> Option<String> {
        let batch_ids = HashSet::from_iter(block.batches.iter().map(|b| &b.header_signature));
        let comparison_batch_ids: HashSet<&String> = HashSet::from_iter(ids.iter().cloned());
        batch_ids
            .intersection(&comparison_batch_ids)
            .next()
            .map(|t| t.to_string())
    }

    fn persisted_branch_contains_block<'a>(
        &self,
        blockstore_by_name: &'a HashMap<String, Box<IndexedBlockStore>>,
        block_id: &str,
    ) -> Result<Option<&'a IndexedBlockStore>, BlockManagerError> {
        if let Some((_, store)) = blockstore_by_name
            .iter()
            .find(|(_, store)| store.get(&[block_id]).map(|res| res.count()).unwrap_or(0) > 0)
        {
            Ok(Some(store.as_ref()))
        } else {
            Ok(None)
        }
    }

    fn persisted_branch_contains_any_transactions(
        &self,
        store: &IndexedBlockStore,
        block_id: &str,
        ids: &[&String],
    ) -> Result<Option<String>, BlockManagerError> {
        for id in ids {
            if self.transaction_index_contains(store, block_id, id)? {
                return Ok(Some(id.to_string()));
            }
        }
        Ok(None)
    }

    fn persisted_branch_contains_any_batches(
        &self,
        store: &IndexedBlockStore,
        block_id: &str,
        ids: &[&String],
    ) -> Result<Option<String>, BlockManagerError> {
        for id in ids {
            if self.batch_index_contains(store, block_id, id)? {
                return Ok(Some(id.to_string()));
            }
        }

        Ok(None)
    }

    pub fn contains(&self, block_id: &str) -> Result<bool, BlockManagerError> {
        let references_by_block_id = self
            .state
            .references_by_block_id
            .read()
            .expect("Acquiring references read lock; lock poisoned");
        let blockstore_by_name = self
            .state
            .blockstore_by_name
            .read()
            .expect("Acquiring blockstore name read lock; lock poisoned");
        BlockManagerState::contains(&references_by_block_id, &blockstore_by_name, block_id)
    }

    /// Put is idempotent, making the guarantee that after put is called with a
    /// block in the vector argument, that block is in the BlockManager
    /// whether or not it was already in the BlockManager.
    /// Put makes three other guarantees
    ///     - If the zeroth block in branch does not have its predecessor
    ///       in the BlockManager an error is returned
    ///     - If any block after the zeroth block in branch
    ///       does not have its predecessor as the block to its left in
    ///       branch, an error is returned.
    ///     - If branch is empty, an error is returned
    pub fn put(&self, branch: Vec<Block>) -> Result<(), BlockManagerError> {
        self.state.put(branch)
    }

    pub fn get(&self, block_ids: &[&str]) -> Box<Iterator<Item = Option<Block>>> {
        Box::new(GetBlockIterator::new(Arc::clone(&self.state), block_ids))
    }

    pub fn get_from_blockstore(
        &self,
        block_id: &str,
        store_name: &str,
    ) -> Result<Option<Block>, BlockManagerError> {
        self.state.get_block_from_blockstore(block_id, store_name)
    }

    pub fn branch(&self, tip: &str) -> Result<Box<Iterator<Item = Block>>, BlockManagerError> {
        Ok(Box::new(BranchIterator::new(
            Arc::clone(&self.state),
            tip.into(),
        )?))
    }

    pub fn branch_diff(
        &self,
        tip: &str,
        exclude: &str,
    ) -> Result<Box<Iterator<Item = Block>>, BlockManagerError> {
        Ok(Box::new(BranchDiffIterator::new(
            Arc::clone(&self.state),
            tip,
            exclude,
        )?))
    }

    pub fn ref_block(&self, tip: &str) -> Result<BlockRef, BlockManagerError> {
        self.state.ref_block(tip)?;
        Ok(BlockRef::new(tip.into(), self.clone()))
    }

    /// Starting at a tip block, if the tip block's ref-count drops to 0,
    /// remove all blocks until a ref-count of 1 is found.
    /// NOTE: this method will be made private; it will only be called when a `BlockRef` is dropped
    pub fn unref_block(&self, tip: &str) -> Result<bool, BlockManagerError> {
        self.state.unref_block(tip)
    }

    pub fn add_store(
        &self,
        store_name: &str,
        store: Box<IndexedBlockStore>,
    ) -> Result<(), BlockManagerError> {
        self.state.add_store(store_name, store)
    }

    #[allow(clippy::needless_pass_by_value)]
    fn remove_blocks_from_blockstore(
        &self,
        to_be_removed: Vec<Block>,
        block_by_block_id: &mut HashMap<String, Block>,
        store_name: &str,
    ) -> Result<(), BlockManagerError> {
        let blocks_for_the_main_pool = {
            let mut blockstore_by_name = self
                .state
                .blockstore_by_name
                .write()
                .expect("Acquiring blockstore write lock; lock poisoned");
            let mut blockstore = blockstore_by_name
                .get_mut(store_name)
                .ok_or(BlockManagerError::UnknownBlockStore)?;

            blockstore.delete(
                &to_be_removed
                    .iter()
                    .map(|b| b.header_signature.as_str())
                    .collect::<Vec<&str>>(),
            )?
        };

        COLLECTOR
            .counter("BlockManager.persisted", None, None)
            .dec_n(blocks_for_the_main_pool.len());

        for block in blocks_for_the_main_pool {
            block_by_block_id.insert(block.header_signature.clone(), block);
        }

        Ok(())
    }

    fn insert_blocks_in_blockstore(
        &self,
        to_be_inserted: Vec<Block>,
        block_by_block_id: &mut HashMap<String, Block>,
        store_name: &str,
    ) -> Result<(), BlockManagerError> {
        COLLECTOR
            .counter("BlockManager.persisted", None, None)
            .inc_n(to_be_inserted.len());

        for block in &to_be_inserted {
            block_by_block_id.remove(&block.header_signature);
        }

        let mut blockstore_by_name = self
            .state
            .blockstore_by_name
            .write()
            .expect("Acquiring blockstore write lock; lock poisoned");
        let blockstore = blockstore_by_name
            .get_mut(store_name)
            .ok_or(BlockManagerError::UnknownBlockStore)?;
        blockstore.put(to_be_inserted)?;

        Ok(())
    }

    pub fn persist(&self, head: &str, store_name: &str) -> Result<(), BlockManagerError> {
        let _lock = self
            .persist_lock
            .write()
            .expect("The persist RwLock is poisoned");
        if !self
            .state
            .blockstore_by_name
            .read()
            .expect("Unable to obtain read lock; it has been poisoned")
            .contains_key(store_name)
        {
            return Err(BlockManagerError::UnknownBlockStore);
        }

        let head_block_in_blockstore = {
            let blockstore_by_name = self
                .state
                .blockstore_by_name
                .read()
                .expect("Acquiring blockstore read lock; lock poisoned");
            let mut block_store_iter = blockstore_by_name
                .get(store_name)
                .expect("Blockstore removed during persist operation")
                .iter()?;
            block_store_iter.nth(0).map(|b| b.header_signature.clone())
        };
        if let Some(head_block_in_blockstore) = head_block_in_blockstore {
            let other = head_block_in_blockstore.as_str();
            let to_be_inserted = self.branch_diff(head, other)?.collect();
            let to_be_removed = self.branch_diff(other, head)?.collect();
            let mut block_by_block_id = self
                .state
                .block_by_block_id
                .write()
                .expect("Acquiring block pool write lock; lock poisoned");
            self.remove_blocks_from_blockstore(to_be_removed, &mut block_by_block_id, store_name)?;
            self.insert_blocks_in_blockstore(to_be_inserted, &mut block_by_block_id, store_name)?;
        } else {
            // There are no other blocks in the blockstore and so
            // we would like to insert all of the blocks
            let to_be_inserted = self.branch(head)?.collect();
            let mut block_by_block_id = self
                .state
                .block_by_block_id
                .write()
                .expect("Acquiring block pool write lock; lock poisoned");
            self.insert_blocks_in_blockstore(to_be_inserted, &mut block_by_block_id, store_name)?;
        }

        Ok(())
    }
}

pub struct GetBlockIterator {
    state: Arc<BlockManagerState>,
    block_ids: Vec<String>,
    index: usize,
}

impl GetBlockIterator {
    fn new(state: Arc<BlockManagerState>, block_ids: &[&str]) -> Self {
        GetBlockIterator {
            state,
            block_ids: block_ids.iter().map(|s| (*s).into()).collect(),
            index: 0,
        }
    }
}

impl Iterator for GetBlockIterator {
    type Item = Option<Block>;

    fn next(&mut self) -> Option<Self::Item> {
        if self.index >= self.block_ids.len() {
            return None;
        }

        let block_id = &self.block_ids[self.index];
        let block: Option<Block> = match self
            .state
            .get_block_from_main_cache_or_blockstore_name(&block_id)
        {
            BlockLocation::MainCache(block) => Some(block),

            BlockLocation::InStore(blockstore_name) => self
                .state
                .get_block_from_blockstore(block_id, &blockstore_name)
                .expect("The blockstore name returned for a block id doesn't contain the block."),

            BlockLocation::Unknown => None,
        };

        self.index += 1;

        Some(block)
    }
}

pub struct BranchIterator {
    state: Arc<BlockManagerState>,
    initial_block_id: String,
    next_block_id: String,
    blockstore: Option<String>,
}

impl BranchIterator {
    fn new(
        state: Arc<BlockManagerState>,
        first_block_id: String,
    ) -> Result<Self, BlockManagerError> {
        let next_block_id = {
            match state.ref_block(&first_block_id) {
                Ok(_) => first_block_id,
                Err(BlockManagerError::UnknownBlock) => {
                    return Err(BlockManagerError::UnknownBlock)
                }
                Err(err) => {
                    warn!("During constructing branch iterator: {:?}", err);
                    return Err(BlockManagerError::UnknownBlock);
                }
            }
        };
        Ok(BranchIterator {
            state,
            initial_block_id: next_block_id.clone(),
            next_block_id,
            blockstore: None,
        })
    }
}

impl Drop for BranchIterator {
    fn drop(&mut self) {
        if self.initial_block_id != NULL_BLOCK_IDENTIFIER {
            match self.state.unref_block(&self.initial_block_id) {
                Ok(_) => (),
                Err(err) => {
                    error!(
                        "Unable to unref block at {}: {:?}; ignoring",
                        &self.initial_block_id, err
                    );
                }
            }
        }
    }
}

impl Iterator for BranchIterator {
    type Item = Block;

    fn next(&mut self) -> Option<Self::Item> {
        if self.next_block_id == NULL_BLOCK_IDENTIFIER {
            None
        } else if self.blockstore.is_none() {
            match self
                .state
                .get_block_from_main_cache_or_blockstore_name(&self.next_block_id)
            {
                BlockLocation::MainCache(block) => {
                    self.next_block_id = block.previous_block_id.clone();
                    Some(block.clone())
                }
                BlockLocation::InStore(blockstore_name) => {
                    self.blockstore = Some(blockstore_name.clone());
                    let block = self.state
                        .get_block_from_blockstore(&self.next_block_id, &blockstore_name)
                        .expect("The blockstore name returned for a block id doesn't exist.")
                        .expect("The blockstore name returned for a block id doesn't contain the block.");

                    self.next_block_id = block.previous_block_id.clone();
                    Some(block)
                }
                BlockLocation::Unknown => None,
            }
        } else {
            let blockstore_id = self.blockstore.as_ref().unwrap();

            let block_option = self
                .state
                .get_block_from_blockstore(&self.next_block_id, blockstore_id)
                .expect("The BlockManager has lost a blockstore that is referenced by a block.");

            if let Some(block) = block_option {
                self.next_block_id = block.previous_block_id.clone();
                Some(block.clone())
            } else {
                None
            }
        }
    }
}

pub struct BranchDiffIterator {
    left_branch: Peekable<BranchIterator>,
    right_branch: Peekable<BranchIterator>,

    has_reached_common_ancestor: bool,
}

impl BranchDiffIterator {
    fn new(
        state: Arc<BlockManagerState>,
        tip: &str,
        exclude: &str,
    ) -> Result<Self, BlockManagerError> {
        let mut left_iterator = BranchIterator::new(state.clone(), tip.into())?.peekable();
        let mut right_iterator = BranchIterator::new(state, exclude.into())?.peekable();

        let difference = {
            left_iterator
                .peek()
                .map(|left| {
                    left.block_num as i64
                        - right_iterator
                            .peek()
                            .map(|right| right.block_num as i64)
                            .unwrap_or(0)
                })
                .unwrap_or(0)
        };
        if difference < 0 {
            // seek to the same height on the exclude side
            right_iterator.nth(difference.abs() as usize - 1);
        }

        Ok(BranchDiffIterator {
            left_branch: left_iterator,
            right_branch: right_iterator,
            has_reached_common_ancestor: false,
        })
    }
}

impl Iterator for BranchDiffIterator {
    type Item = Block;

    fn next(&mut self) -> Option<Self::Item> {
        if self.has_reached_common_ancestor {
            None
        } else {
            let advance_right = {
                let left_peek = self.left_branch.peek();
                let right_peek = self.right_branch.peek();

                if left_peek.is_none() {
                    self.has_reached_common_ancestor = true;
                    return None;
                }

                if right_peek.is_some()
                    && right_peek.as_ref().unwrap().header_signature
                        == left_peek.as_ref().unwrap().header_signature
                {
                    self.has_reached_common_ancestor = true;
                    return None;
                }

                right_peek.is_some()
                    && right_peek.as_ref().unwrap().block_num
                        == left_peek.as_ref().unwrap().block_num
            };

            if advance_right {
                self.right_branch.next();
            }

            self.left_branch.next()
        }
    }
}

#[cfg(test)]
mod tests {

    use super::{BlockManager, BlockManagerError};
    use block::Block;
    use journal::block_store::InMemoryBlockStore;
    use journal::NULL_BLOCK_IDENTIFIER;

    fn create_block(header_signature: &str, previous_block_id: &str, block_num: u64) -> Block {
        Block {
            header_signature: header_signature.into(),
            batches: vec![],
            state_root_hash: "".into(),
            consensus: vec![],
            batch_ids: vec![],
            signer_public_key: "".into(),
            previous_block_id: previous_block_id.into(),
            block_num,
            header_bytes: vec![],
        }
    }

    #[test]
    fn test_put_ref_then_unref() {
        let a = create_block("A", NULL_BLOCK_IDENTIFIER, 0);
        let b = create_block("B", "A", 1);
        let b_block_id = b.header_signature.clone();
        let c = create_block("C", "B", 2);
        let c_block_id = c.header_signature.clone();

        let block_manager = BlockManager::new();
        assert_eq!(block_manager.put(vec![a, b]), Ok(()));

        assert_eq!(block_manager.put(vec![c]), Ok(()));

        block_manager.ref_block(b_block_id.as_str()).unwrap();
        block_manager.unref_block(c_block_id.as_str()).unwrap();

        let d = create_block("D", "C", 3);

        assert_eq!(
            block_manager.put(vec![d]),
            Err(BlockManagerError::MissingPredecessor(format!(
                "During Put, missing predecessor of block D: C"
            )))
        );

        let e = create_block("E", "B", 2);

        block_manager.put(vec![e]).unwrap();
    }

    #[test]
    fn test_multiple_branches_put_ref_then_unref() {
        let a = create_block("A", NULL_BLOCK_IDENTIFIER, 0);
        let b = create_block("B", "A", 1);
        let c = create_block("C", "B", 2);
        let c_block_id = &c.header_signature.clone();
        let d = create_block("D", "C", 3);
        let d_block_id = &d.header_signature.clone();
        let e = create_block("E", "C", 3);

        let f = create_block("F", "E", 4);
        let f_block_id = &f.header_signature.clone();

        let block_manager = BlockManager::new();
        block_manager.put(vec![a.clone(), b, c]).unwrap();
        block_manager.put(vec![d]).unwrap();
        block_manager.put(vec![e, f]).unwrap();

        block_manager.unref_block(d_block_id).unwrap();

        block_manager.unref_block(f_block_id).unwrap();

        let q = create_block("Q", "C", 3);
        let q_block_id = &q.header_signature.clone();
        block_manager.put(vec![q]).unwrap();
        block_manager.unref_block(c_block_id).unwrap();
        block_manager.unref_block(q_block_id).unwrap();

        let g = create_block("G", "A", 1);
        assert_eq!(
            block_manager.put(vec![g]),
            Err(BlockManagerError::MissingPredecessor(format!(
                "During Put, missing predecessor of block G: A"
            )))
        );
    }

    #[test]
    fn test_put_empty_vec() {
        let block_manager = BlockManager::new();
        assert_eq!(
            block_manager.put(vec![]),
            Err(BlockManagerError::MissingInput)
        );
    }

    #[test]
    fn test_put_missing_predecessor() {
        let block_manager = BlockManager::new();
        let a = create_block("A", "o", 54);
        let b = create_block("B", "A", 55);
        assert_eq!(
            block_manager.put(vec![a, b]),
            Err(BlockManagerError::MissingPredecessor(format!(
                "During Put, missing predecessor of block A: o"
            )))
        );
    }

    #[test]
    fn test_get_blocks() {
        let block_manager = BlockManager::new();
        let a = create_block("A", NULL_BLOCK_IDENTIFIER, 0);
        let b = create_block("B", "A", 1);
        let c = create_block("C", "B", 2);

        block_manager
            .put(vec![a.clone(), b.clone(), c.clone()])
            .unwrap();

        let mut get_block_iter = block_manager.get(&["A", "C", "D"]);

        assert_eq!(get_block_iter.next(), Some(Some(a.clone())));
        assert_eq!(get_block_iter.next(), Some(Some(c.clone())));
        assert_eq!(get_block_iter.next(), Some(None));
        assert_eq!(get_block_iter.next(), None);

        // Should only return the items that are found.
        let mut get_block_with_unknowns = block_manager.get(&["A", "X", "C"]);
        assert_eq!(get_block_with_unknowns.next(), Some(Some(a.clone())));
        assert_eq!(get_block_with_unknowns.next(), Some(None));
        assert_eq!(get_block_with_unknowns.next(), Some(Some(c.clone())));
        assert_eq!(get_block_with_unknowns.next(), None);
    }

    #[test]
    fn test_branch_in_memory() {
        let block_manager = BlockManager::new();
        let a = create_block("A", NULL_BLOCK_IDENTIFIER, 0);
        let b = create_block("B", "A", 1);
        let c = create_block("C", "B", 2);

        block_manager
            .put(vec![a.clone(), b.clone(), c.clone()])
            .unwrap();

        let mut branch_iter = block_manager.branch("C").unwrap();

        assert_eq!(branch_iter.next(), Some(c));
        assert_eq!(branch_iter.next(), Some(b));
        assert_eq!(branch_iter.next(), Some(a));
        assert_eq!(branch_iter.next(), None);

        assert!(
            block_manager.branch("P").is_err(),
            "Iterating on a branch that does not exist returns an error"
        );
    }

    #[test]
    fn test_branch_diff() {
        let block_manager = BlockManager::new();

        let a = create_block("A", NULL_BLOCK_IDENTIFIER, 0);
        let b = create_block("B", "A", 1);
        let c = create_block("C", "A", 1);
        let d = create_block("D", "C", 2);
        let e = create_block("E", "D", 3);

        block_manager.put(vec![a.clone(), b.clone()]).unwrap();
        block_manager.put(vec![c.clone()]).unwrap();
        block_manager.put(vec![d.clone(), e.clone()]).unwrap();

        let mut branch_diff_iter = block_manager.branch_diff("C", "B").unwrap();

        assert_eq!(branch_diff_iter.next(), Some(c.clone()));
        assert_eq!(branch_diff_iter.next(), None);

        let mut branch_diff_iter2 = block_manager.branch_diff("B", "E").unwrap();

        assert_eq!(branch_diff_iter2.next(), Some(b.clone()));
        assert_eq!(branch_diff_iter2.next(), None);

        let mut branch_diff_iter3 = block_manager.branch_diff("C", "E").unwrap();

        assert_eq!(branch_diff_iter3.next(), None);

        let mut branch_diff_iter4 = block_manager.branch_diff("E", "C").unwrap();

        assert_eq!(branch_diff_iter4.next(), Some(e.clone()));
        assert_eq!(branch_diff_iter4.next(), Some(d.clone()));
        assert_eq!(branch_diff_iter4.next(), None);

        // Test that it will return an error if a block is missing
        assert!(block_manager.branch_diff("E", "X").is_err());

        // Test that it will return an error result if the tip is unkown
        assert!(
            block_manager.branch_diff("X", "E").is_err(),
            "Branch Diff with an unknown tip will cause an error"
        );
    }

    #[test]
    fn test_persist_ref_unref() {
        let block_manager = BlockManager::new();

        let a = create_block("A", NULL_BLOCK_IDENTIFIER, 0);
        let b = create_block("B", "A", 1);
        let c = create_block("C", "A", 1);
        let d = create_block("D", "C", 2);
        let e = create_block("E", "D", 3);
        let f = create_block("F", "C", 2);

        let q = create_block("Q", "F", 3);
        let p = create_block("P", "E", 4);

        block_manager.put(vec![a.clone(), b.clone()]).unwrap();
        block_manager
            .put(vec![c.clone(), d.clone(), e.clone()])
            .unwrap();
        block_manager.put(vec![f.clone()]).unwrap();

        let blockstore = Box::new(InMemoryBlockStore::new());
        block_manager.add_store("commit", blockstore).unwrap();

        block_manager.persist("C", "commit").unwrap();
        block_manager.persist("B", "commit").unwrap();

        {
            let d_ref = block_manager.ref_block("D").unwrap();

            block_manager.persist("C", "commit").unwrap();
            block_manager.unref_block("B").unwrap();

            block_manager.persist("F", "commit").unwrap();
            block_manager.persist("E", "commit").unwrap();

            block_manager.unref_block("F").unwrap();
        } // Drop d_ref

        block_manager.persist("A", "commit").unwrap();

        block_manager.unref_block("E").unwrap();

        assert_eq!(
            block_manager.put(vec![q]),
            Err(BlockManagerError::MissingPredecessor(format!(
                "During Put, missing predecessor of block Q: F"
            )))
        );

        assert_eq!(
            block_manager.put(vec![p]),
            Err(BlockManagerError::MissingPredecessor(format!(
                "During Put, missing predecessor of block P: E"
            )))
        );
    }

    #[test]
    fn test_idempotent() {
        let blockman = BlockManager::new();

        let a = create_block("A", NULL_BLOCK_IDENTIFIER, 0);
        let b = create_block("B", "A", 1);
        let c = create_block("C", "B", 1);
        let d = create_block("D", "C", 1);

        blockman
            .put(vec![a.clone(), b.clone(), c.clone(), d.clone()])
            .unwrap();
        // Ext. Ref. = 1

        {
            let d_ref = blockman.ref_block("D").unwrap();
            // Ext. Ref. = 2

            blockman
                .put(vec![a.clone(), b.clone(), c.clone(), d.clone()])
                .unwrap();
            // Ext. Ref. = 2
        }
        // Ext. Ref. = 1 (dropped d_ref)

        assert!(blockman.unref_block("D").unwrap());
        // Ext. Ref. = 0, dropped
    }
}

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

use std::collections::{HashMap, HashSet};
use std::sync::{Arc, Mutex};

use block::Block;
use journal::block_validator::BlockStatusStore;
use journal::block_wrapper::BlockStatus;
use journal::chain::COMMIT_STORE;
use journal::{block_manager::BlockManager, NULL_BLOCK_IDENTIFIER};
use metrics;

lazy_static! {
    static ref COLLECTOR: metrics::MetricsCollectorHandle =
        metrics::get_collector("sawtooth_validator.block_validator");
}

#[derive(Clone)]
pub struct BlockScheduler<B: BlockStatusStore> {
    state: Arc<Mutex<BlockSchedulerState<B>>>,
}

impl<B: BlockStatusStore> BlockScheduler<B> {
    pub fn new(block_manager: BlockManager, block_status_store: B) -> Self {
        BlockScheduler {
            state: Arc::new(Mutex::new(BlockSchedulerState {
                block_manager,
                block_status_store,
                pending: HashSet::new(),
                processing: HashSet::new(),
                descendants_by_previous_id: HashMap::new(),
            })),
        }
    }

    /// Schedule the blocks, returning those that are directly ready to
    /// validate
    pub fn schedule(&self, blocks: Vec<Block>) -> Vec<Block> {
        self.state
            .lock()
            .expect("The BlockScheduler Mutex was poisoned")
            .schedule(blocks)
    }

    /// Mark the block associated with block_id as having completed block
    /// validation, returning any blocks that are not available for processing
    pub fn done(&self, block_id: &str) -> Vec<Block> {
        self.state
            .lock()
            .expect("The BlockScheduler Mutex was poisoned")
            .done(block_id)
    }

    pub fn contains(&self, block_id: &str) -> bool {
        self.state
            .lock()
            .expect("The BlockScheduler Mutex was poisoned")
            .contains(block_id)
    }
}

struct BlockSchedulerState<B: BlockStatusStore> {
    pub block_manager: BlockManager,
    pub block_status_store: B,
    pub pending: HashSet<String>,
    pub processing: HashSet<String>,
    pub descendants_by_previous_id: HashMap<String, Vec<Block>>,
}

impl<B: BlockStatusStore> BlockSchedulerState<B> {
    fn schedule(&mut self, blocks: Vec<Block>) -> Vec<Block> {
        let mut ready = vec![];
        for block in blocks {
            if self.processing.contains(&block.header_signature) {
                debug!(
                    "During block scheduling, block already in process: {}",
                    &block.header_signature
                );
                continue;
            }

            if self.pending.contains(&block.header_signature) {
                debug!(
                    "During block scheduling, block already in pending: {}",
                    &block.header_signature
                );
                continue;
            }

            if self.processing.contains(&block.previous_block_id) {
                debug!(
                    "During block scheduling, previous block {} in process, adding block {} to pending",
                    &block.previous_block_id,
                    &block.header_signature);
                self.add_block_to_pending(block);
                continue;
            }

            if self.pending.contains(&block.previous_block_id) {
                debug!(
                    "During block scheduling, previous block {} is pending, adding block {} to pending",
                    &block.previous_block_id,
                    &block.header_signature);

                self.add_block_to_pending(block);
                continue;
            }

            if block.previous_block_id != NULL_BLOCK_IDENTIFIER
                && self.block_validity(&block.previous_block_id) == BlockStatus::Unknown
            {
                info!(
                    "During block scheduling, predecessor of block {}, {}, status is unknown. Scheduling all blocks since last predecessor with known status",
                    &block.header_signature, &block.previous_block_id);

                let blocks_previous_to_previous = self.block_manager
                        .branch(&block.previous_block_id)
                        .expect("Block id of block previous to block being scheduled is unknown to the block manager");
                self.add_block_to_pending(block);

                let mut to_be_scheduled = vec![];
                for predecessor in blocks_previous_to_previous {
                    if self
                        .block_status_store
                        .status(&predecessor.header_signature)
                        != BlockStatus::Unknown
                    {
                        break;
                    }
                    match self.block_manager.ref_block(&predecessor.header_signature) {
                        Ok(_) => (),
                        Err(err) => {
                            warn!(
                                "Failed to ref block {} during cache-miss block rescheduling: {:?}",
                                &predecessor.header_signature, err
                            );
                        }
                    }
                    to_be_scheduled.push(predecessor);
                }

                to_be_scheduled.reverse();

                for block in self.schedule(to_be_scheduled) {
                    if !ready.contains(&block) {
                        self.processing.insert(block.header_signature.clone());
                        ready.push(block);
                    }
                }
            } else {
                debug!("Adding block {} for processing", &block.header_signature);

                self.processing.insert(block.header_signature.clone());
                ready.push(block);
            }
        }
        self.update_gauges();
        ready
    }

    fn block_validity(&self, block_id: &str) -> BlockStatus {
        let status = self.block_status_store.status(block_id);
        if status == BlockStatus::Unknown {
            match self
                .block_manager
                .get_from_blockstore(block_id, COMMIT_STORE)
            {
                Err(err) => {
                    warn!("Error during checking block validity: {:?}", err);
                    BlockStatus::Unknown
                }
                Ok(None) => BlockStatus::Unknown,
                Ok(Some(_)) => BlockStatus::Valid,
            }
        } else {
            status
        }
    }

    fn done(&mut self, block_id: &str) -> Vec<Block> {
        self.processing.remove(block_id);
        let ready = self
            .descendants_by_previous_id
            .remove(block_id)
            .unwrap_or_default();

        for blk in &ready {
            self.pending.remove(&blk.header_signature);
            self.processing.insert(blk.header_signature.clone());
        }

        self.update_gauges();
        ready
    }

    fn contains(&self, block_id: &str) -> bool {
        self.pending.contains(block_id) || self.processing.contains(block_id)
    }

    fn add_block_to_pending(&mut self, block: Block) {
        self.pending.insert(block.header_signature.clone());
        if let Some(ref mut waiting_descendants) = self
            .descendants_by_previous_id
            .get_mut(&block.previous_block_id)
        {
            if !waiting_descendants.contains(&block) {
                waiting_descendants.push(block);
            }
            return;
        }

        self.descendants_by_previous_id
            .insert(block.previous_block_id.clone(), vec![block]);
    }

    fn update_gauges(&self) {
        let mut blocks_processing = COLLECTOR.gauge("BlockScheduler.blocks_processing", None, None);
        blocks_processing.set_value(self.processing.len());
        let mut blocks_pending = COLLECTOR.gauge("BlockScheduler.blocks_pending", None, None);
        blocks_pending.set_value(self.pending.len())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use journal::NULL_BLOCK_IDENTIFIER;
    use std::sync::{Arc, Mutex};

    #[test]
    fn test_block_scheduler_simple() {
        let block_manager = BlockManager::new();
        let block_status_store = MockStore::new();
        let block_a = create_block("A", NULL_BLOCK_IDENTIFIER, 0);
        let block_a1 = create_block("A1", "A", 1);
        let block_a2 = create_block("A2", "A", 1);
        let block_b2 = create_block("B2", "A2", 2);

        let block_unknown = create_block("UNKNOWN", "A", 1);
        let block_b = create_block("B", "UNKNOWN", 2);
        block_manager
            .put(vec![block_a.clone(), block_unknown.clone()])
            .expect("The block manager failed to `put` a branch");

        let block_scheduler = BlockScheduler::new(block_manager, block_status_store);

        assert_eq!(
            block_scheduler.schedule(vec![
                block_a.clone(),
                block_a1.clone(),
                block_a2.clone(),
                block_b2.clone(),
            ]),
            vec![block_a.clone()]
        );

        assert_eq!(
            block_scheduler.done(&block_a.header_signature),
            vec![block_a1, block_a2]
        );

        assert_eq!(block_scheduler.schedule(vec![block_b]), vec![block_unknown]);
    }

    #[test]
    fn test_block_scheduler_multiple_forks() {
        let block_manager = BlockManager::new();
        let block_status_store: Arc<Mutex<HashMap<String, BlockStatus>>> =
            Arc::new(Mutex::new(HashMap::new()));

        let block_a = create_block("A", NULL_BLOCK_IDENTIFIER, 0);
        let block_b = create_block("B", "A", 1);
        let block_c1 = create_block("C1", "B", 2);
        let block_c2 = create_block("C2", "B", 2);
        let block_c3 = create_block("C3", "B", 2);
        let block_d1 = create_block("D11", "C1", 3);
        let block_d2 = create_block("D12", "C1", 3);
        let block_d3 = create_block("D13", "C1", 3);

        block_manager
            .put(vec![
                block_a.clone(),
                block_b.clone(),
                block_c1.clone(),
                block_d1.clone(),
            ])
            .expect("The block manager failed to `put` a branch");
        block_manager
            .put(vec![block_b.clone(), block_c2.clone()])
            .expect("The block manager failed to put a branch");

        block_manager
            .put(vec![block_b.clone(), block_c3.clone()])
            .expect("The block manager failed to put a block");

        block_manager
            .put(vec![block_c1.clone(), block_d2.clone()])
            .expect("The block manager failed to `put` a branch");

        block_manager
            .put(vec![block_c1.clone(), block_d3.clone()])
            .expect("The block manager failed to put a branch");

        let block_scheduler = BlockScheduler::new(block_manager, block_status_store);

        assert_eq!(
            block_scheduler.schedule(vec![block_a.clone()]),
            vec![block_a.clone()],
            "The genesis block's predecessor does not need to be validated"
        );

        assert_eq!(
            block_scheduler.schedule(vec![
                block_b.clone(),
                block_c1.clone(),
                block_c2.clone(),
                block_c3.clone(),
            ]),
            vec![],
            "Block A has not been validated yet"
        );

        assert_eq!(
            block_scheduler.done(&block_a.header_signature),
            vec![block_b.clone()],
            "Marking Block A as complete, makes Block B available"
        );

        assert_eq!(
            block_scheduler.schedule(vec![block_d1.clone(), block_d2.clone(), block_d3.clone()]),
            vec![],
            "None of Blocks D1, D2, D3 are available"
        );

        assert_eq!(
            block_scheduler.done(&block_b.header_signature),
            vec![block_c1.clone(), block_c2.clone(), block_c3.clone()],
            "Marking Block B as complete, makes Block C1, C2, C3 available"
        );

        assert_eq!(
            block_scheduler.done(&block_c2.header_signature),
            vec![],
            "No Blocks are available"
        );

        assert_eq!(
            block_scheduler.done(&block_c3.header_signature),
            vec![],
            "No Blocks are available"
        );

        assert_eq!(
            block_scheduler.done(&block_c1.header_signature),
            vec![block_d1.clone(), block_d2.clone(), block_d3.clone()],
            "Blocks D1, D2, D3 are available"
        );
    }

    #[test]
    fn test_cache_misses() {
        let block_manager = BlockManager::new();
        let block_status_store: Arc<Mutex<HashMap<String, BlockStatus>>> =
            Arc::new(Mutex::new(HashMap::new()));

        let block_a = create_block("A", NULL_BLOCK_IDENTIFIER, 0);
        let block_b = create_block("B", "A", 1);
        let block_c1 = create_block("C1", "B", 2);
        let block_c2 = create_block("C2", "B", 2);
        let block_c3 = create_block("C3", "B", 2);

        block_manager
            .put(vec![block_a.clone(), block_b.clone(), block_c1.clone()])
            .expect("Block manager errored trying to put a branch");

        block_manager
            .put(vec![block_b.clone(), block_c2.clone()])
            .expect("Block manager errored trying to put a branch");

        block_manager
            .put(vec![block_b.clone(), block_c3.clone()])
            .expect("Block manager errored trying to put a branch");

        let block_scheduler = BlockScheduler::new(block_manager, Arc::clone(&block_status_store));

        assert_eq!(
            block_scheduler.schedule(vec![block_a.clone(), block_b.clone()]),
            vec![block_a.clone()],
            "Block A is ready, but block b is not"
        );

        block_status_store
            .lock()
            .expect("Mutex was poisoned")
            .insert(block_a.header_signature.clone(), BlockStatus::Valid);

        assert_eq!(
            block_scheduler.done(&block_a.header_signature),
            vec![block_b.clone()],
            "Now Block B is ready"
        );

        // We are not inserting a status for block b so there will be a later miss

        assert_eq!(
            block_scheduler.done(&block_b.header_signature),
            vec![],
            "Block B is done and there are no further blocks"
        );

        // Now a cache miss

        assert_eq!(
            block_scheduler.schedule(vec![block_c1.clone(), block_c2.clone(), block_c3.clone()]),
            vec![block_b.clone()],
            "Since there was a cache miss, block b must be scheduled again"
        );
    }

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

    impl BlockStatusStore for Arc<Mutex<HashMap<String, BlockStatus>>> {
        fn status(&self, block_id: &str) -> BlockStatus {
            self.lock()
                .expect("Mutex was poisoned")
                .get(block_id)
                .cloned()
                .unwrap_or(BlockStatus::Unknown)
        }
    }
    #[derive(Clone)]
    struct MockStore {}

    impl MockStore {
        fn new() -> Self {
            MockStore {}
        }
    }

    impl BlockStatusStore for MockStore {
        fn status(&self, block_id: &str) -> BlockStatus {
            if block_id == "UNKNOWN" {
                return BlockStatus::Unknown;
            }
            BlockStatus::Valid
        }
    }
}

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

            if &block.previous_block_id != NULL_BLOCK_IDENTIFIER
                && self.block_status_store.status(&block.previous_block_id) == BlockStatus::Unknown
            {
                info!(
                    "During block scheduling, predecessor of block {} status is unknown. Scheduling all blocks since last predecessor with known status",
                    &block.header_signature);

                let blocks_previous_to_previous = self.block_manager
                        .branch(&block.previous_block_id)
                        .expect("Block id of block previous to block being scheduled is unknown to the block manager");
                self.add_block_to_pending(block);

                let mut to_be_scheduled = vec![];
                for predecessor in blocks_previous_to_previous {
                    eprintln!("{}", &predecessor.header_signature);
                    if self
                        .block_status_store
                        .status(&predecessor.header_signature)
                        != BlockStatus::Unknown
                    {
                        break;
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

    fn done(&mut self, block_id: &str) -> Vec<Block> {
        self.processing.remove(block_id);
        let ready = self
            .descendants_by_previous_id
            .remove(block_id)
            .unwrap_or(vec![]);

        for blk in &ready {
            self.pending.remove(&blk.header_signature);
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

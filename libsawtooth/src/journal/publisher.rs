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

 // allow borrowed box, this is required to use PublisherState trait
 #![allow(clippy::borrowed_box)]

use std::collections::{HashMap, HashSet, VecDeque};
use std::mem;
use std::slice::Iter;
use std::sync::{Arc, RwLock};

use crate::journal::block_manager::BlockRef;
use crate::journal::candidate_block::CandidateBlock;
use crate::{batch::Batch, block::Block, execution::execution_platform::ExecutionPlatform};

#[derive(Debug)]
pub enum InitializeBlockError {
    BlockInProgress,
    MissingPredecessor,
}

#[derive(Debug)]
pub enum FinalizeBlockError {
    BlockNotInitialized,
    BlockEmpty,
}

pub trait BatchObserver: Send + Sync {
    fn notify_batch_pending(&self, batch: &Batch);
}

pub trait PublisherState: Send + Sync {
    fn pending_batches(&self) -> &PendingBatchesPool;

    fn mut_pending_batches(&mut self) -> &mut PendingBatchesPool;

    fn chain_head(&mut self, block: Option<Block>);

    fn candidate_block(&mut self) -> &mut Option<Box<dyn CandidateBlock>>;

    fn set_candidate_block(
        &mut self,
        candidate_block: Option<Box<dyn CandidateBlock>>,
    ) -> Option<Box<dyn CandidateBlock>>;

    fn block_references(&mut self) -> &mut HashMap<String, BlockRef>;

    fn batch_observers(&self) -> &[Box<dyn BatchObserver>];

    fn transaction_executor(&self) -> &Box<dyn ExecutionPlatform>;
}

pub trait SyncPublisher: Send + Sync {
    fn box_clone(&self) -> Box<dyn SyncPublisher>;

    fn state(&self) -> &Arc<RwLock<Box<dyn PublisherState>>>;

    fn on_chain_updated(
        &self,
        state: &mut Box<dyn PublisherState>,
        chain_head: Block,
        committed_batches: Vec<Batch>,
        uncommitted_batches: Vec<Batch>,
    );

    fn on_chain_updated_internal(
        &mut self,
        chain_head: Block,
        committed_batches: Vec<Batch>,
        uncommitted_batches: Vec<Batch>,
    );

    fn on_batch_received(&self, batch: Batch);

    fn cancel_block(&self, state: &mut Box<dyn PublisherState>, unref_block: bool);

    fn initialize_block(
        &self,
        state: &mut Box<dyn PublisherState>,
        previous_block: &Block,
        ref_block: bool,
    ) -> Result<(), InitializeBlockError>;

    fn finalize_block(
        &self,
        state: &mut Box<dyn PublisherState>,
        consensus_data: &[u8],
        force: bool,
    ) -> Result<String, FinalizeBlockError>;

    fn summarize_block(
        &self,
        state: &mut Box<dyn PublisherState>,
        force: bool,
    ) -> Result<Vec<u8>, FinalizeBlockError>;

    fn stopped(&self) -> bool;

    fn stop(&self);
}

impl Clone for Box<dyn SyncPublisher> {
    fn clone(&self) -> Box<dyn SyncPublisher> {
        self.box_clone()
    }
}

/// Ordered batches waiting to be processed
pub struct PendingBatchesPool {
    batches: Vec<Batch>,
    ids: HashSet<String>,
    limit: QueueLimit,
}

impl PendingBatchesPool {
    pub fn new(sample_size: usize, initial_value: usize) -> PendingBatchesPool {
        PendingBatchesPool {
            batches: Vec::new(),
            ids: HashSet::new(),
            limit: QueueLimit::new(sample_size, initial_value),
        }
    }

    pub fn len(&self) -> usize {
        self.batches.len()
    }

    pub fn is_empty(&self) -> bool {
        self.batches.is_empty()
    }

    pub fn iter(&self) -> Iter<Batch> {
        self.batches.iter()
    }

    pub fn contains(&self, id: &str) -> bool {
        self.ids.contains(id)
    }

    fn reset(&mut self) {
        self.batches = Vec::new();
        self.ids = HashSet::new();
    }

    pub fn append(&mut self, batch: Batch) -> bool {
        if self.ids.insert(batch.header_signature.clone()) {
            self.batches.push(batch);
            true
        } else {
            false
        }
    }

    /// Recomputes the list of pending batches
    ///
    /// Args:
    ///   committed (List<Batches>): Batches committed in the current chain
    ///   since the root of the fork switching from.
    ///   uncommitted (List<Batches): Batches that were committed in the old
    ///   fork since the common root.
    pub fn rebuild(&mut self, committed: Option<Vec<Batch>>, uncommitted: Option<Vec<Batch>>) {
        let committed_set = if let Some(committed) = committed {
            committed
                .iter()
                .map(|i| i.header_signature.clone())
                .collect::<HashSet<String>>()
        } else {
            HashSet::new()
        };

        let previous_batches = self.batches.clone();

        self.reset();

        // Uncommitted and pending are disjoint sets since batches can only be
        // committed to a chain once.

        if let Some(batch_list) = uncommitted {
            for batch in batch_list {
                if !committed_set.contains(&batch.header_signature) {
                    self.append(batch);
                }
            }
        }

        for batch in previous_batches {
            if !committed_set.contains(&batch.header_signature) {
                self.append(batch);
            }
        }

        gauge!(
            "publisher.BlockPublisher.pending_batch_gauge",
            self.batches.len() as i64
        );
    }

    pub fn update(&mut self, mut still_pending: Vec<Batch>, last_sent: &Batch) {
        let last_index = self
            .batches
            .iter()
            .position(|i| i.header_signature == last_sent.header_signature);

        let unsent = if let Some(idx) = last_index {
            let mut unsent = vec![];
            mem::swap(&mut unsent, &mut self.batches);
            still_pending.extend_from_slice(unsent.split_off(idx + 1).as_slice());
            still_pending
        } else {
            let mut unsent = vec![];
            mem::swap(&mut unsent, &mut self.batches);
            unsent
        };

        self.reset();

        for batch in unsent {
            self.append(batch);
        }

        gauge!(
            "publisher.BlockPublisher.pending_batch_gauge",
            self.batches.len() as i64
        );
    }

    pub fn update_limit(&mut self, consumed: usize) {
        self.limit.update(self.batches.len(), consumed);
    }

    pub fn limit(&self) -> usize {
        self.limit.get()
    }
}

struct RollingAverage {
    samples: VecDeque<usize>,
    current_average: usize,
}

impl RollingAverage {
    pub fn new(sample_size: usize, initial_value: usize) -> RollingAverage {
        let mut samples = VecDeque::with_capacity(sample_size);
        samples.push_back(initial_value);

        RollingAverage {
            samples,
            current_average: initial_value,
        }
    }

    pub fn value(&self) -> usize {
        self.current_average
    }

    /// Add the sample and return the updated average.
    pub fn update(&mut self, sample: usize) -> usize {
        self.samples.push_back(sample);
        self.current_average = self.samples.iter().sum::<usize>() / self.samples.len();
        self.current_average
    }
}

struct QueueLimit {
    avg: RollingAverage,
}

const QUEUE_MULTIPLIER: usize = 10;

impl QueueLimit {
    pub fn new(sample_size: usize, initial_value: usize) -> QueueLimit {
        QueueLimit {
            avg: RollingAverage::new(sample_size, initial_value),
        }
    }

    /// Use the current queue size and the number of items consumed to
    /// update the queue limit, if there was a significant enough change.
    /// Args:
    ///     queue_length (int): the current size of the queue
    ///     consumed (int): the number items consumed
    pub fn update(&mut self, queue_length: usize, consumed: usize) {
        if consumed > 0 {
            // Only update the average if either:
            // a. Not drained below the current average
            // b. Drained the queue, but the queue was not bigger than the
            //    current running average

            let remainder = queue_length.saturating_sub(consumed);

            if remainder > self.avg.value() || consumed > self.avg.value() {
                self.avg.update(consumed);
            }
        }
    }

    pub fn get(&self) -> usize {
        // Limit the number of items to QUEUE_MULTIPLIER times the publishing
        // average.  This allows the queue to grow geometrically, if the queue
        // is drained.
        QUEUE_MULTIPLIER * self.avg.value()
    }
}

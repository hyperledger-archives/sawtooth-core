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

use batch::Batch;

use std::collections::{HashSet, VecDeque};
use std::mem;
use std::slice::Iter;
use std::sync::mpsc::{channel, Receiver, RecvTimeoutError, SendError, Sender};
use std::sync::{Arc, Mutex, MutexGuard, PoisonError};
use std::time::Duration;

/// This queue keeps track of the batch ids so that components on the edge
/// can filter out duplicates early. However, there is still an opportunity for
/// duplicates to make it into this queue, which is intentional to avoid
/// blocking threads trying to put/get from the queue. Any duplicates
/// introduced by this must be filtered out later.
pub fn make_batch_queue() -> (IncomingBatchSender, IncomingBatchReceiver) {
    let (sender, reciever) = channel();
    let ids = Arc::new(Mutex::new(HashSet::new()));
    (
        IncomingBatchSender::new(ids.clone(), sender),
        IncomingBatchReceiver::new(ids, reciever),
    )
}

pub struct IncomingBatchReceiver {
    ids: Arc<Mutex<HashSet<String>>>,
    receiver: Receiver<Batch>,
}

impl IncomingBatchReceiver {
    pub fn new(
        ids: Arc<Mutex<HashSet<String>>>,
        receiver: Receiver<Batch>,
    ) -> IncomingBatchReceiver {
        IncomingBatchReceiver { ids, receiver }
    }

    pub fn get(&mut self, timeout: Duration) -> Result<Batch, BatchQueueError> {
        let batch = self.receiver.recv_timeout(timeout)?;
        self.ids.lock()?.remove(&batch.header_signature);
        Ok(batch)
    }
}

pub struct IncomingBatchSender {
    ids: Arc<Mutex<HashSet<String>>>,
    sender: Sender<Batch>,
}

impl IncomingBatchSender {
    pub fn new(ids: Arc<Mutex<HashSet<String>>>, sender: Sender<Batch>) -> IncomingBatchSender {
        IncomingBatchSender { ids, sender }
    }
    pub fn put(&mut self, batch: Batch) -> Result<(), BatchQueueError> {
        if !self.ids.lock()?.contains(&batch.header_signature) {
            self.ids.lock()?.insert(batch.header_signature.clone());
            self.sender.send(batch).map_err(BatchQueueError::from)
        } else {
            Ok(())
        }
    }
}

pub enum BatchQueueError {
    SenderError(SendError<Batch>),
    TimeoutError(RecvTimeoutError),
    MutexPoisonError(String),
}

impl From<SendError<Batch>> for BatchQueueError {
    fn from(e: SendError<Batch>) -> Self {
        BatchQueueError::SenderError(e)
    }
}

impl From<RecvTimeoutError> for BatchQueueError {
    fn from(e: RecvTimeoutError) -> Self {
        BatchQueueError::TimeoutError(e)
    }
}

impl<'a> From<PoisonError<MutexGuard<'a, HashSet<String>>>> for BatchQueueError {
    fn from(_e: PoisonError<MutexGuard<HashSet<String>>>) -> Self {
        BatchQueueError::MutexPoisonError("Muxtex Poisoned".into())
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

    pub fn iter(&self) -> Iter<Batch> {
        self.batches.iter()
    }

    fn contains(&self, id: &str) -> bool {
        self.ids.contains(id)
    }

    fn reset(&mut self) {
        self.batches = Vec::new();
        self.ids = HashSet::new();
    }

    pub fn append(&mut self, batch: Batch) {
        if !self.contains(&batch.header_signature) {
            self.ids.insert(batch.header_signature.clone());
            self.batches.push(batch);
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
    }

    pub fn update(&mut self, mut still_pending: Vec<Batch>, last_sent: Batch) {
        let last_index = self.batches
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

            let remainder = queue_length - consumed;

            if remainder > self.avg.value() || consumed > self.avg.value() {
                self.avg.update(consumed);
            }
        }
    }

    pub fn get(&self) -> usize {
        // Limit the number of items to 2 times the publishing average.  This
        // allows the queue to grow geometrically, if the queue is drained.
        2 * self.avg.value()
    }
}

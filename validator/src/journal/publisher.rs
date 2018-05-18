use proto::batch::Batch;
use std::collections::{HashSet, VecDeque};
use std::mem;
use std::slice::Iter;

/// Ordered batches wating to be processed
pub struct PendingBatchesPool {
    batches: Vec<Batch>,
    ids: HashSet<String>,
    limit: QueueLimit,
}

impl PendingBatchesPool {
    pub fn new(sample_size: usize, initial_value: i32) -> PendingBatchesPool {
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
        if !self.contains(&batch.get_header_signature()) {
            self.ids.insert(batch.get_header_signature().into());
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
                .map(|i| i.get_header_signature().into())
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
                if !committed_set.contains(batch.get_header_signature()) {
                    self.append(batch);
                }
            }
        }

        for batch in previous_batches {
            if !committed_set.contains(batch.get_header_signature()) {
                self.append(batch);
            }
        }
    }

    pub fn update(&mut self, mut still_pending: Vec<Batch>, last_sent: Batch) {
        let last_index = self.batches
            .iter()
            .position(|i| i.get_header_signature() == last_sent.get_header_signature());

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

    pub fn update_limit(&mut self, consumed: i32) {
        self.limit.update(self.batches.len() as i32, consumed);
    }

    pub fn limit(&self) -> i32 {
        self.limit.get()
    }
}

struct RollingAverage {
    samples: VecDeque<i32>,
    current_average: i32,
}

impl RollingAverage {
    pub fn new(sample_size: usize, initial_value: i32) -> RollingAverage {
        let mut samples = VecDeque::with_capacity(sample_size);
        samples.push_back(initial_value);

        RollingAverage {
            samples,
            current_average: initial_value,
        }
    }

    pub fn value(&self) -> i32 {
        self.current_average
    }

    /// Add the sample and return the updated average.
    pub fn update(&mut self, sample: i32) -> i32 {
        self.samples.push_back(sample);
        self.current_average = self.samples.iter().sum::<i32>() / self.samples.len() as i32;
        self.current_average
    }
}

struct QueueLimit {
    avg: RollingAverage,
}

impl QueueLimit {
    pub fn new(sample_size: usize, initial_value: i32) -> QueueLimit {
        QueueLimit {
            avg: RollingAverage::new(sample_size, initial_value),
        }
    }

    /// Use the current queue size and the number of items consumed to
    /// update the queue limit, if there was a significant enough change.
    /// Args:
    ///     queue_length (int): the current size of the queue
    ///     consumed (int): the number items consumed
    pub fn update(&mut self, queue_length: i32, consumed: i32) {
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

    pub fn get(&self) -> i32 {
        // Limit the number of items to 2 times the publishing average.  This
        // allows the queue to grow geometrically, if the queue is drained.
        2 * self.avg.value()
    }
}

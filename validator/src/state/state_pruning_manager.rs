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
use std::cmp::Ordering;
use std::collections::BinaryHeap;

use database::lmdb::LmdbDatabase;
use metrics;
use state::merkle::MerkleDatabase;

lazy_static! {
    static ref COLLECTOR: metrics::MetricsCollectorHandle =
        metrics::get_collector("sawtooth_validator.state");
}

/// The StatePruneManager manages a collection of state root hashes that will be
/// prune from the MerkleDatabase at intervals.  Pruning will occur by decimating
/// the state root hashes.  I.e. ten percent (rounded down) of the state roots in
/// the queue will be pruned.  This allows state roots to remain in the queue for
/// a period of time, on the chance that they are from a chain that has been
/// abandoned and then re-chosen as the primary chain.
pub struct StatePruningManager {
    // Contains the state root hashes slated for pruning
    state_root_prune_queue: BinaryHeap<PruneCandidate>,
    state_database: LmdbDatabase,
}

#[derive(Eq, PartialEq, Debug, Ord)]
struct PruneCandidate(u64, String);

impl PartialOrd for PruneCandidate {
    fn partial_cmp(&self, other: &PruneCandidate) -> Option<Ordering> {
        Some(Ordering::reverse(self.0.cmp(&other.0)))
    }
}

impl StatePruningManager {
    pub fn new(state_database: LmdbDatabase) -> Self {
        StatePruningManager {
            state_root_prune_queue: BinaryHeap::new(),
            state_database,
        }
    }

    /// Updates the pruning queue.  Abandoned roots will be added to the queue.
    /// Added roots will be removed from the queue.  This ensures that the state
    /// roots won't be removed, regardless of the chain state.
    pub fn update_queue(&mut self, added_roots: &[&str], abandoned_roots: &[(u64, &str)]) {
        // add the roots that have been abandoned.
        for (height, state_root_hash) in abandoned_roots {
            self.add_to_queue(*height, state_root_hash);
        }
        // Remove any state root hashes from the pruning queue that we may have switched
        // back too from an alternate chain
        let mut new_queue = BinaryHeap::with_capacity(0);
        ::std::mem::swap(&mut self.state_root_prune_queue, &mut new_queue);
        self.state_root_prune_queue = new_queue
            .into_iter()
            .filter(|candidate| {
                if !added_roots.contains(&candidate.1.as_str()) {
                    true
                } else {
                    debug!("Removing {} from pruning queue", candidate.1);
                    false
                }
            })
            .collect();
    }

    /// Add a single state root to the pruning queue.
    pub fn add_to_queue(&mut self, height: u64, state_root_hash: &str) {
        let state_root_hash = state_root_hash.into();
        if !self
            .state_root_prune_queue
            .iter()
            .any(|candidate| candidate.1 == state_root_hash)
        {
            debug!("Adding {} to pruning queue", state_root_hash);
            self.state_root_prune_queue
                .push(PruneCandidate(height, state_root_hash));
        }
    }

    /// Executes prune on any state root hash at or below the given depth.
    pub fn execute(&mut self, at_depth: u64) {
        let mut prune_candidates = vec![];

        while let Some(candidate) = self.state_root_prune_queue.pop() {
            if candidate.0 <= at_depth {
                prune_candidates.push(candidate);
            } else {
                self.state_root_prune_queue.push(candidate);
                break;
            }
        }

        let mut total_pruned_entries: usize = 0;
        for candidate in prune_candidates {
            match MerkleDatabase::prune(&self.state_database, &candidate.1) {
                Ok(removed_keys) => {
                    total_pruned_entries += removed_keys.len();

                    // the state root was not pruned (it is likely the root of a
                    // fork), so push it back into the queue.
                    if removed_keys.is_empty() {
                        self.state_root_prune_queue.push(candidate);
                    } else {
                        let mut state_roots_pruned_count =
                            COLLECTOR.counter("StatePruneManager.state_roots_pruned", None, None);
                        state_roots_pruned_count.inc();
                    }
                }
                Err(err) => {
                    error!("Unable to prune state root {}: {:?}", candidate.1, err);
                    self.state_root_prune_queue.push(candidate);
                }
            }
        }

        if total_pruned_entries > 0 {
            info!(
                "Pruned {} keys from the Global state Database",
                total_pruned_entries
            );
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ordering_candidates() {
        let mut heap = ::std::collections::BinaryHeap::new();

        heap.push(PruneCandidate(2, "two".into()));
        heap.push(PruneCandidate(3, "three".into()));
        heap.push(PruneCandidate(3, "another_three".into()));
        heap.push(PruneCandidate(4, "four".into()));

        assert_eq!(heap.pop(), Some(PruneCandidate(2, "two".into())));
        assert_eq!(heap.pop(), Some(PruneCandidate(3, "another_three".into())));
        assert_eq!(heap.pop(), Some(PruneCandidate(3, "three".into())));
        assert_eq!(heap.pop(), Some(PruneCandidate(4, "four".into())));
        assert_eq!(heap.pop(), None);
    }
}

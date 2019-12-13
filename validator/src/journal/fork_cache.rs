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

use std::collections::HashMap;
use std::mem;
use std::time::{Duration, Instant};

/// Tracks the most recently used chains
///
/// Forks expire when:
/// 1. A new fork is inserted with a `previous` equal to an existing fork
/// 2. The cache is purged and a fork has been in the cache longer than `keep_time`
///
pub struct ForkCache {
    keep_time: Duration,
    cache: HashMap<String, Instant>,
}

impl ForkCache {
    /// Create a new ForkCache which will call `on_expired` whenever a Fork expires from the cache.
    pub fn new(keep_time: Duration) -> Self {
        ForkCache {
            keep_time,
            cache: HashMap::new(),
        }
    }

    /// Insert a new fork. If `previous` is not None and it exists, it is removed and returned.
    /// Inserting the same `head` twice has no affect.
    pub fn insert(&mut self, head: &str, previous: Option<&str>) -> Option<String> {
        if self.cache.get(head).is_some() {
            return None;
        }

        let expired = self.take_previous_if_some(previous);

        self.insert_new_fork(head);

        expired
    }

    /// Remove and return all forks that have been in the cache longer than `keep_time`.
    pub fn purge(&mut self) -> Vec<String> {
        let mut cache = HashMap::with_capacity(self.cache.len());
        mem::swap(&mut self.cache, &mut cache);

        let (expired, keep): (HashMap<_, _>, HashMap<_, _>) = cache
            .into_iter()
            .partition(|(_, timestamp)| timestamp.elapsed() > self.keep_time);

        for (head, timestamp) in keep {
            self.cache.insert(head, timestamp);
        }

        expired.into_iter().map(|(key, _)| key).collect()
    }

    pub fn forks(&self) -> Vec<&String> {
        self.cache.keys().collect()
    }

    // Private helper methods

    fn insert_new_fork(&mut self, head: &str) {
        self.cache.insert(head.into(), Instant::now());
    }

    fn take_previous_if_some(&mut self, previous: Option<&str>) -> Option<String> {
        if let Some(previous) = previous {
            if let Some((replaced, _)) = self.cache.remove_entry(previous) {
                return Some(replaced);
            }
        }
        None
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // Setup a cache and a vector for expired items to be sent to
    fn setup() -> ForkCache {
        ForkCache::new(Duration::from_secs(0))
    }

    // Check that inserted items are purged after their timestamp expires
    #[test]
    fn test_simple_insert_and_purge() {
        let mut cache = setup();

        assert_eq!(None, cache.insert("a", None));
        let expired = cache.purge();

        assert_eq!(1, expired.len());
        assert!(expired.contains(&String::from("a")));
    }

    // Check that inserting an item twice has no effect
    #[test]
    fn test_idempotent() {
        let mut cache = setup();

        assert_eq!(None, cache.insert("a", None));
        assert_eq!(None, cache.insert("a", None));

        let expired = cache.purge();
        assert_eq!(1, expired.len());
        assert!(expired.contains(&String::from("a")));
    }

    // Check that inserted items with a previous field replace their predecessors
    #[test]
    fn test_previous_replaces() {
        let mut cache = setup();

        assert_eq!(None, cache.insert("b", None));
        assert_eq!(Some(String::from("b")), cache.insert("c", Some("b")));

        let expired = cache.purge();
        assert_eq!(1, expired.len());
        assert!(expired.contains(&String::from("c")));
    }

    // Check that inserting multiple forks that extend the same fork works and causes `on_expired`
    // to be called only once
    #[test]
    fn test_multiple_extending_single() {
        let mut cache = setup();

        assert_eq!(None, cache.insert("a", None));
        assert_eq!(Some(String::from("a")), cache.insert("b", Some("a")));
        assert_eq!(None, cache.insert("c", Some("a")));
        assert_eq!(None, cache.insert("d", Some("a")));

        let expired = cache.purge();

        assert_eq!(3, expired.len());
        assert!(expired.contains(&String::from("b")));
        assert!(expired.contains(&String::from("c")));
        assert!(expired.contains(&String::from("d")));
    }
}

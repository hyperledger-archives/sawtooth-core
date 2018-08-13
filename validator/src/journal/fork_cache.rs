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
pub struct ForkCache<F: Fn(String)> {
    keep_time: Duration,
    on_expired: F,
    cache: HashMap<String, Instant>,
}

impl<F: Fn(String)> ForkCache<F> {
    /// Create a new ForkCache which will call `on_expired` whenever a Fork expires from the cache.
    pub fn new(keep_time: Duration, on_expired: F) -> Self {
        ForkCache {
            keep_time,
            on_expired,
            cache: HashMap::new(),
        }
    }

    /// Insert a new fork. If `previous` is not None and it exists, it is removed and `on_expired`
    /// is called with it. Inserting the same `head` twice has no affect.
    pub fn insert(&mut self, head: &str, previous: Option<&str>) {
        if self.cache.get(head).is_some() {
            return;
        }

        let expired = self.take_previous_if_some(previous);

        self.insert_new_fork(head);

        self.call_on_expired_if_some(expired);
    }

    /// Remove all forks that have been in the cache longer than `keep_time` and call `on_expired`
    /// with the it.
    pub fn purge(&mut self) {
        let mut cache = HashMap::with_capacity(self.cache.len());
        mem::swap(&mut self.cache, &mut cache);

        let (expired, keep): (HashMap<_, _>, HashMap<_, _>) = cache
            .into_iter()
            .partition(|(_, timestamp)| timestamp.elapsed() > self.keep_time);

        for (head, timestamp) in keep {
            self.cache.insert(head, timestamp);
        }

        for (head, _) in expired {
            (self.on_expired)(head);
        }
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

    fn call_on_expired_if_some(&self, expired: Option<String>) {
        if let Some(expired) = expired {
            (self.on_expired)(expired);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::cell::RefCell;
    use std::rc::Rc;

    // Setup a cache and a vector for expired items to be sent to
    fn setup(keep_time: Duration) -> (ForkCache<impl Fn(String)>, Rc<RefCell<Vec<String>>>) {
        let expired = Rc::new(RefCell::new(Vec::new()));
        let expired_cloned = Rc::clone(&expired);
        let cache = ForkCache::new(keep_time, move |id| expired_cloned.borrow_mut().push(id));
        (cache, expired)
    }

    // Check that inserted items are purged after their timestamp expires
    #[test]
    fn test_simple_insert_and_purge() {
        let (mut cache, expired) = setup(Duration::from_secs(0));

        cache.insert("a", None);
        cache.purge();

        let expired = expired.borrow();
        assert_eq!(1, expired.len());
        assert!(expired.contains(&String::from("a")));
    }

    // Check that inserting an item twice has no effect
    #[test]
    fn test_idempotent() {
        let (mut cache, expired) = setup(Duration::from_secs(0));

        cache.insert("a", None);
        cache.insert("a", None);

        let expired = expired.borrow();
        assert_eq!(0, expired.len());
    }

    // Check that inserted items with a previous field replace their predecessors
    #[test]
    fn test_previous_replaces() {
        let (mut cache, expired) = setup(Duration::from_secs(0));

        cache.insert("b", None);
        cache.insert("c", Some("b"));

        {
            // Need to drop the RefCell borrow
            let mut expired = expired.borrow_mut();
            assert_eq!(1, expired.len());
            assert!(expired.contains(&String::from("b")));
            expired.clear();
        }

        cache.purge();

        let expired = expired.borrow();
        assert_eq!(1, expired.len());
        assert!(expired.contains(&String::from("c")));
    }

    // Check that inserting multiple forks that extend the same fork works and causes `on_expired`
    // to be called only once
    #[test]
    fn test_multiple_extending_single() {
        let (mut cache, expired) = setup(Duration::from_secs(0));

        cache.insert("a", None);
        cache.insert("b", Some("a"));
        cache.insert("c", Some("a"));
        cache.insert("d", Some("a"));

        {
            // Need to drop the RefCell borrow
            let mut expired = expired.borrow_mut();
            assert_eq!(vec![String::from("a")], *expired);
            expired.clear();
        }

        cache.purge();

        let expired = expired.borrow();
        assert_eq!(3, expired.len());
        assert!(expired.contains(&String::from("b")));
        assert!(expired.contains(&String::from("c")));
        assert!(expired.contains(&String::from("d")));
    }
}

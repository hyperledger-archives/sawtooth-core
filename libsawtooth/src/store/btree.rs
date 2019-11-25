// Copyright 2019 Cargill Incorporated
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

use std::collections::BTreeMap;
use std::convert::TryInto;
use std::fmt::Debug;
use std::sync::{Arc, Mutex};

use super::{OrderedStore, OrderedStoreError, OrderedStoreRange};

struct BTreeOrderedStoreInternal<K, V, I> {
    // The main store contains the index of the entry so it can be mapped back to the index store
    main_store: BTreeMap<K, (V, I)>,
    index_store: BTreeMap<I, K>,
}

impl<K: Ord, V, I: Ord> Default for BTreeOrderedStoreInternal<K, V, I> {
    fn default() -> Self {
        Self {
            main_store: BTreeMap::default(),
            index_store: BTreeMap::default(),
        }
    }
}

/// A BTreeMap-backed implementation of the `OrderedStore` trait that provides an in-memory,
/// ordered key/value store.
#[derive(Default)]
pub struct BTreeOrderedStore<K: Ord + Sync + Send, V: Sync + Send, I: Ord + Sync + Send> {
    internal: Arc<Mutex<BTreeOrderedStoreInternal<K, V, I>>>,
}

impl<K: Ord + Sync + Send, V: Sync + Send, I: Ord + Sync + Send> BTreeOrderedStore<K, V, I> {
    pub fn new() -> Self {
        Self {
            internal: Arc::new(Mutex::new(BTreeOrderedStoreInternal::default())),
        }
    }
}

impl<
        K: Ord + Clone + Debug + Sync + Send + 'static,
        V: Clone + Sync + Send + 'static,
        I: Ord + Clone + Debug + Sync + Send + 'static,
    > OrderedStore<K, V, I> for BTreeOrderedStore<K, V, I>
{
    fn get_value_by_index(&self, idx: &I) -> Result<Option<V>, OrderedStoreError> {
        let internal = self
            .internal
            .lock()
            .map_err(|err| OrderedStoreError::LockPoisoned(err.to_string()))?;
        Ok(internal
            .index_store
            .get(idx)
            .and_then(|key| internal.main_store.get(key).map(|(val, _)| val).cloned()))
    }

    fn get_value_by_key(&self, key: &K) -> Result<Option<V>, OrderedStoreError> {
        Ok(self
            .internal
            .lock()
            .map_err(|err| OrderedStoreError::LockPoisoned(err.to_string()))?
            .main_store
            .get(key)
            .map(|(val, _)| val)
            .cloned())
    }

    fn get_index_by_key(&self, key: &K) -> Result<Option<I>, OrderedStoreError> {
        Ok(self
            .internal
            .lock()
            .map_err(|err| OrderedStoreError::LockPoisoned(err.to_string()))?
            .main_store
            .get(key)
            .map(|(_, idx)| idx)
            .cloned())
    }

    fn count(&self) -> Result<u64, OrderedStoreError> {
        Ok(self
            .internal
            .lock()
            .map_err(|err| OrderedStoreError::LockPoisoned(err.to_string()))?
            .main_store
            .iter()
            .count()
            .try_into()
            .map_err(|err| OrderedStoreError::Internal(Box::new(err)))?)
    }

    fn iter(&self) -> Result<Box<dyn Iterator<Item = V> + Send>, OrderedStoreError> {
        let internal = self
            .internal
            .lock()
            .map_err(|err| OrderedStoreError::LockPoisoned(err.to_string()))?;
        Ok(Box::new(
            internal
                .index_store
                .iter()
                .map(|(_, key)| internal.main_store.get(key).map(|(val, _)| val).cloned())
                .collect::<Option<Vec<_>>>()
                .ok_or_else(|| {
                    OrderedStoreError::StoreCorrupted("value missing from main store".into())
                })?
                .into_iter(),
        ))
    }

    fn range_iter(
        &self,
        range: OrderedStoreRange<I>,
    ) -> Result<Box<dyn Iterator<Item = V> + Send>, OrderedStoreError> {
        let internal = self
            .internal
            .lock()
            .map_err(|err| OrderedStoreError::LockPoisoned(err.to_string()))?;
        Ok(Box::new(
            internal
                .index_store
                .range((range.start, range.end))
                .map(|(_, key)| internal.main_store.get(key).map(|(val, _)| val).cloned())
                .collect::<Option<Vec<_>>>()
                .ok_or_else(|| {
                    OrderedStoreError::StoreCorrupted("value missing from main store".into())
                })?
                .into_iter(),
        ))
    }

    fn insert(&mut self, key: K, value: V, idx: I) -> Result<(), OrderedStoreError> {
        let mut internal = self
            .internal
            .lock()
            .map_err(|err| OrderedStoreError::LockPoisoned(err.to_string()))?;

        if internal.main_store.contains_key(&key) {
            return Err(OrderedStoreError::ValueAlreadyExistsForKey(Box::new(key)));
        }
        if internal.index_store.contains_key(&idx) {
            return Err(OrderedStoreError::ValueAlreadyExistsAtIndex(Box::new(idx)));
        }

        internal.index_store.insert(idx.clone(), key.clone());
        internal.main_store.insert(key, (value, idx));

        Ok(())
    }

    fn remove_by_index(&mut self, idx: &I) -> Result<Option<(K, V)>, OrderedStoreError> {
        let mut internal = self
            .internal
            .lock()
            .map_err(|err| OrderedStoreError::LockPoisoned(err.to_string()))?;
        Ok(if let Some(key) = internal.index_store.remove(idx) {
            let val = internal
                .main_store
                .remove(&key)
                .map(|(val, _)| val)
                .ok_or_else(|| {
                    OrderedStoreError::StoreCorrupted("value missing from main store".into())
                })?;
            Some((key, val))
        } else {
            None
        })
    }

    fn remove_by_key(&mut self, key: &K) -> Result<Option<(V, I)>, OrderedStoreError> {
        let mut internal = self
            .internal
            .lock()
            .map_err(|err| OrderedStoreError::LockPoisoned(err.to_string()))?;
        Ok(
            if let Some((val, index)) = internal.main_store.remove(key) {
                internal.index_store.remove(&index);
                Some((val, index))
            } else {
                None
            },
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    use crate::store::tests::test_u8_ordered_store;

    /// Verify that the `BTreeOrderedStore` passes the u8 ordered store test.
    #[test]
    fn u8_btree_store() {
        test_u8_ordered_store(Box::new(BTreeOrderedStore::new()))
    }
}

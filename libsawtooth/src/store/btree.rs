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

use super::{OrderedStore, OrderedStoreError};

/// A BTreeMap-backed implementation of the `OrderedStore` trait that provides an in-memory,
/// ordered key/value store.
#[derive(Default)]
pub struct BTreeOrderedStore<K: Ord, V, I: Ord> {
    // The main store contains the index of the entry so it can be mapped back to the index store
    main_store: BTreeMap<K, (V, I)>,
    index_store: BTreeMap<I, K>,
}

impl<K: Ord, V, I: Ord> BTreeOrderedStore<K, V, I> {
    pub fn new() -> Self {
        Self {
            main_store: BTreeMap::default(),
            index_store: BTreeMap::default(),
        }
    }
}

impl<K: Ord + Clone + Debug + 'static, V: Clone + 'static, I: Ord + Clone + Debug + 'static>
    OrderedStore<K, V, I> for BTreeOrderedStore<K, V, I>
{
    fn get_by_index(&self, idx: &I) -> Result<Option<V>, OrderedStoreError> {
        Ok(self
            .index_store
            .get(idx)
            .and_then(|key| self.main_store.get(key).map(|(val, _)| val).cloned()))
    }

    fn get_by_key(&self, key: &K) -> Result<Option<V>, OrderedStoreError> {
        Ok(self.main_store.get(key).map(|(val, _)| val).cloned())
    }

    fn count(&self) -> Result<u64, OrderedStoreError> {
        Ok(self
            .main_store
            .iter()
            .count()
            .try_into()
            .map_err(|err| OrderedStoreError::Internal(Box::new(err)))?)
    }

    fn iter(&self) -> Result<Box<dyn Iterator<Item = V>>, OrderedStoreError> {
        Ok(Box::new(
            self.index_store
                .iter()
                .map(|(_, key)| self.main_store.get(key).map(|(val, _)| val).cloned())
                .collect::<Option<Vec<_>>>()
                .ok_or_else(|| {
                    OrderedStoreError::StoreCorrupted("value missing from main store".into())
                })?
                .into_iter(),
        ))
    }

    fn insert(&mut self, key: K, value: V, idx: I) -> Result<(), OrderedStoreError> {
        if self.main_store.contains_key(&key) {
            return Err(OrderedStoreError::ValueAlreadyExistsForKey(Box::new(key)));
        }
        if self.index_store.contains_key(&idx) {
            return Err(OrderedStoreError::ValueAlreadyExistsAtIndex(Box::new(idx)));
        }

        self.index_store.insert(idx.clone(), key.clone());
        self.main_store.insert(key, (value, idx));

        Ok(())
    }

    fn remove_by_index(&mut self, idx: &I) -> Result<Option<(K, V)>, OrderedStoreError> {
        Ok(if let Some(key) = self.index_store.remove(idx) {
            let val = self
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
        Ok(if let Some((val, index)) = self.main_store.remove(key) {
            self.index_store.remove(&index);
            Some((val, index))
        } else {
            None
        })
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

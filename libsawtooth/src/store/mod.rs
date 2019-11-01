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

#[cfg(feature = "btree-store")]
pub mod btree;
mod error;
#[cfg(feature = "receipt-store")]
pub mod receipt_store;

pub use error::OrderedStoreError;

/// A key/vaue store that is indexed by a type with total ordering
pub trait OrderedStore<K, V, I: Ord> {
    /// Get the value at the index if it exists.
    fn get_by_index(&self, idx: &I) -> Result<Option<V>, OrderedStoreError>;

    /// Get the value by the specified key if it exists.
    fn get_by_key(&self, key: &K) -> Result<Option<V>, OrderedStoreError>;

    /// Get the number of entries in the store.
    fn count(&self) -> Result<u64, OrderedStoreError>;

    /// Get an iterator of all values in the store.
    fn iter(&self) -> Result<Box<dyn Iterator<Item = V>>, OrderedStoreError>;

    /// Insert the key,value pair at the index. If a value already exists for the key or index, an
    /// error is returned.
    fn insert(&mut self, key: K, value: V, idx: I) -> Result<(), OrderedStoreError>;

    /// Remove the value at the index and return the key,value pair if it exists.
    fn remove_by_index(&mut self, idx: &I) -> Result<Option<(K, V)>, OrderedStoreError>;

    /// Remove the value corresponding to the key and return the valu,index pair if it exists.
    fn remove_by_key(&mut self, key: &K) -> Result<Option<(V, I)>, OrderedStoreError>;
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Test that a basic `OrderedStore` (one that only stores `u8`s) works properly.
    pub fn test_u8_ordered_store(mut store: Box<dyn OrderedStore<u8, u8, u8>>) {
        assert_eq!(store.count().expect("Failed to get count"), 0);

        store.insert(0, 0, 0).expect("Failed to perform insert");
        store.insert(1, 1, 1).expect("Failed to perform insert");

        assert_eq!(store.count().expect("Failed to get count"), 2);

        assert_eq!(
            store.get_by_index(&0).expect("Failed to get by index"),
            Some(0)
        );
        assert_eq!(
            store.get_by_index(&2).expect("Failed to get by index"),
            None
        );

        assert_eq!(store.get_by_key(&1).expect("Failed to get by key"), Some(1));
        assert_eq!(store.get_by_key(&2).expect("Failed to get by key"), None);

        let mut iter = store.iter().expect("Failed to get iter");
        assert_eq!(iter.next(), Some(0));
        assert_eq!(iter.next(), Some(1));
        assert_eq!(iter.next(), None);

        assert!(store.insert(0, 2, 2).is_err());
        assert!(store.insert(2, 2, 0).is_err());

        assert_eq!(
            store
                .remove_by_index(&2)
                .expect("Failed to remove by index"),
            None
        );
        assert_eq!(store.count().expect("Failed to get count"), 2);
        assert_eq!(
            store
                .remove_by_index(&1)
                .expect("Failed to remove by index"),
            Some((1, 1))
        );
        assert_eq!(
            store.get_by_index(&1).expect("Failed to get by index"),
            None
        );
        assert_eq!(store.get_by_key(&1).expect("Failed to get by key"), None);
        assert_eq!(store.count().expect("Failed to get count"), 1);

        assert_eq!(
            store.remove_by_key(&2).expect("Failed to remove by key"),
            None
        );
        assert_eq!(store.count().expect("Failed to get count"), 1);
        assert_eq!(
            store.remove_by_key(&0).expect("Failed to remove by key"),
            Some((0, 0))
        );
        assert_eq!(
            store.get_by_index(&0).expect("Failed to get by index"),
            None
        );
        assert_eq!(store.get_by_key(&0).expect("Failed to get by key"), None);
        assert_eq!(store.count().expect("Failed to get count"), 0);
    }
}

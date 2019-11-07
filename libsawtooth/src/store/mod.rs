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
#[cfg(feature = "redis-store")]
pub mod redis;

use std::convert::TryInto;

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

/// Trait used by some `OrderedStore` implementations that require converting a key, value, or
/// index to bytes for storage.
pub trait AsBytes {
    fn as_bytes(&self) -> Vec<u8>;
}

impl AsBytes for String {
    fn as_bytes(&self) -> Vec<u8> {
        self.as_bytes().to_vec()
    }
}

impl AsBytes for u8 {
    fn as_bytes(&self) -> Vec<u8> {
        self.to_ne_bytes().to_vec()
    }
}

impl AsBytes for u64 {
    fn as_bytes(&self) -> Vec<u8> {
        self.to_ne_bytes().to_vec()
    }
}

/// Trait used by some `OrderedStore` implementations that store a key, value, or index as bytes,
/// and therefore must convert back to the native type.
pub trait FromBytes: Sized {
    fn from_bytes(bytes: &[u8]) -> Result<Self, String>;
}

impl FromBytes for String {
    fn from_bytes(bytes: &[u8]) -> Result<Self, String> {
        String::from_utf8(bytes.to_vec()).map_err(|err| err.to_string())
    }
}

impl FromBytes for u8 {
    fn from_bytes(bytes: &[u8]) -> Result<Self, String> {
        bytes
            .try_into()
            .map(u8::from_ne_bytes)
            .map_err(|err| err.to_string())
    }
}

impl FromBytes for u64 {
    fn from_bytes(bytes: &[u8]) -> Result<Self, String> {
        bytes
            .try_into()
            .map(u64::from_ne_bytes)
            .map_err(|err| err.to_string())
    }
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

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
#[cfg(feature = "lmdb-store")]
pub mod lmdb;
#[cfg(feature = "receipt-store")]
pub mod receipt_store;
#[cfg(feature = "redis-store")]
pub mod redis;

use std::convert::TryInto;
use std::ops::{Bound, Range, RangeFrom, RangeFull, RangeInclusive, RangeTo, RangeToInclusive};

pub use error::OrderedStoreError;

/// A key/vaue store that is indexed by a type with total ordering
pub trait OrderedStore<K, V, I: Ord>: Sync + Send {
    /// Get the value at the index if it exists.
    fn get_value_by_index(&self, idx: &I) -> Result<Option<V>, OrderedStoreError>;

    /// Get the value by the specified key if it exists.
    fn get_value_by_key(&self, key: &K) -> Result<Option<V>, OrderedStoreError>;

    /// Get the index of the entry with the specified key if it exists.
    fn get_index_by_key(&self, key: &K) -> Result<Option<I>, OrderedStoreError>;

    /// Get the number of entries in the store.
    fn count(&self) -> Result<u64, OrderedStoreError>;

    /// Get an iterator of all values in the store.
    fn iter<'a>(&'a self) -> Result<Box<dyn Iterator<Item = V> + 'a + Send>, OrderedStoreError>;

    /// Get an iterator over a range of values in the store.
    fn range_iter<'a>(
        &'a self,
        range: OrderedStoreRange<I>,
    ) -> Result<Box<dyn Iterator<Item = V> + 'a + Send>, OrderedStoreError>;

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

/// A range describing the start and end bounds for a range iterator on an OrderedStore.
///
/// This struct is similar to the various implementations of the RangeBounds trait in the standard
/// library, but is necessary for implementing the most generic set of bounds while still allowing
/// OrderedStore to be used in a boxed-dyn context.
pub struct OrderedStoreRange<I> {
    pub start: Bound<I>,
    pub end: Bound<I>,
}

impl<I: PartialOrd> OrderedStoreRange<I> {
    fn contains(&self, item: &I) -> bool {
        let lower = match &self.start {
            Bound::Included(start_idx) => item >= start_idx,
            Bound::Excluded(start_idx) => item > start_idx,
            Bound::Unbounded => true,
        };
        let upper = match &self.end {
            Bound::Included(end_idx) => item <= end_idx,
            Bound::Excluded(end_idx) => item < end_idx,
            Bound::Unbounded => true,
        };
        lower && upper
    }
}

impl<I> From<Range<I>> for OrderedStoreRange<I> {
    fn from(range: Range<I>) -> Self {
        Self {
            start: Bound::Included(range.start),
            end: Bound::Excluded(range.end),
        }
    }
}

impl<I> From<RangeInclusive<I>> for OrderedStoreRange<I> {
    fn from(range: RangeInclusive<I>) -> Self {
        let (start, end) = range.into_inner();
        Self {
            start: Bound::Included(start),
            end: Bound::Included(end),
        }
    }
}

impl<I> From<RangeFull> for OrderedStoreRange<I> {
    fn from(_: RangeFull) -> Self {
        Self {
            start: Bound::Unbounded,
            end: Bound::Unbounded,
        }
    }
}

impl<I> From<RangeFrom<I>> for OrderedStoreRange<I> {
    fn from(range: RangeFrom<I>) -> Self {
        Self {
            start: Bound::Included(range.start),
            end: Bound::Unbounded,
        }
    }
}

impl<I> From<RangeTo<I>> for OrderedStoreRange<I> {
    fn from(range: RangeTo<I>) -> Self {
        Self {
            start: Bound::Unbounded,
            end: Bound::Excluded(range.end),
        }
    }
}

impl<I> From<RangeToInclusive<I>> for OrderedStoreRange<I> {
    fn from(range: RangeToInclusive<I>) -> Self {
        Self {
            start: Bound::Unbounded,
            end: Bound::Included(range.end),
        }
    }
}

impl<I> From<(Bound<I>, Bound<I>)> for OrderedStoreRange<I> {
    fn from((start, end): (Bound<I>, Bound<I>)) -> Self {
        Self { start, end }
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
            store
                .get_value_by_index(&0)
                .expect("Failed to get value by index"),
            Some(0)
        );
        assert_eq!(
            store
                .get_value_by_index(&2)
                .expect("Failed to get value by index"),
            None
        );

        assert_eq!(
            store
                .get_value_by_key(&1)
                .expect("Failed to get value by key"),
            Some(1)
        );
        assert_eq!(
            store
                .get_value_by_key(&2)
                .expect("Failed to get value by key"),
            None
        );

        assert_eq!(
            store
                .get_index_by_key(&1)
                .expect("Failed to get index by key"),
            Some(1)
        );
        assert_eq!(
            store
                .get_index_by_key(&2)
                .expect("Failed to get index by key"),
            None
        );

        assert_eq!(
            store
                .iter()
                .expect("Failed to get iter")
                .collect::<Vec<_>>(),
            vec![0, 1]
        );

        assert_eq!(
            store
                .range_iter((1..).into())
                .expect("Failed to get iter from 1")
                .collect::<Vec<_>>(),
            vec![1]
        );

        assert_eq!(
            store
                .range_iter((..1).into())
                .expect("Failed to get iter up to 1")
                .collect::<Vec<_>>(),
            vec![0]
        );

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
            store
                .get_value_by_index(&1)
                .expect("Failed to get value by index"),
            None
        );
        assert_eq!(
            store
                .get_value_by_key(&1)
                .expect("Failed to get value by key"),
            None
        );
        assert_eq!(
            store
                .get_index_by_key(&1)
                .expect("Failed to get index by key"),
            None
        );
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
            store
                .get_value_by_index(&0)
                .expect("Failed to get value by index"),
            None
        );
        assert_eq!(
            store
                .get_value_by_key(&0)
                .expect("Failed to get value by key"),
            None
        );
        assert_eq!(
            store
                .get_index_by_key(&0)
                .expect("Failed to get index by key"),
            None
        );
        assert_eq!(store.count().expect("Failed to get count"), 0);
    }

    /// Test that the `OrderedStoreRange` properly determines if a value is within the range.
    #[test]
    fn ordered_store_range() {
        let unbounded_range: OrderedStoreRange<u8> = (..).into();
        assert!(unbounded_range.contains(&std::u8::MIN));
        assert!(unbounded_range.contains(&std::u8::MAX));

        let inclusive_range: OrderedStoreRange<u8> = RangeInclusive::new(1, 3).into();
        assert!(!inclusive_range.contains(&0));
        assert!(inclusive_range.contains(&1));
        assert!(inclusive_range.contains(&2));
        assert!(inclusive_range.contains(&3));
        assert!(!inclusive_range.contains(&4));

        let exclusive_range = OrderedStoreRange {
            start: Bound::Excluded(1),
            end: Bound::Excluded(3),
        };
        assert!(!exclusive_range.contains(&0));
        assert!(!exclusive_range.contains(&1));
        assert!(exclusive_range.contains(&2));
        assert!(!exclusive_range.contains(&3));
        assert!(!exclusive_range.contains(&4));
    }
}

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

use std::collections::VecDeque;
use std::convert::TryInto;
use std::fmt::Debug;
use std::ops::Bound;
use std::path::Path;
use std::sync::Arc;

use lmdb_zero as lmdb;
use lmdb_zero::error::LmdbResultExt;

use super::{AsBytes, FromBytes, OrderedStore, OrderedStoreError, OrderedStoreRange};

const DEFAULT_SIZE: usize = 1 << 40; // 1024 ** 4
const NUM_DBS: u32 = 3; // main DB, index-to-key DB, and key-to-index DB
const ITER_CACHE_SIZE: usize = 64; // num of items at a time that are loaded into memory by iter

impl From<lmdb::Error> for OrderedStoreError {
    fn from(err: lmdb::Error) -> Self {
        Self::Internal(Box::new(err))
    }
}

/// An LMDB-backed implementation of the `OrderedStore` trait that provides a persistent, ordered
/// key/value store.
pub struct LmdbOrderedStore {
    env: Arc<lmdb::Environment>,
    // The main DB stores the (key, value) pairs
    main_db: Arc<lmdb::Database<'static>>,
    // The index-to-key DB stores the (index, key) mapping to support interacting with indexes
    index_to_key_db: Arc<lmdb::Database<'static>>,
    // The key-to-index DB stores the (key, index) mapping to support removing by key
    key_to_index_db: Arc<lmdb::Database<'static>>,
}

impl LmdbOrderedStore {
    pub fn new(filepath: &Path, size: Option<usize>) -> Result<Self, OrderedStoreError> {
        let flags = lmdb::open::MAPASYNC
            | lmdb::open::WRITEMAP
            | lmdb::open::NORDAHEAD
            | lmdb::open::NOSUBDIR;

        let filepath_str = filepath.to_str().ok_or_else(|| {
            OrderedStoreError::InitializationFailed(format!("invalid filepath: {:?}", filepath))
        })?;

        let mut builder = lmdb::EnvBuilder::new().map_err(|err| {
            OrderedStoreError::InitializationFailed(format!(
                "failed to initialize environment builder: {}",
                err
            ))
        })?;
        builder.set_maxdbs(NUM_DBS).map_err(|err| {
            OrderedStoreError::InitializationFailed(format!("failed to set MAX_DBS: {}", err))
        })?;
        builder
            .set_mapsize(size.unwrap_or(DEFAULT_SIZE))
            .map_err(|err| {
                OrderedStoreError::InitializationFailed(format!("failed to set MAP_SIZE: {}", err))
            })?;

        let env = Arc::new(unsafe {
            builder.open(filepath_str, flags, 0o600).map_err(|err| {
                OrderedStoreError::InitializationFailed(format!("database not found: {}", err))
            })
        }?);

        let main_db = Arc::new(
            lmdb::Database::open(
                env.clone(),
                Some("main"),
                &lmdb::DatabaseOptions::new(lmdb::db::CREATE),
            )
            .map_err(|err| {
                OrderedStoreError::InitializationFailed(format!(
                    "failed to open main database: {}",
                    err
                ))
            })?,
        );

        let index_to_key_db = Arc::new(
            lmdb::Database::open(
                env.clone(),
                Some("index_to_key"),
                &lmdb::DatabaseOptions::new(lmdb::db::CREATE),
            )
            .map_err(|err| {
                OrderedStoreError::InitializationFailed(format!(
                    "failed to open index-to-key database: {:?}",
                    err
                ))
            })?,
        );

        let key_to_index_db = Arc::new(
            lmdb::Database::open(
                env.clone(),
                Some("key_to_index"),
                &lmdb::DatabaseOptions::new(lmdb::db::CREATE),
            )
            .map_err(|err| {
                OrderedStoreError::InitializationFailed(format!(
                    "failed to open key-to-index database: {:?}",
                    err
                ))
            })?,
        );

        Ok(LmdbOrderedStore {
            env,
            main_db,
            index_to_key_db,
            key_to_index_db,
        })
    }
}

impl<
        K: Clone + Debug + AsBytes + FromBytes + 'static,
        V: Clone + Send + AsBytes + FromBytes + 'static,
        I: Clone + Debug + Ord + Send + AsBytes + FromBytes + 'static,
    > OrderedStore<K, V, I> for LmdbOrderedStore
{
    fn get_value_by_index(&self, idx: &I) -> Result<Option<V>, OrderedStoreError> {
        let txn = lmdb::ReadTransaction::new(self.env.clone())?;
        let access = txn.access();

        Ok(
            match access
                .get::<_, [u8]>(&self.index_to_key_db, &idx.as_bytes())
                .to_opt()?
            {
                Some(key) => access
                    .get::<_, [u8]>(&self.main_db, key)
                    .to_opt()?
                    .map(|val| V::from_bytes(val))
                    .transpose()
                    .map_err(OrderedStoreError::BytesParsingFailed)?,
                None => None,
            },
        )
    }

    fn get_value_by_key(&self, key: &K) -> Result<Option<V>, OrderedStoreError> {
        let txn = lmdb::ReadTransaction::new(self.env.clone())?;
        let access = txn.access();

        Ok(access
            .get::<_, [u8]>(&self.main_db, &key.as_bytes())
            .to_opt()?
            .map(|val| V::from_bytes(val))
            .transpose()
            .map_err(OrderedStoreError::BytesParsingFailed)?)
    }

    fn get_index_by_key(&self, key: &K) -> Result<Option<I>, OrderedStoreError> {
        let txn = lmdb::ReadTransaction::new(self.env.clone())?;
        let access = txn.access();

        Ok(access
            .get::<_, [u8]>(&self.key_to_index_db, &key.as_bytes())
            .to_opt()?
            .map(|idx| I::from_bytes(idx))
            .transpose()
            .map_err(OrderedStoreError::BytesParsingFailed)?)
    }

    fn count(&self) -> Result<u64, OrderedStoreError> {
        Ok(lmdb::ReadTransaction::new(self.env.clone())?
            .db_stat(&self.main_db)?
            .entries
            .try_into()
            .map_err(|err| OrderedStoreError::Internal(Box::new(err)))?)
    }

    fn iter(&self) -> Result<Box<dyn Iterator<Item = V> + Send>, OrderedStoreError> {
        let iter: LmdbOrderedStoreIter<V, I> = LmdbOrderedStoreIter::new(
            self.env.clone(),
            self.index_to_key_db.clone(),
            self.main_db.clone(),
            None,
        )?;

        Ok(Box::new(iter))
    }

    fn range_iter(
        &self,
        range: OrderedStoreRange<I>,
    ) -> Result<Box<dyn Iterator<Item = V> + Send>, OrderedStoreError> {
        let iter: LmdbOrderedStoreIter<V, I> = LmdbOrderedStoreIter::new(
            self.env.clone(),
            self.index_to_key_db.clone(),
            self.main_db.clone(),
            Some(range),
        )?;

        Ok(Box::new(iter))
    }

    fn insert(&mut self, key: K, value: V, idx: I) -> Result<(), OrderedStoreError> {
        let txn = lmdb::WriteTransaction::new(self.env.clone())?;

        {
            let mut access = txn.access();

            if access
                .get::<_, [u8]>(&self.main_db, &key.as_bytes())
                .to_opt()?
                .is_some()
            {
                return Err(OrderedStoreError::ValueAlreadyExistsForKey(Box::new(key)));
            }
            if access
                .get::<_, [u8]>(&self.index_to_key_db, &idx.as_bytes())
                .to_opt()?
                .is_some()
            {
                return Err(OrderedStoreError::ValueAlreadyExistsAtIndex(Box::new(idx)));
            }

            access.put(
                &self.main_db,
                &key.as_bytes(),
                &value.as_bytes(),
                lmdb::put::NOOVERWRITE,
            )?;
            access.put(
                &self.index_to_key_db,
                &idx.as_bytes(),
                &key.as_bytes(),
                lmdb::put::NOOVERWRITE,
            )?;
            access.put(
                &self.key_to_index_db,
                &key.as_bytes(),
                &idx.as_bytes(),
                lmdb::put::NOOVERWRITE,
            )?;
        }

        txn.commit()?;

        Ok(())
    }

    fn remove_by_index(&mut self, idx: &I) -> Result<Option<(K, V)>, OrderedStoreError> {
        let txn = lmdb::WriteTransaction::new(self.env.clone())?;

        let kv_option = {
            let mut access = txn.access();

            if let Some(key) = access
                .get::<_, [u8]>(&self.index_to_key_db, &idx.as_bytes())
                .to_opt()?
                .map(Vec::from)
            {
                let val = access
                    .get::<_, [u8]>(&self.main_db, &key)
                    .to_opt()?
                    .ok_or_else(|| {
                        OrderedStoreError::StoreCorrupted("value missing from main store".into())
                    })
                    .and_then(|val| {
                        V::from_bytes(val).map_err(OrderedStoreError::BytesParsingFailed)
                    })?;

                access.del_key(&self.main_db, &key)?;
                access.del_key(&self.index_to_key_db, &idx.as_bytes())?;
                access.del_key(&self.key_to_index_db, &key)?;

                let key = K::from_bytes(&key).map_err(OrderedStoreError::BytesParsingFailed)?;

                Some((key, val))
            } else {
                None
            }
        };

        txn.commit()?;

        Ok(kv_option)
    }

    fn remove_by_key(&mut self, key: &K) -> Result<Option<(V, I)>, OrderedStoreError> {
        let txn = lmdb::WriteTransaction::new(self.env.clone())?;

        let vi_option = {
            let mut access = txn.access();

            if let Some(idx) = access
                .get::<_, [u8]>(&self.key_to_index_db, &key.as_bytes())
                .to_opt()?
                .map(Vec::from)
            {
                let val = access
                    .get::<_, [u8]>(&self.main_db, &key.as_bytes())
                    .to_opt()?
                    .ok_or_else(|| {
                        OrderedStoreError::StoreCorrupted("value missing from main store".into())
                    })
                    .and_then(|val| {
                        V::from_bytes(val).map_err(OrderedStoreError::BytesParsingFailed)
                    })?;

                access.del_key(&self.main_db, &key.as_bytes())?;
                access.del_key(&self.index_to_key_db, &idx)?;
                access.del_key(&self.key_to_index_db, &key.as_bytes())?;

                let idx = I::from_bytes(&idx).map_err(OrderedStoreError::BytesParsingFailed)?;

                Some((val, idx))
            } else {
                None
            }
        };

        txn.commit()?;

        Ok(vi_option)
    }
}

/// `LmdbOrderedStoreIter` is an iterator over entries in an LMDB ordered store. It uses an
/// in-memory cache of items that it retrieves from the database using a cursor. The cache is
/// refilled when it is emptied, and its size is defined by the ITER_CACHE_SIZE constant.
///
/// An optional `OrderedStoreRange` may be provided to get only a subset of entries from the
/// database.
struct LmdbOrderedStoreIter<V, I> {
    env: Arc<lmdb::Environment>,
    index_to_key_db: Arc<lmdb::Database<'static>>,
    main_db: Arc<lmdb::Database<'static>>,

    cache: VecDeque<V>,
    range: OrderedStoreRange<I>,
}

impl<V: FromBytes, I: AsBytes + FromBytes + PartialEq + PartialOrd> LmdbOrderedStoreIter<V, I> {
    fn new(
        env: Arc<lmdb::Environment>,
        index_to_key_db: Arc<lmdb::Database<'static>>,
        main_db: Arc<lmdb::Database<'static>>,
        range: Option<OrderedStoreRange<I>>,
    ) -> Result<Self, OrderedStoreError> {
        let mut iter = Self {
            env,
            index_to_key_db,
            main_db,
            cache: VecDeque::new(),
            range: range.unwrap_or_else(|| (..).into()), // default to unbounded range
        };

        // Load initial values into the cache
        if let Err(err) = iter.reload_cache() {
            error!("Failed to load iterator's initial cache: {}", err);
        }

        Ok(iter)
    }

    fn reload_cache(&mut self) -> Result<(), String> {
        let txn = lmdb::ReadTransaction::new(self.env.clone()).map_err(|err| err.to_string())?;
        let access = txn.access();
        let mut index_cursor = txn
            .cursor(self.index_to_key_db.clone())
            .map_err(|err| err.to_string())?;

        // Set the cursor to the start of the range and get the first entry
        let mut first_entry = Some(match &self.range.start {
            Bound::Included(idx) => {
                // Get the first entry >= idx; that will be the first entry.
                index_cursor.seek_range_k::<[u8], [u8]>(&access, &idx.as_bytes())
            }
            Bound::Excluded(idx) => {
                // Get the first entry >= idx. If that entry == idx, get the next entry since this
                // is an exclusive bound.
                match index_cursor.seek_range_k::<[u8], [u8]>(&access, &idx.as_bytes()) {
                    // If this is the same as the range's index,
                    Ok((found_idx, _)) if found_idx == idx.as_bytes().as_slice() => {
                        index_cursor.next::<[u8], [u8]>(&access)
                    }
                    other => other,
                }
            }
            Bound::Unbounded => {
                // Starting from the beginning
                index_cursor.first::<[u8], [u8]>(&access)
            }
        });

        // Load up to ITER_CACHE_SIZE entries; stop if all entries have been read or if the end of
        // the range is reached.
        for _ in 0..ITER_CACHE_SIZE {
            let next_entry = first_entry
                .take()
                .unwrap_or_else(|| index_cursor.next::<[u8], [u8]>(&access));
            match next_entry {
                Ok((idx, key)) => {
                    let idx = I::from_bytes(idx)?;
                    // If this index is in the range, add the value to the cache; otherwise, exit.
                    if !self.range.contains(&idx) {
                        break;
                    } else {
                        self.cache.push_back(V::from_bytes(
                            access
                                .get::<_, [u8]>(&self.main_db, key)
                                .map_err(|err| err.to_string())?,
                        )?);
                        // Update the range start to reflect only what's left
                        self.range.start = Bound::Excluded(idx);
                    }
                }
                Err(lmdb::error::Error::Code(lmdb::error::NOTFOUND)) => break,
                Err(err) => return Err(err.to_string()),
            }
        }

        Ok(())
    }
}

impl<V: FromBytes, I: AsBytes + FromBytes + PartialEq + PartialOrd> Iterator
    for LmdbOrderedStoreIter<V, I>
{
    type Item = V;

    fn next(&mut self) -> Option<Self::Item> {
        if self.cache.is_empty() {
            if let Err(err) = self.reload_cache() {
                error!("Failed to load iterator's cache: {}", err);
            }
        }
        self.cache.pop_front()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    use crate::store::tests::test_u8_ordered_store;

    /// Verify that the `LmdbOrderedStore` passes the u8 ordered store test.
    #[test]
    fn u8_lmdb_store() {
        let temp_db_path = get_temp_db_path();

        let test_result = std::panic::catch_unwind(|| {
            test_u8_ordered_store(Box::new(
                LmdbOrderedStore::new(temp_db_path.as_path(), Some(1024 * 1024))
                    .expect("Failed to create LMDB ordered store"),
            ))
        });

        std::fs::remove_file(temp_db_path.as_path()).expect("Failed to remove temp DB file");

        assert!(test_result.is_ok());
    }

    /// Verify that the `LmdbOrderedStoreIter` works properly with various ranges.
    #[test]
    fn iterator_with_ranges() {
        let temp_db_path = get_temp_db_path();

        let test_result = std::panic::catch_unwind(|| {
            let mut store = LmdbOrderedStore::new(temp_db_path.as_path(), Some(1024 * 1024))
                .expect("Failed to create LMDB ordered store");

            store.insert(1u8, 1u8, 1u8).expect("failed to add 1");
            store.insert(2u8, 2u8, 2u8).expect("failed to add 2");
            store.insert(3u8, 3u8, 3u8).expect("failed to add 3");
            store.insert(4u8, 4u8, 4u8).expect("failed to add 4");
            store.insert(5u8, 5u8, 5u8).expect("failed to add 5");

            // Get all entries in iterator
            let all_entries = LmdbOrderedStoreIter::<u8, u8>::new(
                store.env.clone(),
                store.index_to_key_db.clone(),
                store.main_db.clone(),
                None,
            )
            .expect("failed to create iter for all entries");

            assert_eq!(
                all_entries.collect::<Vec<_>>(),
                vec![1u8, 2u8, 3u8, 4u8, 5u8],
            );

            // Get all entries starting at a certain point
            let from_2 = LmdbOrderedStoreIter::<u8, u8>::new(
                store.env.clone(),
                store.index_to_key_db.clone(),
                store.main_db.clone(),
                Some((2..).into()),
            )
            .expect("failed to create iter for entries from 2");

            assert_eq!(from_2.collect::<Vec<_>>(), vec![2u8, 3u8, 4u8, 5u8]);

            // Get all entries up to a certain point
            let up_to_4 = LmdbOrderedStoreIter::<u8, u8>::new(
                store.env.clone(),
                store.index_to_key_db.clone(),
                store.main_db.clone(),
                Some((..5).into()), // upper bound is exclusive
            )
            .expect("failed to create iter for entries up to 4");

            assert_eq!(up_to_4.collect::<Vec<_>>(), vec![1u8, 2u8, 3u8, 4u8]);

            // Get all entries between two points
            let from_2_to_4 = LmdbOrderedStoreIter::<u8, u8>::new(
                store.env.clone(),
                store.index_to_key_db.clone(),
                store.main_db.clone(),
                Some((2..5).into()), // upper bound is exclusive
            )
            .expect("failed to create iter for entries from 2 to 4");

            assert_eq!(from_2_to_4.collect::<Vec<_>>(), vec![2u8, 3u8, 4u8]);

            // Verify inclusive start, even if it's the first value
            let from_1_inclusive = LmdbOrderedStoreIter::<u8, u8>::new(
                store.env.clone(),
                store.index_to_key_db.clone(),
                store.main_db.clone(),
                Some((1..).into()),
            )
            .expect("failed to create iter for entries from 1 (inclusive)");

            assert_eq!(
                from_1_inclusive.collect::<Vec<_>>(),
                vec![1u8, 2u8, 3u8, 4u8, 5u8]
            );

            // Verify inclusive start, even when the specified start index doesn't exist
            let from_0_inclusive = LmdbOrderedStoreIter::<u8, u8>::new(
                store.env.clone(),
                store.index_to_key_db.clone(),
                store.main_db.clone(),
                Some((0..).into()),
            )
            .expect("failed to create iter for entries from 0 (inclusive)");

            assert_eq!(
                from_0_inclusive.collect::<Vec<_>>(),
                vec![1u8, 2u8, 3u8, 4u8, 5u8]
            );

            // Verify exclusive start, even if it's the first value
            let from_1_exclusive = LmdbOrderedStoreIter::<u8, u8>::new(
                store.env.clone(),
                store.index_to_key_db.clone(),
                store.main_db.clone(),
                Some(OrderedStoreRange {
                    start: Bound::Excluded(1),
                    end: Bound::Unbounded,
                }),
            )
            .expect("failed to create iter for entries from 1 (exclusive)");

            assert_eq!(
                from_1_exclusive.collect::<Vec<_>>(),
                vec![2u8, 3u8, 4u8, 5u8]
            );

            // Verify exclusive start, even when the specified start index doesn't exist
            let from_0_exclusive = LmdbOrderedStoreIter::<u8, u8>::new(
                store.env.clone(),
                store.index_to_key_db.clone(),
                store.main_db.clone(),
                Some((0..).into()),
            )
            .expect("failed to create iter for entries from 0 (exclusive)");

            assert_eq!(
                from_0_exclusive.collect::<Vec<_>>(),
                vec![1u8, 2u8, 3u8, 4u8, 5u8]
            );

            // Test inclusive end, even if it's the last value
            let up_to_5_inclusive = LmdbOrderedStoreIter::<u8, u8>::new(
                store.env.clone(),
                store.index_to_key_db.clone(),
                store.main_db.clone(),
                Some(std::ops::RangeToInclusive { end: 5 }.into()),
            )
            .expect("failed to create iter for entries up to 5 (inclusive)");

            assert_eq!(
                up_to_5_inclusive.collect::<Vec<_>>(),
                vec![1u8, 2u8, 3u8, 4u8, 5u8]
            );

            // Verify inclusive end, even when the specified end index doesn't exist
            let up_to_6_inclusive = LmdbOrderedStoreIter::<u8, u8>::new(
                store.env.clone(),
                store.index_to_key_db.clone(),
                store.main_db.clone(),
                Some(std::ops::RangeToInclusive { end: 6 }.into()),
            )
            .expect("failed to create iter for entries up to 6 (inclusive)");

            assert_eq!(
                up_to_6_inclusive.collect::<Vec<_>>(),
                vec![1u8, 2u8, 3u8, 4u8, 5u8]
            );

            // Test exclusive end, even if it's the last value
            let up_to_5_exclusive = LmdbOrderedStoreIter::<u8, u8>::new(
                store.env.clone(),
                store.index_to_key_db.clone(),
                store.main_db.clone(),
                Some((..5).into()),
            )
            .expect("failed to create iter for entries up to 5 (exclusive)");

            assert_eq!(
                up_to_5_exclusive.collect::<Vec<_>>(),
                vec![1u8, 2u8, 3u8, 4u8]
            );

            // Verify exclusive end, even when the specified end index doesn't exist
            let up_to_6_exclusive = LmdbOrderedStoreIter::<u8, u8>::new(
                store.env.clone(),
                store.index_to_key_db.clone(),
                store.main_db.clone(),
                Some((..6).into()),
            )
            .expect("failed to create iter for entries up to 6 (exclusive)");

            assert_eq!(
                up_to_6_exclusive.collect::<Vec<_>>(),
                vec![1u8, 2u8, 3u8, 4u8, 5u8]
            );
        });

        std::fs::remove_file(temp_db_path.as_path()).expect("Failed to remove temp DB file");

        assert!(test_result.is_ok());
    }

    /// Verify that the `LmdbOrderedStoreIter` properly populates its cache with only
    /// `ITER_CACHE_SIZE` items at a time, and that it is able to repopulate this cache as needed.
    #[test]
    fn iterator_large_db() {
        let temp_db_path = get_temp_db_path();

        let test_result = std::panic::catch_unwind(|| {
            let mut store = LmdbOrderedStore::new(temp_db_path.as_path(), Some(1024 * 1024))
                .expect("Failed to create LMDB ordered store");

            for i in 0..std::u8::MAX {
                store.insert(i, i, i).expect("Failed to add u8");
            }

            let mut iter = LmdbOrderedStoreIter::<u8, u8>::new(
                store.env.clone(),
                store.index_to_key_db.clone(),
                store.main_db.clone(),
                None,
            )
            .expect("failed to create iter");

            assert_eq!(iter.cache.len(), ITER_CACHE_SIZE);

            for _ in 0..(ITER_CACHE_SIZE - 1) {
                iter.next().expect("failed to get item");
            }
            assert_eq!(iter.cache.len(), 1);

            let item63 = iter.next().expect("failed to get another item");
            assert_eq!(item63, 63);
            assert_eq!(iter.cache.len(), 0);

            let item64 = iter
                .next()
                .expect("failed to get another item or reload the cache");
            assert_eq!(item64, 64);
            assert_eq!(iter.cache.len(), 63);

            let remaining_items = iter.collect::<Vec<_>>();
            assert_eq!(remaining_items.len(), (std::u8::MAX - 65) as usize);
            assert_eq!(remaining_items.first().expect("no first"), &65);
            assert_eq!(
                remaining_items.last().expect("no last"),
                &(std::u8::MAX - 1)
            );
        });

        std::fs::remove_file(temp_db_path.as_path()).expect("Failed to remove temp DB file");

        assert!(test_result.is_ok());
    }

    fn get_temp_db_path() -> std::path::PathBuf {
        let mut temp_db_path = std::env::temp_dir();
        let thread_id = std::thread::current().id();
        temp_db_path.push(format!("store-{:?}.lmdb", thread_id));
        temp_db_path
    }
}

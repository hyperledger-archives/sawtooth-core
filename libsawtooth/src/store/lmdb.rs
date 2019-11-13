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

use std::convert::TryInto;
use std::fmt::Debug;
use std::path::Path;
use std::sync::Arc;

use lmdb_zero as lmdb;
use lmdb_zero::error::LmdbResultExt;

use super::{AsBytes, FromBytes, OrderedStore, OrderedStoreError};

const DEFAULT_SIZE: usize = 1 << 40; // 1024 ** 4
const NUM_DBS: u32 = 3; // main DB, index-to-key DB, and key-to-index DB

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
        V: Clone + AsBytes + FromBytes + 'static,
        I: Clone + Debug + Ord + AsBytes + FromBytes + 'static,
    > OrderedStore<K, V, I> for LmdbOrderedStore
{
    fn get_by_index(&self, idx: &I) -> Result<Option<V>, OrderedStoreError> {
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

    fn get_by_key(&self, key: &K) -> Result<Option<V>, OrderedStoreError> {
        let txn = lmdb::ReadTransaction::new(self.env.clone())?;
        let access = txn.access();

        Ok(access
            .get::<_, [u8]>(&self.main_db, &key.as_bytes())
            .to_opt()?
            .map(|val| V::from_bytes(val))
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

    fn iter(&self) -> Result<Box<dyn Iterator<Item = V>>, OrderedStoreError> {
        let txn = lmdb::ReadTransaction::new(self.env.clone())?;
        let access = txn.access();
        let mut index_cursor = txn.cursor(self.index_to_key_db.clone())?;

        let index_iter = lmdb::CursorIter::new(
            lmdb::MaybeOwned::Borrowed(&mut index_cursor),
            &access,
            |c, a| c.first(a),
            lmdb::Cursor::next::<[u8], [u8]>,
        )?;

        Ok(Box::new(
            index_iter
                .map(|res| {
                    res.map_err(|err| OrderedStoreError::Internal(Box::new(err)))
                        .and_then(|(_, key)| {
                            access
                                .get::<_, [u8]>(&self.main_db, key)
                                .map_err(|err| OrderedStoreError::Internal(Box::new(err)))
                                .and_then(|val| {
                                    V::from_bytes(val)
                                        .map_err(OrderedStoreError::BytesParsingFailed)
                                })
                        })
                })
                .collect::<Result<Vec<_>, _>>()?
                .into_iter(),
        ))
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

#[cfg(test)]
mod tests {
    use super::*;

    use crate::store::tests::test_u8_ordered_store;

    /// Verify that the `LmdbOrderedStore` passes the u8 ordered store test.
    #[test]
    fn u8_lmdb_store() {
        let mut temp_db_path = std::env::temp_dir();
        let thread_id = std::thread::current().id();
        temp_db_path.push(format!("store-{:?}.lmdb", thread_id));

        test_u8_ordered_store(Box::new(
            LmdbOrderedStore::new(temp_db_path.as_path(), Some(1024 * 1024))
                .expect("Failed to create LMDB ordered store"),
        ));

        std::fs::remove_file(temp_db_path.as_path()).expect("Failed to remove temp DB file");
    }
}

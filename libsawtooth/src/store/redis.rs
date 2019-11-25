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

use std::fmt::Debug;
use std::sync::{Arc, Mutex};

use redis::{Client, Commands, Connection, FromRedisValue, RedisError, ToRedisArgs};

use super::{OrderedStore, OrderedStoreError, OrderedStoreRange};

const MAIN_STORE: &str = "main";
const INDEX_STORE: &str = "index";

impl From<RedisError> for OrderedStoreError {
    fn from(err: RedisError) -> Self {
        Self::Internal(Box::new(err))
    }
}

pub struct RedisOrderedStore {
    conn: Arc<Mutex<Connection>>,
}

impl RedisOrderedStore {
    pub fn new(url: &str) -> Result<Self, OrderedStoreError> {
        let conn = Arc::new(Mutex::new(
            Client::open(url)
                .map_err(|err| OrderedStoreError::InitializationFailed(err.to_string()))?
                .get_connection()
                .map_err(|err| OrderedStoreError::InitializationFailed(err.to_string()))?,
        ));
        Ok(Self { conn })
    }
}

impl<
        K: Debug + FromRedisValue + ToRedisArgs + 'static,
        V: Send + FromRedisValue + ToRedisArgs + 'static,
        I: Debug + Ord + FromRedisValue + ToRedisArgs + 'static,
    > OrderedStore<K, V, I> for RedisOrderedStore
{
    fn get_value_by_index(&self, idx: &I) -> Result<Option<V>, OrderedStoreError> {
        Ok(
            match self
                .conn
                .lock()
                .map_err(|err| OrderedStoreError::LockPoisoned(err.to_string()))?
                .hget::<_, _, Option<K>>(INDEX_STORE, idx.to_redis_args())?
            {
                Some(key) => self
                    .conn
                    .lock()
                    .map_err(|err| OrderedStoreError::LockPoisoned(err.to_string()))?
                    .hget(MAIN_STORE, key)?,
                None => None,
            },
        )
    }

    fn get_value_by_key(&self, key: &K) -> Result<Option<V>, OrderedStoreError> {
        Ok(self
            .conn
            .lock()
            .map_err(|err| OrderedStoreError::LockPoisoned(err.to_string()))?
            .hget(MAIN_STORE, key.to_redis_args())?)
    }

    fn get_index_by_key(&self, _key: &K) -> Result<Option<I>, OrderedStoreError> {
        unimplemented!()
    }

    fn count(&self) -> Result<u64, OrderedStoreError> {
        Ok(self
            .conn
            .lock()
            .map_err(|err| OrderedStoreError::LockPoisoned(err.to_string()))?
            .hlen(MAIN_STORE)?)
    }

    fn iter(&self) -> Result<Box<dyn Iterator<Item = V> + Send>, OrderedStoreError> {
        let mut conn = self
            .conn
            .lock()
            .map_err(|err| OrderedStoreError::LockPoisoned(err.to_string()))?;

        Ok(Box::new(
            conn.hgetall::<_, Vec<K>>(INDEX_STORE)?
                .into_iter()
                .map(|key| conn.hget(MAIN_STORE, key.to_redis_args()))
                .collect::<Result<Option<Vec<_>>, _>>()?
                .ok_or_else(|| {
                    OrderedStoreError::StoreCorrupted("value missing from main store".into())
                })?
                .into_iter(),
        ))
    }

    fn range_iter(
        &self,
        _range: OrderedStoreRange<I>,
    ) -> Result<Box<dyn Iterator<Item = V> + Send>, OrderedStoreError> {
        unimplemented!()
    }

    fn insert(&mut self, key: K, value: V, idx: I) -> Result<(), OrderedStoreError> {
        if self
            .conn
            .lock()
            .map_err(|err| OrderedStoreError::LockPoisoned(err.to_string()))?
            .hexists(MAIN_STORE, key.to_redis_args())?
        {
            return Err(OrderedStoreError::ValueAlreadyExistsForKey(Box::new(key)));
        }
        if self
            .conn
            .lock()
            .map_err(|err| OrderedStoreError::LockPoisoned(err.to_string()))?
            .hexists(INDEX_STORE, idx.to_redis_args())?
        {
            return Err(OrderedStoreError::ValueAlreadyExistsAtIndex(Box::new(idx)));
        }

        self.conn
            .lock()
            .map_err(|err| OrderedStoreError::LockPoisoned(err.to_string()))?
            .hset(INDEX_STORE, idx.to_redis_args(), key.to_redis_args())?;
        self.conn
            .lock()
            .map_err(|err| OrderedStoreError::LockPoisoned(err.to_string()))?
            .hset(MAIN_STORE, key, (value, idx))?;

        Ok(())
    }

    fn remove_by_index(&mut self, idx: &I) -> Result<Option<(K, V)>, OrderedStoreError> {
        Ok(
            if let Some(key) = self
                .conn
                .lock()
                .map_err(|err| OrderedStoreError::LockPoisoned(err.to_string()))?
                .hdel::<_, _, Option<K>>(INDEX_STORE, idx.to_redis_args())?
            {
                let val = self
                    .conn
                    .lock()
                    .map_err(|err| OrderedStoreError::LockPoisoned(err.to_string()))?
                    .hdel::<_, _, Option<V>>(MAIN_STORE, key.to_redis_args())?
                    .ok_or_else(|| {
                        OrderedStoreError::StoreCorrupted("value missing from main store".into())
                    })?;
                Some((key, val))
            } else {
                None
            },
        )
    }

    fn remove_by_key(&mut self, key: &K) -> Result<Option<(V, I)>, OrderedStoreError> {
        Ok(
            if let Some((val, idx)) = self
                .conn
                .lock()
                .map_err(|err| OrderedStoreError::LockPoisoned(err.to_string()))?
                .hdel::<_, _, Option<(V, I)>>(MAIN_STORE, key.to_redis_args())?
            {
                self.conn
                    .lock()
                    .map_err(|err| OrderedStoreError::LockPoisoned(err.to_string()))?
                    .hdel(INDEX_STORE, idx.to_redis_args())?;
                Some((val, idx))
            } else {
                None
            },
        )
    }
}

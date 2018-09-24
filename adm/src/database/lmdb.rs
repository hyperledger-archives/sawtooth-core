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
use std::path::Path;

use lmdb_zero as lmdb;

use database::error::DatabaseError;

const DEFAULT_SIZE: usize = 1 << 40; // 1024 ** 4

pub struct LmdbContext {
    pub env: lmdb::Environment,
}

impl LmdbContext {
    pub fn new(filepath: &Path, indexes: u32, size: Option<usize>) -> Result<Self, DatabaseError> {
        let flags = lmdb::open::MAPASYNC | lmdb::open::WRITEMAP | lmdb::open::NOSUBDIR;

        let filepath_str = filepath
            .to_str()
            .ok_or_else(|| DatabaseError::InitError(format!("Invalid filepath: {:?}", filepath)))?;

        let mut builder = lmdb::EnvBuilder::new().map_err(|err| {
            DatabaseError::InitError(format!("Failed to initialize environment: {}", err))
        })?;
        builder
            .set_maxdbs(indexes + 1)
            .map_err(|err| DatabaseError::InitError(format!("Failed to set MAX_DBS: {}", err)))?;
        builder
            .set_mapsize(size.unwrap_or(DEFAULT_SIZE))
            .map_err(|err| DatabaseError::InitError(format!("Failed to set MAP_SIZE: {}", err)))?;

        let env = unsafe {
            builder
                .open(filepath_str, flags, 0o600)
                .map_err(|err| DatabaseError::InitError(format!("Database not found: {}", err)))
        }?;
        Ok(LmdbContext { env: env })
    }
}

pub struct LmdbDatabase<'e> {
    ctx: &'e LmdbContext,
    main: lmdb::Database<'e>,
    indexes: HashMap<String, lmdb::Database<'e>>,
}

impl<'e> LmdbDatabase<'e> {
    pub fn new(ctx: &'e LmdbContext, indexes: &[&str]) -> Result<Self, DatabaseError> {
        let main = lmdb::Database::open(
            &ctx.env,
            Some("main"),
            &lmdb::DatabaseOptions::new(lmdb::db::CREATE),
        ).map_err(|err| DatabaseError::InitError(format!("Failed to open database: {:?}", err)))?;

        let mut index_dbs = HashMap::with_capacity(indexes.len());
        for name in indexes {
            let db = lmdb::Database::open(
                &ctx.env,
                Some(name),
                &lmdb::DatabaseOptions::new(lmdb::db::CREATE),
            ).map_err(|err| {
                DatabaseError::InitError(format!("Failed to open database: {:?}", err))
            })?;
            index_dbs.insert(String::from(*name), db);
        }
        Ok(LmdbDatabase {
            ctx: ctx,
            main: main,
            indexes: index_dbs,
        })
    }

    pub fn reader(&self) -> Result<LmdbDatabaseReader, DatabaseError> {
        let txn = lmdb::ReadTransaction::new(&self.ctx.env).map_err(|err| {
            DatabaseError::ReaderError(format!("Failed to create reader: {}", err))
        })?;
        Ok(LmdbDatabaseReader { db: self, txn: txn })
    }

    pub fn writer(&self) -> Result<LmdbDatabaseWriter, DatabaseError> {
        let txn = lmdb::WriteTransaction::new(&self.ctx.env).map_err(|err| {
            DatabaseError::WriterError(format!("Failed to create writer: {}", err))
        })?;
        Ok(LmdbDatabaseWriter { db: self, txn: txn })
    }
}

pub struct LmdbDatabaseReader<'a> {
    db: &'a LmdbDatabase<'a>,
    txn: lmdb::ReadTransaction<'a>,
}

impl<'a> LmdbDatabaseReader<'a> {
    pub fn get(&self, key: &[u8]) -> Option<Vec<u8>> {
        let access = self.txn.access();
        let val: Result<&[u8], _> = access.get(&self.db.main, key);
        val.ok().map(Vec::from)
    }

    pub fn index_get(&self, index: &str, key: &[u8]) -> Result<Option<Vec<u8>>, DatabaseError> {
        let index = self
            .db
            .indexes
            .get(index)
            .ok_or_else(|| DatabaseError::ReaderError(format!("Not an index: {}", index)))?;
        let access = self.txn.access();
        let val: Result<&[u8], _> = access.get(index, key);
        Ok(val.ok().map(Vec::from))
    }

    #[allow(dead_code)]
    pub fn cursor(&self) -> Result<LmdbDatabaseReaderCursor, DatabaseError> {
        let cursor = self
            .txn
            .cursor(&self.db.main)
            .map_err(|err| DatabaseError::ReaderError(format!("{}", err)))?;
        let access = self.txn.access();
        Ok(LmdbDatabaseReaderCursor {
            access: access,
            cursor: cursor,
        })
    }

    pub fn index_cursor(&self, index: &str) -> Result<LmdbDatabaseReaderCursor, DatabaseError> {
        let index = self
            .db
            .indexes
            .get(index)
            .ok_or_else(|| DatabaseError::ReaderError(format!("Not an index: {}", index)))?;
        let cursor = self
            .txn
            .cursor(index)
            .map_err(|err| DatabaseError::ReaderError(format!("{}", err)))?;
        let access = self.txn.access();
        Ok(LmdbDatabaseReaderCursor {
            access: access,
            cursor: cursor,
        })
    }

    pub fn count(&self) -> Result<usize, DatabaseError> {
        self.txn
            .db_stat(&self.db.main)
            .map_err(|err| {
                DatabaseError::CorruptionError(format!("Failed to get database stats: {}", err))
            }).map(|stat| stat.entries)
    }

    pub fn index_count(&self, index: &str) -> Result<usize, DatabaseError> {
        let index = self
            .db
            .indexes
            .get(index)
            .ok_or_else(|| DatabaseError::ReaderError(format!("Not an index: {}", index)))?;
        self.txn
            .db_stat(index)
            .map_err(|err| {
                DatabaseError::CorruptionError(format!("Failed to get database stats: {}", err))
            }).map(|stat| stat.entries)
    }
}

pub struct LmdbDatabaseReaderCursor<'a> {
    access: lmdb::ConstAccessor<'a>,
    cursor: lmdb::Cursor<'a, 'a>,
}

impl<'a> LmdbDatabaseReaderCursor<'a> {
    #[allow(dead_code)]
    pub fn first(&mut self) -> Option<(Vec<u8>, Vec<u8>)> {
        self.cursor
            .first(&self.access)
            .ok()
            .map(|(key, value): (&[u8], &[u8])| (Vec::from(key), Vec::from(value)))
    }

    pub fn last(&mut self) -> Option<(Vec<u8>, Vec<u8>)> {
        self.cursor
            .last(&self.access)
            .ok()
            .map(|(key, value): (&[u8], &[u8])| (Vec::from(key), Vec::from(value)))
    }
}

pub struct LmdbDatabaseWriter<'a> {
    db: &'a LmdbDatabase<'a>,
    txn: lmdb::WriteTransaction<'a>,
}

impl<'a> LmdbDatabaseWriter<'a> {
    pub fn put(&mut self, key: &[u8], value: &[u8]) -> Result<(), DatabaseError> {
        self.txn
            .access()
            .put(&self.db.main, key, value, lmdb::put::Flags::empty())
            .map_err(|err| DatabaseError::WriterError(format!("{}", err)))
    }

    pub fn delete(&mut self, key: &[u8]) -> Result<(), DatabaseError> {
        self.txn
            .access()
            .del_key(&self.db.main, key)
            .map_err(|err| DatabaseError::WriterError(format!("{}", err)))
    }

    pub fn index_put(
        &mut self,
        index: &str,
        key: &[u8],
        value: &[u8],
    ) -> Result<(), DatabaseError> {
        let index = self
            .db
            .indexes
            .get(index)
            .ok_or_else(|| DatabaseError::WriterError(format!("Not an index: {}", index)))?;
        self.txn
            .access()
            .put(index, key, value, lmdb::put::Flags::empty())
            .map_err(|err| DatabaseError::WriterError(format!("{}", err)))
    }

    pub fn index_delete(&mut self, index: &str, key: &[u8]) -> Result<(), DatabaseError> {
        let index = self
            .db
            .indexes
            .get(index)
            .ok_or_else(|| DatabaseError::WriterError(format!("Not an index: {}", index)))?;
        self.txn
            .access()
            .del_key(index, key)
            .map_err(|err| DatabaseError::WriterError(format!("{}", err)))
    }

    pub fn commit(self) -> Result<(), DatabaseError> {
        self.txn
            .commit()
            .map_err(|err| DatabaseError::WriterError(format!("{}", err)))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use config;

    /// Asserts that there are COUNT many objects in DB.
    fn assert_database_count(count: usize, db: &LmdbDatabase) {
        let reader = db.reader().unwrap();

        assert_eq!(reader.count().unwrap(), count,);
    }

    /// Asserts that there are are COUNT many objects in DB's INDEX.
    fn assert_index_count(index: &str, count: usize, db: &LmdbDatabase) {
        let reader = db.reader().unwrap();

        assert_eq!(reader.index_count(index).unwrap(), count,);
    }

    /// Asserts that KEY is associated with VAL in DB.
    fn assert_key_value(key: u8, val: u8, db: &LmdbDatabase) {
        let reader = db.reader().unwrap();

        assert_eq!(reader.get(&[key]).unwrap(), [val],);
    }

    /// Asserts that KEY is associated with VAL in DB's INDEX.
    fn assert_index_key_value(index: &str, key: u8, val: u8, db: &LmdbDatabase) {
        let reader = db.reader().unwrap();

        assert_eq!(reader.index_get(index, &[key]).unwrap().unwrap(), [val],);
    }

    /// Asserts that KEY is not in DB.
    fn assert_not_in_database(key: u8, db: &LmdbDatabase) {
        let reader = db.reader().unwrap();

        assert!(reader.get(&[key]).is_none());
    }

    /// Asserts that KEY is not in DB's INDEX.
    fn assert_not_in_index(index: &str, key: u8, db: &LmdbDatabase) {
        let reader = db.reader().unwrap();

        assert!(reader.index_get(index, &[key]).unwrap().is_none());
    }

    /// Opens an LmdbDatabase and executes its basic operations
    /// (adding keys, deleting keys, etc), making assertions about the
    /// database contents at each step.
    #[test]
    fn test_lmdb() {
        let path_config = config::get_path_config();

        let blockstore_path = &path_config.data_dir.join(String::from("unit-lmdb.lmdb"));

        let ctx = LmdbContext::new(blockstore_path, 3, None)
            .map_err(|err| DatabaseError::InitError(format!("{}", err)))
            .unwrap();

        let database = LmdbDatabase::new(&ctx, &["a", "b"])
            .map_err(|err| DatabaseError::InitError(format!("{}", err)))
            .unwrap();

        assert_database_count(0, &database);
        assert_not_in_database(3, &database);
        assert_not_in_database(5, &database);

        // Add {3: 4}
        let mut writer = database.writer().unwrap();
        writer.put(&[3], &[4]).unwrap();

        assert_database_count(0, &database);
        assert_not_in_database(3, &database);

        writer.commit().unwrap();

        assert_database_count(1, &database);
        assert_key_value(3, 4, &database);

        // Add {5: 6}
        let mut writer = database.writer().unwrap();
        writer.put(&[5], &[6]).unwrap();
        writer.commit().unwrap();

        assert_database_count(2, &database);
        assert_key_value(5, 6, &database);
        assert_key_value(3, 4, &database);

        // Delete {3: 4}
        let mut writer = database.writer().unwrap();
        writer.delete(&[3]).unwrap();

        assert_database_count(2, &database);

        writer.commit().unwrap();

        assert_database_count(1, &database);
        assert_key_value(5, 6, &database);
        assert_not_in_database(3, &database);

        // Add {55: 5} in "a"
        assert_index_count("a", 0, &database);
        assert_index_count("b", 0, &database);
        assert_not_in_index("a", 5, &database);
        assert_not_in_index("b", 5, &database);

        let mut writer = database.writer().unwrap();
        writer.index_put("a", &[55], &[5]).unwrap();

        assert_index_count("a", 0, &database);
        assert_index_count("b", 0, &database);
        assert_not_in_index("a", 5, &database);
        assert_not_in_index("b", 5, &database);

        writer.commit().unwrap();

        assert_index_count("a", 1, &database);
        assert_index_count("b", 0, &database);
        assert_index_key_value("a", 55, 5, &database);
        assert_not_in_index("b", 5, &database);
        assert_database_count(1, &database);
        assert_key_value(5, 6, &database);
        assert_not_in_database(3, &database);

        // Delete {55: 5} in "a"
        let mut writer = database.writer().unwrap();
        writer.index_delete("a", &[55]).unwrap();

        assert_index_count("a", 1, &database);
        assert_index_count("b", 0, &database);
        assert_index_key_value("a", 55, 5, &database);
        assert_not_in_index("b", 5, &database);

        writer.commit().unwrap();

        assert_index_count("a", 0, &database);
        assert_index_count("b", 0, &database);
        assert_not_in_index("a", 5, &database);
        assert_not_in_index("b", 5, &database);
        assert_database_count(1, &database);
        assert_key_value(5, 6, &database);
        assert_not_in_database(3, &database);
    }
}

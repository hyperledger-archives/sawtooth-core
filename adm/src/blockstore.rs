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

use protobuf;
use protobuf::Message;
use sawtooth_sdk::messages::block::{Block, BlockHeader};

use database::database::DatabaseError;
use database::lmdb::LmdbDatabase;

pub struct Blockstore<'a> {
    db: LmdbDatabase<'a>,
}

impl<'a> Blockstore<'a> {
    pub fn new(db: LmdbDatabase<'a>) -> Self {
        Blockstore{
            db: db,
        }
    }

    pub fn get(&self, block_id: &str) -> Result<Block, DatabaseError> {
        let reader = self.db.reader()?;
        let packed = reader.get(&block_id.as_bytes())
            .ok_or(DatabaseError::NotFoundError(format!("Block not found: {}", block_id)))?;
        let block: Block = protobuf::parse_from_bytes(&packed)
            .map_err(|err|
                DatabaseError::CorruptionError(
                    format!("Could not interpret stored data as a block: {}", err)))?;
        Ok(block)
    }

    pub fn get_by_height(&self, height: u64) -> Result<Block, DatabaseError> {
        let reader = self.db.reader()?;
        let block_num = format!("0x{:0>16x}", height);
        let block_id = reader.index_get("index_block_num", &block_num.as_bytes())
            .and_then(|block_id|
                block_id.ok_or(
                    DatabaseError::NotFoundError(format!("Block not found: {}", height))))?;
        let packed = reader.get(&block_id)
            .ok_or(DatabaseError::CorruptionError(format!("Block not found: {:?}", block_id)))?;
        let block: Block = protobuf::parse_from_bytes(&packed)
            .map_err(|err|
                DatabaseError::CorruptionError(
                    format!("Could not interpret stored data as a block: {}", err)))?;
        Ok(block)
    }

    pub fn get_by_batch(&self, batch_id: &str) -> Result<Block, DatabaseError> {
        let reader = self.db.reader()?;
        let block_id = reader.index_get("index_batch", &batch_id.as_bytes())
            .and_then(|block_id|
                block_id.ok_or(
                    DatabaseError::NotFoundError(format!("Batch not found: {}", batch_id))))?;
        let packed = reader.get(&block_id)
            .ok_or(DatabaseError::CorruptionError(format!("Block not found: {:?}", block_id)))?;
        let block: Block = protobuf::parse_from_bytes(&packed)
            .map_err(|err|
                DatabaseError::CorruptionError(
                    format!("Could not interpret stored data as a block: {}", err)))?;
        Ok(block)
    }

    pub fn get_by_transaction(&self, transaction_id: &str) -> Result<Block, DatabaseError> {
        let reader = self.db.reader()?;
        let block_id = reader.index_get("index_transaction", &transaction_id.as_bytes())
            .and_then(|block_id|
                block_id.ok_or(
                    DatabaseError::NotFoundError(format!("Transaction not found: {}", transaction_id))))?;
        let packed = reader.get(&block_id)
            .ok_or(DatabaseError::CorruptionError(format!("Block not found: {:?}", block_id)))?;
        let block: Block = protobuf::parse_from_bytes(&packed)
            .map_err(|err|
                DatabaseError::CorruptionError(
                    format!("Could not interpret stored data as a block: {}", err)))?;
        Ok(block)
    }

    pub fn put(&self, block: Block) -> Result<(), DatabaseError> {
        let block_header: BlockHeader = protobuf::parse_from_bytes(&block.header).map_err(|err|
            DatabaseError::CorruptionError(format!("Invalid block header: {}", err)))?;
        let mut writer = self.db.writer()?;
        // Add block to main db
        let packed = block.write_to_bytes().map_err(|err|
            DatabaseError::WriterError(format!("Failed to serialize block: {}", err)))?;
        writer.put(&block.header_signature.as_bytes(), &packed)?;

        // Add block to block num index
        let block_num_index = format!("0x{:0>16x}", block_header.block_num);
        writer.index_put("index_block_num", &block_num_index.as_bytes(), &block.header_signature.as_bytes())?;

        for batch in block.batches.iter() {
            for txn in batch.transactions.iter() {
                writer.index_put(
                    "index_transaction",
                    &txn.header_signature.as_bytes(),
                    &block.header_signature.as_bytes())?;
            }
        }

        // Add block to batch index
        for batch in block.batches.iter() {
            writer.index_put(
                "index_batch",
                &batch.header_signature.as_bytes(),
                &block.header_signature.as_bytes())?;
        }

        writer.commit()
    }

    pub fn delete(&self, block_id: &str) -> Result<(), DatabaseError> {
        let block = self.get(block_id)?;
        let block_id = &block.header_signature;
        let block_header: BlockHeader = protobuf::parse_from_bytes(&block.header).map_err(|err|
            DatabaseError::CorruptionError(format!("Invalid block header: {}", err)))?;
        // Delete block from main db
        let mut writer = self.db.writer()?;
        writer.delete(&block_id.as_bytes())?;

        // Delete block from block_num index
        let block_num_index = format!("0x{:0>16x}", block_header.block_num);
        writer.index_delete("index_block_num", &block_num_index.as_bytes())?;

        // Delete block from transaction index
        for batch in block.batches.iter() {
            for txn in batch.transactions.iter() {
                writer.index_delete("index_transaction", &txn.header_signature.as_bytes())?;
            }
        }

        // Delete block from batch index
        for batch in block.batches.iter() {
            writer.index_delete("index_batch", &batch.header_signature.as_bytes())?;
        }
        writer.commit()
    }

    /// Get the header signature of the highest block in the blockstore.
    pub fn get_chain_head(&self) -> Result<String, DatabaseError> {
        let reader = self.db.reader()?;
        let mut cursor = reader.index_cursor("index_block_num")?;
        let (_, val) = cursor.last().ok_or(
            DatabaseError::NotFoundError("No chain head".into()))?;
        String::from_utf8(val.into()).map_err(|err|
            DatabaseError::CorruptionError(format!("Chain head block id is corrupt: {}", err)))
    }
}

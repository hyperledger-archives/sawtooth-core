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

use database::error::DatabaseError;
use database::lmdb::LmdbDatabase;

pub struct Blockstore<'a> {
    db: LmdbDatabase<'a>,
}

impl<'a> Blockstore<'a> {
    pub fn new(db: LmdbDatabase<'a>) -> Self {
        Blockstore { db: db }
    }

    pub fn get(&self, block_id: &str) -> Result<Block, DatabaseError> {
        let reader = self.db.reader()?;
        let packed = reader.get(&block_id.as_bytes()).ok_or_else(|| {
            DatabaseError::NotFoundError(format!("Block not found: {}", block_id))
        })?;
        let block: Block = protobuf::parse_from_bytes(&packed).map_err(|err| {
            DatabaseError::CorruptionError(format!(
                "Could not interpret stored data as a block: {}",
                err
            ))
        })?;
        Ok(block)
    }

    pub fn get_by_height(&self, height: u64) -> Result<Block, DatabaseError> {
        let reader = self.db.reader()?;
        let block_num = format!("0x{:0>16x}", height);
        let block_id = reader
            .index_get("index_block_num", &block_num.as_bytes())
            .and_then(|block_id| {
                block_id.ok_or_else(|| {
                    DatabaseError::NotFoundError(format!("Block not found: {}", height))
                })
            })?;
        let packed = reader.get(&block_id).ok_or_else(|| {
            DatabaseError::CorruptionError(format!("Block not found: {:?}", block_id))
        })?;
        let block: Block = protobuf::parse_from_bytes(&packed).map_err(|err| {
            DatabaseError::CorruptionError(format!(
                "Could not interpret stored data as a block: {}",
                err
            ))
        })?;
        Ok(block)
    }

    pub fn get_by_batch(&self, batch_id: &str) -> Result<Block, DatabaseError> {
        let reader = self.db.reader()?;
        let block_id = reader
            .index_get("index_batch", &batch_id.as_bytes())
            .and_then(|block_id| {
                block_id.ok_or_else(|| {
                    DatabaseError::NotFoundError(format!("Batch not found: {}", batch_id))
                })
            })?;
        let packed = reader.get(&block_id).ok_or_else(|| {
            DatabaseError::CorruptionError(format!("Block not found: {:?}", block_id))
        })?;
        let block: Block = protobuf::parse_from_bytes(&packed).map_err(|err| {
            DatabaseError::CorruptionError(format!(
                "Could not interpret stored data as a block: {}",
                err
            ))
        })?;
        Ok(block)
    }

    pub fn get_by_transaction(&self, transaction_id: &str) -> Result<Block, DatabaseError> {
        let reader = self.db.reader()?;
        let block_id = reader
            .index_get("index_transaction", &transaction_id.as_bytes())
            .and_then(|block_id| {
                block_id.ok_or_else(|| {
                    DatabaseError::NotFoundError(format!(
                        "Transaction not found: {}",
                        transaction_id
                    ))
                })
            })?;
        let packed = reader.get(&block_id).ok_or_else(|| {
            DatabaseError::CorruptionError(format!("Block not found: {:?}", block_id))
        })?;
        let block: Block = protobuf::parse_from_bytes(&packed).map_err(|err| {
            DatabaseError::CorruptionError(format!(
                "Could not interpret stored data as a block: {}",
                err
            ))
        })?;
        Ok(block)
    }

    pub fn put(&self, block: &Block) -> Result<(), DatabaseError> {
        let block_header: BlockHeader =
            protobuf::parse_from_bytes(&block.header).map_err(|err| {
                DatabaseError::CorruptionError(format!("Invalid block header: {}", err))
            })?;
        let mut writer = self.db.writer()?;
        // Add block to main db
        let packed = block.write_to_bytes().map_err(|err| {
            DatabaseError::WriterError(format!("Failed to serialize block: {}", err))
        })?;
        writer.put(&block.header_signature.as_bytes(), &packed)?;

        // Add block to block num index
        let block_num_index = format!("0x{:0>16x}", block_header.block_num);
        writer.index_put(
            "index_block_num",
            &block_num_index.as_bytes(),
            &block.header_signature.as_bytes(),
        )?;

        for batch in block.batches.iter() {
            for txn in batch.transactions.iter() {
                writer.index_put(
                    "index_transaction",
                    &txn.header_signature.as_bytes(),
                    &block.header_signature.as_bytes(),
                )?;
            }
        }

        // Add block to batch index
        for batch in block.batches.iter() {
            writer.index_put(
                "index_batch",
                &batch.header_signature.as_bytes(),
                &block.header_signature.as_bytes(),
            )?;
        }

        writer.commit()
    }

    pub fn delete(&self, block_id: &str) -> Result<(), DatabaseError> {
        let block = self.get(block_id)?;
        let block_id = &block.header_signature;
        let block_header: BlockHeader =
            protobuf::parse_from_bytes(&block.header).map_err(|err| {
                DatabaseError::CorruptionError(format!("Invalid block header: {}", err))
            })?;
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
        let (_, val) = cursor
            .last()
            .ok_or_else(|| DatabaseError::NotFoundError("No chain head".into()))?;
        String::from_utf8(val).map_err(|err| {
            DatabaseError::CorruptionError(format!("Chain head block id is corrupt: {}", err))
        })
    }

    // Get the number of blocks
    pub fn get_current_height(&self) -> Result<usize, DatabaseError> {
        let reader = self.db.reader()?;
        reader.count()
    }

    pub fn get_transaction_count(&self) -> Result<usize, DatabaseError> {
        let reader = self.db.reader()?;
        reader.index_count("index_transaction")
    }

    pub fn get_batch_count(&self) -> Result<usize, DatabaseError> {
        let reader = self.db.reader()?;
        reader.index_count("index_batch")
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use config;
    use database::lmdb::LmdbContext;
    use sawtooth_sdk::messages::batch::{Batch, BatchHeader};
    use sawtooth_sdk::messages::transaction::Transaction;

    /// Asserts that BLOCKSTORE has a current height of COUNT.
    fn assert_current_height(count: usize, blockstore: &Blockstore) {
        assert_eq!(blockstore.get_current_height().unwrap(), count,);
    }

    /// Asserts that BLOCK has SIGNATURE.
    fn assert_header_signature(block: Block, signature: String) {
        assert_eq!(block.header_signature, signature,);
    }

    /// Asserts that BLOCKSTORE's chain head has SIGNATURE.
    fn assert_chain_head(signature: String, blockstore: &Blockstore) {
        assert_eq!(blockstore.get_chain_head().unwrap(), signature,);
    }

    /// Opens a blockstore and executes its basic operations (adding,
    /// deleting, and looking up blocks), making assertions about the
    /// blockstore contents at each step.
    #[test]
    fn test_blockstore() {
        let path_config = config::get_path_config();

        let blockstore_path = &path_config.data_dir.join(config::get_blockstore_filename());

        // Set the file size to 10MB, so as to support file systems that do
        // not support sparse files.
        let ctx = LmdbContext::new(blockstore_path, 3, Some(10 * 1024 * 1024))
            .map_err(|err| DatabaseError::InitError(format!("{}", err)))
            .unwrap();

        let database = LmdbDatabase::new(
            &ctx,
            &["index_batch", "index_transaction", "index_block_num"],
        ).map_err(|err| DatabaseError::InitError(format!("{}", err)))
        .unwrap();

        let blockstore = Blockstore::new(database);

        // The blockstore starts with no blocks.
        assert_current_height(0, &blockstore);

        // Add 5 blocks.
        for i in 0..5 {
            let mut block = Block::new();
            block.set_header_signature(format!("block-{}", i));
            let mut header = BlockHeader::new();
            header.set_block_num(i);
            block.set_header(header.write_to_bytes().unwrap());

            blockstore.put(&block).unwrap();

            assert_current_height(i as usize + 1, &blockstore);
            assert_chain_head(format!("block-{}", i), &blockstore);
        }

        assert_current_height(5, &blockstore);

        // Check that the blocks are in the right order.
        for i in 0..5 {
            let block = blockstore.get_by_height(i).unwrap();

            assert_header_signature(block, format!("block-{}", i));
        }

        // Get a block.
        let get_block = blockstore.get("block-2").unwrap();

        assert_header_signature(get_block, String::from("block-2"));

        // Add a block with a batch.
        let mut transaction = Transaction::new();
        transaction.set_header_signature(String::from("transaction"));

        let mut batch = Batch::new();
        batch.set_header_signature(String::from("batch"));
        batch.set_transactions(protobuf::RepeatedField::from_vec(vec![transaction]));
        let batch_header = BatchHeader::new();
        batch.set_header(batch_header.write_to_bytes().unwrap());

        let mut block = Block::new();
        block.set_header_signature(String::from("block-with-batch"));
        let mut block_header = BlockHeader::new();
        block_header.set_block_num(6);
        block.set_header(block_header.write_to_bytes().unwrap());
        block.set_batches(protobuf::RepeatedField::from_vec(vec![batch]));

        blockstore.put(&block).unwrap();

        assert_current_height(6, &blockstore);
        assert_chain_head(String::from("block-with-batch"), &blockstore);

        let get_by_batch = blockstore.get_by_batch("batch").unwrap();

        assert_header_signature(get_by_batch, String::from("block-with-batch"));

        let get_by_transaction = blockstore.get_by_transaction("transaction").unwrap();

        assert_header_signature(get_by_transaction, String::from("block-with-batch"));

        // Delete a block.
        blockstore.delete("block-with-batch").unwrap();

        assert_current_height(5, &blockstore);
        assert_chain_head(String::from("block-4"), &blockstore);
    }
}

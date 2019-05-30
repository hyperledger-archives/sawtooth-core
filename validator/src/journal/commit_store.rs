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

use proto::block::{Block as ProtoBlock, BlockHeader};
use protobuf;
use protobuf::Message;

use batch::Batch;
use block::Block;
use database::error::DatabaseError;
use database::lmdb::DatabaseReader;
use database::lmdb::LmdbDatabase;
use database::lmdb::LmdbDatabaseWriter;
use journal::block_store::{
    BatchIndex, BlockStore, BlockStoreError, IndexedBlockStore, TransactionIndex,
};
use journal::chain::{ChainReadError, ChainReader};
use transaction::Transaction;

/// Contains all committed blocks for the current chain
#[derive(Clone)]
pub struct CommitStore {
    db: LmdbDatabase,
}

impl CommitStore {
    pub fn new(db: LmdbDatabase) -> Self {
        CommitStore { db }
    }

    // Get

    fn read_proto_block_from_main(
        reader: &DatabaseReader,
        block_id: &[u8],
    ) -> Result<ProtoBlock, DatabaseError> {
        let packed = reader.get(&block_id).ok_or_else(|| {
            DatabaseError::NotFoundError(format!("Block not found: {:?}", block_id))
        })?;
        let proto_block: ProtoBlock = protobuf::parse_from_bytes(&packed).map_err(|err| {
            DatabaseError::CorruptionError(format!(
                "Could not interpret stored data as a block: {}",
                err
            ))
        })?;
        Ok(proto_block)
    }

    fn read_block_id_from_batch_index(
        reader: &DatabaseReader,
        batch_id: &[u8],
    ) -> Result<Vec<u8>, DatabaseError> {
        reader
            .index_get("index_batch", &batch_id)
            .and_then(|block_id| {
                block_id.ok_or_else(|| {
                    DatabaseError::NotFoundError(format!("Batch not found: {:?}", batch_id))
                })
            })
    }

    fn read_block_id_from_transaction_index(
        reader: &DatabaseReader,
        transaction_id: &[u8],
    ) -> Result<Vec<u8>, DatabaseError> {
        reader
            .index_get("index_transaction", &transaction_id)
            .and_then(|block_id| {
                block_id.ok_or_else(|| {
                    DatabaseError::NotFoundError(format!(
                        "Transaction not found: {:?}",
                        transaction_id
                    ))
                })
            })
    }

    fn read_block_id_from_block_num_index(
        reader: &DatabaseReader,
        block_num: u64,
    ) -> Result<Vec<u8>, DatabaseError> {
        reader
            .index_get(
                "index_block_num",
                &format!("0x{:0>16x}", block_num).as_bytes(),
            )
            .and_then(|block_id| {
                block_id.ok_or_else(|| {
                    DatabaseError::NotFoundError(format!("Block not found: {}", block_num))
                })
            })
    }

    fn read_chain_head_id_from_block_num_index(
        reader: &DatabaseReader,
    ) -> Result<Vec<u8>, DatabaseError> {
        let mut cursor = reader.index_cursor("index_block_num")?;
        let (_, val) = cursor
            .seek_last()
            .ok_or_else(|| DatabaseError::NotFoundError("No chain head".into()))?;
        Ok(val)
    }

    pub fn get_by_block_id(&self, block_id: &str) -> Result<Block, DatabaseError> {
        let reader = self.db.reader()?;
        let proto_block = Self::read_proto_block_from_main(&reader, block_id.as_bytes())?;
        Ok(proto_block.into())
    }

    pub fn get_by_block_num(&self, block_num: u64) -> Result<Block, DatabaseError> {
        let reader = self.db.reader()?;
        let block_id = Self::read_block_id_from_block_num_index(&reader, block_num)?;
        let proto_block = Self::read_proto_block_from_main(&reader, &block_id)?;
        Ok(proto_block.into())
    }

    pub fn get_by_batch_id(&self, batch_id: &str) -> Result<Block, DatabaseError> {
        let reader = self.db.reader()?;
        let block_id = Self::read_block_id_from_batch_index(&reader, batch_id.as_bytes())?;
        let proto_block = Self::read_proto_block_from_main(&reader, &block_id)?;
        Ok(proto_block.into())
    }

    pub fn get_by_transaction_id(&self, transaction_id: &str) -> Result<Block, DatabaseError> {
        let reader = self.db.reader()?;
        let block_id =
            Self::read_block_id_from_transaction_index(&reader, transaction_id.as_bytes())?;
        let proto_block = Self::read_proto_block_from_main(&reader, &block_id)?;
        Ok(proto_block.into())
    }

    pub fn get_chain_head(&self) -> Result<Block, DatabaseError> {
        let reader = self.db.reader()?;
        let chain_head_id = Self::read_chain_head_id_from_block_num_index(&reader)?;
        let proto_block = Self::read_proto_block_from_main(&reader, &chain_head_id)?;
        Ok(proto_block.into())
    }

    // Put

    fn write_proto_block_to_main_db(
        writer: &mut LmdbDatabaseWriter,
        proto_block: &ProtoBlock,
    ) -> Result<(), DatabaseError> {
        let packed = proto_block.write_to_bytes().map_err(|err| {
            DatabaseError::WriterError(format!("Failed to serialize block: {}", err))
        })?;
        writer.put(&proto_block.header_signature.as_bytes(), &packed)
    }

    fn write_block_num_to_index(
        writer: &mut LmdbDatabaseWriter,
        block_num: u64,
        header_signature: &String,
    ) -> Result<(), DatabaseError> {
        let block_num_index = format!("0x{:0>16x}", block_num);
        writer.index_put(
            "index_block_num",
            &block_num_index.as_bytes(),
            &header_signature.as_bytes(),
        )
    }

    fn write_proto_batches_to_index(
        writer: &mut LmdbDatabaseWriter,
        proto_block: &ProtoBlock,
    ) -> Result<(), DatabaseError> {
        for proto_batch in proto_block.batches.iter() {
            writer.index_put(
                "index_batch",
                &proto_batch.header_signature.as_bytes(),
                &proto_block.header_signature.as_bytes(),
            )?;
        }
        Ok(())
    }

    fn write_proto_transctions_to_index(
        writer: &mut LmdbDatabaseWriter,
        proto_block: &ProtoBlock,
    ) -> Result<(), DatabaseError> {
        for proto_batch in proto_block.batches.iter() {
            for proto_txn in proto_batch.transactions.iter() {
                writer.index_put(
                    "index_transaction",
                    &proto_txn.header_signature.as_bytes(),
                    &proto_block.header_signature.as_bytes(),
                )?;
            }
        }
        Ok(())
    }

    pub fn put_blocks(&self, blocks: Vec<Block>) -> Result<(), DatabaseError> {
        let mut writer = self.db.writer()?;
        for block in blocks {
            Self::put_block(&mut writer, block)?;
        }
        writer.commit()
    }

    fn put_block(writer: &mut LmdbDatabaseWriter, block: Block) -> Result<(), DatabaseError> {
        let block_num = block.block_num;
        let proto_block: ProtoBlock = block.into();

        Self::write_proto_block_to_main_db(writer, &proto_block)?;
        Self::write_block_num_to_index(writer, block_num, &proto_block.header_signature)?;
        Self::write_proto_transctions_to_index(writer, &proto_block)?;
        Self::write_proto_batches_to_index(writer, &proto_block)?;

        Ok(())
    }

    // Delete

    fn delete_proto_block_from_main_db(
        writer: &mut LmdbDatabaseWriter,
        proto_block: &ProtoBlock,
    ) -> Result<(), DatabaseError> {
        writer.delete(&proto_block.header_signature.as_bytes())
    }

    fn delete_block_num_from_index(
        writer: &mut LmdbDatabaseWriter,
        block_num: u64,
    ) -> Result<(), DatabaseError> {
        writer.index_delete(
            "index_block_num",
            &format!("0x{:0>16x}", block_num).as_bytes(),
        )
    }

    fn delete_proto_batches_from_index(
        writer: &mut LmdbDatabaseWriter,
        proto_block: &ProtoBlock,
    ) -> Result<(), DatabaseError> {
        for proto_batch in proto_block.batches.iter() {
            writer.index_delete("index_batch", &proto_batch.header_signature.as_bytes())?;
        }
        Ok(())
    }

    fn delete_proto_transactions_from_index(
        writer: &mut LmdbDatabaseWriter,
        proto_block: &ProtoBlock,
    ) -> Result<(), DatabaseError> {
        for proto_batch in proto_block.batches.iter() {
            for proto_txn in proto_batch.transactions.iter() {
                writer.index_delete("index_transaction", &proto_txn.header_signature.as_bytes())?;
            }
        }
        Ok(())
    }

    fn delete_block_by_id(
        writer: &mut LmdbDatabaseWriter,
        block_id: &str,
    ) -> Result<Block, DatabaseError> {
        let proto_block = Self::read_proto_block_from_main(&*writer, block_id.as_bytes())?;
        let block_header: BlockHeader = protobuf::parse_from_bytes(proto_block.get_header())
            .expect("Unable to parse BlockHeader bytes");

        Self::delete_proto_block_from_main_db(writer, &proto_block)?;
        Self::delete_block_num_from_index(writer, block_header.block_num)?;
        Self::delete_proto_batches_from_index(writer, &proto_block)?;
        Self::delete_proto_transactions_from_index(writer, &proto_block)?;

        Ok(proto_block.into())
    }

    fn delete_blocks_by_ids(&self, block_ids: &[&str]) -> Result<Vec<Block>, DatabaseError> {
        let mut blocks = Vec::new();
        let mut writer = self.db.writer()?;

        for block_id in block_ids {
            blocks.push(Self::delete_block_by_id(&mut writer, block_id)?);
        }

        writer.commit()?;

        Ok(blocks)
    }

    // Legacy

    pub fn get_batch(&self, batch_id: &str) -> Result<Batch, DatabaseError> {
        self.get_by_batch_id(batch_id).and_then(|block| {
            block
                .batches
                .into_iter()
                .skip_while(|batch| batch.header_signature != batch_id)
                .next()
                .ok_or_else(|| DatabaseError::CorruptionError("Batch index corrupted".into()))
        })
    }

    pub fn get_transaction(&self, transaction_id: &str) -> Result<Transaction, DatabaseError> {
        self.get_by_transaction_id(transaction_id)
            .and_then(|block| {
                block
                    .batches
                    .into_iter()
                    .flat_map(|batch| batch.transactions.into_iter())
                    .skip_while(|txn| txn.header_signature != transaction_id)
                    .next()
                    .ok_or_else(|| {
                        DatabaseError::CorruptionError("Transaction index corrupted".into())
                    })
            })
    }

    pub fn get_batch_by_transaction(&self, transaction_id: &str) -> Result<Batch, DatabaseError> {
        self.get_by_transaction_id(transaction_id)
            .and_then(|block| {
                block
                    .batches
                    .into_iter()
                    .skip_while(|batch| {
                        batch
                            .transaction_ids
                            .iter()
                            .any(|txn_id| txn_id == transaction_id)
                    })
                    .next()
                    .ok_or_else(|| {
                        DatabaseError::CorruptionError("Transaction index corrupted".into())
                    })
            })
    }

    pub fn contains_block(&self, block_id: &str) -> Result<bool, DatabaseError> {
        match self.db.reader()?.get(block_id.as_bytes()) {
            Some(_) => Ok(true),
            None => Ok(false),
        }
    }

    pub fn contains_batch(&self, batch_id: &str) -> Result<bool, DatabaseError> {
        match self
            .db
            .reader()?
            .index_get("index_batch", batch_id.as_bytes())?
        {
            Some(_) => Ok(true),
            None => Ok(false),
        }
    }

    pub fn contains_transaction(&self, transaction_id: &str) -> Result<bool, DatabaseError> {
        match self
            .db
            .reader()?
            .index_get("index_transaction", transaction_id.as_bytes())?
        {
            Some(_) => Ok(true),
            None => Ok(false),
        }
    }

    pub fn get_block_count(&self) -> Result<usize, DatabaseError> {
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

    pub fn get_block_by_height_iter(
        &self,
        start: Option<u64>,
        direction: ByHeightDirection,
    ) -> CommitStoreByHeightIterator {
        let next = if start.is_none() {
            match &direction {
                ByHeightDirection::Increasing => Some(0),
                ByHeightDirection::Decreasing => Some(
                    self.get_chain_head()
                        .map(|head| head.block_num)
                        .unwrap_or(0),
                ),
            }
        } else {
            start
        };
        CommitStoreByHeightIterator {
            store: self.clone(),
            next,
            direction,
        }
    }
}

impl BlockStore for CommitStore {
    fn get<'a>(
        &'a self,
        block_ids: &[&str],
    ) -> Result<Box<Iterator<Item = Block> + 'a>, BlockStoreError> {
        Ok(Box::new(CommitStoreGetIterator {
            store: self.clone(),
            block_ids: block_ids.into_iter().map(|id| (*id).into()).collect(),
            index: 0,
        }))
    }

    fn delete(&mut self, block_ids: &[&str]) -> Result<Vec<Block>, BlockStoreError> {
        self.delete_blocks_by_ids(block_ids)
            .map_err(|err| match err {
                DatabaseError::NotFoundError(_) => BlockStoreError::UnknownBlock,
                err => BlockStoreError::Error(format!("{:?}", err)),
            })
    }

    fn put(&mut self, blocks: Vec<Block>) -> Result<(), BlockStoreError> {
        self.put_blocks(blocks).map_err(|err| match err {
            DatabaseError::NotFoundError(_) => BlockStoreError::UnknownBlock,
            err => BlockStoreError::Error(format!("{:?}", err)),
        })
    }

    fn iter<'a>(&'a self) -> Result<Box<Iterator<Item = Block> + 'a>, BlockStoreError> {
        match self.get_chain_head() {
            Ok(head) => Ok(Box::new(self.get_block_by_height_iter(
                Some(head.block_num),
                ByHeightDirection::Decreasing,
            ))),
            Err(DatabaseError::NotFoundError(_)) => Ok(Box::new(
                self.get_block_by_height_iter(None, ByHeightDirection::Decreasing),
            )),
            Err(err) => Err(BlockStoreError::Error(format!("{:?}", err))),
        }
    }
}

impl BatchIndex for CommitStore {
    fn contains(&self, id: &str) -> Result<bool, BlockStoreError> {
        self.contains_batch(id)
            .map_err(|err| BlockStoreError::Error(format!("{:?}", err)))
    }

    fn get_block_by_id(&self, id: &str) -> Result<Option<Block>, BlockStoreError> {
        match self.get_by_batch_id(id) {
            Ok(block) => Ok(Some(block)),
            Err(DatabaseError::NotFoundError(_)) => Ok(None),
            Err(err) => Err(BlockStoreError::Error(format!("{:?}", err))),
        }
    }
}

impl TransactionIndex for CommitStore {
    fn contains(&self, id: &str) -> Result<bool, BlockStoreError> {
        self.contains_transaction(id)
            .map_err(|err| BlockStoreError::Error(format!("{:?}", err)))
    }

    fn get_block_by_id(&self, id: &str) -> Result<Option<Block>, BlockStoreError> {
        match self.get_by_transaction_id(id) {
            Ok(block) => Ok(Some(block)),
            Err(DatabaseError::NotFoundError(_)) => Ok(None),
            Err(err) => Err(BlockStoreError::Error(format!("{:?}", err))),
        }
    }
}

impl IndexedBlockStore for CommitStore {}

struct CommitStoreGetIterator {
    store: CommitStore,
    block_ids: Vec<String>,
    index: usize,
}

impl Iterator for CommitStoreGetIterator {
    type Item = Block;

    fn next(&mut self) -> Option<Self::Item> {
        if let Some(block_id) = self.block_ids.get(self.index) {
            self.index += 1;
            match self.store.get_by_block_id(block_id) {
                Ok(block) => Some(block),
                Err(DatabaseError::NotFoundError(_)) => None,
                Err(err) => {
                    error!("Error getting next block: {:?}", err);
                    None
                }
            }
        } else {
            None
        }
    }
}

pub enum ByHeightDirection {
    Increasing,
    Decreasing,
}

pub struct CommitStoreByHeightIterator {
    store: CommitStore,
    next: Option<u64>,
    direction: ByHeightDirection,
}

impl Iterator for CommitStoreByHeightIterator {
    type Item = Block;

    fn next(&mut self) -> Option<Self::Item> {
        let block = match self.next {
            None => return None,
            Some(next) => match self.store.get_by_block_num(next) {
                Ok(block) => Some(block),
                Err(DatabaseError::NotFoundError(_)) => None,
                Err(err) => {
                    error!("Error getting next block: {:?}", err);
                    return None;
                }
            },
        };
        if block.is_some() {
            self.next = match self.direction {
                ByHeightDirection::Increasing => self.next.map(|next| next + 1),
                ByHeightDirection::Decreasing => self.next.map(|next| next - 1),
            }
        }
        block
    }
}

fn map_block_database_result_to_chain_reader_result(
    result: Result<Block, DatabaseError>,
) -> Result<Option<Block>, ChainReadError> {
    match result {
        Ok(block) => Ok(Some(block)),
        Err(DatabaseError::NotFoundError(_)) => Ok(None),
        Err(err) => Err(ChainReadError::GeneralReadError(format!("{:?}", err))),
    }
}

impl ChainReader for CommitStore {
    fn chain_head(&self) -> Result<Option<Block>, ChainReadError> {
        map_block_database_result_to_chain_reader_result(self.get_chain_head())
    }

    fn get_block_by_block_id(&self, block_id: &str) -> Result<Option<Block>, ChainReadError> {
        map_block_database_result_to_chain_reader_result(self.get_by_block_id(block_id))
    }

    fn get_block_by_block_num(&self, block_num: u64) -> Result<Option<Block>, ChainReadError> {
        map_block_database_result_to_chain_reader_result(self.get_by_block_num(block_num))
    }

    fn count_committed_transactions(&self) -> Result<usize, ChainReadError> {
        self.get_transaction_count()
            .map_err(|err| ChainReadError::GeneralReadError(format!("{:?}", err)))
    }
}

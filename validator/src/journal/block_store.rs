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

use std::sync::{Arc, Mutex};

use std::collections::HashMap;

use block::Block;

#[derive(Debug)]
pub enum BlockStoreError {
    Error(String),
    UnknownBlock,
}

pub trait BlockStore: Sync + Send {
    fn get<'a>(
        &'a self,
        block_ids: &[&str],
    ) -> Result<Box<Iterator<Item = Block> + 'a>, BlockStoreError>;

    fn delete(&mut self, block_ids: &[&str]) -> Result<Vec<Block>, BlockStoreError>;

    fn put(&mut self, blocks: Vec<Block>) -> Result<(), BlockStoreError>;

    fn iter<'a>(&'a self) -> Result<Box<Iterator<Item = Block> + 'a>, BlockStoreError>;
}

pub trait BatchIndex: Sync + Send {
    fn contains(&self, id: &str) -> Result<bool, BlockStoreError>;

    fn get_block_by_id(&self, id: &str) -> Result<Option<Block>, BlockStoreError>;
}

pub trait TransactionIndex: Sync + Send {
    fn contains(&self, id: &str) -> Result<bool, BlockStoreError>;

    fn get_block_by_id(&self, id: &str) -> Result<Option<Block>, BlockStoreError>;
}

pub trait IndexedBlockStore: BlockStore + TransactionIndex + BatchIndex {}

#[derive(Clone, Default)]
pub struct InMemoryBlockStore {
    state: Arc<Mutex<InMemoryBlockStoreState>>,
}

impl InMemoryBlockStore {
    pub fn new() -> Self {
        InMemoryBlockStore::default()
    }

    fn get_block_by_block_id(&self, block_id: &str) -> Option<Block> {
        self.state
            .lock()
            .expect("The mutex is not poisoned")
            .get_block_by_block_id(block_id)
            .cloned()
    }
}

impl IndexedBlockStore for InMemoryBlockStore {}

impl BlockStore for InMemoryBlockStore {
    fn get<'a>(
        &'a self,
        block_ids: &[&str],
    ) -> Result<Box<Iterator<Item = Block> + 'a>, BlockStoreError> {
        let block_ids_owned = block_ids.into_iter().map(|id| (*id).into()).collect();
        Ok(Box::new(InMemoryGetBlockIterator::new(
            self.clone(),
            block_ids_owned,
        )))
    }

    fn delete(&mut self, block_ids: &[&str]) -> Result<Vec<Block>, BlockStoreError> {
        self.state
            .lock()
            .expect("The mutex is poisoned")
            .delete(block_ids)
    }

    fn put(&mut self, blocks: Vec<Block>) -> Result<(), BlockStoreError> {
        self.state
            .lock()
            .expect("The mutex is poisoned")
            .put(blocks)
    }

    fn iter<'a>(&'a self) -> Result<Box<Iterator<Item = Block> + 'a>, BlockStoreError> {
        let chain_head = self
            .state
            .lock()
            .expect("The mutex is poisoned")
            .chain_head_id
            .clone();
        Ok(Box::new(InMemoryIter::new(self.clone(), chain_head)))
    }
}

#[derive(Default)]
pub struct InMemoryBlockStoreState {
    block_by_block_id: HashMap<String, Block>,
    chain_head_num: u64,
    chain_head_id: String,
}

impl InMemoryBlockStoreState {
    fn get_block_by_block_id(&self, block_id: &str) -> Option<&Block> {
        self.block_by_block_id.get(block_id)
    }
}

impl InMemoryBlockStoreState {
    fn delete(&mut self, block_ids: &[&str]) -> Result<Vec<Block>, BlockStoreError> {
        if block_ids
            .iter()
            .any(|block_id| !self.block_by_block_id.contains_key(*block_id))
        {
            return Err(BlockStoreError::UnknownBlock);
        }
        let blocks = block_ids.iter().map(|block_id| {
            let block = self
                .block_by_block_id
                .remove(*block_id)
                .expect("Block removed during middle of delete operation");
            if block.block_num <= self.chain_head_num {
                self.chain_head_id = block.previous_block_id.clone();
                self.chain_head_num = block.block_num - 1;
            }
            block
        });

        Ok(blocks.collect())
    }

    fn put(&mut self, blocks: Vec<Block>) -> Result<(), BlockStoreError> {
        blocks.into_iter().for_each(|block| {
            if block.block_num > self.chain_head_num {
                self.chain_head_id = block.header_signature.clone();
                self.chain_head_num = block.block_num;
            }

            self.block_by_block_id
                .insert(block.header_signature.clone(), block);
        });
        Ok(())
    }
}

impl BatchIndex for InMemoryBlockStore {
    fn contains(&self, id: &str) -> Result<bool, BlockStoreError> {
        Ok(self
            .iter()?
            .flat_map(|block| block.batches)
            .any(|batch| batch.header_signature == id))
    }

    fn get_block_by_id(&self, id: &str) -> Result<Option<Block>, BlockStoreError> {
        Ok(self
            .iter()?
            .find(|block| block.batch_ids.contains(&id.into())))
    }
}

impl TransactionIndex for InMemoryBlockStore {
    fn contains(&self, id: &str) -> Result<bool, BlockStoreError> {
        Ok(self
            .iter()?
            .flat_map(|block| block.batches)
            .flat_map(|batch| batch.transactions)
            .any(|txn| txn.header_signature == id))
    }

    fn get_block_by_id(&self, id: &str) -> Result<Option<Block>, BlockStoreError> {
        Ok(self.iter()?.find(|block| {
            block
                .batches
                .iter()
                .any(|batch| batch.transaction_ids.contains(&id.into()))
        }))
    }
}

struct InMemoryGetBlockIterator {
    blockstore: InMemoryBlockStore,
    block_ids: Vec<String>,
    index: usize,
}

impl InMemoryGetBlockIterator {
    fn new(blockstore: InMemoryBlockStore, block_ids: Vec<String>) -> InMemoryGetBlockIterator {
        InMemoryGetBlockIterator {
            blockstore,
            block_ids,
            index: 0,
        }
    }
}

impl Iterator for InMemoryGetBlockIterator {
    type Item = Block;

    fn next(&mut self) -> Option<Self::Item> {
        let block = match self.block_ids.get(self.index) {
            Some(block_id) => self.blockstore.get_block_by_block_id(block_id),
            None => None,
        };
        self.index += 1;
        block
    }
}

struct InMemoryIter {
    blockstore: InMemoryBlockStore,
    head: String,
}

impl InMemoryIter {
    fn new(blockstore: InMemoryBlockStore, head: String) -> Self {
        InMemoryIter { blockstore, head }
    }
}

impl Iterator for InMemoryIter {
    type Item = Block;

    fn next(&mut self) -> Option<Self::Item> {
        let block = self.blockstore.get_block_by_block_id(&self.head);
        if let Some(ref b) = block {
            self.head = b.previous_block_id.clone();
        }
        block
    }
}

#[cfg(test)]
mod test {
    use super::*;
    use block::Block;
    use journal::NULL_BLOCK_IDENTIFIER;

    fn create_block(header_signature: &str, block_num: u64, previous_block_id: &str) -> Block {
        Block {
            header_signature: header_signature.into(),
            previous_block_id: previous_block_id.into(),
            block_num,
            batches: vec![],
            state_root_hash: "".into(),
            consensus: vec![],
            batch_ids: vec![],
            signer_public_key: "".into(),
            header_bytes: vec![],
        }
    }

    #[test]
    fn test_block_store() {
        let mut store = InMemoryBlockStore::new();

        let block_a = create_block("A", 1, NULL_BLOCK_IDENTIFIER);
        let block_b = create_block("B", 2, "A");
        let block_c = create_block("C", 3, "B");

        store
            .put(vec![block_a.clone(), block_b.clone(), block_c.clone()])
            .unwrap();
        assert_eq!(store.get(&["A"]).unwrap().next().unwrap(), block_a);

        {
            let mut iterator = store.iter().unwrap();

            assert_eq!(iterator.next().unwrap(), block_c);
            assert_eq!(iterator.next().unwrap(), block_b);
            assert_eq!(iterator.next().unwrap(), block_a);
            assert_eq!(iterator.next(), None);
        }

        assert_eq!(store.delete(&["C"]).unwrap(), vec![block_c]);
    }
}

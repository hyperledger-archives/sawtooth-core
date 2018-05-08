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

use block::Block;

#[derive(Debug)]
pub enum BlockStoreError {
    Error(String),
    UnknownBlock,
}

pub trait BlockStore {
    fn get<'a>(&'a self, block_ids: Vec<String>) -> Box<Iterator<Item = &'a Block> + 'a>;

    fn delete(&mut self, block_ids: Vec<String>) -> Result<(), BlockStoreError>;

    fn put(&mut self, blocks: Vec<Block>) -> Result<(), BlockStoreError>;
}

#[derive(Default)]
pub struct InMemoryBlockStore {
    block_by_block_id: HashMap<String, Block>,
}

impl InMemoryBlockStore {
    pub fn new() -> Self {
        InMemoryBlockStore::default()
    }

    fn get_block_by_block_id(&self, block_id: &str) -> Option<&Block> {
        self.block_by_block_id.get(block_id)
    }
}

impl BlockStore for InMemoryBlockStore {
    fn get<'a>(&'a self, block_ids: Vec<String>) -> Box<Iterator<Item = &'a Block> + 'a> {
        let iterator: InMemoryGetBlockIterator = InMemoryGetBlockIterator::new(self, block_ids);

        Box::new(iterator)
    }

    fn delete(&mut self, block_ids: Vec<String>) -> Result<(), BlockStoreError> {
        if block_ids
            .iter()
            .any(|block_id| !self.block_by_block_id.contains_key(block_id))
        {
            return Err(BlockStoreError::UnknownBlock);
        }
        block_ids.iter().for_each(|block_id| {
            self.block_by_block_id.remove(block_id);
        });
        Ok(())
    }

    fn put(&mut self, blocks: Vec<Block>) -> Result<(), BlockStoreError> {
        blocks.into_iter().for_each(|block| {
            self.block_by_block_id
                .insert(block.header_signature.clone(), block);
        });
        Ok(())
    }
}

struct InMemoryGetBlockIterator<'a> {
    blockstore: &'a InMemoryBlockStore,
    block_ids: Vec<String>,
    index: usize,
}

impl<'a> InMemoryGetBlockIterator<'a> {
    fn new(
        blockstore: &'a InMemoryBlockStore,
        block_ids: Vec<String>,
    ) -> InMemoryGetBlockIterator<'a> {
        InMemoryGetBlockIterator {
            blockstore,
            block_ids,
            index: 0,
        }
    }
}

impl<'a> Iterator for InMemoryGetBlockIterator<'a> {
    type Item = &'a Block;

    fn next(&mut self) -> Option<Self::Item> {
        let block = match self.block_ids.get(self.index) {
            Some(block_id) => self.blockstore.get_block_by_block_id(block_id),
            None => None,
        };
        self.index += 1;
        block
    }
}

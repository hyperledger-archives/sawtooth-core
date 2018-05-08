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
use std::rc::Rc;
use std::sync::RwLock;

use block::Block;
use journal::{BlockStore, NULL_BLOCK_IDENTIFIER};

#[derive(Debug, PartialEq)]
pub enum BlockManagerError {
    MissingPredecessor(String),
    MissingPredecessorInBranch,
    MissingInput,
}

struct Anchor {
    pub blockstore: String,
    pub ref_count: i64,
    pub block_id: String,
}

#[derive(Default)]
pub struct BlockManager {
    block_by_block_id: Rc<RwLock<HashMap<String, (Block, i64)>>>,
    blockstore_by_name: Rc<RwLock<HashMap<String, Box<BlockStore>>>>,

    anchors: Rc<RwLock<HashMap<String, Anchor>>>,
}

/// The BlockManager maintains integrity of all the blocks it contains,
/// such that for any Block within the BlockManager,
/// that Block's predecessor is also within the BlockManager.
impl BlockManager {
    pub fn new() -> Self {
        BlockManager {
            block_by_block_id: Rc::new(RwLock::new(HashMap::new())),
            blockstore_by_name: Rc::new(RwLock::new(HashMap::new())),

            anchors: Rc::new(RwLock::new(HashMap::new())),
        }
    }

    fn garbage_collect(&mut self) {
        let blocks_to_remove: Vec<String> = self.block_by_block_id
            .read()
            .unwrap()
            .iter()
            .filter(|&(_, &(_, count))| count <= 0)
            .map(|(block_id, &(_, _))| block_id.to_owned())
            .collect();
        blocks_to_remove.iter().for_each(|block_id| {
            self.block_by_block_id.write().unwrap().remove(block_id);
        });
    }

    /// Put is idempotent, making the guarantee that after put is called with a
    /// block in the vector argument, that block is in the BlockManager
    /// whether or not it was already in the BlockManager.
    /// Put makes three other guarantees
    ///     - If the zeroth block in branch does not have its predecessor
    ///       in the BlockManager an error is returned
    ///     - If any block after the zeroth block in branch
    ///       does not have its predecessor as the block to its left in
    ///       branch, an error is returned.
    ///     - If branch is empty, an error is returned
    pub fn put(&mut self, branch: Vec<Block>) -> Result<(), BlockManagerError> {
        match branch.split_first() {
            Some((head, tail)) => {
                let predecessor_of_head_in_memory = self.block_by_block_id
                    .read()
                    .unwrap()
                    .contains_key(&head.previous_block_id);
                let predecessor_of_head_in_any_blockstore = self.blockstore_by_name
                    .read()
                    .unwrap()
                    .values()
                    .any(|blockstore| {
                        blockstore
                            .get(vec![head.previous_block_id.as_str()])
                            .count() > 0
                    });
                let head_is_genesis = head.previous_block_id == NULL_BLOCK_IDENTIFIER;

                if !(predecessor_of_head_in_memory || predecessor_of_head_in_any_blockstore
                    || head_is_genesis)
                {
                    return Err(BlockManagerError::MissingPredecessor(format!(
                        "Missing predecessor of block {}: {}",
                        head.header_signature, head.previous_block_id
                    )));
                } else {
                    let mut previous: Option<&str> = None;
                    let branch_has_predecessor_relationship = tail.iter().all(|ref b| {
                        let all_blocks_in_tail_of_branch_have_predecessor = match previous {
                            Some(header_signature) => b.previous_block_id == header_signature,
                            None => b.previous_block_id == head.header_signature,
                        };
                        previous = Some(b.header_signature.as_str());
                        all_blocks_in_tail_of_branch_have_predecessor
                    });
                    if !branch_has_predecessor_relationship {
                        return Err(BlockManagerError::MissingPredecessorInBranch);
                    } else {
                        match self.block_by_block_id
                            .write()
                            .unwrap()
                            .get_mut(head.previous_block_id.as_str())
                        {
                            Some(mut tup) => {
                                let &mut (_, ref mut count) = tup;
                                *count += 1;
                            }
                            None => {
                                if let Some(anchor) = self.anchors
                                    .write()
                                    .unwrap()
                                    .get_mut(head.previous_block_id.as_str())
                                {
                                    anchor.ref_count += 1
                                }
                            }
                        }
                    }
                }
            }
            None => return Err(BlockManagerError::MissingInput),
        }
        let blocks_not_added_yet: Vec<Block> = branch
            .into_iter()
            .filter(|block| {
                !self.block_by_block_id
                    .read()
                    .unwrap()
                    .contains_key(&block.header_signature)
                    && !self.blockstore_by_name
                        .read()
                        .unwrap()
                        .values()
                        .any(|blockstore| {
                            blockstore
                                .get(vec![block.header_signature.as_str()])
                                .count() > 0
                        })
            })
            .collect();
        for block in blocks_not_added_yet {
            self.block_by_block_id
                .write()
                .unwrap()
                .insert(block.header_signature.clone(), (block, 1));
        }
        Ok(())
    }

    pub fn get(&self, block_ids: Vec<String>) -> Box<Iterator<Item = Block>> {
        Box::new(GetBlockIterator::new(
            Rc::clone(&self.block_by_block_id),
            Rc::clone(&self.blockstore_by_name),
            block_ids,
        ))
    }

    pub fn branch(&self, tip: &str) -> Box<Iterator<Item = Block>> {
        unimplemented!()
    }

    pub fn branch_diff(&self, tip: &str, exclude: &str) -> Box<Iterator<Item = Block>> {
        unimplemented!()
    }

    pub fn ref_block(&mut self, block_id: &str) -> Result<(), BlockManagerError> {
        unimplemented!()
    }

    pub fn unref_block(&mut self, block_id: &str) -> Result<(), BlockManagerError> {
        if let Some(tup) = self.block_by_block_id.write().unwrap().get_mut(block_id) {
            let &mut (_, ref mut ref_count) = tup;
            *ref_count -= 1;
        }

        self.garbage_collect();
        Ok(())
    }

    pub fn add_store(
        &mut self,
        store_name: &str,
        store: Box<BlockStore>,
    ) -> Result<(), BlockManagerError> {
        unimplemented!()
    }

    pub fn persist(&mut self, head: &str, store_name: &str) -> Result<(), BlockManagerError> {
        unimplemented!()
    }
}

struct GetBlockIterator {
    block_by_block_id: Rc<RwLock<HashMap<String, (Block, i64)>>>,
    blockstore_by_name: Rc<RwLock<HashMap<String, Box<BlockStore>>>>,
    block_ids: Vec<String>,
    index: usize,
}

impl GetBlockIterator {
    pub fn new(
        block_by_block_id: Rc<RwLock<HashMap<String, (Block, i64)>>>,
        blockstore_by_name: Rc<RwLock<HashMap<String, Box<BlockStore>>>>,
        block_ids: Vec<String>,
    ) -> Self {
        GetBlockIterator {
            block_by_block_id,
            blockstore_by_name,
            block_ids,
            index: 0,
        }
    }
}

impl Iterator for GetBlockIterator {
    type Item = Block;

    fn next(&mut self) -> Option<Self::Item> {
        let item = match self.block_ids.get(self.index) {
            Some(block_id) => {
                let block_by_block_id = self.block_by_block_id.read().unwrap();
                match block_by_block_id.get(block_id) {
                    Some(&(ref block, _)) => Some(block.clone()),
                    None => self.blockstore_by_name
                        .read()
                        .unwrap()
                        .values()
                        .find(|blockstore| blockstore.get(vec![block_id]).count() > 0)
                        .map(|blockstore| blockstore.get(vec![block_id]).nth(0).unwrap()),
                }
            }
            None => None,
        };
        self.index += 1;
        item
    }
}

#[cfg(test)]
mod tests {

    use super::{BlockManager, BlockManagerError};
    use block::Block;
    use journal::NULL_BLOCK_IDENTIFIER;

    fn create_block(header_signature: &str, previous_block_id: &str, block_num: u64) -> Block {
        Block {
            header_signature: header_signature.to_string(),
            batches: vec![],
            state_root_hash: "".to_string(),
            consensus: vec![],
            batch_ids: vec![],
            signer_public_key: "".to_string(),
            previous_block_id: previous_block_id.to_string(),
            block_num,
        }
    }

    #[test]
    fn test_put_then_unref() {
        let a = create_block("A", NULL_BLOCK_IDENTIFIER, 0);
        let b = create_block("B", "A", 1);
        let c = create_block("C", "A", 1);
        let c_block_id = c.header_signature.clone();

        let mut block_manager = BlockManager::new();
        assert_eq!(block_manager.put(vec![a, b]), Ok(()));

        assert_eq!(block_manager.put(vec![c]), Ok(()));

        block_manager.unref_block(c_block_id.as_str()).unwrap();

        let d = create_block("D", "C", 2);

        assert_eq!(
            block_manager.put(vec![d]),
            Err(BlockManagerError::MissingPredecessor(format!(
                "Missing predecessor of block D: C"
            )))
        );
    }

    #[test]
    fn test_put_empty_vec() {
        let mut block_manager = BlockManager::new();
        assert_eq!(
            block_manager.put(vec![]),
            Err(BlockManagerError::MissingInput)
        );
    }

    #[test]
    fn test_put_missing_predecessor() {
        let mut block_manager = BlockManager::new();
        let a = create_block("A", "o", 54);
        let b = create_block("B", "A", 55);
        assert_eq!(
            block_manager.put(vec![a, b]),
            Err(BlockManagerError::MissingPredecessor(format!(
                "Missing predecessor of block A: o"
            )))
        );
    }

    #[test]
    fn test_get_blocks() {
        let mut block_manager = BlockManager::new();
        let a = create_block("A", NULL_BLOCK_IDENTIFIER, 0);
        let b = create_block("B", "A", 1);
        let c = create_block("C", "B", 2);

        block_manager
            .put(vec![a.clone(), b.clone(), c.clone()])
            .unwrap();

        let mut get_block_iter =
            block_manager.get(vec!["A".to_string(), "C".to_string(), "D".to_string()]);

        assert_eq!(get_block_iter.next(), Some(a));
        assert_eq!(get_block_iter.next(), Some(c));
        assert_eq!(get_block_iter.next(), None);
        assert_eq!(get_block_iter.next(), None);
    }
}

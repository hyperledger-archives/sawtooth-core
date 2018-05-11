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
use std::collections::HashSet;

use block::Block;
use journal::NULL_BLOCK_IDENTIFIER;
use journal::block_store::BlockStore;

#[derive(Debug, PartialEq)]
pub enum BlockManagerError {
    MissingPredecessor(String),
    MissingPredecessorInBranch(String),
    MissingInput,
    UnknownBlock,
    UnknownBlockStore,
}

/// Anchors hold reference count information for blocks that are just on the inside edge
/// of a blockstore. This includes the head block in a blockstore.
#[derive(Default)]
struct Anchors {
    anchors_by_blockstore_name: HashMap<String, HashSet<String>>,

    anchors_by_block_id: HashMap<String, Anchor>,
}

impl Anchors {
    fn add_anchor(
        &mut self,
        block_id: &str,
        blockstore_name: &str,
        external_ref_count: u64,
        internal_ref_count: u64,
    ) {
        let anchor = Anchor {
            blockstore_name: blockstore_name.into(),
            external_ref_count,
            internal_ref_count,
            block_id: block_id.into(),
        };
        self.anchors_by_block_id.insert(block_id.into(), anchor);

        if self.anchors_by_blockstore_name
            .get_mut(blockstore_name)
            .map(|ref mut anchors| anchors.insert(block_id.into()))
            .is_none()
        {
            let mut set = HashSet::new();
            set.insert(block_id.into());

            self.anchors_by_blockstore_name
                .insert(blockstore_name.into(), set);
        }
    }

    fn get_blockstore_name(&self, block_id: &str) -> Option<&str> {
        self.anchors_by_block_id
            .get(block_id)
            .map(|anchor| anchor.blockstore_name.as_str())
    }

    fn convert(&mut self, blocks: Vec<Block>) -> Vec<RefBlock> {
        blocks
            .into_iter()
            .map(|block| {
                let anchor = self.anchors_by_block_id
                    .remove(block.header_signature.as_str())
                    .unwrap();
                let anchors = self.anchors_by_blockstore_name
                    .get_mut(anchor.blockstore_name.as_str())
                    .expect("Anchors in anchor_by_block_id and anchors_by_blockstore_name lost integrity");

                anchors.remove(block.header_signature.as_str());
                RefBlock::new(block, anchor.external_ref_count, anchor.internal_ref_count)
            })
            .collect()
    }

    fn iter_by_blockstore<'a>(
        &'a self,
        blockstore_name: &str,
    ) -> Box<Iterator<Item = &Anchor> + 'a> {
        let anchors_by_block_id = &self.anchors_by_block_id;

        match self.anchors_by_blockstore_name.get(blockstore_name) {
            Some(anchors) => {
                let iter = anchors
                    .iter()
                    .map(move |block_id| anchors_by_block_id.get(block_id).unwrap());
                Box::new(iter)
            }
            None => Box::new(::std::iter::empty()),
        }
    }

    fn contains(&self, block_id: &str) -> bool {
        self.anchors_by_block_id.contains_key(block_id)
    }

    fn increase_internal_ref_count(&mut self, block_id: &str) {
        if let Some(anchor) = self.anchors_by_block_id.get_mut(block_id) {
            anchor.internal_ref_count += 1;
        }
    }

    fn decrease_internal_ref_count(&mut self, block_id: &str) {
        if let Some(anchor) = self.anchors_by_block_id.get_mut(block_id) {
            match anchor.internal_ref_count.checked_sub(1) {
                Some(ref_count) => anchor.internal_ref_count = ref_count,
                None => panic!("The internal ref-count on an anchor dropped below 0"),
            }
        }
    }

    fn get_internal_ref_count(&self, block_id: &str) -> Option<u64> {
        self.anchors_by_block_id
            .get(block_id)
            .map(|anchor| anchor.internal_ref_count)
    }

    fn increase_external_ref_count(&mut self, block_id: &str) {
        if let Some(anchor) = self.anchors_by_block_id.get_mut(block_id) {
            anchor.external_ref_count += 1;
        }
    }

    fn decrease_external_ref_count(&mut self, block_id: &str) {
        if let Some(anchor) = self.anchors_by_block_id.get_mut(block_id) {
            match anchor.external_ref_count.checked_sub(1) {
                Some(ref_count) => anchor.external_ref_count = ref_count,
                None => panic!("The external ref-count on an anchor dropped below 0"),
            }
        }
    }

    fn get_external_ref_count(&self, block_id: &str) -> Option<u64> {
        self.anchors_by_block_id
            .get(block_id)
            .map(|anchor| anchor.external_ref_count)
    }
}

struct Anchor {
    pub blockstore_name: String,
    pub external_ref_count: u64,
    pub internal_ref_count: u64,
    pub block_id: String,
}

struct RefBlock {
    pub block: Block,
    pub external_ref_count: u64,
    pub internal_ref_count: u64,
}

impl RefBlock {
    fn new_reffed_block(block: Block) -> Self {
        RefBlock {
            block,
            external_ref_count: 0,
            internal_ref_count: 1,
        }
    }

    fn new_unreffed_block(block: Block) -> Self {
        RefBlock {
            block,
            external_ref_count: 1,
            internal_ref_count: 0,
        }
    }

    fn new(block: Block, external_ref_count: u64, internal_ref_count: u64) -> Self {
        RefBlock {
            block,
            external_ref_count,
            internal_ref_count,
        }
    }

    fn increase_internal_ref_count(&mut self) {
        self.internal_ref_count += 1;
    }

    fn decrease_internal_ref_count(&mut self) {
        match self.internal_ref_count.checked_sub(1) {
            Some(ref_count) => self.internal_ref_count = ref_count,
            None => panic!("The internal ref-count fell below zero, its lowest possible value"),
        }
    }

    fn increase_external_ref_count(&mut self) {
        self.external_ref_count += 1;
    }

    fn decrease_external_ref_count(&mut self) {
        match self.external_ref_count.checked_sub(1) {
            Some(ref_count) => self.external_ref_count = ref_count,
            None => panic!("The external ref-count fell below zero, its lowest possible value"),
        }
    }
}

#[derive(Default)]
pub struct BlockManager {
    block_by_block_id: HashMap<String, RefBlock>,

    blockstore_by_name: HashMap<String, Box<BlockStore>>,

    anchors: Anchors,
}

/// The BlockManager maintains integrity of all the blocks it contains,
/// such that for any Block within the BlockManager,
/// that Block's predecessor is also within the BlockManager.
impl BlockManager {
    pub fn new() -> Self {
        BlockManager::default()
    }

    fn contains(&self, block_id: &str) -> bool {
        let in_memory = self.block_by_block_id.contains_key(block_id);

        let in_any_blockstore = self.blockstore_by_name
            .values()
            .any(|blockstore| blockstore.get(vec![block_id.into()]).count() > 0);
        let is_root = block_id == NULL_BLOCK_IDENTIFIER;

        in_memory || in_any_blockstore || is_root
    }

    /// Checks that every block is preceded by the block referenced by block.previous_block_id except the
    /// zeroth block in tail, which references head.
    fn check_predecessor_relationship(
        &self,
        tail: &[Block],
        head: &Block,
    ) -> Result<(), BlockManagerError> {
        let mut previous = None;
        for block in tail {
            match previous {
                Some(previous_block_id) => {
                    if block.previous_block_id != previous_block_id {
                        return Err(BlockManagerError::MissingPredecessorInBranch(format!(
                            "During Put, missing predecessor of block {}: {}",
                            block.header_signature, block.previous_block_id
                        )));
                    }
                    previous = Some(block.header_signature.as_str());
                }
                None => {
                    if block.previous_block_id != head.header_signature {
                        return Err(BlockManagerError::MissingPredecessorInBranch(format!(
                            "During Put, missing predecessor of block {}: {}",
                            block.previous_block_id, head.header_signature
                        )));
                    }

                    previous = Some(block.header_signature.as_str());
                }
            }
        }
        Ok(())
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
                if !self.contains(head.previous_block_id.as_str()) {
                    return Err(BlockManagerError::MissingPredecessor(format!(
                        "During Put, missing predecessor of block {}: {}",
                        head.header_signature, head.previous_block_id
                    )));
                }

                self.check_predecessor_relationship(tail, head)?;

                match self.block_by_block_id
                    .get_mut(head.previous_block_id.as_str())
                {
                    Some(ref mut ref_block) => ref_block.increase_internal_ref_count(),
                    None => {
                        self.anchors
                            .increase_internal_ref_count(head.previous_block_id.as_str());
                    }
                }
            }
            None => return Err(BlockManagerError::MissingInput),
        }
        let blocks_not_added_yet: Vec<Block> = branch
            .into_iter()
            .filter(|block| !self.contains(block.header_signature.as_str()))
            .collect();

        if let Some((last_block, blocks_with_references)) = blocks_not_added_yet.split_last() {
            self.block_by_block_id.insert(
                last_block.header_signature.clone(),
                RefBlock::new_unreffed_block(last_block.clone()),
            );

            blocks_with_references.into_iter().for_each(|block| {
                self.block_by_block_id.insert(
                    block.header_signature.clone(),
                    RefBlock::new_reffed_block(block.clone()),
                );
            });
        };
        Ok(())
    }

    pub fn get<'a>(&'a self, block_ids: &'a [&'a str]) -> Box<Iterator<Item = &'a Block> + 'a> {
        Box::new(GetBlockIterator::new(self, block_ids))
    }

    fn get_block_by_block_id(&self, block_id: &str) -> Option<&Block> {
        self.block_by_block_id
            .get(block_id)
            .map(|ref ref_block| &ref_block.block)
    }

    fn get_block_from_main_cache_or_blockstore_name(
        &self,
        block_id: &str,
    ) -> (Option<&Block>, Option<&str>) {
        let block = self.get_block_by_block_id(block_id);
        if block.is_some() {
            (block, None)
        } else {
            (None, self.anchors.get_blockstore_name(block_id))
        }
    }

    fn get_block_from_blockstore<'a>(
        &'a self,
        block_id: String,
        store_name: &str,
    ) -> Result<Option<&'a Block>, BlockManagerError> {
        Ok(self.blockstore_by_name
            .get(store_name)
            .ok_or(BlockManagerError::UnknownBlockStore)?
            .get(vec![block_id])
            .nth(0))
    }

    fn get_block_from_any_blockstore(&self, block_id: String) -> Option<&Block> {
        self.blockstore_by_name
            .values()
            .find(|blockstore| blockstore.get(vec![block_id.clone()]).count() > 0)
            .map(|blockstore| blockstore.get(vec![block_id]).nth(0).unwrap())
    }

    pub fn branch(&self, tip: &str) -> Box<Iterator<Item = Block>> {
        unimplemented!()
    }

    pub fn branch_diff(&self, tip: &str, exclude: &str) -> Box<Iterator<Item = Block>> {
        unimplemented!()
    }

    pub fn ref_block(&mut self, block_id: &str) -> Result<(), BlockManagerError> {
        match self.block_by_block_id.get_mut(block_id) {
            Some(ref mut ref_block) => {
                ref_block.increase_external_ref_count();
                Ok(())
            }
            None => {
                if self.anchors.contains(block_id) {
                    self.anchors.increase_external_ref_count(block_id);
                    Ok(())
                } else {
                    Err(BlockManagerError::UnknownBlock)
                }
            }
        }
    }

    pub fn unref_block(&mut self, tip: &str) -> Result<(), BlockManagerError> {
        unimplemented!()
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

struct GetBlockIterator<'a> {
    block_manager: &'a BlockManager,
    block_ids: &'a [&'a str],
    index: usize,
}

impl<'a> GetBlockIterator<'a> {
    pub fn new(block_manager: &'a BlockManager, block_ids: &'a [&'a str]) -> Self {
        GetBlockIterator {
            block_manager,
            block_ids,
            index: 0,
        }
    }
}

impl<'a> Iterator for GetBlockIterator<'a> {
    type Item = &'a Block;

    fn next(&mut self) -> Option<Self::Item> {
        let block = match self.block_ids.get(self.index) {
            Some(block_id) => {
                let (optional_block, optional_blockstore_name) = self.block_manager
                    .get_block_from_main_cache_or_blockstore_name(block_id);
                match optional_block {
                    Some(block) => Some(block),
                    None => {
                        if let Some(blockstore_name) = optional_blockstore_name {
                            self.block_manager
                                .get_block_from_blockstore((*block_id).into(), blockstore_name)
                                .expect("An anchor pointed to a blockstore that does not exist")
                        } else {
                            self.block_manager
                                .get_block_from_any_blockstore((*block_id).into())
                        }
                    }
                }
            }
            None => None,
        };
        self.index += 1;
        block
    }
}

#[cfg(test)]
mod tests {

    use super::{BlockManager, BlockManagerError};
    use block::Block;
    use journal::NULL_BLOCK_IDENTIFIER;

    fn create_block(header_signature: &str, previous_block_id: &str, block_num: u64) -> Block {
        Block {
            header_signature: header_signature.into(),
            batches: vec![],
            state_root_hash: "".into(),
            consensus: vec![],
            batch_ids: vec![],
            signer_public_key: "".into(),
            previous_block_id: previous_block_id.into(),
            block_num,
            header_bytes: vec![],
        }
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
                "During Put, missing predecessor of block A: o"
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

        let mut get_block_iter = block_manager.get(&["A", "C", "D"]);

        assert_eq!(get_block_iter.next(), Some(&a));
        assert_eq!(get_block_iter.next(), Some(&c));
        assert_eq!(get_block_iter.next(), None);
        assert_eq!(get_block_iter.next(), None);
    }
}

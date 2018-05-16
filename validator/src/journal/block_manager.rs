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
use journal::block_store::{BlockStore, BlockStoreError};

#[derive(Debug, PartialEq)]
pub enum BlockManagerError {
    MissingPredecessor(String),
    MissingPredecessorInBranch(String),
    MissingInput,
    UnknownBlock,
    UnknownBlockStore,
    BlockStoreError,
}

impl From<BlockStoreError> for BlockManagerError {
    fn from(_other: BlockStoreError) -> Self {
        BlockManagerError::BlockStoreError
    }
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
        block_num: u64,
        external_ref_count: u64,
        internal_ref_count: u64,
    ) {
        let anchor = Anchor {
            blockstore_name: blockstore_name.into(),
            external_ref_count,
            internal_ref_count,
            block_id: block_id.into(),
            block_num,
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
    pub block_num: u64,
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

    fn insert_block_by_block_id(&mut self, block: RefBlock) {
        self.block_by_block_id
            .insert(block.block.header_signature.clone(), block);
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

    pub fn branch<'a>(&'a self, tip: &str) -> Box<Iterator<Item = &Block> + 'a> {
        Box::new(BranchIterator::new(self, tip.into()))
    }

    pub fn branch_diff<'a>(
        &'a self,
        tip: &str,
        exclude: &str,
    ) -> Box<Iterator<Item = &Block> + 'a> {
        Box::new(BranchDiffIterator::new(self, tip, exclude))
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

    /// Starting at a tip block, if the tip block's ref-count drops to 0,
    /// remove all blocks until a ref-count of 2 is found.
    pub fn unref_block(&mut self, tip: &str) -> Result<(), BlockManagerError> {
        let (external_ref_count, internal_ref_count, block_id) =
            self.lower_tip_blocks_refcount(tip)?;

        let mut blocks_to_remove = vec![];

        let mut optional_new_tip = None;

        if external_ref_count == 0 && internal_ref_count == 0 {
            if let Some(block_id) = block_id {
                let (mut predecesors_to_remove, new_tip) =
                    self.find_block_ids_for_blocks_with_refcount_1_or_less(&block_id);
                blocks_to_remove.append(&mut predecesors_to_remove);
                self.block_by_block_id.remove(tip);
                optional_new_tip = new_tip;
            }
        }

        blocks_to_remove.iter().for_each(|block_id| {
            self.block_by_block_id.remove(block_id.as_str());
        });

        if let Some(block_id) = optional_new_tip {
            if let Some(ref mut new_tip) = self.block_by_block_id.get_mut(block_id.as_str()) {
                new_tip.decrease_internal_ref_count();
            };
        };

        Ok(())
    }

    fn lower_tip_blocks_refcount(
        &mut self,
        tip: &str,
    ) -> Result<(u64, u64, Option<String>), BlockManagerError> {
        match self.block_by_block_id.get_mut(tip) {
            Some(ref mut ref_block) => {
                if ref_block.external_ref_count > 0 {
                    ref_block.decrease_external_ref_count();
                }
                Ok((
                    ref_block.external_ref_count,
                    ref_block.internal_ref_count,
                    Some(ref_block.block.previous_block_id.clone()),
                ))
            }
            None => {
                if self.anchors.contains(tip) {
                    self.anchors.decrease_external_ref_count(tip);

                    Ok((
                        self.anchors.get_external_ref_count(tip).unwrap(),
                        self.anchors.get_internal_ref_count(tip).unwrap(),
                        None,
                    ))
                } else {
                    Err(BlockManagerError::UnknownBlock)
                }
            }
        }
    }

    /// Starting from some `tip` block_id, walk back until finding a block that has a
    /// internal ref_count >= 2 or an external_ref_count > 0.
    fn find_block_ids_for_blocks_with_refcount_1_or_less(
        &mut self,
        tip: &str,
    ) -> (Vec<String>, Option<String>) {
        let mut blocks_to_remove = vec![];
        let mut block_id = tip;
        let pointed_to;
        loop {
            if let Some(ref ref_block) = self.block_by_block_id.get(block_id) {
                if ref_block.internal_ref_count >= 2 || ref_block.external_ref_count >= 1 {
                    pointed_to = Some(block_id.into());
                    break;
                } else if ref_block.block.previous_block_id == NULL_BLOCK_IDENTIFIER {
                    blocks_to_remove.push(block_id.into());
                    pointed_to = None;
                    break;
                } else {
                    blocks_to_remove.push(block_id.into());
                }
                block_id = &ref_block.block.previous_block_id;
            } else {
                self.anchors.decrease_internal_ref_count(block_id);
                pointed_to = None;
                break;
            }
        }
        (blocks_to_remove, pointed_to)
    }

    pub fn add_store(
        &mut self,
        store_name: &str,
        store: Box<BlockStore>,
    ) -> Result<(), BlockManagerError> {
        self.blockstore_by_name.insert(store_name.into(), store);
        Ok(())
    }

    fn remove_blocks_from_blockstore(
        &mut self,
        head: &str,
        other: &str,
        store_name: &str,
    ) -> Result<(), BlockManagerError> {
        let to_be_removed: Vec<Block> = self.branch_diff(other, head).cloned().collect();

        {
            let blockstore = self.blockstore_by_name
                .get_mut(store_name)
                .ok_or(BlockManagerError::UnknownBlockStore)?;

            blockstore.delete(
                to_be_removed
                    .iter()
                    .map(|b| b.header_signature.clone())
                    .collect(),
            )?;
        }

        let (have_anchors, no_anchors) = to_be_removed
            .into_iter()
            .partition(|b| self.anchors.contains(b.header_signature.as_str()));

        for ref_block in self.anchors.convert(have_anchors) {
            self.insert_block_by_block_id(ref_block);
        }

        for block in no_anchors {
            self.insert_block_by_block_id(RefBlock::new_reffed_block(block));
        }

        Ok(())
    }

    fn insert_blocks_in_blockstore(
        &mut self,
        head: &str,
        other: &str,
        store_name: &str,
    ) -> Result<(), BlockManagerError> {
        let to_be_inserted: Vec<Block> = self.branch_diff(head, other).cloned().collect();

        let block_by_block_id = &self.block_by_block_id;
        if let Some((head, tail)) = to_be_inserted.split_first() {
            let ref_block = block_by_block_id
                .get(head.header_signature.as_str())
                .expect("A block that is being inserted in the blockstore will already be in the main cache.");

            self.anchors.add_anchor(
                head.header_signature.as_str(),
                store_name,
                head.block_num,
                ref_block.external_ref_count,
                ref_block.internal_ref_count,
            );

            for block in tail {
                let ref_block = block_by_block_id
                    .get(block.header_signature.as_str())
                    .expect("A block that is being inserted in the blockstore will already be in the main cache.");
                if ref_block.external_ref_count > 0 || ref_block.internal_ref_count > 0 {
                    self.anchors.add_anchor(
                        block.header_signature.as_str(),
                        store_name,
                        block.block_num,
                        ref_block.external_ref_count,
                        ref_block.internal_ref_count,
                    );
                }
            }
        }

        let blockstore = self.blockstore_by_name
            .get_mut(store_name)
            .ok_or(BlockManagerError::UnknownBlockStore)?;
        blockstore.put(to_be_inserted)?;
        Ok(())
    }

    pub fn persist(&mut self, head: &str, store_name: &str) -> Result<(), BlockManagerError> {
        if !self.blockstore_by_name.contains_key(store_name) {
            return Err(BlockManagerError::UnknownBlockStore);
        }

        let head_block_in_blockstore = self.anchors
            .iter_by_blockstore(store_name)
            .max_by_key(|anchor| anchor.block_num)
            .map(|anchor| anchor.block_id.clone());

        if let Some(head_block_in_blockstore) = head_block_in_blockstore {
            let other = head_block_in_blockstore.as_str();

            self.remove_blocks_from_blockstore(head, other, store_name)?;

            self.insert_blocks_in_blockstore(head, other, store_name)?;
        } else {
            // There are no other blocks in the blockstore and so
            // we would like to insert all of the blocks
            self.insert_blocks_in_blockstore(head, "NULL", store_name)?;
        }

        Ok(())
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

struct BranchIterator<'a> {
    block_manager: &'a BlockManager,
    next_block_id: String,
    blockstore: Option<String>,
}

impl<'a> BranchIterator<'a> {
    pub fn new(block_manager: &'a BlockManager, first_block_id: String) -> Self {
        BranchIterator {
            block_manager,
            next_block_id: first_block_id,
            blockstore: None,
        }
    }
}

impl<'a> Iterator for BranchIterator<'a> {
    type Item = &'a Block;

    fn next(&mut self) -> Option<Self::Item> {
        if self.next_block_id == NULL_BLOCK_IDENTIFIER {
            None
        } else if self.blockstore.is_none() {
            let (block_option, blockstore_name_option) = self.block_manager
                .get_block_from_main_cache_or_blockstore_name(self.next_block_id.as_str());
            let block = block_option.or_else(|| {
                blockstore_name_option
                    .map(|blockstore_name| {
                        self.blockstore = Some(blockstore_name.into());
                        self.block_manager
                            .get_block_from_blockstore(self.next_block_id.clone(), blockstore_name)
                            .expect("Blockstore referenced by anchor does not exist")
                    })
                    .unwrap_or(None)
            });
            if let Some(block) = block {
                self.next_block_id = block.previous_block_id.clone();
            }
            block
        } else {
            let blockstore_id = self.blockstore.as_ref().unwrap();
            let block = self.block_manager
                .get_block_from_blockstore(self.next_block_id.clone(), blockstore_id)
                .expect("The Blockmanager has lost a blockstore that is referenced by an anchor")
                .expect(
                    "The block was not in the blockstore referenced by a successor block's anchor",
                );
            Some(block)
        }
    }
}

struct BranchDiffIterator<'a> {
    block_manager: &'a BlockManager,

    left_block: Option<&'a Block>,
    right_block: Option<&'a Block>,

    blockstore: Option<String>,

    has_reached_common_ancestor: bool,
}

impl<'a> BranchDiffIterator<'a> {
    fn new(block_manager: &'a BlockManager, tip: &str, exclude: &str) -> Self {
        let mut iterator = BranchDiffIterator {
            block_manager,
            left_block: None,
            right_block: None,

            blockstore: None,
            has_reached_common_ancestor: false,
        };

        iterator.left_block = iterator.get_block_by_block_id(tip.into());
        iterator.right_block = iterator.get_block_by_block_id(exclude.into());

        if let Some(left) = iterator.left_block {
            if let Some(right) = iterator.right_block {
                let difference = iterator.block_num_difference(left, right);
                if difference < 0 {
                    iterator.right_block = iterator.get_nth_previous_block(
                        right.header_signature.clone(),
                        difference.abs() as u64,
                    );
                }
            }
        }

        iterator
    }

    fn block_num_difference(&self, left: &Block, right: &Block) -> i64 {
        left.block_num as i64 - right.block_num as i64
    }

    fn get_previous_block(&mut self, block_id: String) -> Option<&'a Block> {
        let block = self.get_block_by_block_id(block_id);
        block
            .map(|b| self.get_block_by_block_id(b.previous_block_id.clone()))
            .unwrap_or(None)
    }

    fn get_nth_previous_block(&mut self, block_id: String, n: u64) -> Option<&'a Block> {
        if n == 0 {
            return None;
        }

        let mut current_block_id = block_id;

        let mut block = self.get_previous_block(current_block_id.clone());
        if let Some(b) = block {
            current_block_id = b.header_signature.clone();
        }

        for _ in 1..n {
            block = self.get_previous_block(current_block_id.clone());
            if let Some(b) = block {
                current_block_id = b.header_signature.clone();
            }
        }
        block
    }

    fn get_block_by_block_id(&mut self, block_id: String) -> Option<&'a Block> {
        if block_id == NULL_BLOCK_IDENTIFIER {
            None
        } else if self.blockstore.is_none() {
            let (block_option, blockstore_name_option) = self.block_manager
                .get_block_from_main_cache_or_blockstore_name(block_id.as_str());
            block_option.or_else(|| {
                blockstore_name_option
                    .map(|blockstore_name| {
                        self.blockstore = Some(blockstore_name.into());
                        self.block_manager
                            .get_block_from_blockstore(block_id, blockstore_name)
                            .expect("Blockstore referenced by anchor does not exist")
                    })
                    .unwrap_or(None)
            })
        } else {
            let blockstore_id = self.blockstore.as_ref().unwrap();
            let block = self.block_manager
                .get_block_from_blockstore(block_id.clone(), blockstore_id)
                .expect("The Blockmanager has lost a blockstore that is referenced by an anchor")
                .expect(
                    "The block was not in the blockstore referenced by a successor block's anchor",
                );
            Some(block)
        }
    }
}

impl<'a> Iterator for BranchDiffIterator<'a> {
    type Item = &'a Block;

    fn next(&mut self) -> Option<Self::Item> {
        if self.has_reached_common_ancestor {
            None
        } else if let Some(left) = self.left_block {
            if let Some(right) = self.right_block {
                if left.header_signature == NULL_BLOCK_IDENTIFIER {
                    return None;
                }
                if left.header_signature == right.header_signature
                    && left.block_num == right.block_num
                {
                    self.has_reached_common_ancestor = true;
                    return None;
                }
                let difference = self.block_num_difference(left, right);
                if difference > 0 {
                    self.left_block = self.get_previous_block(left.header_signature.clone());
                } else {
                    self.left_block = self.get_previous_block(left.header_signature.clone());
                    self.right_block = self.get_previous_block(right.header_signature.clone());
                }
                Some(left)
            } else {
                self.left_block = self.get_previous_block(left.header_signature.clone());
                Some(left)
            }
        } else {
            None
        }
    }
}

#[cfg(test)]
mod tests {

    use super::{BlockManager, BlockManagerError};
    use block::Block;
    use journal::NULL_BLOCK_IDENTIFIER;
    use journal::block_store::InMemoryBlockStore;

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
    fn test_put_ref_then_unref() {
        let a = create_block("A", NULL_BLOCK_IDENTIFIER, 0);
        let b = create_block("B", "A", 1);
        let b_block_id = b.header_signature.clone();
        let c = create_block("C", "B", 2);
        let c_block_id = c.header_signature.clone();

        let mut block_manager = BlockManager::new();
        assert_eq!(block_manager.put(vec![a, b]), Ok(()));

        assert_eq!(block_manager.put(vec![c]), Ok(()));

        block_manager.ref_block(b_block_id.as_str()).unwrap();
        block_manager.unref_block(c_block_id.as_str()).unwrap();

        let d = create_block("D", "C", 3);

        assert_eq!(
            block_manager.put(vec![d]),
            Err(BlockManagerError::MissingPredecessor(format!(
                "During Put, missing predecessor of block D: C"
            )))
        );

        let e = create_block("E", "B", 2);

        block_manager.put(vec![e]).unwrap();
    }

    #[test]
    fn test_multiple_branches_put_ref_then_unref() {
        let a = create_block("A", NULL_BLOCK_IDENTIFIER, 0);
        let b = create_block("B", "A", 1);
        let c = create_block("C", "B", 2);
        let c_block_id = &c.header_signature.clone();
        let d = create_block("D", "C", 3);
        let d_block_id = &d.header_signature.clone();
        let e = create_block("E", "C", 3);

        let f = create_block("F", "E", 4);
        let f_block_id = &f.header_signature.clone();

        let mut block_manager = BlockManager::new();
        block_manager.put(vec![a.clone(), b, c]).unwrap();
        block_manager.put(vec![d]).unwrap();
        block_manager.put(vec![e, f]).unwrap();

        block_manager.unref_block(d_block_id).unwrap();

        block_manager.unref_block(f_block_id).unwrap();

        let q = create_block("Q", "C", 3);
        let q_block_id = &q.header_signature.clone();
        block_manager.put(vec![q]).unwrap();
        block_manager.unref_block(c_block_id).unwrap();
        block_manager.unref_block(q_block_id).unwrap();

        let g = create_block("G", "A", 1);
        assert_eq!(
            block_manager.put(vec![g]),
            Err(BlockManagerError::MissingPredecessor(format!(
                "During Put, missing predecessor of block G: A"
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

    #[test]
    fn test_branch_in_memory() {
        let mut block_manager = BlockManager::new();
        let a = create_block("A", NULL_BLOCK_IDENTIFIER, 0);
        let b = create_block("B", "A", 1);
        let c = create_block("C", "B", 2);

        block_manager
            .put(vec![a.clone(), b.clone(), c.clone()])
            .unwrap();

        let mut branch_iter = block_manager.branch("C");

        assert_eq!(branch_iter.next(), Some(&c));
        assert_eq!(branch_iter.next(), Some(&b));
        assert_eq!(branch_iter.next(), Some(&a));
        assert_eq!(branch_iter.next(), None);

        let mut empty_iter = block_manager.branch("P");

        assert_eq!(empty_iter.next(), None);
    }

    #[test]
    fn test_branch_diff() {
        let mut block_manager = BlockManager::new();

        let a = create_block("A", NULL_BLOCK_IDENTIFIER, 0);
        let b = create_block("B", "A", 1);
        let c = create_block("C", "A", 1);
        let d = create_block("D", "C", 2);
        let e = create_block("E", "D", 3);

        block_manager.put(vec![a.clone(), b.clone()]).unwrap();
        block_manager.put(vec![c.clone()]).unwrap();
        block_manager.put(vec![d.clone(), e.clone()]).unwrap();

        let mut branch_diff_iter = block_manager.branch_diff("C", "B");

        assert_eq!(branch_diff_iter.next(), Some(&c));
        assert_eq!(branch_diff_iter.next(), None);

        let mut branch_diff_iter2 = block_manager.branch_diff("B", "E");

        assert_eq!(branch_diff_iter2.next(), Some(&b));
        assert_eq!(branch_diff_iter2.next(), None);

        let mut branch_diff_iter3 = block_manager.branch_diff("C", "E");

        assert_eq!(branch_diff_iter3.next(), None);

        let mut branch_diff_iter4 = block_manager.branch_diff("E", "C");

        assert_eq!(branch_diff_iter4.next(), Some(&e));
        assert_eq!(branch_diff_iter4.next(), Some(&d));
        assert_eq!(branch_diff_iter4.next(), None);
    }

    #[test]
    fn test_persist_ref_unref() {
        let mut block_manager = BlockManager::new();

        let a = create_block("A", NULL_BLOCK_IDENTIFIER, 0);
        let b = create_block("B", "A", 1);
        let c = create_block("C", "A", 1);
        let d = create_block("D", "C", 2);
        let e = create_block("E", "D", 3);
        let f = create_block("F", "C", 2);

        let q = create_block("Q", "F", 3);
        let p = create_block("P", "E", 4);

        block_manager.put(vec![a.clone(), b.clone()]).unwrap();
        block_manager
            .put(vec![c.clone(), d.clone(), e.clone()])
            .unwrap();
        block_manager.put(vec![f.clone()]).unwrap();

        let blockstore = Box::new(InMemoryBlockStore::new());
        block_manager.add_store("commit", blockstore).unwrap();

        block_manager.persist("C", "commit").unwrap();
        block_manager.persist("B", "commit").unwrap();

        block_manager.ref_block("D").unwrap();

        block_manager.persist("C", "commit").unwrap();
        block_manager.unref_block("B").unwrap();

        block_manager.persist("F", "commit").unwrap();
        block_manager.persist("E", "commit").unwrap();

        block_manager.unref_block("F").unwrap();
        block_manager.unref_block("D").unwrap();

        block_manager.persist("A", "commit").unwrap();

        block_manager.unref_block("E").unwrap();

        assert_eq!(
            block_manager.put(vec![q]),
            Err(BlockManagerError::MissingPredecessor(format!(
                "During Put, missing predecessor of block Q: F"
            )))
        );

        assert_eq!(
            block_manager.put(vec![p]),
            Err(BlockManagerError::MissingPredecessor(format!(
                "During Put, missing predecessor of block P: E"
            )))
        );
    }
}

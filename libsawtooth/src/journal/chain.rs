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
use crate::block::Block;

pub const COMMIT_STORE: &str = "commit_store";

#[derive(Debug)]
pub enum ChainReadError {
    GeneralReadError(String),
}

pub trait ChainReader: Send + Sync {
    fn chain_head(&self) -> Result<Option<Block>, ChainReadError>;
    fn count_committed_transactions(&self) -> Result<usize, ChainReadError>;
    fn get_block_by_block_num(&self, block_num: u64) -> Result<Option<Block>, ChainReadError>;
    fn get_block_by_block_id(&self, block_id: &str) -> Result<Option<Block>, ChainReadError>;
}

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

use batch::Batch;
use block::Block;
use scheduler::TxnExecutionResult;
use std::fmt;

#[derive(Debug, Clone)]
pub enum BlockStatus {
    Unknown = 0,
    Invalid = 1,
    Valid = 2,
    Missing = 3,
}

impl Default for BlockStatus {
    fn default() -> Self {
        BlockStatus::Unknown
    }
}

#[derive(Clone, Debug, Default)]
pub struct BlockWrapper {
    pub block: Block,
    pub status: BlockStatus,
    pub execution_results: Vec<TxnExecutionResult>,
    pub num_transactions: usize,
}

impl BlockWrapper {
    pub fn new(block: Block) -> Self {
        BlockWrapper {
            block,
            ..BlockWrapper::default()
        }
    }

    pub fn header_signature(&self) -> &str {
        &self.block.header_signature
    }

    pub fn previous_block_id(&self) -> &str {
        &self.block.previous_block_id
    }

    pub fn block_num(&self) -> u64 {
        self.block.block_num
    }

    pub fn batches(&self) -> &[Batch] {
        &self.block.batches
    }
}

impl fmt::Display for BlockWrapper {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        write!(f, "{}", self.block)
    }
}

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

use crate::journal::block_wrapper::BlockStatus;
use crate::scheduler::TxnExecutionResult;

const BLOCK_VALIDATION_RESULT_CACHE_SIZE: usize = 512;

type BlockValidationResultCache =
    uluru::LRUCache<[uluru::Entry<BlockValidationResult>; BLOCK_VALIDATION_RESULT_CACHE_SIZE]>;

#[derive(Clone, Default)]
pub struct BlockValidationResultStore {
    validation_result_cache: Arc<Mutex<BlockValidationResultCache>>,
}

impl BlockValidationResultStore {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn insert(&self, result: BlockValidationResult) {
        self.validation_result_cache
            .lock()
            .expect("The mutex is poisoned")
            .insert(result)
    }

    pub fn get(&self, block_id: &str) -> Option<BlockValidationResult> {
        self.validation_result_cache
            .lock()
            .expect("The mutex is poisoned")
            .find(|r| r.block_id == block_id)
            .cloned()
    }

    pub fn fail_block(&self, block_id: &str) {
        if let Some(ref mut result) = self
            .validation_result_cache
            .lock()
            .expect("The mutex is poisoned")
            .find(|r| r.block_id == block_id)
        {
            result.status = BlockStatus::Invalid
        }
    }
}

impl BlockStatusStore for BlockValidationResultStore {
    fn status(&self, block_id: &str) -> BlockStatus {
        self.validation_result_cache
            .lock()
            .expect("The mutex is poisoned")
            .find(|r| r.block_id == block_id)
            .map(|r| r.status.clone())
            .unwrap_or(BlockStatus::Unknown)
    }
}

#[derive(Clone, Debug)]
pub struct BlockValidationResult {
    pub block_id: String,
    pub execution_results: Vec<TxnExecutionResult>,
    pub num_transactions: u64,
    pub status: BlockStatus,
}

impl BlockValidationResult {
    #[allow(dead_code)]
    fn new(
        block_id: String,
        execution_results: Vec<TxnExecutionResult>,
        num_transactions: u64,
        status: BlockStatus,
    ) -> Self {
        BlockValidationResult {
            block_id,
            execution_results,
            num_transactions,
            status,
        }
    }
}

pub trait BlockStatusStore: Clone + Send + Sync {
    fn status(&self, block_id: &str) -> BlockStatus;
}

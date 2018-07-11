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
use std::sync::mpsc::Sender;

use journal::block_wrapper::BlockWrapper;

#[derive(Debug)]
pub enum ValidationError {
    BlockValidationFailure(String),
}

pub trait BlockValidator: Send + Sync {
    fn has_block(&self, block_id: &str) -> bool;

    fn validate_block(&self, block: BlockWrapper) -> Result<(), ValidationError>;

    fn submit_blocks_for_verification(
        &self,
        blocks: &[BlockWrapper],
        response_sender: Sender<BlockWrapper>,
    );
}

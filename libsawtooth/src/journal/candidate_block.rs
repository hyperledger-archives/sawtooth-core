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

use crate::{batch::Batch, block::Block};

#[derive(Debug)]
pub enum CandidateBlockError {
    BlockEmpty,
}

#[derive(Debug)]
pub struct FinalizeBlockResult {
    pub block: Option<Block>,
    pub remaining_batches: Vec<Batch>,
    pub last_batch: Batch,
    pub injected_batch_ids: Vec<String>,
}

pub trait CandidateBlock: Send + Sync {
    fn cancel(&mut self);

    fn previous_block_id(&self) -> String;

    fn add_batch(&mut self, batch: Batch);

    fn can_add_batch(&self) -> bool;

    fn summarize(&mut self, force: bool) -> Result<Option<Vec<u8>>, CandidateBlockError>;

    fn finalize(
        &mut self,
        consensus_data: &[u8],
        force: bool,
    ) -> Result<FinalizeBlockResult, CandidateBlockError>;
}

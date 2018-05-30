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
use std::fmt;

#[derive(Clone, Debug, PartialEq, Default)]
pub struct Block {
    pub header_signature: String,
    pub batches: Vec<Batch>,
    pub state_root_hash: String,
    pub consensus: Vec<u8>,
    pub batch_ids: Vec<String>,
    pub signer_public_key: String,
    pub previous_block_id: String,
    pub block_num: u64,

    pub header_bytes: Vec<u8>,
}

impl fmt::Display for Block {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        write!(
            f,
            "Block(id: {}, block_num: {}, state_root_hash: {}, previous_block_id: {})",
            self.header_signature, self.block_num, self.state_root_hash, self.previous_block_id
        )
    }
}

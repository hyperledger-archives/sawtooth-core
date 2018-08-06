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
use proto;
use protobuf::{self, Message};
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

impl From<Block> for proto::block::Block {
    fn from(other: Block) -> Self {
        let mut proto_block = proto::block::Block::new();
        proto_block.set_batches(protobuf::RepeatedField::from_vec(
            other
                .batches
                .into_iter()
                .map(proto::batch::Batch::from)
                .collect(),
        ));
        proto_block.set_header_signature(other.header_signature);
        proto_block.set_header(other.header_bytes);
        proto_block
    }
}

impl From<proto::block::Block> for Block {
    fn from(mut proto_block: proto::block::Block) -> Self {
        let mut block_header: proto::block::BlockHeader =
            protobuf::parse_from_bytes(proto_block.get_header())
                .expect("Unable to parse BlockHeader bytes");

        Block {
            header_signature: proto_block.take_header_signature(),
            header_bytes: proto_block.take_header(),
            state_root_hash: block_header.take_state_root_hash(),
            consensus: block_header.take_consensus(),
            batch_ids: block_header.take_batch_ids().into_vec(),
            signer_public_key: block_header.take_signer_public_key(),
            previous_block_id: block_header.take_previous_block_id(),
            block_num: block_header.get_block_num(),

            batches: proto_block
                .take_batches()
                .into_iter()
                .map(Batch::from)
                .collect(),
        }
    }
}

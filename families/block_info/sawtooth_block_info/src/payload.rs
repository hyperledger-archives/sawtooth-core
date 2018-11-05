/*
 * Copyright 2018 Bitwise IO, Inc.
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

use state::BlockInfo;

cfg_if! {
    if #[cfg(target_arch = "wasm32")] {
        use sabre_sdk::ApplyError;
    } else {
        use sawtooth_sdk::processor::handler::ApplyError;
    }
}

use protobuf;
use protos::block_info::BlockInfoTxn;

fn validate_hex(string: &str, length: usize) -> bool {
    hex::decode(string).is_ok() && string.len() == length
}

pub struct BlockInfoPayload {
    pub block: BlockInfo,
    pub target_count: u64,
    pub sync_tolerance: u64,
}

impl BlockInfoPayload {
    pub fn new(payload_data: &[u8]) -> Result<BlockInfoPayload, ApplyError> {
        let payload: BlockInfoTxn = parse_protobuf(&payload_data)?;

        {
            let next_block = payload.get_block();

            if !(validate_hex(next_block.get_previous_block_id(), 128)
                || next_block.get_previous_block_id() == "0000000000000000")
            {
                let warning_string = format!(
                    "Invalid previous block id '{}'",
                    next_block.get_previous_block_id()
                );
                warn!("Invalid Transaction: {}", &warning_string);
                return Err(ApplyError::InvalidTransaction(warning_string));
            }
            if !validate_hex(next_block.get_signer_public_key(), 66) {
                let warning_string = format!(
                    "Invalid signer public_key '{}'",
                    next_block.get_signer_public_key()
                );
                warn!("Invalid Transaction: {}", &warning_string);
                return Err(ApplyError::InvalidTransaction(warning_string));
            }
            if !validate_hex(next_block.get_header_signature(), 128) {
                let warning_string = format!(
                    "Invalid header signature '{}'",
                    next_block.get_header_signature()
                );
                warn!("Invalid Transaction: {}", &warning_string);
                return Err(ApplyError::InvalidTransaction(warning_string));
            }
        }

        Ok(payload.into())
    }
}

fn parse_protobuf<M: protobuf::Message>(bytes: &[u8]) -> Result<M, ApplyError> {
    protobuf::parse_from_bytes(bytes).map_err(|err| {
        let warning_string = format!("Failed to serialize protobuf: {:?}", err);
        warn!("Invalid Transaction: {}", &warning_string);
        ApplyError::InvalidTransaction(warning_string)
    })
}

impl From<BlockInfoTxn> for BlockInfoPayload {
    fn from(other: BlockInfoTxn) -> BlockInfoPayload {
        BlockInfoPayload {
            block: other.get_block().into(),
            target_count: other.get_target_count(),
            sync_tolerance: other.get_sync_tolerance(),
        }
    }
}

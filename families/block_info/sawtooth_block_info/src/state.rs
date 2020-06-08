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

use addressing::{create_block_address, get_config_addr};
use protobuf::Message;
use protos;

pub const DEFAULT_SYNC_TOLERANCE: u64 = 60 * 5;
pub const DEFAULT_TARGET_COUNT: u64 = 256;

cfg_if! {
    if #[cfg(target_arch = "wasm32")] {
        use sabre_sdk::ApplyError;
        use sabre_sdk::TransactionContext;
    } else {
        use sawtooth_sdk::processor::handler::ApplyError;
        use sawtooth_sdk::processor::handler::TransactionContext;
    }
}

pub struct Config {
    pub latest_block: u64,
    pub oldest_block: u64,
    pub target_count: u64,
    pub sync_tolerance: u64,
}

pub struct BlockInfo {
    pub block_num: u64,
    pub previous_block_id: String,
    pub signer_public_key: String,
    pub header_signature: String,
    pub timestamp: u64,
}

pub struct BlockInfoState<'a> {
    context: &'a mut dyn TransactionContext,
}
impl<'a> BlockInfoState<'a> {
    pub fn new(context: &'a mut dyn TransactionContext) -> BlockInfoState {
        BlockInfoState { context }
    }

    pub fn get_config_from_state(&mut self) -> Result<Option<Config>, ApplyError> {
        let state_data = self.context.get_state_entry(&get_config_addr());

        let block_config = match state_data {
            Ok(result) => result,
            Err(err) => {
                warn!("Error getting BlockConfig from state, {}", err);
                return Err(ApplyError::InternalError(
                    "Error getting BlockConfig from state".into(),
                ));
            }
        };

        match block_config {
            Some(ref d) => Ok(Some(
                ::protobuf::parse_from_bytes::<protos::block_info::BlockInfoConfig>(d)
                    .map_err(|_| {
                        ApplyError::InternalError("Failed to deserialize BlockInfoConfig".into())
                    })?
                    .into(),
            )),
            None => Ok(None),
        }
    }

    pub fn get_block_by_num(&mut self, block_num: u64) -> Result<Option<BlockInfo>, ApplyError> {
        let state_data = self
            .context
            .get_state_entry(&create_block_address(block_num));

        let block_data = match state_data {
            Ok(result) => result,
            Err(err) => {
                warn!("Error getting BlockInfo from state, {}", err);
                return Err(ApplyError::InternalError(
                    "Error during block_by_num get from state".into(),
                ));
            }
        };

        match block_data {
            Some(ref d) => Ok(Some(
                (&::protobuf::parse_from_bytes::<protos::block_info::BlockInfo>(d).map_err(
                    |_| ApplyError::InternalError("Failed to deserialize BlockInfo".into()),
                )?)
                    .into(),
            )),
            None => Ok(None),
        }
    }

    pub fn set_config_and_block(
        &mut self,
        config: Config,
        block: BlockInfo,
    ) -> Result<(), ApplyError> {
        let mut deletes = vec![];
        let mut possible_oldest_block = config.oldest_block;

        while block.block_num - possible_oldest_block > config.target_count {
            deletes.push(create_block_address(possible_oldest_block));
            possible_oldest_block += 1;
        }

        let oldest_block = config.oldest_block;

        let mut config_proto: protos::block_info::BlockInfoConfig = config.into();
        if possible_oldest_block > oldest_block {
            config_proto.set_oldest_block(possible_oldest_block);
        }

        config_proto.set_latest_block(block.block_num);

        let num_deletes = deletes.len();

        if num_deletes > 0 {
            let actually_deleted = self.context.delete_state_entries(&deletes)?;
            if actually_deleted.len() != num_deletes {
                return Err(ApplyError::InternalError(
                    "Failed to delete blocks that should have been in state.".into(),
                ));
            }
        }

        let block_num = block.block_num;
        let block_info: protos::block_info::BlockInfo = block.into();
        self.context.set_state_entries(vec![
            (
                get_config_addr(),
                config_proto.write_to_bytes().map_err(|_| {
                    warn!("Failed to serialize config proto");
                    ApplyError::InvalidTransaction(
                        "This transaction caused the config to fail to serialze".into(),
                    )
                })?,
            ),
            (
                create_block_address(block_num),
                block_info.write_to_bytes().map_err(|_| {
                    warn!("Failed to serialize block info proto");
                    ApplyError::InvalidTransaction(
                        "This transaction caused the block info to fail to serialze".into(),
                    )
                })?,
            ),
        ])?;

        Ok(())
    }
}

impl From<protos::block_info::BlockInfoConfig> for Config {
    fn from(other: protos::block_info::BlockInfoConfig) -> Self {
        let sync_tolerance = if other.sync_tolerance != 0 {
            other.get_sync_tolerance()
        } else {
            DEFAULT_SYNC_TOLERANCE
        };
        let target_count = if other.target_count != 0 {
            other.get_target_count()
        } else {
            DEFAULT_TARGET_COUNT
        };

        Config {
            latest_block: other.get_latest_block(),
            oldest_block: other.get_oldest_block(),
            sync_tolerance,
            target_count,
        }
    }
}

impl From<Config> for protos::block_info::BlockInfoConfig {
    fn from(other: Config) -> Self {
        let mut config = protos::block_info::BlockInfoConfig::new();
        config.set_latest_block(other.latest_block);
        config.set_oldest_block(other.oldest_block);
        config.set_sync_tolerance(other.sync_tolerance);
        config.set_target_count(other.target_count);
        config
    }
}

impl<'a> From<&'a protos::block_info::BlockInfo> for BlockInfo {
    fn from(other: &protos::block_info::BlockInfo) -> Self {
        BlockInfo {
            block_num: other.get_block_num(),
            previous_block_id: other.get_previous_block_id().to_string(),
            signer_public_key: other.get_signer_public_key().to_string(),
            header_signature: other.get_header_signature().to_string(),
            timestamp: other.get_timestamp(),
        }
    }
}

impl From<BlockInfo> for protos::block_info::BlockInfo {
    fn from(other: BlockInfo) -> Self {
        let mut block_info = protos::block_info::BlockInfo::new();
        block_info.set_block_num(other.block_num);
        block_info.set_previous_block_id(other.previous_block_id);
        block_info.set_signer_public_key(other.signer_public_key);
        block_info.set_header_signature(other.header_signature);
        block_info.set_timestamp(other.timestamp);
        block_info
    }
}

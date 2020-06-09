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

use std::time::{SystemTime, UNIX_EPOCH};

use addressing::NAMESPACE;
use payload::BlockInfoPayload;
use state::{BlockInfoState, Config, DEFAULT_SYNC_TOLERANCE, DEFAULT_TARGET_COUNT};

cfg_if! {
    if #[cfg(target_arch = "wasm32")] {
        use sabre_sdk::ApplyError;
        use sabre_sdk::TransactionContext;
        use sabre_sdk::TransactionHandler;
        use sabre_sdk::TpProcessRequest;
        use sabre_sdk::{WasmPtr, execute_entrypoint};
    } else {
        use sawtooth_sdk::messages::processor::TpProcessRequest;
        use sawtooth_sdk::processor::handler::ApplyError;
        use sawtooth_sdk::processor::handler::TransactionContext;
        use sawtooth_sdk::processor::handler::TransactionHandler;
    }
}

fn validate_timestamp(timestamp: u64, tolerance: u64) -> Result<(), ApplyError> {
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("System time is before Unix epoch.")
        .as_secs();
    if now + tolerance < timestamp {
        let warning_string = format!(
            "Timestamp must be less than local time. Expected {0} + {1} < {2}",
            now, tolerance, timestamp
        );
        warn!("Invalid Transaction: {}", &warning_string);
        return Err(ApplyError::InvalidTransaction(warning_string));
    }

    Ok(())
}

#[derive(Default)]
pub struct BlockInfoTransactionHandler {
    family_name: String,
    family_versions: Vec<String>,
    namespaces: Vec<String>,
}

impl BlockInfoTransactionHandler {
    pub fn new() -> BlockInfoTransactionHandler {
        BlockInfoTransactionHandler {
            family_name: "block_info".to_string(),
            family_versions: vec!["1.0".to_string()],
            namespaces: vec![NAMESPACE.to_string()],
        }
    }

    pub fn execute_block_info_transaction(
        &self,
        payload: BlockInfoPayload,
        state: &mut BlockInfoState,
    ) -> Result<(), ApplyError> {
        if let Some(config) = Self::mutate_config_if_exists(&payload, state)? {
            validate_timestamp(payload.block.timestamp, config.sync_tolerance)?;

            if let Some(previous_block) = state.get_block_by_num(config.latest_block)? {
                if previous_block.block_num != config.latest_block {
                    return Err(ApplyError::InternalError(
                        "Config and state out of synce. Latest block has different block num from block in state".into(),
                    ));
                }
                if payload.block.previous_block_id != previous_block.header_signature {
                    let warning_string = format!(
                            "Previous block id must match header signature of previous block. Expected {}, Found {}",
                            previous_block.header_signature,
                            payload.block.previous_block_id,
                    );
                    warn!("Invalid transaction: {}", &warning_string);
                    return Err(ApplyError::InvalidTransaction(warning_string));
                }

                if payload.block.timestamp < previous_block.timestamp {
                    let warning_string = format!(
                        "Timestamp must be greater than previous block's. Got {}, expected >{}",
                        payload.block.timestamp, previous_block.timestamp
                    );
                    warn!("Invalid Transaction: {}", &warning_string);
                    return Err(ApplyError::InvalidTransaction(warning_string));
                }
            } else {
                return Err(ApplyError::InternalError(
                    "Config and state out of sync. Latest block not found in state.".into(),
                ));
            }

            state.set_config_and_block(config, payload.block)?;
        } else {
            let sync_tolerance = if payload.sync_tolerance != 0 {
                payload.sync_tolerance
            } else {
                DEFAULT_SYNC_TOLERANCE
            };

            let target_count = if payload.target_count != 0 {
                payload.target_count
            } else {
                DEFAULT_TARGET_COUNT
            };

            let config = Config {
                sync_tolerance,
                target_count,
                latest_block: payload.block.block_num,
                oldest_block: payload.block.block_num,
            };

            validate_timestamp(payload.block.timestamp, config.sync_tolerance)?;

            state.set_config_and_block(config, payload.block)?;
        }

        Ok(())
    }

    /// If the config exists in state, modify the target count, sync_tolerance if they are set,
    /// and update the latest block.
    fn mutate_config_if_exists(
        payload: &BlockInfoPayload,
        state: &mut BlockInfoState,
    ) -> Result<Option<Config>, ApplyError> {
        if let Some(mut config) = state.get_config_from_state()? {
            if payload.target_count != 0 {
                config.target_count = payload.target_count;
            }

            if payload.sync_tolerance != 0 {
                config.sync_tolerance = payload.sync_tolerance;
            }

            if payload.block.block_num != config.latest_block + 1 {
                let warning_string = format!(
                    "Current block is {}, but latest block calculated from config is {}",
                    &payload.block.block_num,
                    &config.latest_block + 1
                );
                warn!("Invalid Transaction: {}", &warning_string);
                return Err(ApplyError::InvalidTransaction(warning_string));
            }
            Ok(Some(config))
        } else {
            Ok(None)
        }
    }
}

impl TransactionHandler for BlockInfoTransactionHandler {
    fn family_name(&self) -> String {
        self.family_name.clone()
    }

    fn family_versions(&self) -> Vec<String> {
        self.family_versions.clone()
    }

    fn namespaces(&self) -> Vec<String> {
        self.namespaces.clone()
    }

    fn apply(
        &self,
        request: &TpProcessRequest,
        context: &mut dyn TransactionContext,
    ) -> Result<(), ApplyError> {
        let payload = BlockInfoPayload::new(request.get_payload())?;
        let mut state = BlockInfoState::new(context);

        self.execute_block_info_transaction(payload, &mut state)
    }
}

#[cfg(target_arch = "wasm32")]
// Sabre apply must return a bool
fn apply(request: &TpProcessRequest, context: &mut TransactionContext) -> Result<bool, ApplyError> {
    let handler = BlockInfoTransactionHandler::new();
    match handler.apply(request, context) {
        Ok(_) => Ok(true),
        Err(err) => Err(err),
    }
}

#[cfg(target_arch = "wasm32")]
#[no_mangle]
pub unsafe fn entrypoint(payload: WasmPtr, signer: WasmPtr, signature: WasmPtr) -> i32 {
    execute_entrypoint(payload, signer, signature, apply)
}

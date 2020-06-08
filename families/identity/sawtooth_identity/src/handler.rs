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

cfg_if! {
    if #[cfg(target_arch = "wasm32")] {
        use protos::identity::{Policy, Role};
        use protos::setting::Setting;
        use sabre_sdk::{
            execute_entrypoint, ApplyError, TpProcessRequest, TransactionContext,
            TransactionHandler, WasmPtr,
        };
    } else {
        use sawtooth_sdk::messages::identity::{Policy, Role};
        use sawtooth_sdk::messages::processor::TpProcessRequest;
        use sawtooth_sdk::messages::setting::Setting;
        use sawtooth_sdk::processor::handler::{ApplyError, TransactionContext, TransactionHandler};
    }
}

use crypto::digest::Digest;
use crypto::sha2::Sha256;
use protobuf;
use protos::identities::{IdentityPayload, IdentityPayload_IdentityType};
use state::IdentityState;
use std::iter::repeat;

#[cfg(target_arch = "wasm32")]
// Sabre apply must return a bool
fn apply(request: &TpProcessRequest, context: &mut TransactionContext) -> Result<bool, ApplyError> {
    let handler = IdentityTransactionHandler::new();
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

// The identity namespace is special: it is not derived from a hash.
const IDENTITY_NAMESPACE: &str = "00001d";
const ALLOWED_SIGNER_SETTING: &str = "sawtooth.identity.allowed_keys";

// Constants to be used when constructing config namespace addresses
const SETTING_NAMESPACE: &str = "000000";
const SETTING_MAX_KEY_PARTS: usize = 4;
const SETTING_ADDRESS_PART_SIZE: usize = 16;

/// Computes the address for the given setting key.
/// Keys are broken into four parts, based on the dots in the string. For
/// example, the key `a.b.c` address is computed based on `a`, `b`, `c` and
/// padding. A longer key, for example `a.b.c.d.e`, is still
/// broken into four parts, but the remaining pieces are in the last part:
/// `a`, `b`, `c` and `d.e`.
///
/// Each of these pieces has a short hash computed (the first
/// _SETTING_ADDRESS_PART_SIZE characters of its SHA256 hash in hex), and is
/// joined into a single address, with the config namespace
/// (_SETTING_NAMESPACE) added at the beginning.
///
/// Args:
///     key (str): the setting key
/// Returns:
///     str: the computed address
///
fn setting_key_to_address(key: &str) -> String {
    let mut address = String::new();
    address.push_str(SETTING_NAMESPACE);
    address.push_str(
        &key.splitn(SETTING_MAX_KEY_PARTS, '.')
            .chain(repeat(""))
            .map(short_hash)
            .take(SETTING_MAX_KEY_PARTS)
            .collect::<Vec<_>>()
            .join(""),
    );

    address
}

fn short_hash(s: &str) -> String {
    let mut sha = Sha256::new();
    sha.input(s.as_bytes());
    sha.result_str()[..SETTING_ADDRESS_PART_SIZE].to_string()
}

fn get_allowed_signer_address() -> String {
    setting_key_to_address("sawtooth.identity.allowed_keys")
}

#[derive(Default)]
pub struct IdentityTransactionHandler {
    family_name: String,
    family_versions: Vec<String>,
    namespaces: Vec<String>,
}

impl IdentityTransactionHandler {
    pub fn new() -> IdentityTransactionHandler {
        IdentityTransactionHandler {
            family_name: "sawtooth_identity".to_string(),
            family_versions: vec!["1.0".to_string()],
            namespaces: vec![IDENTITY_NAMESPACE.to_string()],
        }
    }
}

impl TransactionHandler for IdentityTransactionHandler {
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
        transaction: &TpProcessRequest,
        context: &mut dyn TransactionContext,
    ) -> Result<(), ApplyError> {
        check_allowed_transactor(transaction, context)?;

        let payload: IdentityPayload = unpack_data(transaction.get_payload())?;
        let mut state = IdentityState::new(context);
        let data = payload.get_data();

        match payload.get_field_type() {
            IdentityPayload_IdentityType::ROLE => set_role(&data, &mut state),
            IdentityPayload_IdentityType::POLICY => set_policy(&data, &mut state),
            IdentityPayload_IdentityType::IDENTITY_TYPE_UNSET => {
                Err(ApplyError::InvalidTransaction(String::from(
                    "The IdentityType must be either a ROLE or a POLICY",
                )))
            }
        }
    }
}

fn unpack_data<T>(data: &[u8]) -> Result<T, ApplyError>
where
    T: protobuf::Message,
{
    protobuf::parse_from_bytes(&data).map_err(|err| {
        warn!(
            "Invalid transaction: Failed to unmarshal IdentityTransaction: {:?}",
            err
        );
        ApplyError::InvalidTransaction(format!(
            "Failed to unmarshal IdentityTransaction: {:?}",
            err
        ))
    })
}

fn set_policy(data: &[u8], state: &mut IdentityState) -> Result<(), ApplyError> {
    let new_policy: Policy = unpack_data(data)?;

    if new_policy.get_entries().is_empty() {
        return Err(ApplyError::InvalidTransaction(String::from(
            "At least one entry must be in a policy.",
        )));
    }
    if new_policy.get_name().is_empty() {
        return Err(ApplyError::InvalidTransaction(String::from(
            "The name must be set in a policy.",
        )));
    }
    // check entries in the policy
    for entry in new_policy.get_entries().iter() {
        if entry.get_key().is_empty() {
            return Err(ApplyError::InvalidTransaction(String::from(
                "Every policy entry must have a key.",
            )));
        }
    }

    state.set_policy(new_policy)
}

fn set_role(data: &[u8], state: &mut IdentityState) -> Result<(), ApplyError> {
    let role: Role = unpack_data(data)?;

    if role.get_policy_name().is_empty() {
        return Err(ApplyError::InvalidTransaction(String::from(
            "A role must contain a policy name.",
        )));
    }
    if role.get_name().is_empty() {
        return Err(ApplyError::InvalidTransaction(String::from(
            "The name must be set in a role.",
        )));
    }

    // Check that the policy referenced exists
    let policy_list = state.get_policy_list(role.get_policy_name())?;

    let policy_exists = match policy_list {
        None => false,
        Some(policy_list) => {
            let mut exist = false;
            for policy in policy_list.get_policies().iter() {
                if policy.get_name() == role.get_policy_name() {
                    exist = true;
                }
            }
            exist
        }
    };
    if !policy_exists {
        return Err(ApplyError::InvalidTransaction(format!(
            "Cannot set Role: {}, the Policy: {} is not set.",
            role.get_name(),
            role.get_policy_name()
        )));
    }

    state.set_role(role)
}

fn check_allowed_transactor(
    transaction: &TpProcessRequest,
    context: &mut dyn TransactionContext,
) -> Result<(), ApplyError> {
    let header = transaction.get_header();

    let entries_list = get_state_data(&get_allowed_signer_address(), context)?;

    match entries_list {
        None => Err(ApplyError::InvalidTransaction(format!(
            "The transaction signer is not authorized to submit transactions: {:?}",
            header.get_signer_public_key()
        ))),
        Some(entries) => {
            let setting: Setting = unpack_data(&entries)?;
            for entry in setting.get_entries().iter() {
                if entry.get_key() == ALLOWED_SIGNER_SETTING {
                    let allowed_signer: Vec<&str> = entry.get_value().split(',').collect();
                    if allowed_signer.contains(&header.get_signer_public_key()) {
                        return Ok(());
                    }
                }
            }
            Err(ApplyError::InvalidTransaction(format!(
                "The transaction signer is not authorized to submit transactions: {:?}",
                header.get_signer_public_key()
            )))
        }
    }
}

fn get_state_data(
    address: &str,
    context: &mut dyn TransactionContext,
) -> Result<Option<Vec<u8>>, ApplyError> {
    context.get_state_entry(address).map_err(|err| {
        warn!("Invalid transaction: Failed to load state: {:?}", err);
        ApplyError::InvalidTransaction(format!("Failed to load state: {:?}", err))
    })
}

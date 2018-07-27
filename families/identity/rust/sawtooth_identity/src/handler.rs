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
         use sabre_sdk::ApplyError;
         use sabre_sdk::TransactionContext;
         use sabre_sdk::TransactionHandler;
         use sabre_sdk::TpProcessRequest;
         use sabre_sdk::{WasmPtr, execute_entrypoint};
         use identity::{ Policy,
                         PolicyList,
                         Role,
                         RoleList};
         use setting::Setting;

     } else {

         use sawtooth_sdk::messages::processor::TpProcessRequest;
         use sawtooth_sdk::processor::handler::ApplyError;
         use sawtooth_sdk::processor::handler::TransactionContext;
         use sawtooth_sdk::processor::handler::TransactionHandler;
         use sawtooth_sdk::messages::setting::Setting;
         use sawtooth_sdk::messages::identity::{ Policy,
                                                 PolicyList,
                                                 Role,
                                                 RoleList};
     }

}
use identities::{IdentityPayload, IdentityPayload_IdentityType};

use crypto::digest::Digest;
use crypto::sha2::Sha256;
use protobuf;
use std::collections::HashMap;
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
        &key.splitn(SETTING_MAX_KEY_PARTS, ".")
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
        context: &mut TransactionContext,
    ) -> Result<(), ApplyError> {
        check_allowed_transactor(transaction, context)?;

        let payload: IdentityPayload = unpack_data(transaction.get_payload())?;
        let data = payload.get_data();

        match payload.get_field_type() {
            IdentityPayload_IdentityType::ROLE => set_role(&data, context),
            IdentityPayload_IdentityType::POLICY => set_policy(&data, context),
            IdentityPayload_IdentityType::IDENTITY_TYPE_UNSET => {
                Err(ApplyError::InvalidTransaction(format!(
                    "The IdentityType must be either a ROLE or a POLICY"
                )))
            }
        }
    }
}

pub struct IdentityState<'a> {
    context: &'a mut TransactionContext,
}

impl<'a> IdentityState<'a> {
    pub fn new(context: &'a mut TransactionContext) -> IdentityState {
        IdentityState { context: context }
    }

    const MAX_KEY_PARTS: usize = 4;
    const _FIRST_ADDRESS_PART_SIZE: usize = 14;
    const _ADDRESS_PART_SIZE: usize = 16;
    const POLICY_NS: &'a str = "00001d00";
    const ROLE_NS: &'a str = "00001d01";

    fn get_policy_state(&mut self, name: &str) -> Result<Option<Vec<u8>>, ApplyError> {
        let address = self.get_policy_address(name);
        self.get_state_data(&address)
    }

    fn get_role_state(&mut self, name: &str) -> Result<Option<Vec<u8>>, ApplyError> {
        let address = self.get_role_address(name);
        self.get_state_data(&address)
    }

    fn get_state_data(&mut self, address: &str) -> Result<Option<Vec<u8>>, ApplyError> {
        self.context
            .get_state(vec![address.to_string()])
            .map_err(|err| {
                #[cfg(not(target_arch = "wasm32"))]
                warn!("Invalid transaction: Failed to load state: {:?}", err);
                ApplyError::InvalidTransaction(format!("Failed to load state: {:?}", err))
            })
    }

    fn set_policy(
        &mut self,
        policy_name: &str,
        policy_list: &PolicyList,
    ) -> Result<(), ApplyError> {
        let address = self.get_policy_address(policy_name);
        let data = protobuf::Message::write_to_bytes(policy_list).map_err(|err| {
            ApplyError::InternalError(format!("Failed to serialize PolicyList: {:?}", err))
        })?;

        self.set_state(policy_name, &address, data)
    }

    fn set_role(&mut self, role_name: &str, role_list: &RoleList) -> Result<(), ApplyError> {
        let address = self.get_role_address(role_name);
        let data = protobuf::Message::write_to_bytes(role_list).map_err(|err| {
            ApplyError::InternalError(format!("Failed to serialize RoleList: {:?}", err))
        })?;
        self.set_state(role_name, &address, data)
    }

    fn set_state(&mut self, name: &str, address: &String, data: Vec<u8>) -> Result<(), ApplyError> {
        let mut state_entries = HashMap::new();
        state_entries.insert(address.clone(), data);
        self.context.set_state(state_entries).map_err(|err| {
            #[cfg(not(target_arch = "wasm32"))]
            warn!("Failed to set {} at {}", name, address);
            ApplyError::InternalError(format!("Unable to save role {}", name))
        })?;
        #[cfg(not(target_arch = "wasm32"))]
        debug!("Set: \n{:?}", name);

        #[cfg(not(target_arch = "wasm32"))]
        self.context
            .add_event(
                "identity/update".to_string(),
                vec![("updated".to_string(), name.to_string())],
                &vec![],
            )
            .map_err(|err| {
                #[cfg(not(target_arch = "wasm32"))]
                warn!("Failed to add event {}", name);
                ApplyError::InternalError(format!("Failed to add event {}", name))
            })?;
        Ok(())
    }

    fn short_hash(&mut self, s: &str, length: usize) -> String {
        let mut sha = Sha256::new();
        sha.input(s.as_bytes());
        sha.result_str()[..length].to_string()
    }

    fn get_role_address(&mut self, name: &str) -> String {
        let mut address = String::new();
        address.push_str(IdentityState::ROLE_NS);
        address.push_str(
            &name
                .splitn(IdentityState::MAX_KEY_PARTS, ".")
                .chain(repeat(""))
                .enumerate()
                .map(|(i, part)| self.short_hash(part, if i == 0 { 14 } else { 16 }))
                .take(IdentityState::MAX_KEY_PARTS)
                .collect::<Vec<_>>()
                .join(""),
        );

        address
    }

    fn get_policy_address(&mut self, name: &str) -> String {
        let mut address = String::new();
        address.push_str(IdentityState::POLICY_NS);
        address.push_str(&self.short_hash(name, 62));
        address
    }
}

fn unpack_data<T>(data: &[u8]) -> Result<T, ApplyError>
where
    T: protobuf::Message,
{
    protobuf::parse_from_bytes(&data).map_err(|err| {
        #[cfg(not(target_arch = "wasm32"))]
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

fn set_policy(data: &[u8], context: &mut TransactionContext) -> Result<(), ApplyError> {
    let new_policy: Policy = unpack_data(data)?;

    if new_policy.get_entries().is_empty() {
        return Err(ApplyError::InvalidTransaction(format!(
            "At least one entry must be in a policy."
        )));
    }
    if new_policy.get_name().is_empty() {
        return Err(ApplyError::InvalidTransaction(format!(
            "The name must be set in a policy."
        )));
    }
    // check entries in the policy
    for entry in new_policy.get_entries().iter() {
        if entry.get_key().is_empty() {
            return Err(ApplyError::InvalidTransaction(format!(
                "Every policy entry must have a key."
            )));
        }
    }
    let mut state = IdentityState::new(context);
    let entries_list = state.get_policy_state(new_policy.get_name())?;

    let policies: Vec<Policy> = match entries_list {
        None => vec![new_policy.clone()],
        Some(entries) => {
            let policy_list: PolicyList = unpack_data(&entries)?;

            // if a policy with the same name exists, replace that policy
            let mut policy_vec: Vec<Policy> = policy_list
                .get_policies()
                .to_vec()
                .into_iter()
                .filter(|x| x.get_name() != new_policy.get_name())
                .collect();
            policy_vec.push(new_policy.clone());

            // sort all policies by policy.name
            policy_vec.sort_unstable_by(|p1, p2| p1.get_name().cmp(p2.get_name()));
            policy_vec
        }
    };

    let mut new_policy_list = PolicyList::new();

    // Store policy in a PolicyList incase of hash collisions
    new_policy_list.set_policies(protobuf::RepeatedField::from_vec(policies));

    state.set_policy(new_policy.get_name(), &new_policy_list)
}

fn set_role(data: &[u8], context: &mut TransactionContext) -> Result<(), ApplyError> {
    let role: Role = unpack_data(data)?;

    if role.get_policy_name().is_empty() {
        return Err(ApplyError::InvalidTransaction(format!(
            "A role must contain a policy name."
        )));
    }
    if role.get_name().is_empty() {
        return Err(ApplyError::InvalidTransaction(format!(
            "The name must be set in a role."
        )));
    }

    // Check that the policy referenced exists
    let mut state = IdentityState::new(context);
    let policy_entries_list = state.get_policy_state(role.get_policy_name())?;

    let policy_exists = match policy_entries_list {
        None => false,
        Some(entries) => {
            let policy_list: PolicyList = unpack_data(&entries)?;
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

    let role_entries_list = state.get_role_state(role.get_name())?;

    let role_list = match role_entries_list {
        None => RoleList::new(),
        Some(entries) => unpack_data(&entries)?,
    };
    let mut roles: Vec<Role> = role_list
        .get_roles()
        .to_vec()
        .into_iter()
        .filter(|x| x.get_name() != role.get_name())
        .collect();
    roles.push(role.clone());
    // sort all roles by role.name
    roles.sort_unstable_by(|r1, r2| r1.get_name().cmp(r2.get_name()));

    // Store role in a RoleList incase of hash collisions
    let mut new_role_list = RoleList::new();

    new_role_list.set_roles(protobuf::RepeatedField::from_vec(roles));

    state.set_role(role.get_name(), &new_role_list)
}

fn check_allowed_transactor(
    transaction: &TpProcessRequest,
    context: &mut TransactionContext,
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
                    let allowed_signer: Vec<&str> = entry.get_value().split(",").collect();
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
    context: &mut TransactionContext,
) -> Result<Option<Vec<u8>>, ApplyError> {
    context.get_state(vec![address.to_string()]).map_err(|err| {
        #[cfg(not(target_arch = "wasm32"))]
        warn!("Invalid transaction: Failed to load state: {:?}", err);
        ApplyError::InvalidTransaction(format!("Failed to load state: {:?}", err))
    })
}

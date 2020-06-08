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
         use protos::setting::{ Setting,
                        Setting_Entry};
     } else {
         use sawtooth_sdk::messages::processor::TpProcessRequest;
         use sawtooth_sdk::processor::handler::ApplyError;
         use sawtooth_sdk::processor::handler::TransactionContext;
         use sawtooth_sdk::processor::handler::TransactionHandler;
         use sawtooth_sdk::messages::setting::{ Setting,
                                                 Setting_Entry};
    }
}

extern crate base64;
use crypto::digest::Digest;
use crypto::sha2::Sha256;
use protobuf;
use protos::settings::{
    SettingCandidate, SettingCandidate_VoteRecord, SettingCandidates, SettingProposal, SettingVote,
    SettingVote_Vote, SettingsPayload, SettingsPayload_Action,
};
use std::iter::repeat;

#[cfg(target_arch = "wasm32")]
// Sabre apply must return a bool
fn apply(request: &TpProcessRequest, context: &mut TransactionContext) -> Result<bool, ApplyError> {
    let handler = SettingsTransactionHandler::new();
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

// The config namespace is special: it is not derived from a hash.
const SETTINGS_NAMESPACE: &str = "000000";

#[derive(Default)]
pub struct SettingsTransactionHandler {
    family_name: String,
    family_versions: Vec<String>,
    namespaces: Vec<String>,
}

impl SettingsTransactionHandler {
    pub fn new() -> SettingsTransactionHandler {
        SettingsTransactionHandler {
            family_name: "sawtooth_settings".to_string(),
            family_versions: vec!["1.0".to_string()],
            namespaces: vec![SETTINGS_NAMESPACE.to_string()],
        }
    }
}

impl TransactionHandler for SettingsTransactionHandler {
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
        let public_key = transaction.get_header().get_signer_public_key();
        let auth_keys = get_auth_keys(context)?;
        if !auth_keys.is_empty() && !auth_keys.contains(&public_key.to_string()) {
            return Err(ApplyError::InvalidTransaction(format!(
                "{:?} is not authorized to change settings",
                public_key
            )));
        }

        let settings_payload: SettingsPayload = unpack_data(transaction.get_payload())?;

        match settings_payload.get_action() {
            SettingsPayload_Action::PROPOSE => apply_proposal(
                &auth_keys,
                &public_key,
                settings_payload.get_data(),
                context,
            ),
            SettingsPayload_Action::VOTE => apply_vote(
                &auth_keys,
                &public_key,
                settings_payload.get_data(),
                context,
            ),
            SettingsPayload_Action::ACTION_UNSET => Err(ApplyError::InvalidTransaction(
                String::from("'action' must be one of {PROPOSE, VOTE} in 'Ballot' mode"),
            )),
        }
    }
}

fn apply_proposal(
    auth_keys: &[String],
    public_key: &str,
    setting_proposal_data: &[u8],
    context: &mut dyn TransactionContext,
) -> Result<(), ApplyError> {
    let setting_proposal: SettingProposal = unpack_data(setting_proposal_data)?;

    let proposal_id = proposal_to_hash(setting_proposal_data);

    let approval_threshold = get_approval_threshold(context)?;

    validate_setting(
        auth_keys,
        setting_proposal.get_setting(),
        setting_proposal.get_value(),
    )?;

    if approval_threshold > 1 {
        let mut setting_candidates = get_setting_candidates(context)?;
        for candidate in setting_candidates.get_candidates().iter() {
            if candidate.get_proposal_id() == proposal_id {
                return Err(ApplyError::InvalidTransaction(format!(
                    "Duplicate proposal for {:?}",
                    setting_proposal.get_setting()
                )));
            }
        }

        let mut vote_record = SettingCandidate_VoteRecord::new();
        vote_record.set_public_key(public_key.to_string());
        vote_record.set_vote(SettingVote_Vote::ACCEPT);

        let mut candidate = SettingCandidate::new();
        candidate.set_proposal_id(proposal_id);
        candidate.set_proposal(setting_proposal);
        candidate.set_votes(protobuf::RepeatedField::from_vec(vec![vote_record]));
        setting_candidates.mut_candidates().push(candidate);

        save_settings_candidates(context, &setting_candidates)
    } else {
        set_setting_value(
            context,
            setting_proposal.get_setting(),
            setting_proposal.get_value(),
        )
    }
}

fn apply_vote(
    auth_keys: &[String],
    public_key: &str,
    setting_vote_data: &[u8],
    context: &mut dyn TransactionContext,
) -> Result<(), ApplyError> {
    let setting_vote: SettingVote = unpack_data(setting_vote_data)?;
    let proposal_id = setting_vote.get_proposal_id();

    let mut setting_candidates = get_setting_candidates(context)?;

    let mut accepted_count = 0;
    let mut rejected_count = 0;
    let candidate_value;
    let candidate_setting;
    let candidate_index;

    {
        candidate_index = get_candidate_index(&mut setting_candidates, proposal_id)?;
        let candidate = setting_candidates
            .mut_candidates()
            .get_mut(candidate_index)
            .unwrap();

        for record in candidate.get_votes().iter() {
            if record.get_public_key() == public_key {
                return Err(ApplyError::InvalidTransaction(format!(
                    "{:?} already has voted",
                    public_key
                )));
            }
        }

        let mut vote_record = SettingCandidate_VoteRecord::new();
        vote_record.set_public_key(public_key.to_string());
        vote_record.set_vote(setting_vote.get_vote());
        candidate.mut_votes().push(vote_record);

        for record in candidate.get_votes().iter() {
            match record.get_vote() {
                SettingVote_Vote::ACCEPT => accepted_count += 1,
                SettingVote_Vote::REJECT => rejected_count += 1,
                _ => {
                    return Err(ApplyError::InvalidTransaction(String::from(
                        "Transaction type unset",
                    )));
                }
            }
        }

        candidate_value = candidate.get_proposal().get_value().to_string();
        candidate_setting = candidate.get_proposal().get_setting().to_string();
    }

    let approval_threshold = get_approval_threshold(context)?;
    if accepted_count >= approval_threshold {
        set_setting_value(context, &candidate_setting, &candidate_value)?;
        setting_candidates.mut_candidates().remove(candidate_index);
    } else if rejected_count >= approval_threshold
        || rejected_count + accepted_count == auth_keys.len() as i32
    {
        debug!("Proposal for {} was rejected", &candidate_setting);
        setting_candidates.mut_candidates().remove(candidate_index);
    } else {
        debug!("Vote recorded for {}", &candidate_setting);
    }
    save_settings_candidates(context, &setting_candidates)
}

fn unpack_data<T>(data: &[u8]) -> Result<T, ApplyError>
where
    T: protobuf::Message,
{
    protobuf::parse_from_bytes(&data).map_err(|err| {
        warn!(
            "Invalid error: Failed to unmarshal SettingsTransaction: {:?}",
            err
        );
        ApplyError::InternalError(format!(
            "Failed to unmarshal SettingsTransaction: {:?}",
            err
        ))
    })
}

fn get_candidate_index(
    setting_candidates: &mut SettingCandidates,
    proposal_id: &str,
) -> Result<usize, ApplyError> {
    for (i, setting_candidate) in setting_candidates.mut_candidates().iter_mut().enumerate() {
        if setting_candidate.get_proposal_id() == proposal_id {
            return Ok(i);
        }
    }
    Err(ApplyError::InvalidTransaction(format!(
        "Proposal {:?} does not exist",
        proposal_id
    )))
}

fn save_settings_candidates(
    context: &mut dyn TransactionContext,
    setting_candidates: &SettingCandidates,
) -> Result<(), ApplyError> {
    let data = protobuf::Message::write_to_bytes(setting_candidates).map_err(|err| {
        ApplyError::InternalError(format!("Failed to serialize SettingsCandidates: {:?}", err))
    })?;
    set_setting_value(
        context,
        "sawtooth.settings.vote.proposals",
        &base64::encode(&data),
    )
}

fn set_setting_value(
    context: &mut dyn TransactionContext,
    key: &str,
    value: &str,
) -> Result<(), ApplyError> {
    let address = make_settings_key(key);
    let setting_data = get_setting_data(&address, context)?;
    let mut setting = match setting_data {
        None => Setting::new(),
        Some(entries) => unpack_data(&entries)?,
    };

    let old_index = get_entry_index(&setting, key);

    match old_index {
        None => {
            let mut setting_entry = Setting_Entry::new();
            setting_entry.set_key(key.to_string());
            setting_entry.set_value(value.to_string());
            setting.mut_entries().push(setting_entry);
        }
        Some(i) => {
            setting.mut_entries()[i].set_value(value.to_string());
        }
    }

    set_state(context, key, value, &address, &setting)
}

fn set_state(
    context: &mut dyn TransactionContext,
    key: &str,
    value: &str,
    address: &str,
    setting: &Setting,
) -> Result<(), ApplyError> {
    let data = protobuf::Message::write_to_bytes(setting).map_err(|err| {
        ApplyError::InternalError(format!("Failed to serialize Setting: {:?}", err))
    })?;

    context
        .set_state_entry(address.to_string(), data)
        .map_err(|_| {
            warn!("Failed to save value on address {}", &address);
            ApplyError::InternalError(format!("Unable to save config value {}", key))
        })?;
    if key != "sawtooth.settings.vote.proposals" {
        info!("Setting {:?} changed to {:?}", key, value);
    }
    #[cfg(not(target_arch = "wasm32"))]
    context
        .add_event(
            "settings/update".to_string(),
            vec![("updated".to_string(), key.to_string())],
            &[],
        )
        .map_err(|_| {
            warn!("Failed to add event {}", key);
            ApplyError::InternalError(format!("Failed to add event {}", key))
        })?;
    Ok(())
}

fn get_entry_index(setting: &Setting, key: &str) -> Option<usize> {
    for (i, entry) in setting.get_entries().iter().enumerate() {
        if entry.get_key() == key {
            return Some(i);
        }
    }
    None
}

fn get_setting_candidates(
    context: &mut dyn TransactionContext,
) -> Result<SettingCandidates, ApplyError> {
    let value = get_setting_value(context, "sawtooth.settings.vote.proposals")?;
    match value {
        None => Ok(SettingCandidates::new()),
        Some(val) => {
            let v = base64::decode(&val).map_err(|err| {
                ApplyError::InternalError(format!(
                    "Cannot decode sawtooth.settings.vote.proposals: {:?} ",
                    err
                ))
            })?;
            unpack_data(&v)
        }
    }
}

fn validate_setting(auth_keys: &[String], setting: &str, value: &str) -> Result<(), ApplyError> {
    if auth_keys.is_empty() && setting != "sawtooth.settings.vote.authorized_keys" {
        return Err(ApplyError::InvalidTransaction(format!(
            "Cannot set {:?} until authorized_keys is set.",
            setting
        )));
    }
    if setting == "sawtooth.settings.vote.authorized_keys" && split_ignore_empties(value).is_empty()
    {
        return Err(ApplyError::InvalidTransaction(
            "authorized_keys must not be empty.".into(),
        ));
    }
    if setting == "sawtooth.settings.vote.approval_threshold" {
        let threshold = value.parse::<i32>().map_err(|_| {
            warn!("Failed to parse sawtooth.settings.vote.approval_threshold value");
            ApplyError::InvalidTransaction("approval_threshold must be an integer".into())
        })?;
        if threshold > auth_keys.len() as i32 {
            return Err(ApplyError::InvalidTransaction(
                "approval_threshold must be less than or equal to number of authorized_keys".into(),
            ));
        }
    }
    if setting == "sawtooth.settings.vote.proposals" {
        return Err(ApplyError::InvalidTransaction(
            "Setting sawtooth.settings.vote.proposals is read-only".into(),
        ));
    }
    Ok(())
}

fn get_auth_keys(context: &mut dyn TransactionContext) -> Result<Vec<String>, ApplyError> {
    let auth_keys = get_setting_value(context, "sawtooth.settings.vote.authorized_keys")?;
    match auth_keys {
        None => Ok(vec![]),
        Some(value) => Ok(split_ignore_empties(&value)),
    }
}
fn split_ignore_empties(values: &str) -> Vec<String> {
    values
        .split(',')
        .map(|v| v.trim().to_string())
        .filter(|v| !v.is_empty())
        .collect()
}

fn proposal_to_hash(value: &[u8]) -> String {
    let mut sha = Sha256::new();
    sha.input(value);
    sha.result_str()
}

fn get_approval_threshold(context: &mut dyn TransactionContext) -> Result<i32, ApplyError> {
    let settings_value = get_setting_value(context, "sawtooth.settings.vote.approval_threshold")?;
    match settings_value {
        None => Ok(1), //1 is the default_value for approval_threshold
        Some(value) => {
            let val = value.parse::<i32>().map_err(|err| {
                warn!("Failed to parse sawtooth.settings.vote.approval_threshold value");
                ApplyError::InternalError(format!("Failed to parse
                                              sawtooth.settings.vote.approval_threshold value: {:?}", err))
            })?;
            Ok(val)
        }
    }
}

fn get_setting_value(
    context: &mut dyn TransactionContext,
    key: &str,
) -> Result<Option<String>, ApplyError> {
    let address = make_settings_key(key);
    let setting_data = get_setting_data(&address, context)?;

    match setting_data {
        None => Ok(None),
        Some(entries) => {
            let setting: Setting = unpack_data(&entries)?;
            for entry in setting.get_entries().iter() {
                if entry.get_key() == key {
                    return Ok(Some(entry.get_value().to_string()));
                }
            }
            Ok(None)
        }
    }
}

fn get_setting_data(
    address: &str,
    context: &mut dyn TransactionContext,
) -> Result<Option<Vec<u8>>, ApplyError> {
    context.get_state_entry(address).map_err(|err| {
        warn!("Internal Error: Failed to load state: {:?}", err);
        ApplyError::InternalError(format!("Failed to load state: {:?}", err))
    })
}

const MAX_KEY_PARTS: usize = 4;
const ADDRESS_PART_SIZE: usize = 16;

fn make_settings_key(key: &str) -> String {
    let mut address = String::new();
    address.push_str(SETTINGS_NAMESPACE);
    address.push_str(
        &key.splitn(MAX_KEY_PARTS, '.')
            .chain(repeat(""))
            .map(short_hash)
            .take(MAX_KEY_PARTS)
            .collect::<Vec<_>>()
            .join(""),
    );

    address
}

fn short_hash(s: &str) -> String {
    let mut sha = Sha256::new();
    sha.input(s.as_bytes());
    sha.result_str()[..ADDRESS_PART_SIZE].to_string()
}

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

use std::fs::{File, OpenOptions};
use std::io::{Read, Write};
use std::os::unix::fs::OpenOptionsExt;
use std::path::Path;

use clap::ArgMatches;
use protobuf;
use protobuf::Message;

use proto::batch::{Batch, BatchList};
use proto::genesis::GenesisData;
use proto::settings::{SettingProposal, SettingsPayload, SettingsPayload_Action};
use proto::transaction::TransactionHeader;

use config;
use err::CliError;

pub fn run<'a>(args: &ArgMatches<'a>) -> Result<(), CliError> {
    let genesis_file_path = if args.is_present("output") {
        args.value_of("output")
            .ok_or_else(|| CliError::ArgumentError("Failed to read `output` arg".into()))
            .map(|pathstr| Path::new(pathstr).to_path_buf())
    } else {
        Ok(config::get_path_config().data_dir.join("genesis.batch"))
    }?;

    if genesis_file_path.exists() {
        return Err(CliError::EnvironmentError(format!(
            "File already exists: {:?}",
            genesis_file_path
        )));
    }

    let input_files = args
        .values_of("input_file")
        .ok_or_else(|| CliError::ArgumentError("No input files passed".into()))?;

    let batch_lists = input_files
        .map(|filepath| {
            let mut file = File::open(filepath).map_err(|err| {
                CliError::EnvironmentError(format!("Failed to open file: {}", err))
            })?;
            let mut packed = Vec::new();
            file.read_to_end(&mut packed).map_err(|err| {
                CliError::EnvironmentError(format!("Failed to read file: {}", err))
            })?;
            let batch_list: BatchList = protobuf::parse_from_bytes(&packed).map_err(|err| {
                CliError::ArgumentError(format!("Unable to read {}: {}", filepath, err))
            })?;
            Ok(batch_list)
        })
        .collect::<Result<Vec<BatchList>, CliError>>()?;

    let batches = batch_lists
        .into_iter()
        .fold(Vec::new(), |mut batches, batch_list| {
            batches.extend(batch_list.batches.into_iter());
            batches
        });

    validate_depedencies(&batches)?;
    if !args.is_present("ignore_required_settings") {
        check_required_settings(&batches)?;
    }

    let mut genesis_data = GenesisData::new();
    genesis_data.set_batches(protobuf::RepeatedField::from_vec(batches));

    let buf = genesis_data.write_to_bytes().map_err(|err| {
        CliError::ArgumentError(format!(
            "Failed to convert BatchLists to GenesisData: {}",
            err
        ))
    })?;

    let mut genesis_data_file = OpenOptions::new()
        .write(true)
        .create(true)
        .mode(0o640)
        .open(genesis_file_path.as_path())
        .map_err(|err| CliError::EnvironmentError(format!("{}", err)))?;

    genesis_data_file
        .write(&buf)
        .map_err(|err| CliError::EnvironmentError(format!("{}", err)))?;

    Ok(())
}

fn validate_depedencies(batches: &[Batch]) -> Result<(), CliError> {
    let mut txn_ids: Vec<String> = Vec::new();
    for batch in batches.iter() {
        for txn in batch.transactions.iter() {
            let header: TransactionHeader =
                protobuf::parse_from_bytes(&txn.header).map_err(|err| {
                    CliError::ArgumentError(format!(
                        "Invalid transaction header for txn {}: {}",
                        &txn.header_signature, err
                    ))
                })?;
            for dep in header.dependencies.iter() {
                if !txn_ids.contains(dep) {
                    return Err(CliError::ArgumentError(format!(
                        "Unsatisfied dependency in given transaction {}: {}",
                        &txn.header_signature, dep
                    )));
                }
                txn_ids.push(dep.clone())
            }
        }
    }
    Ok(())
}

fn check_required_settings(batches: &[Batch]) -> Result<(), CliError> {
    let mut required_settings = vec![
        "sawtooth.consensus.algorithm.name",
        "sawtooth.consensus.algorithm.version",
    ];

    for batch in batches.iter() {
        for txn in batch.transactions.iter() {
            let txn_header: TransactionHeader =
                protobuf::parse_from_bytes(&txn.header).map_err(|err| {
                    CliError::ArgumentError(format!(
                        "Invalid transaction header for txn {}: {}",
                        &txn.header_signature, err
                    ))
                })?;
            if txn_header.family_name == "sawtooth_settings" {
                let settings_payload: SettingsPayload = protobuf::parse_from_bytes(&txn.payload)
                    .map_err(|err| {
                        CliError::ArgumentError(format!(
                            "Invalid payload for settings txn {}: {}",
                            &txn.header_signature, err
                        ))
                    })?;
                if let SettingsPayload_Action::PROPOSE = settings_payload.action {
                    let proposal: SettingProposal =
                        protobuf::parse_from_bytes(&settings_payload.data).map_err(|err| {
                            CliError::ArgumentError(format!(
                                "Invalid proposal for settings payload: {}",
                                err
                            ))
                        })?;
                    required_settings.retain(|setting| setting != &proposal.setting);
                }
            }
        }
    }

    if !required_settings.is_empty() {
        Err(CliError::ArgumentError(format!(
            "The following setting(s) are required at genesis, but were not included in the \
             genesis batches: {:?}",
            required_settings
        )))
    } else {
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    use protobuf::RepeatedField;

    use proto::batch::BatchHeader;
    use proto::transaction::Transaction;

    fn get_required_settings_batch() -> Batch {
        let required_settings = vec![
            "sawtooth.consensus.algorithm.name".into(),
            "sawtooth.consensus.algorithm.version".into(),
        ];

        let (txn_ids, txns) = required_settings
            .iter()
            .enumerate()
            .map(|(idx, setting): (_, &String)| {
                let txn_id = format!("setting{}", idx);

                let mut proposal = SettingProposal::new();
                proposal.set_setting(setting.clone());
                let proposal_bytes = proposal
                    .write_to_bytes()
                    .expect("Failed to serialize proposal");

                let mut payload = SettingsPayload::new();
                payload.set_action(SettingsPayload_Action::PROPOSE);
                payload.set_data(proposal_bytes);
                let payload_bytes = payload
                    .write_to_bytes()
                    .expect("Failed to serialize payload");

                let mut header = TransactionHeader::new();
                header.set_family_name("sawtooth_settings".into());
                header.set_family_version("1.0".into());
                let header_bytes = header.write_to_bytes().expect("Failed to serialize header");

                let mut txn = Transaction::new();
                txn.set_header(header_bytes);
                txn.set_header_signature(txn_id.clone());
                txn.set_payload(payload_bytes);

                (txn_id, txn)
            })
            .unzip();

        let mut batch_header = BatchHeader::new();
        batch_header.set_transaction_ids(RepeatedField::from_vec(txn_ids));
        let batch_header_bytes = batch_header
            .write_to_bytes()
            .expect("Failed to serialize batch_header");

        let mut batch = Batch::new();
        batch.set_header(batch_header_bytes);
        batch.set_transactions(RepeatedField::from_vec(txns));

        batch
    }

    #[test]
    fn test_check_required_settings() {
        assert!(check_required_settings(&[get_required_settings_batch()]).is_ok());
        assert!(check_required_settings(&[]).is_err());
    }
}

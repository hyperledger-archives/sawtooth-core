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

use sawtooth_sdk::messages::batch::{Batch, BatchList};
use sawtooth_sdk::messages::genesis::GenesisData;
use sawtooth_sdk::messages::transaction::TransactionHeader;

use config;
use err::CliError;

pub fn run<'a>(args: &ArgMatches<'a>) -> Result<(), CliError> {
    let genesis_file_path = if args.is_present("output") {
        args.value_of("output")
            .ok_or_else(|| CliError::ArgumentError(format!("Failed to read `output` arg")))
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
        }).collect::<Result<Vec<BatchList>, CliError>>()?;

    let batches = batch_lists
        .into_iter()
        .fold(Vec::new(), |mut batches, batch_list| {
            batches.extend(batch_list.batches.into_iter());
            batches
        });

    validate_depedencies(&batches)?;

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

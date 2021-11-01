// Copyright 2020 Bitwise IO
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

use clap::ArgMatches;
use sawtooth::client::{
    rest::{RestApiSawtoothClient, RestApiSawtoothClientBuilder},
    Batch, Header, InvalidTransaction, SawtoothClient, SawtoothClientError as ClientError, Status,
    Transaction, TransactionHeader,
};
use serde::Serialize;
use std::time::Duration;

use crate::err::CliError;

pub fn run(args: &ArgMatches) -> Result<(), CliError> {
    match args.subcommand() {
        ("list", Some(args)) => run_list(args),
        ("show", Some(args)) => run_show(args),
        ("status", Some(args)) => run_status(args),
        _ => {
            println!("Invalid subcommand; Pass --help for usage.");
            Ok(())
        }
    }
}

fn create_client(args: &ArgMatches) -> Result<RestApiSawtoothClient, CliError> {
    let mut url = args
        .value_of("url")
        .unwrap_or("http://localhost:8008")
        .to_string();
    if !url.contains("http://") {
        url = format!("http://{}", url);
    }

    let mut client_builder = RestApiSawtoothClientBuilder::new().with_url(&url);

    if let Some(auth) = args.value_of("username") {
        let credentials = get_credentials(auth)?;
        client_builder = client_builder.with_basic_auth(credentials[0], credentials[1]);
    }

    let client = client_builder
        .build()
        .map_err(|err| CliError::EnvironmentError(format!("Failed to create client: {}", err)))?;

    Ok(client)
}

fn run_list(args: &ArgMatches) -> Result<(), CliError> {
    let client = create_client(args)?;

    let batches = client.list_batches().map_err(|err| {
        CliError::EnvironmentError(format!("Failed to retrieve batch list, {}", err))
    })?;

    let format = args.value_of("format").unwrap_or("default");

    if format == "csv" {
        let data = parse_batches_into_rows(batches)?;
        for row in data {
            println!("{}", row.join(","))
        }
    } else if format == "json" || format == "yaml" {
        let structured_output_batches = batches
            .map(|item: Result<Batch, _>| item.map(|batch| DisplayBatchListItem::from(&batch)))
            .collect::<Result<Vec<DisplayBatchListItem>, ClientError>>()
            .map_err(|err| {
                CliError::EnvironmentError(format!(
                    "Failed to convert sawtooth::client::Batch to DisplayBatchListItem: {}",
                    err
                ))
            })?;
        if format == "json" {
            println!(
                "{}",
                serde_json::to_string_pretty(&structured_output_batches).map_err(|err| {
                    CliError::EnvironmentError(format!("Cannot format batches into json: {}", err))
                })?
            );
        } else {
            println!(
                "{}",
                serde_yaml::to_string(&structured_output_batches).map_err(|err| {
                    CliError::EnvironmentError(format!("Cannot format batches into yaml: {}", err))
                })?
            );
        }
    } else {
        let data = parse_batches_into_rows(batches)?;
        print_table(data);
    }
    Ok(())
}

fn run_show(args: &ArgMatches) -> Result<(), CliError> {
    let client = create_client(args)?;
    let format = args.value_of("format").unwrap_or("default");
    let key = args.value_of("key");
    let batch_id = args.value_of("batch_id").unwrap().to_string();

    let batch = client
        .get_batch(batch_id)
        .map_err(|err| CliError::EnvironmentError(format!("Failed to get batch: {}", err)))?;

    match batch {
        Some(b) => {
            let display_batch = DisplayBatch::from(&b);
            match format {
                "json" => {
                    let output = match key {
                        Some(k) => single_property_json(k, &display_batch),
                        None => serde_json::to_string_pretty(&display_batch),
                    };
                    println!(
                        "{}",
                        output.map_err(|err| {
                            CliError::EnvironmentError(format!("Cannot format into json: {}", err))
                        })?
                    )
                }
                _ => {
                    let output = match key {
                        Some(k) => single_property_yaml(k, &display_batch),
                        None => serde_yaml::to_string(&display_batch),
                    };
                    println!(
                        "{}",
                        output.map_err(|err| {
                            CliError::EnvironmentError(format!(
                                "Cannot format into yaml (default): {}",
                                err
                            ))
                        })?
                    )
                }
            }
            Ok(())
        }
        None => Err(CliError::EnvironmentError(format!(
            "No batch exists with batch id provided"
        ))),
    }
}

fn run_status(args: &ArgMatches) -> Result<(), CliError> {
    let client = create_client(args)?;
    let format = args.value_of("format").unwrap_or("default");
    let batch_id_args = args.value_of("batch_ids").unwrap().to_string();
    let batch_ids = batch_id_args.split(",").collect::<Vec<&str>>();
    let wait: Option<Duration> = match args.value_of("wait") {
        Some(w) => Some(Duration::from_secs(w.parse::<u64>().map_err(|err| {
            CliError::EnvironmentError(format!("Failed to parse wait: {}", err))
        })?)),
        None => None,
    };

    let statuses = client
        .list_batch_status(batch_ids, wait)
        .map_err(|err| CliError::EnvironmentError(format!("Failed to get batch status: {}", err)))
        .unwrap()
        .unwrap()
        .iter()
        .map(|x| DisplayStatus::from(x))
        .collect::<Vec<DisplayStatus>>();

    match format {
        "json" => println!(
            "{}",
            serde_json::to_string_pretty(&statuses).map_err(|err| {
                CliError::EnvironmentError(format!("Cannot format statuses into json: {}", err))
            })?
        ),
        _ => println!(
            "{}",
            serde_yaml::to_string(&statuses).map_err(|err| {
                CliError::EnvironmentError(format!("Cannot format statuses into yaml: {}", err))
            })?
        ),
    }

    Ok(())
}

/// Parse batches into rows containing batch id, number of transactions, and signer pulic key
fn parse_batches_into_rows(
    batches: Box<dyn Iterator<Item = Result<Batch, ClientError>>>,
) -> Result<Vec<Vec<String>>, CliError> {
    let mut data = Vec::new();
    data.push(vec![
        "BATCH_ID".to_string(),
        "TXNS".to_string(),
        "SIGNER".to_string(),
    ]);

    for batch in batches {
        let batch =
            batch.map_err(|err| CliError::ParseError(format!("Failed to get batch: {}", err)))?;
        data.push(vec![
            batch.header_signature.to_string(),
            batch.transactions.len().to_string(),
            batch.header.signer_public_key.to_string(),
        ]);
    }
    Ok(data)
}

/// Attempt to parse the given credentials formatted as "username:password"
fn get_credentials(auth: &str) -> Result<Vec<&str>, CliError> {
    match auth.splitn(2, ':').collect::<Vec<&str>>() {
        credentials if credentials.len() == 2 => Ok(credentials),
        _ => Err(CliError::ArgumentError(
            "Username and password formatted incorrectly".to_string(),
        )),
    }
}

fn print_table(table: Vec<Vec<String>>) {
    let mut max_lengths = Vec::new();

    // find the max lengths of the columns
    for row in table.iter() {
        for (i, col) in row.iter().enumerate() {
            if let Some(length) = max_lengths.get_mut(i) {
                if col.len() > *length {
                    *length = col.len()
                }
            } else {
                max_lengths.push(col.len())
            }
        }
    }

    // print each row with correct column size
    for row in table.iter() {
        let mut col_string = String::from("");
        for (i, len) in max_lengths.iter().enumerate() {
            if let Some(value) = row.get(i) {
                col_string += &format!("{}{} ", value, " ".repeat(*len - value.len()),);
            } else {
                col_string += &" ".repeat(*len);
            }
        }
        println!("{}", col_string);
    }
}

fn single_property_json(
    key: &str,
    display_batch: &DisplayBatch,
) -> Result<String, serde_json::Error> {
    match key {
        "header" => serde_json::to_string_pretty(&display_batch.header),
        "header_signature" => serde_json::to_string_pretty(&display_batch.header_signature),
        "trace" => serde_json::to_string_pretty(&display_batch.trace),
        "transactions" => serde_json::to_string_pretty(&display_batch.transactions),
        "signer_public_key" => {
            serde_json::to_string_pretty(&display_batch.header.signer_public_key)
        }
        "transaction_ids" => serde_json::to_string_pretty(&display_batch.header.transaction_ids),
        _ => serde_json::to_string_pretty(&display_batch),
    }
}

fn single_property_yaml(
    key: &str,
    display_batch: &DisplayBatch,
) -> Result<String, serde_yaml::Error> {
    match key {
        "header" => serde_yaml::to_string(&display_batch.header),
        "header_signature" => serde_yaml::to_string(&display_batch.header_signature),
        "trace" => serde_yaml::to_string(&display_batch.trace),
        "transactions" => serde_yaml::to_string(&display_batch.transactions),
        "signer_public_key" => serde_yaml::to_string(&display_batch.header.signer_public_key),
        "transaction_ids" => serde_yaml::to_string(&display_batch.header.transaction_ids),
        _ => serde_yaml::to_string(&display_batch),
    }
}

#[derive(Debug, Serialize)]
struct DisplayBatchListItem {
    batch_id: String,
    signer: String,
    txns: usize,
}
impl From<&Batch> for DisplayBatchListItem {
    fn from(batch: &Batch) -> Self {
        DisplayBatchListItem {
            batch_id: batch.header_signature.to_string(),
            signer: batch.header.signer_public_key.to_string(),
            txns: batch.transactions.len(),
        }
    }
}

#[derive(Debug, Serialize)]
struct DisplayBatch {
    header: DisplayHeader,
    header_signature: String,
    trace: bool,
    transactions: Vec<DisplayTransaction>,
}
impl From<&Batch> for DisplayBatch {
    fn from(batch: &Batch) -> Self {
        DisplayBatch {
            header: DisplayHeader::from(&batch.header),
            header_signature: batch.header_signature.clone(),
            trace: batch.trace,
            transactions: batch
                .transactions
                .iter()
                .map(|x| DisplayTransaction::from(x))
                .collect(),
        }
    }
}

#[derive(Debug, Serialize)]
struct DisplayHeader {
    signer_public_key: String,
    transaction_ids: Vec<String>,
}
impl From<&Header> for DisplayHeader {
    fn from(header: &Header) -> Self {
        DisplayHeader {
            signer_public_key: header.signer_public_key.clone(),
            transaction_ids: header.transaction_ids.clone(),
        }
    }
}

#[derive(Debug, Serialize)]
struct DisplayTransaction {
    header: DisplayTransactionHeader,
    header_signature: String,
    payload: String,
}
impl From<&Transaction> for DisplayTransaction {
    fn from(transaction: &Transaction) -> Self {
        DisplayTransaction {
            header: DisplayTransactionHeader::from(&transaction.header),
            header_signature: transaction.header_signature.clone(),
            payload: transaction.payload.clone(),
        }
    }
}

#[derive(Debug, Serialize)]
struct DisplayTransactionHeader {
    batcher_public_key: String,
    dependencies: Vec<String>,
    family_name: String,
    family_version: String,
    inputs: Vec<String>,
    nonce: String,
    outputs: Vec<String>,
    payload_sha512: String,
    signer_public_key: String,
}
impl From<&TransactionHeader> for DisplayTransactionHeader {
    fn from(transaction_header: &TransactionHeader) -> Self {
        DisplayTransactionHeader {
            batcher_public_key: transaction_header.batcher_public_key.clone(),
            dependencies: transaction_header.dependencies.clone(),
            family_name: transaction_header.family_name.clone(),
            family_version: transaction_header.family_version.clone(),
            inputs: transaction_header.inputs.clone(),
            nonce: transaction_header.nonce.clone(),
            outputs: transaction_header.outputs.clone(),
            payload_sha512: transaction_header.payload_sha512.clone(),
            signer_public_key: transaction_header.signer_public_key.clone(),
        }
    }
}

#[derive(Debug, Serialize)]
struct DisplayStatus {
    id: String,
    invalid_transactions: Vec<DisplayInvalidTransaction>,
    status: String,
}
impl From<&Status> for DisplayStatus {
    fn from(status: &Status) -> Self {
        DisplayStatus {
            id: status.id.clone(),
            invalid_transactions: status
                .invalid_transactions
                .iter()
                .map(|x| DisplayInvalidTransaction::from(x))
                .collect(),
            status: status.status.clone(),
        }
    }
}

#[derive(Debug, Serialize)]
struct DisplayInvalidTransaction {
    id: String,
    message: String,
    extended_data: Vec<u8>,
}
impl From<&InvalidTransaction> for DisplayInvalidTransaction {
    fn from(invalid_transaction: &InvalidTransaction) -> Self {
        DisplayInvalidTransaction {
            id: invalid_transaction.id.clone(),
            message: invalid_transaction.message.clone(),
            extended_data: invalid_transaction.extended_data.clone(),
        }
    }
}

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
    rest::RestApiSawtoothClientBuilder, Batch, SawtoothClient, SawtoothClientError as ClientError,
    SawtoothClientError,
};
use serde::Serialize;

use crate::err::CliError;

pub fn run<'a>(args: &ArgMatches<'a>) -> Result<(), CliError> {
    match args.subcommand() {
        ("list", Some(args)) => run_list_command(args),
        _ => {
            println!("Invalid subcommand; Pass --help for usage.");
            Ok(())
        }
    }
}

fn run_list_command<'a>(args: &ArgMatches<'a>) -> Result<(), CliError> {
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
            .map(|item: Result<Batch, _>| item.map(|batch| StructuredOutputBatch::from(&batch)))
            .collect::<Result<Vec<StructuredOutputBatch>, SawtoothClientError>>()
            .map_err(|err| {
                CliError::EnvironmentError(format!(
                    "Failed to convert sawtooth::client::Batch to StructuredOutputBatch: {}",
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

#[derive(Debug, Serialize)]
struct StructuredOutputBatch {
    batch_id: String,
    signer: String,
    txns: usize,
}

impl<'a> From<&'a Batch> for StructuredOutputBatch {
    fn from(batch: &Batch) -> Self {
        StructuredOutputBatch {
            batch_id: batch.header_signature.to_string(),
            signer: batch.header.signer_public_key.to_string(),
            txns: batch.transactions.len(),
        }
    }
}

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

use std::io::{self, Write};
use std::fs::File;
use std::io::prelude::*;

use clap::ArgMatches;
use protobuf;
use protobuf::Message;
use serde_yaml;

use sawtooth_sdk::messages::block::{Block, BlockHeader};

use blockstore::Blockstore;
use database::lmdb;
use database::database::DatabaseError;
use err::{CliError};
use config;
use wrappers::Block as BlockWrapper;

pub fn run<'a>(args: &ArgMatches<'a>) -> Result<(), CliError> {
    match args.subcommand() {
        ("list", Some(args)) => run_list_command(args),
        ("show", Some(args)) => run_show_command(args),
        ("prune", Some(args)) => run_prune_command(args),
        ("export", Some(args)) => run_export_command(args),
        ("import", Some(args)) => run_import_command(args),
        _ => { println!("Invalid subcommand; Pass --help for usage."); Ok(()) },
    }
}

fn run_list_command<'a>(args: &ArgMatches<'a>) -> Result<(), CliError> {
    let ctx = create_context()?;
    let blockstore = open_blockstore(&ctx)?;

    let mut count = u64::from_str_radix(args.value_of("count").unwrap_or("100"), 10).unwrap();

    // Get the chain head
    let head_sig = match args.value_of("start") {
        None => blockstore.get_chain_head().map_err(|err|
            CliError::EnvironmentError(format!("{}", err))),
        Some(sig) => Ok(sig.into()),
    }?;

    // Walk back from the chain head
    let mut block_id = head_sig;
    print_block_store_list_header();

    while block_id != "0000000000000000" && count > 0 {
        let block = blockstore.get(&block_id).map_err(|err|
            CliError::EnvironmentError(format!("{}", err)))?;
        let block_header: BlockHeader = protobuf::parse_from_bytes(&block.header)
            .map_err(|err| CliError::ParseError(format!("{}", err)))?;
        let batches = block.batches.len();
        let txns = block.batches.iter().fold(0, |acc, batch| acc + batch.transactions.len());
        print_block_store_list_row(
            block_header.block_num,
            &block.header_signature,
            batches, txns,
            &block_header.signer_public_key);
        block_id = block_header.previous_block_id;
        count -= 1;
    }
    Ok(())
}

fn print_block_store_list_header() {
    println!(
        "{:<5} {:<128} {:<5} {:<5} {}",
        "NUM", "BLOCK_ID", "BATS", "TXNS", "SIGNER");
}

fn print_block_store_list_row(block_num: u64, block_id: &str, batches: usize, txns: usize, signer: &str) {
    println!(
        "{:<5} {:<128} {:<5} {:<5} {}...",
        block_num, block_id, batches, txns, &signer[..6]);
}

fn run_show_command<'a>(args: &ArgMatches<'a>) -> Result<(), CliError> {
    let ctx = create_context()?;
    let blockstore = open_blockstore(&ctx)?;

    let block_id = args.value_of("block").ok_or(CliError::ArgumentError("No block id".into()))?;

    let block = blockstore.get(block_id).map_err(|_|
        CliError::ArgumentError(format!("Block not found: {}", block_id)))?;

    let block_wrapper = BlockWrapper::try_from(block).map_err(|err|
        CliError::EnvironmentError(format!("{}", err)))?;

    let block_yaml = serde_yaml::to_string(&block_wrapper).map_err(|err|
        CliError::EnvironmentError(format!("{}", err)))?;

    println!("{}", block_yaml);
    Ok(())
}

fn run_prune_command<'a>(args: &ArgMatches<'a>) -> Result<(), CliError> {
    let ctx = create_context()?;
    let blockstore = open_blockstore(&ctx)?;

    let block_id = args.value_of("block").ok_or(CliError::ArgumentError("No block id".into()))?;

    blockstore.get(block_id).map_err(|_|
        CliError::ArgumentError(format!("Block not found: {}", block_id)))?;

    // Get the chain head
    let chain_head = blockstore.get_chain_head()
        .map_err(|err| CliError::EnvironmentError(format!("{}", err)))?;

    let mut current = blockstore.get(&chain_head)
        .map_err(|err| CliError::EnvironmentError(format!("{}", err)))?;

    loop {
        blockstore.delete(&current.header_signature)
            .map_err(|err| CliError::EnvironmentError(format!("{}", err)))?;
        if current.header_signature == block_id {
            break;
        }
        let header: BlockHeader = protobuf::parse_from_bytes(&current.header)
            .map_err(|err| CliError::ParseError(format!("{}", err)))?;

        current = blockstore.get(&header.previous_block_id)
            .map_err(|err| CliError::EnvironmentError(format!("{}", err)))?;
    }
    Ok(())
}

fn run_export_command<'a>(args: &ArgMatches<'a>) -> Result<(), CliError> {
    let ctx = create_context()?;
    let blockstore = open_blockstore(&ctx)?;

    let block_id = args.value_of("block").ok_or(CliError::ArgumentError("No block id".into()))?;

    let block = blockstore.get(block_id).map_err(|_|
        CliError::ArgumentError(format!("Block not found: {}", block_id)))?;

    let packed = block.write_to_bytes().map_err(|err|
        CliError::EnvironmentError(format!("{}", err)))?;

    let stdout = io::stdout();
    let mut handle = stdout.lock();
    handle.write(&packed)
        .map(|_| ())
        .map_err(|err| CliError::EnvironmentError(format!("{}", err)))
}

fn run_import_command<'a>(args: &ArgMatches<'a>) -> Result<(), CliError> {
    let ctx = create_context()?;
    let blockstore = open_blockstore(&ctx)?;

    let filepath = args.value_of("blockfile").ok_or(CliError::ArgumentError("No file".into()))?;
    let mut file = File::open(filepath).map_err(|err|
        CliError::EnvironmentError(format!("Failed to open file: {}", err)))?;
    let mut packed = Vec::new();
    file.read_to_end(&mut packed).map_err(|err|
        CliError::EnvironmentError(format!("Failed to read file: {}", err)))?;

    let block: Block = protobuf::parse_from_bytes(&packed)
        .map_err(|err| CliError::ParseError(format!("{}", err)))?;
    let block_header: BlockHeader = protobuf::parse_from_bytes(&block.header)
        .map_err(|err| CliError::ParseError(format!("{}", err)))?;
    let block_id = block.header_signature.clone();

    // Ensure this block is an immediate child of the current chain head
    match blockstore.get_chain_head() {
        Ok(chain_head) => {
            if block_header.previous_block_id != chain_head {
                return Err(CliError::ArgumentError(format!(
                    "New block must be an immediate child of the current chain head: {}",
                    chain_head)))
            }
        },
        Err(DatabaseError::NotFoundError(_)) => (),
        Err(err) => {
            return Err(CliError::EnvironmentError(format!("{}", err)));
        },
    }

    blockstore.put(block).map_err(|err|
        CliError::ArgumentError(format!("Failed to put block into database: {}", err)))?;

    println!("Block {} added", block_id);
    Ok(())
}

fn create_context() -> Result<lmdb::LmdbContext, CliError> {
    let path_config = config::get_path_config();
    let blockstore_path = &path_config.data_dir.join(config::get_blockstore_filename());

    lmdb::LmdbContext::new(blockstore_path, 3, None)
        .map_err(|err| CliError::EnvironmentError(format!("{}", err)))
}

fn open_blockstore<'a>(ctx: &'a lmdb::LmdbContext) -> Result<Blockstore<'a>, CliError> {
    let blockstore_db = lmdb::LmdbDatabase::new(ctx, &["index_batch", "index_transaction", "index_block_num"])
        .map_err(|err| CliError::EnvironmentError(format!("{}", err)))?;

    Ok(Blockstore::new(blockstore_db))
}

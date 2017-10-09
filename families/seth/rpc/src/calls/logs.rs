/*
 * Copyright 2017 Intel Corporation
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

use std::collections::HashMap;

use jsonrpc_core::{Params, Value, Error};
use serde_json::Map;
use protobuf;

use client::{
    ValidatorClient,
    Error as ClientError,
    BlockKey,
};
use requests::{RequestHandler};
use transform;

use sawtooth_sdk::messaging::stream::MessageSender;

use sawtooth_sdk::messages::block::{Block, BlockHeader};
use sawtooth_sdk::messages::transaction::TransactionHeader;
use error;
use filters::*;
use transactions::{SethLog};

pub fn get_method_list<T>() -> Vec<(String, RequestHandler<T>)> where T: MessageSender {
    let mut methods: Vec<(String, RequestHandler<T>)> = Vec::new();

    methods.push((String::from("eth_newFilter"), new_filter));
    methods.push((String::from("eth_newBlockFilter"), new_block_filter));
    methods.push((String::from("eth_newPendingTransactionFilter"), new_pending_transaction_filter));
    methods.push((String::from("eth_uninstallFilter"), uninstall_filter));
    methods.push((String::from("eth_getFilterChanges"), get_filter_changes));
    methods.push((String::from("eth_getFilterLogs"), get_filter_logs));
    methods.push((String::from("eth_getLogs"), get_logs));

    methods
}

pub fn new_filter<T>(params: Params, mut client: ValidatorClient<T>)
    -> Result<Value, Error> where T: MessageSender
{
    info!("eth_newFilter");
    let (filter,): (Map<String, Value>,) = params.parse().map_err(|_|
        Error::invalid_params("Takes [filter: OBJECT]"))?;
    let log_filter = LogFilter::from_map(filter)?;

    let current_block = client.get_current_block_number().map_err(|error| {
        error!("Failed to get current block number: {}", error);
        Error::internal_error()
    })?;

    let filter_id = client.filters.new_filter(Filter::Log(log_filter), current_block);

    Ok(transform::hex_prefix(&filter_id_to_hex(filter_id)))
}

pub fn new_block_filter<T>(_params: Params, mut client: ValidatorClient<T>)
    -> Result<Value, Error> where T: MessageSender
{
    info!("eth_newBlockFilter");
    let current_block = client.get_current_block_number().map_err(|error| {
        error!("Failed to get current block number: {}", error);
        Error::internal_error()
    })?;
    let filter_id = client.filters.new_filter(Filter::Block, current_block);
    Ok(transform::hex_prefix(&filter_id_to_hex(filter_id)))
}

pub fn new_pending_transaction_filter<T>(_params: Params, mut client: ValidatorClient<T>)
    -> Result<Value, Error> where T: MessageSender
{
    info!("eth_newPendingTransactionFilter");
    let current_block = client.get_current_block_number().map_err(|error| {
        error!("Failed to get current block number: {}", error);
        Error::internal_error()
    })?;
    let filter_id = client.filters.new_filter(Filter::Transaction, current_block);
    Ok(transform::hex_prefix(&filter_id_to_hex(filter_id)))
}

pub fn uninstall_filter<T>(params: Params, mut client: ValidatorClient<T>)
    -> Result<Value, Error> where T: MessageSender
{
    info!("eth_uninstallFilter");
    let filter_id = params.parse()
        .and_then(|(v,): (Value,)| transform::string_from_hex_value(&v))
        .and_then(|s| filter_id_from_hex(&s).map_err(|error|
            Error::invalid_params(format!("{}", error))))?;

    Ok(Value::Bool(client.filters.remove_filter(&filter_id).is_some()))
}

pub fn get_filter_changes<T>(params: Params, mut client: ValidatorClient<T>)
    -> Result<Value, Error> where T: MessageSender
{
    info!("eth_getFilterChanges");
    let filter_id = params.parse()
        .and_then(|(v,): (Value,)| transform::string_from_hex_value(&v))
        .and_then(|s| filter_id_from_hex(&s).map_err(|error|
            Error::invalid_params(format!("{}", error))))?;

    let FilterEntry{filter, last_block_sent} = client.filters.get_filter(&filter_id).ok_or_else(||
        Error::invalid_params(format!("Unknown filter id: {}", filter_id)))?;

    let blocks = client.get_blocks_since(last_block_sent).map_err(|error| {
        error!("Failed to get blocks: {}", error);
        Error::internal_error()
    })?;

    let response = match filter {
        Filter::Block => {
            blocks.iter()
                .map(|&(_, ref block)| transform::hex_prefix(&block.header_signature))
                .collect()
        },
        Filter::Transaction => {
            blocks.iter()
                .flat_map(|&(_, ref block)| block.get_batches().into_iter()
                    .flat_map(|batch| batch.get_transactions().into_iter()
                        .filter(|txn| {
                            let header: Result<TransactionHeader, _> =
                                protobuf::parse_from_bytes(&txn.header);
                            if let Ok(header) = header {
                                if header.family_name == "seth" {
                                    true
                                } else {
                                    false
                                }
                            } else {
                                false
                            }
                        })
                        .map(|txn| transform::hex_prefix(&txn.header_signature))))
                .collect()
        },
        Filter::Log(log_filter) => {
            let mut all_logs = Vec::new();
            for &(_, ref block) in blocks.iter() {
                let logs = get_logs_from_block_and_filter(&mut client, block, &log_filter)?;
                all_logs.extend(logs.into_iter());
            }
            all_logs
        },
    };

    // NOTE: Updating is delayed until there are no more error sources that could cause an early
    // return after upadting the filter
    if let Some(&(block_num, _)) = blocks.last() {
        client.filters.update_latest_block(&filter_id, block_num);
    }

    Ok(Value::Array(response))
}

pub fn get_filter_logs<T>(params: Params, mut client: ValidatorClient<T>)
    -> Result<Value, Error> where T: MessageSender
{
    info!("eth_getFilterLogs");
    let filter_id = params.parse()
        .and_then(|(v,): (Value,)| transform::string_from_hex_value(&v))
        .and_then(|s| filter_id_from_hex(&s).map_err(|error|
            Error::invalid_params(format!("{}", error))))?;

    let FilterEntry{filter, last_block_sent: _} = client.filters.get_filter(&filter_id).ok_or_else(||
        Error::invalid_params(format!("Unknown filter id: {}", filter_id)))?;

    if let Filter::Log(log_filter) = filter {
        get_logs_from_filter(&mut client, &log_filter)
    } else {
        Err(Error::invalid_params(format!("Filter {} is not a log filter", filter_id)))
    }
}

pub fn get_logs<T>(params: Params, mut client: ValidatorClient<T>)
    -> Result<Value, Error> where T: MessageSender
{
    info!("eth_getLogs");
    let (filter,): (Map<String, Value>,) = params.parse().map_err(|_|
        Error::invalid_params("Takes [filter: OBJECT]"))?;
    let log_filter = LogFilter::from_map(filter)?;

    get_logs_from_filter(&mut client, &log_filter)
}

fn get_logs_from_filter<T>(mut client: &mut ValidatorClient<T>, log_filter: &LogFilter)
    -> Result<Value, Error>
    where T: MessageSender
{

    let interval = (log_filter.from_block, log_filter.to_block);

    match interval {
        // Request for logs in the latest block
        (None, None) => {
            let block = client.get_current_block().map_err(|e| {
                error!("Unable to get current block: {:?}", e);
                Error::internal_error()
            })?;

            let logs = get_logs_from_block_and_filter(&mut client, &block, &log_filter)?;
            Ok(Value::Array(logs))
        },
        // Request for logs from a block to the latest block
        (Some(from), None) => {
            let mut block_index = from;
            let mut all_logs = Vec::new();
            loop {
                match client.get_block(BlockKey::Number(block_index)) {
                    Ok(block) => {
                        let logs = get_logs_from_block_and_filter(&mut client, &block, &log_filter)?;
                        all_logs.extend(logs.into_iter());
                    },
                    Err(ClientError::NoResource) => {
                        // Stop getting blocks when there are no more left
                        return Ok(Value::Array(all_logs));
                    },
                    Err(error) => {
                        error!("{}", error);
                        return Err(Error::internal_error());
                    },
                }
                block_index += 1;
            }
        },
        // Request for logs from a block to a block
        (Some(from), Some(to)) => {
            let mut all_logs = Vec::new();
            for block_index in from..to {
                match client.get_block(BlockKey::Number(block_index)) {
                    Ok(block) => {
                        let logs = get_logs_from_block_and_filter(&mut client, &block, &log_filter)?;
                        all_logs.extend(logs.into_iter());
                    },
                    Err(ClientError::NoResource) => {
                        // If we get a no resource, just send what was found
                        return Ok(Value::Array(all_logs));
                    },
                    Err(error) => {
                        error!("{}", error);
                        return Err(Error::internal_error());
                    },
                }
            }
            Ok(Value::Array(all_logs))
        },
        // Getting the entire block history up to a certain block is not supported
        (None, Some(_)) => {
            Err(error::not_implemented())
        },
    }
}

fn get_logs_from_block_and_filter<T>(client: &mut ValidatorClient<T>, block: &Block, log_filter: &LogFilter)
    -> Result<Vec<Value>, Error>
    where T: MessageSender
{
    let block_header: BlockHeader = protobuf::parse_from_bytes(&block.header).map_err(|e| {
        error!("Error parsing block header: {:?}", e);
        Error::internal_error()
    })?;

    // Get receipts (which have logs in them)
    let receipts = client.get_receipts_from_block(&block).map_err(|error| {
        error!("Unable to get receipts for current block: {}", error);
        Error::internal_error()
    })?;

    warn!("LogFilter: {:?}", log_filter);
    // Filter logs
    let logs: HashMap<String, Vec<SethLog>> = receipts.into_iter()
        .map(|(txn_id, receipt)| {
            warn!("Logs: {:?}", receipt.logs);
            let logs: Vec<SethLog> = receipt.logs.into_iter()
                .filter(|log: &SethLog|
                    log_filter.contains(&log, None))
                .collect();
            (txn_id, logs)
        })
        .filter(|&(_, ref logs)| logs.len() > 0)
        .collect();
    warn!("Filtered Logs: {:?}", logs);

    // Contextual data for logs
    let block_id = block.get_header_signature();
    let block_num = block_header.get_block_num();
    let transactions = block.get_batches().iter()
        .flat_map(|batch| batch.get_transactions().iter()).collect::<Vec<_>>();

    let mut log_objects = Vec::with_capacity(logs.len());
    for (txn_id, logs) in logs.into_iter() {
        let index = transactions.iter()
            .position(|txn| txn.header_signature == txn_id)
            .ok_or_else(|| {
                error!("Failed to find index of txn `{}` in block `{}`",
                    txn_id, block_id);
                Error::internal_error()})?;
        for log in logs.iter() {
            let log_obj = transform::make_log_obj(
                log, &txn_id, index as u64, block_id, block_num);
            log_objects.push(log_obj);
        }
    }
    Ok(log_objects)
}

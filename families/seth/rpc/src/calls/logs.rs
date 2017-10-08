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

use std::sync::atomic::{AtomicUsize, Ordering, ATOMIC_USIZE_INIT};
use std::collections::HashMap;

use jsonrpc_core::{Params, Value, Error};
use serde_json::Map;
use protobuf;

use client::{
    ValidatorClient,
};
use requests::{RequestHandler};
use transform;

use sawtooth_sdk::messaging::stream::MessageSender;

use sawtooth_sdk::messages::block::{BlockHeader};
use sawtooth_sdk::messages::client::{
    ClientBlockListRequest,
    ClientBlockListResponse,
    PagingControls,
};
use sawtooth_sdk::messages::events::Event;
use sawtooth_sdk::messages::txn_receipt::{
    ClientReceiptGetRequest,
    ClientReceiptGetResponse,
    ClientReceiptGetResponse_Status,
};
use sawtooth_sdk::messages::transaction::TransactionHeader;
use sawtooth_sdk::messages::validator::Message_MessageType;
use error;
use filters::*;

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


static FILTER_ID: AtomicUsize = ATOMIC_USIZE_INIT;

fn to_filter_id(value: Value) -> Result<String, Error> {
    match value.get(0) {
        Some(&Value::String(ref id)) => Ok(id.clone()),
        x => Err(Error::invalid_params(format!("Unknown filter id: {:?}", x)))
    }
}

fn add_filter<T>(mut client: ValidatorClient<T>,
                 filter: Filter,
                 starting_block_id: &str)
    -> Result<Value, Error> where T: MessageSender
{
    let filter_id = String::from(
        format!("{:#x}", FILTER_ID.fetch_add(1, Ordering::SeqCst)));

    info!("Adding filter {} for {:?}, starting on block {}",
          filter_id, filter, &starting_block_id[..8]);
    client.set_filter(filter_id.clone(), filter, String::from(starting_block_id));

    Ok(Value::String(filter_id))
}


pub fn new_filter<T>(params: Params, mut client: ValidatorClient<T>)
    -> Result<Value, Error> where T: MessageSender
{
    info!("eth_newFilter");
    let value: Value = params.parse()?;
    let log_filter = LogFilterSpec::from_value(value)?;

    let current_block = client.get_current_block().map_err(|e| {
        error!("Unable to get current block: {:?}", e);
        Error::internal_error()
    })?;

    add_filter(client, Filter::Log(log_filter), current_block.get_header_signature())
}

pub fn new_block_filter<T>(_params: Params, mut client: ValidatorClient<T>)
    -> Result<Value, Error> where T: MessageSender
{
    info!("eth_newBlockFilter");
    let current_block = client.get_current_block().map_err(|e| {
        error!("Unable to get current block: {:?}", e);
        Error::internal_error()
    })?;

    add_filter(client, Filter::Block, current_block.get_header_signature())
}

pub fn new_pending_transaction_filter<T>(_params: Params, mut client: ValidatorClient<T>)
    -> Result<Value, Error> where T: MessageSender
{
    info!("eth_newPendingTransactionFilter");
    let current_block = client.get_current_block().map_err(|e| {
        error!("Unable to get current block: {:?}", e);
        Error::internal_error()
    })?;

    add_filter(client, Filter::Transaction, current_block.get_header_signature())
}

pub fn uninstall_filter<T>(params: Params, mut client: ValidatorClient<T>)
    -> Result<Value, Error> where T: MessageSender
{
    info!("eth_uninstallFilter");
    let filter_id = to_filter_id(params.parse()?)?;

    Ok(Value::Bool(client.remove_filter(&filter_id).is_some()))
}

fn get_block_changes<T>(mut client: ValidatorClient<T>, filter_id: String, last_block_id: String)
    -> Result<Value, Error> where T: MessageSender
{
    let mut paging = PagingControls::new();
    paging.set_count(100);
    let mut request = ClientBlockListRequest::new();
    request.set_paging(paging);

    let response: ClientBlockListResponse =
        client.request(Message_MessageType::CLIENT_BLOCK_LIST_REQUEST, &request)
            .map_err(|error| {
                error!("{}", error);
                Error::internal_error()
            })?;

    let block_ids: Vec<String> = response.blocks.iter()
        .rev()
        .skip_while(|block| block.get_header_signature() != last_block_id)
        .skip(1) // skip the current block
        .map(|block| String::from(block.get_header_signature()))
        .collect();

    if let Some(current_block_id) = block_ids.last() {
        let block_id = (*current_block_id).clone();
        client.set_filter(filter_id, Filter::Block, block_id);
    }

    let values: Vec<Value> =  block_ids.iter().map(|id| hex_prefix(&id)).collect();
    Ok(Value::Array(values))
}

pub fn get_filter_changes<T>(params: Params, mut client: ValidatorClient<T>)
    -> Result<Value, Error> where T: MessageSender
{
    info!("eth_getFilterChanges");
    let filter_id = to_filter_id(params.parse()?)?;
    let (filter, block_id) = client.get_filter(&filter_id).map_err(Error::invalid_params)?;
    debug!("filter: {:?}", filter);

    match filter {
        Filter::Block => get_block_changes(client, filter_id, block_id),
        //  NOTE: There is no analog for this currently in Sawtooth.
        Filter::Transaction => Err(error::not_implemented()),
        Filter::Log(filter_spec) =>
            get_logs_by_filter(client, Some(filter_id), filter_spec, block_id)
    }
}

pub fn get_filter_logs<T>(params: Params, mut client: ValidatorClient<T>)
    -> Result<Value, Error> where T: MessageSender
{
    info!("eth_getFilterLogs");
    let filter_id = to_filter_id(params.parse()?)?;
    let (filter, block_id) = client.get_filter(&filter_id).map_err(Error::invalid_params)?;
    if let Filter::Log(filter_spec) = filter {
        get_logs_by_filter(client, Some(filter_id), filter_spec, block_id)
    } else {
        Err(Error::invalid_params(format!("Filter {} is not a log filter", filter_id)))
    }
}

pub fn get_logs<T>(_params: Params, mut client: ValidatorClient<T>)
    -> Result<Value, Error> where T: MessageSender
{
    info!("eth_getLogs");
    let params: Value = _params.parse()?;
    let log_filter = LogFilterSpec::from_value(params)?;
    let current_block = client.get_current_block().map_err(|e| {
        error!("Unable to get current block: {:?}", e);
        Error::internal_error()
    })?;

    let block_header: BlockHeader = protobuf::parse_from_bytes(&current_block.header).map_err(|e| {
        error!("Error parsing block header: {:?}", e);
        Error::internal_error()
    })?;

    // Filter from the previous block, so as to find all the logs in this block that match
    get_logs_by_filter(client, None, log_filter, block_header.previous_block_id)
}

///
/// Returns the logs by the given filter, since the last block id
fn get_logs_by_filter<T>(mut client: ValidatorClient<T>,
                         _filter_id: Option<String>,
                         filter_spec: LogFilterSpec,
                         last_block_id: String)
    -> Result<Value, Error> where T: MessageSender
{
    debug!("log filter: {:?} since {}", filter_spec, &last_block_id[..8]);
    let mut paging = PagingControls::new();
    paging.set_count(100);
    let mut request = ClientBlockListRequest::new();
    request.set_paging(paging);

    let response: ClientBlockListResponse =
        client.request(Message_MessageType::CLIENT_BLOCK_LIST_REQUEST, &request)
            .map_err(|error| {
                error!("{}", error);
                Error::internal_error()
            })?;

    let mut relevant_txn_ids = Vec::new(); // to maintain txn order
    let mut relevant_txns = HashMap::new();
    for block in response.blocks.iter()
        .rev()
        .skip_while(|block| block.get_header_signature() != last_block_id)
        .skip(1) // skip last_block_id, as well
    {
        let block_header: BlockHeader =
            protobuf::parse_from_bytes(&block.header)
                .map_err(|error| {
                    error!("Parsing error (block header): {}", error);
                    Error::internal_error()
                })?;

        let mut txn_in_block = 0;
        for batch in block.get_batches() {
            for txn in batch.get_transactions() {
                txn_in_block += 1;

                let header: TransactionHeader =
                    protobuf::parse_from_bytes(&txn.header)
                        .map_err(|error| {
                            error!("Parsing error (txn header): {}", error);
                            Error::internal_error()
                        })?;
                if &header.family_name == "seth" {
                    relevant_txn_ids.push(txn.header_signature.clone());
                    relevant_txns.insert(&txn.header_signature,
                                         (block.get_header_signature().clone(),
                                          block_header.block_num.clone(),
                                          txn_in_block));
                }
            }
        }
    }

    let mut receipt_request = ClientReceiptGetRequest::new();
    receipt_request.set_transaction_ids(
        protobuf::RepeatedField::from_vec(relevant_txn_ids));
    let receipt_response: ClientReceiptGetResponse =
        client.request(Message_MessageType::CLIENT_RECEIPT_GET_REQUEST, &request)
            .map_err(|error| {
                error!("{}", error);
                Error::internal_error()
            })?;

    if receipt_response.status == ClientReceiptGetResponse_Status::INTERNAL_ERROR {
        error!("Internal error on validator while requesting receipts");
        return Err(Error::internal_error());
    }

    let logs: Vec<Value> =
        receipt_response.get_receipts().into_iter()
            .flat_map(|receipt| {
                receipt.get_events().into_iter()
                    .filter(|event| event.event_type == "seth_log_event")
                    .map(|event| {
                        let txn_id = &receipt.transaction_id.clone();
                        let (block_id, block_num, txn_in_block) =
                            relevant_txns.get(&txn_id).unwrap().clone();

                        let mut log_obj = Map::new();
                        log_obj.insert(String::from("logIndex"),
                                       num_to_hex(&txn_in_block));
                        log_obj.insert(String::from("transactionIndex"),
                                       num_to_hex(&txn_in_block));
                        log_obj.insert(String::from("transactionHash"),
                                       hex_prefix(&txn_id));
                        log_obj.insert(String::from("blockHash"),
                                       hex_prefix(&block_id));
                        log_obj.insert(String::from("blockNumber"),
                                       num_to_hex(&block_num));

                        let mut topics: Vec<Value> = Vec::new();
                        for topic_key in &["topic1", "topic2", "topic3", "topic4"] {
                            if let Some(topic_data) = get_event_attr(event, topic_key) {
                                topics.push(Value::String(String::from(topic_data)));
                            }
                        }
                        if let Some(address) = get_event_attr(event, "address") {
                            log_obj.insert(String::from("address"),
                                           hex_prefix(&address));
                        }

                        log_obj.insert(String::from("topics"), Value::Array(topics));
                        log_obj.insert(String::from("data"),
                                       Value::String(bytes_to_hex_str(&event.data)));

                        Value::Object(log_obj)
                    })
                    // The following is to manage an issue with the relevant_txns
                    // and the inner closure
                    .collect::<Vec<_>>()
                    .into_iter()
            })
            .collect();

    Ok(Value::Array(logs))
}

fn get_event_attr<'a>(event: &'a Event, attr_key: &str) -> Option<&'a str> {
    event.get_attributes().iter()
         .filter(|attr| &attr.key == attr_key)
         .map(|attr| attr.get_value().clone()).nth(0)
}

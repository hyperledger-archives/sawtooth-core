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

use jsonrpc_core::{Params, Value, Error};

use client::{
    ValidatorClient,
    hex_prefix,
};
use requests::{RequestHandler};

use sawtooth_sdk::messaging::stream::MessageSender;
use sawtooth_sdk::messages::client::{
    ClientBlockListRequest,
    ClientBlockListResponse,
    PagingControls,
};
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
        Filter::Transaction => Err(error::not_implemented()),
        Filter::Log(_) => Err(error::not_implemented())
    }
}

pub fn get_filter_logs<T>(params: Params, mut client: ValidatorClient<T>)
    -> Result<Value, Error> where T: MessageSender
{
    info!("eth_getFilterLogs");
    let filter_id = to_filter_id(params.parse()?)?;

    let filter = client.get_filter(&filter_id).map_err(Error::invalid_params)?;
    debug!("filter: {:?}", filter);

    Err(error::not_implemented())
}

pub fn get_logs<T>(_params: Params, mut _client: ValidatorClient<T>)
    -> Result<Value, Error> where T: MessageSender
{
    info!("eth_getLogs");
    let params: Value = _params.parse()?;
    let log_filter = LogFilterSpec::from_value(params)?;
    debug!("filter: {:?}", log_filter);

    Err(error::not_implemented())
}

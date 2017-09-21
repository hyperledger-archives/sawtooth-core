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

use client::{ValidatorClient};
use requests::{RequestHandler};

use sawtooth_sdk::messaging::stream::MessageSender;
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

fn add_filter<T>(mut client: ValidatorClient<T>, filter: Filter)
    -> Result<Value, Error> where T: MessageSender
{
    let filter_id = String::from(
        format!("{:#x}", FILTER_ID.fetch_add(1, Ordering::SeqCst)));

    client.set_filter(filter_id.clone(), filter, 0);

    Ok(Value::String(filter_id))
}


pub fn new_filter<T>(params: Params, mut client: ValidatorClient<T>)
    -> Result<Value, Error> where T: MessageSender
{
    let value: Value = params.parse()?;
    let log_filter = LogFilterSpec::from_value(value)?;
    add_filter(client, Filter::Log(log_filter))
}

pub fn new_block_filter<T>(_params: Params, mut client: ValidatorClient<T>)
    -> Result<Value, Error> where T: MessageSender
{
    add_filter(client, Filter::Block)
}

pub fn new_pending_transaction_filter<T>(_params: Params, mut client: ValidatorClient<T>)
    -> Result<Value, Error> where T: MessageSender
{
    add_filter(client, Filter::Transaction)
}

pub fn uninstall_filter<T>(params: Params, mut client: ValidatorClient<T>)
    -> Result<Value, Error> where T: MessageSender
{
    let filter_id = to_filter_id(params.parse()?)?;

    match client.remove_filter(&filter_id) {
        Some(_) => Ok(Value::Bool(true)),
        None => Ok(Value::Bool(false))
    }
}


pub fn get_filter_changes<T>(params: Params, mut client: ValidatorClient<T>)
    -> Result<Value, Error> where T: MessageSender
{
    let filter_id = to_filter_id(params.parse()?)?;
    let filter = client.get_filter(&filter_id).map_err(Error::invalid_params)?;
    debug!("filter: {:?}", filter);

    Err(error::not_implemented())
}

pub fn get_filter_logs<T>(params: Params, mut client: ValidatorClient<T>)
    -> Result<Value, Error> where T: MessageSender
{
    let filter_id = to_filter_id(params.parse()?)?;

    let filter = client.get_filter(&filter_id).map_err(Error::invalid_params)?;
    debug!("filter: {:?}", filter);

    Err(error::not_implemented())
}

pub fn get_logs<T>(_params: Params, mut _client: ValidatorClient<T>)
    -> Result<Value, Error> where T: MessageSender
{
    let params: Value = _params.parse()?;
    let log_filter = LogFilterSpec::from_value(params)?;
    debug!("filter: {:?}", log_filter);

    Err(error::not_implemented())
}


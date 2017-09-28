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

use jsonrpc_core::{Params, Value, Error};

use client::{ValidatorClient};
use requests::{RequestHandler};

use sawtooth_sdk::messaging::stream::MessageSender;

const SAWTOOTH_NET_VERSION: &str = "19";

pub fn get_method_list<T>() -> Vec<(String, RequestHandler<T>)> where T: MessageSender {
    let mut methods: Vec<(String, RequestHandler<T>)> = Vec::new();

    methods.push((String::from("net_version"), version));
    methods.push((String::from("net_peerCount"), peer_count));
    methods.push((String::from("net_listening"), listening));

    methods
}

// Version refers to the particular network this JSON-RPC client is connected to
pub fn version<T>(_params: Params, mut _client: ValidatorClient<T>) -> Result<Value, Error> where T: MessageSender {
    info!("net_version");
    Ok(Value::String(String::from(SAWTOOTH_NET_VERSION)))
}

// Since this is only for HTTP right now, there won't be any connected peers
pub fn peer_count<T>(_params: Params, mut _client: ValidatorClient<T>) -> Result<Value, Error> where T: MessageSender {
    info!("net_peerCount");
    Ok(Value::String(format!("{:#x}", 0)))
}

// Return whether we are listening for connections, which is always true
pub fn listening<T>(_params: Params, mut _client: ValidatorClient<T>) -> Result<Value, Error> where T: MessageSender {
    info!("net_listening");
    Ok(Value::Bool(true))
}

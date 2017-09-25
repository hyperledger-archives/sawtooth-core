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

#[macro_use]
extern crate clap;
#[macro_use]
extern crate log;
extern crate simple_logging;
extern crate uuid;
extern crate jsonrpc_core;
extern crate jsonrpc_http_server;
extern crate futures_cpupool;
extern crate sawtooth_sdk;
extern crate protobuf;

use log::LogLevelFilter;

use sawtooth_sdk::messaging::stream::*;
use sawtooth_sdk::messaging::zmq_stream::*;

use jsonrpc_core::{IoHandler};
use jsonrpc_http_server::{ServerBuilder};
use jsonrpc_core::{Params};

mod requests;
mod error;
mod messages;

mod account;
mod block;
mod logs;
mod network;
mod transaction;

use requests::{RequestExecutor, RequestHandler};

const SERVER_THREADS: usize = 3;

fn main() {
    let arg_matches = clap_app!(("seth-rpc") =>
        (version: "1.0")
        (about: "Seth RPC Server")
        (@arg connect: --connect +takes_value
         "Component endpoint of the validator to communicate with.")
        (@arg bind: --bind +takes_value
         "The host and port the RPC server should bind to.")
        (@arg verbose: -v... "Increase the logging level.")
    ).get_matches();

    let bind = arg_matches.value_of("bind")
        .unwrap_or("0.0.0.0:3030");
    let connect = arg_matches.value_of("connect")
        .unwrap_or("tcp://localhost:4004");

    let vs = arg_matches.occurrences_of("verbose");
    let log_level = match vs {
        0 => LogLevelFilter::Warn,
        1 => LogLevelFilter::Info,
        2 => LogLevelFilter::Debug,
        _ => LogLevelFilter::Trace,
    };
    simple_logging::log_to_stderr(log_level).expect("Failed to initialize logger");

    info!("Trying to connect to validator at {}", connect);

    let mut io = IoHandler::new();
    let connection = ZmqMessageConnection::new(connect);
    let (sender, _) = connection.create();
    let executor = RequestExecutor::new(sender);

    let methods = get_method_list();
    for (name, method) in methods {
        let clone = executor.clone();
        io.add_async_method(&name, move |params: Params| {
            clone.run(params, method)
        });
    }

    let endpoint: std::net::SocketAddr = bind.parse().unwrap();
    let server = ServerBuilder::new(io)
        .threads(SERVER_THREADS)
        .start_http(&endpoint)
        .unwrap();

    info!("Starting seth-rpc on http://{}", bind);

    server.wait();
}

fn get_method_list<T>() -> Vec<(String, RequestHandler<T>)> where T: MessageSender {
    let mut methods: Vec<(String, RequestHandler<T>)> = Vec::new();

    methods.push((String::from("eth_getBalance"), account::get_balance));
    methods.push((String::from("eth_getStorageAt"), account::get_storage_at));
    methods.push((String::from("eth_getCode"), account::get_code));
    methods.push((String::from("eth_sign"), account::sign));
    methods.push((String::from("eth_call"), account::call));
    methods.push((String::from("eth_accounts"), account::accounts));

    methods.push((String::from("eth_blockNumber"), block::block_number));
    methods.push((String::from("eth_getBlockByHash"), block::get_block_by_hash));
    methods.push((String::from("eth_getBlockByNumber"), block::get_block_by_number));

    methods.push((String::from("eth_newFilter"), logs::new_filter));
    methods.push((String::from("eth_newBlockFilter"), logs::new_block_filter));
    methods.push((String::from("eth_newPendingTransactionFilter"), logs::new_pending_transaction_filter));
    methods.push((String::from("eth_uninstallFilter"), logs::uninstall_filter));
    methods.push((String::from("eth_getFilterChanges"), logs::get_filter_changes));
    methods.push((String::from("eth_getFilterLogs"), logs::get_filter_logs));
    methods.push((String::from("eth_getLogs"), logs::get_logs));

    methods.push((String::from("net_version"), network::version));
    methods.push((String::from("net_peerCount"), network::peer_count));
    methods.push((String::from("net_listening"), network::listening));

    methods.push((String::from("eth_getTransactionCount"), transaction::get_transaction_count));
    methods.push((String::from("eth_getBlockTransactionCountByHash"), transaction::get_block_transaction_count_by_hash));
    methods.push((String::from("eth_getBlockTransactionCountByNumber"), transaction::get_block_transaction_count_by_number));
    methods.push((String::from("eth_sendTransaction"), transaction::send_transaction));
    methods.push((String::from("eth_sendRawTransaction"), transaction::send_raw_transaction));
    methods.push((String::from("eth_getTransactionByHash"), transaction::get_transaction_by_hash));
    methods.push((String::from("eth_getTransactionByBlockHashAndIndex"), transaction::get_transaction_by_block_hash_and_index));
    methods.push((String::from("eth_getTransactionByBlockNumberAndIndex"), transaction::get_transaction_by_block_number_and_index));
    methods.push((String::from("eth_getTransactionReceipt"), transaction::get_transaction_receipt));
    methods.push((String::from("eth_gasPrice"), transaction::gas_price));
    methods.push((String::from("eth_estimateGas"), transaction::estimate_gas));

    methods
}

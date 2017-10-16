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
extern crate serde_json;
extern crate futures_cpupool;
extern crate sawtooth_sdk;
extern crate protobuf;
extern crate rpassword;
extern crate tiny_keccak;
extern crate crypto;

use std::process;
use log::LogLevelFilter;

use sawtooth_sdk::messaging::stream::*;
use sawtooth_sdk::messaging::zmq_stream::*;

use jsonrpc_core::{IoHandler};
use jsonrpc_http_server::{ServerBuilder};
use jsonrpc_core::{Params};

mod requests;
mod client;
mod messages;
mod calls;
mod accounts;
mod filters;
mod transactions;
mod transform;

use client::{ValidatorClient};
use requests::{RequestExecutor, RequestHandler};
use accounts::{Account};
use calls::*;

const SERVER_THREADS: usize = 3;

fn main() {
    let arg_matches = clap_app!(("seth-rpc") =>
        (version: "1.0")
        (about: "Seth RPC Server")
        (@arg connect: --connect +takes_value
         "Component endpoint of the validator to communicate with.")
        (@arg bind: --bind +takes_value
         "The host and port the RPC server should bind to.")
        (@arg unlock: --unlock... +takes_value
         "The aliases of the accounts to unlock.")
        (@arg verbose: -v... "Increase the logging level.")
    ).get_matches();

    let bind = arg_matches.value_of("bind")
        .unwrap_or("127.0.0.1:3030");
    let connect = arg_matches.value_of("connect")
        .unwrap_or("tcp://127.0.0.1:4004");
    let accounts: Vec<Account> = arg_matches.values_of_lossy("unlock").unwrap_or_else(||
        Vec::new()).iter().map(|alias|
            abort_if_err(Account::load_from_alias(alias))).collect();

    for account in accounts.iter() {
        println!("{} unlocked: {}", account.alias(), account.address());
    }

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
    let client = ValidatorClient::new(sender, accounts);
    let executor = RequestExecutor::new(client);

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

    methods.extend(account::get_method_list().into_iter());
    methods.extend(block::get_method_list().into_iter());
    methods.extend(logs::get_method_list().into_iter());
    methods.extend(network::get_method_list().into_iter());
    methods.extend(transaction::get_method_list().into_iter());

    methods
}

fn abort_if_err<T, E: std::error::Error>(r: Result<T, E>) -> T {
    match r {
        Ok(t) => t,
        Err(error) => {
            eprintln!("{}", error.description());
            process::exit(1);
        }
    }
}

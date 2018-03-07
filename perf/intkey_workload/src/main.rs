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

extern crate cbor;
extern crate clap;
extern crate crypto;
#[macro_use]
extern crate log;
extern crate rand;
extern crate sawtooth_perf;

mod intkey_addresser;
mod intkey_iterator;

use clap::{App, Arg, ArgMatches};

const APP_NAME: &'static str = env!("CARGO_PKG_NAME");
const VERSION: &'static str = env!("CARGO_PKG_VERSION");

fn main() {
    get_arg_matches();
}

fn get_arg_matches<'a>() -> ArgMatches<'a> {
    App::new(APP_NAME)
        .version(VERSION)
        .about("Submit intkey workload at a continuous rate")
        .arg(
            Arg::with_name("display")
                .short("d")
                .takes_value(true)
                .number_of_values(1)
                .default_value("30")
                .value_name("TIME_BETWEEN_DISPLAYS")
                .help("Seconds between statistics displays"),
        )
        .arg(
            Arg::with_name("key")
                .short("k")
                .long("key-file")
                .value_name("KEY_FILE")
                .help("File containing a private key to sign transactions and batches"),
        )
        .arg(
            Arg::with_name("batch-size")
                .short("n")
                .long("batch-size")
                .takes_value(true)
                .default_value("1")
                .number_of_values(1)
                .value_name("BATCH_SIZE")
                .help("Transactions in a batch"),
        )
        .arg(
            Arg::with_name("names")
                .long("num-names")
                .takes_value(true)
                .default_value("100")
                .number_of_values(1)
                .value_name("NUM_NAMES")
                .help("Number of IntKey Names to set"),
        )
        .arg(
            Arg::with_name("rate")
                .short("r")
                .long("rate")
                .takes_value(true)
                .number_of_values(1)
                .default_value("10")
                .value_name("RATE")
                .help("Batches per second to send to a Sawtooth REST Api"),
        )
        .arg(
            Arg::with_name("seed")
                .short("s")
                .long("seed")
                .takes_value(true)
                .number_of_values(1)
                .value_name("SEED")
                .help("Comma separated list of u8 to make the workload reproduceable"),
        )
        .arg(
            Arg::with_name("unsatisfiable")
                .long("unsatisfiable")
                .takes_value(true)
                .number_of_values(1)
                .default_value("0.0")
                .value_name("UNSATISFIABLE")
                .help("Probability of a transaction having an unsatisfiable dependency"),
        )
        .arg(
            Arg::with_name("urls")
                .short("u")
                .long("urls")
                .value_name("URLS")
                .takes_value(true)
                .number_of_values(1)
                .default_value("http://127.0.0.1:8008")
                .help("Comma separated list of Sawtooth REST Apis"),
        )
        .arg(
            Arg::with_name("validity")
                .long("invalid")
                .value_name("INVALID")
                .takes_value(true)
                .number_of_values(1)
                .default_value("0.0")
                .help("Probability of a transaction being invalid"),
        )
        .arg(
            Arg::with_name("wildcard")
                .long("wildcard")
                .value_name("WILDCARD")
                .takes_value(true)
                .number_of_values(1)
                .default_value("0.0")
                .help("Probability of a transaction having a wildcarded input/output"),
        )
        .arg(
            Arg::with_name("username")
                .long("auth-username")
                .value_name("BASIC_AUTH_USERNAME")
                .help("Basic auth username to authenticate with the Sawtooth REST Api"),
        )
        .arg(
            Arg::with_name("password")
                .long("auth-password")
                .value_name("BASIC_AUTH_PASSWORD")
                .help("Basic auth password to authenticate with the Sawtooth REST Api"),
        )
        .get_matches()
}

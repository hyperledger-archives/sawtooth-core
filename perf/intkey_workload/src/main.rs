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
extern crate protobuf;
extern crate rand;
extern crate sawtooth_perf;
extern crate sawtooth_sdk;
extern crate simplelog;

mod intkey_addresser;
mod intkey_iterator;
mod intkey_transformer;

use std::convert::From;
use std::error::Error;
use std::fmt;
use std::fs::File;
use std::io::Read;
use std::num::ParseFloatError;
use std::num::ParseIntError;
use std::str::Split;

use clap::{App, Arg, ArgMatches};

use rand::{Rng, StdRng};

use sawtooth_perf::batch_gen::SignedBatchIterator;
use sawtooth_perf::batch_submit::run_workload;
use sawtooth_perf::batch_submit::InfiniteBatchListIterator;

use sawtooth_sdk::signing;
use sawtooth_sdk::signing::secp256k1::Secp256k1PrivateKey;

use simplelog::{Config, LevelFilter, SimpleLogger};

use intkey_iterator::IntKeyIterator;
use intkey_transformer::IntKeyTransformer;

const APP_NAME: &str = env!("CARGO_PKG_NAME");
const VERSION: &str = env!("CARGO_PKG_VERSION");

fn main() {
    match SimpleLogger::init(LevelFilter::Warn, Config::default()) {
        Ok(_) => (),
        Err(err) => println!("Failed to load logger: {}", err.description()),
    }

    let arg_matches = get_arg_matches();

    match run_load_command(&arg_matches) {
        Ok(_) => (),
        Err(err) => println!("{}", err.description()),
    }
}

fn get_arg_matches<'a>() -> ArgMatches<'a> {
    App::new(APP_NAME)
        .version(VERSION)
        .about("Submit intkey workload at a continuous rate")
        .arg(
            Arg::with_name("display")
                .long("display")
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
            Arg::with_name("unnecessary")
                .long("unnecessary")
                .takes_value(true)
                .number_of_values(1)
                .default_value("0.0")
                .value_name("UNNECESSARY")
                .help("Probability of a transaction having a satisfiable but unnecessary depedendency"),
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
            Arg::with_name("invalid")
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

fn err_if_out_of_range(val: f32) -> Result<f32, IntKeyCliError> {
    if val < 0.0 || val > 1.0 {
        return Err(IntKeyCliError {
            msg: "Value must be between 0.0 and 1.0, inclusively".to_string(),
        });
    }
    Ok(val)
}

fn greater_than_zero32(val: u32) -> Result<u32, IntKeyCliError> {
    if val == 0 {
        return Err(IntKeyCliError {
            msg: "Value must be greater than zero".to_string(),
        });
    }
    Ok(val)
}

fn greater_than_zero(val: usize) -> Result<usize, IntKeyCliError> {
    if val == 0 {
        return Err(IntKeyCliError {
            msg: "Value must be greater than zero".to_string(),
        });
    }
    Ok(val)
}

fn run_load_command(args: &ArgMatches) -> Result<(), Box<Error>> {
    let batch_size: usize = args
        .value_of("batch-size")
        .unwrap_or("1")
        .parse()
        .map_err(IntKeyCliError::from)
        .and_then(greater_than_zero)?;

    let num_names: usize = args
        .value_of("names")
        .unwrap_or("100")
        .parse()
        .map_err(IntKeyCliError::from)
        .and_then(greater_than_zero)?;

    let urls: Vec<String> = args
        .value_of("urls")
        .unwrap_or("http://127.0.0.1:8008")
        .parse()
        .map_err(|_| String::from("urls are a comma separated list of strings"))
        .and_then(|st| {
            let s: String = st;
            let split: Split<char> = s.split(',');
            Ok(split.map(|s| s.to_string()).collect())
        })?;

    let rate: usize = args
        .value_of("rate")
        .unwrap_or("10")
        .parse()
        .map_err(IntKeyCliError::from)
        .and_then(greater_than_zero)?;

    let unsatisfiable: f32 = args
        .value_of("unsatisfiable")
        .unwrap_or("0.0")
        .parse()
        .map_err(IntKeyCliError::from)
        .and_then(err_if_out_of_range)?;

    let unnecessary: f32 = args
        .value_of("unnecessary")
        .unwrap_or("0.0")
        .parse()
        .map_err(IntKeyCliError::from)
        .and_then(err_if_out_of_range)?;

    let wildcard: f32 = args
        .value_of("wildcard")
        .unwrap_or("0.0")
        .parse()
        .map_err(IntKeyCliError::from)
        .and_then(err_if_out_of_range)?;

    let invalid: f32 = args
        .value_of("invalid")
        .unwrap_or("0.0")
        .parse()
        .map_err(IntKeyCliError::from)
        .and_then(err_if_out_of_range)?;

    let display: u32 = args
        .value_of("display")
        .unwrap_or("30")
        .parse()
        .map_err(IntKeyCliError::from)
        .and_then(greater_than_zero32)?;

    let username = args.value_of("username");
    let password = args.value_of("password");

    let basic_auth = {
        match username {
            Some(username) => match password {
                None => Some(String::from(username)),
                Some(password) => Some([username, password].join(":")),
            },
            None => None,
        }
    };
    let s: Result<Vec<usize>, std::num::ParseIntError> = match args.value_of("seed") {
        Some(s) => {
            let split: Split<char> = s.split(',');
            split.map(|s| s.parse()).collect()
        }
        None => {
            let mut rng = StdRng::new()?;

            Ok(rng.gen_iter().take(10).collect())
        }
    };

    let seed = s?;

    let context = signing::create_context("secp256k1")?;

    let private_key: Result<Box<signing::PrivateKey>, Box<Error>> = match args.value_of("key") {
        Some(file) => {
            let mut key_file = File::open(file)?;
            let mut buf = String::new();
            key_file.read_to_string(&mut buf)?;
            buf.pop(); // remove the new line
            let private_key = Secp256k1PrivateKey::from_hex(&buf)?;
            Ok(Box::new(private_key))
        }
        None => {
            let private_key = context.new_random_private_key()?;
            Ok(private_key)
        }
    };

    let priv_key = private_key?;

    let signer = signing::Signer::new(context.as_ref(), priv_key.as_ref());

    let signer_ref = &signer;

    let mut transformer = IntKeyTransformer::new(
        signer_ref,
        &seed,
        unsatisfiable,
        wildcard,
        num_names,
        unnecessary,
    );

    let mut transaction_iterator = IntKeyIterator::new(num_names, invalid, &seed)
        .map(|payload| transformer.intkey_payload_to_transaction(&payload))
        .filter_map(|payload| payload.ok());
    let mut batch_iter =
        SignedBatchIterator::new(&mut transaction_iterator, batch_size, signer_ref);
    let mut batchlist_iter = InfiniteBatchListIterator::new(&mut batch_iter);

    let time_to_wait: u32 = 1_000_000_000 / rate as u32;

    println!("--invalid {} --batch-size {} --rate {} --wildcard {} --urls {:?} --unsatisfiable {} --seed {:?} --num-names {} --display {}",
        invalid,
        batch_size,
        rate,
        wildcard,
        urls,
        unsatisfiable,
        seed,
        num_names,
        display);

    match run_workload(
        &mut batchlist_iter,
        time_to_wait,
        display,
        urls,
        &basic_auth,
    ) {
        Ok(_) => Ok(()),
        Err(err) => Err(Box::new(err)),
    }
}

#[derive(Debug)]
struct IntKeyCliError {
    msg: String,
}

impl Error for IntKeyCliError {
    fn description(&self) -> &str {
        self.msg.as_str()
    }
}

impl fmt::Display for IntKeyCliError {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        write!(f, "{}", format!("IntKeyCliError {}", self.msg))
    }
}

impl From<ParseIntError> for IntKeyCliError {
    fn from(error: ParseIntError) -> Self {
        IntKeyCliError {
            msg: error.description().to_string(),
        }
    }
}

impl From<ParseFloatError> for IntKeyCliError {
    fn from(error: ParseFloatError) -> Self {
        IntKeyCliError {
            msg: error.description().to_string(),
        }
    }
}

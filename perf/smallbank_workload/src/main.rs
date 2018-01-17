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
extern crate clap;
extern crate sawtooth_perf;
extern crate sawtooth_sdk;
extern crate protobuf;

mod playlist;
mod smallbank;

use std::fs::File;
use std::io;
use std::io::Write;
use std::io::Read;
use std::error::Error;

use batch_gen::generate_signed_batches;
use batch_submit::submit_signed_batches;
use playlist::generate_smallbank_playlist;
use playlist::process_smallbank_playlist;
use clap::{App, ArgMatches, AppSettings, Arg, SubCommand};

use sawtooth_perf::batch_gen;
use sawtooth_perf::batch_submit;

use sawtooth_sdk::signing;
use sawtooth_sdk::signing::secp256k1::Secp256k1PrivateKey;

const APP_NAME: &'static str = env!("CARGO_PKG_NAME");
const VERSION: &'static str = env!("CARGO_PKG_VERSION");

fn main() {
    let arg_matches =
        App::new(APP_NAME)
            .version(VERSION)
            .setting(AppSettings::SubcommandRequiredElseHelp)
            .subcommand(create_batch_subcommand_args())
            .subcommand(create_submit_subcommand_args())
            .subcommand(create_playlist_subcommand_args())
            .get_matches();

    let result = match arg_matches.subcommand() {
        ("batch", Some(args)) => run_batch_command(args),
        ("submit", Some(args)) => run_submit_command(args),
        ("playlist", Some(args)) => run_playlist_command(args),
        _ => panic!("Should have processed a subcommand or exited before here")
    };

    std::process::exit(match result {
        Ok(_) => 0,
        Err(err) => {
            writeln!(io::stderr(), "Error: {}", err).unwrap();
            1
        }
    });
}

#[inline]
fn arg_error (msg: &str) -> Result<(), Box<Error>> {
    Err(Box::new(CliError::ArgumentError(String::from(msg))))
}

fn create_batch_subcommand_args<'a, 'b>() -> App<'a, 'b> {
    SubCommand::with_name("batch")
        .about("Generates signed batches from transaction input.\n \
                The transaction input is expected to be length-delimited protobuf \
                Transaction messages, which should also be pre-signed for \
                submission to the validator.")
        .arg(Arg::with_name("input")
             .short("i")
             .long("input")
             .value_name("FILE")
             .required(true)
             .help("The source of input transactions"))
        .arg(Arg::with_name("output")
             .short("o")
             .long("output")
             .value_name("FILE")
             .required(true)
             .help("The target for the signed batches"))
        .arg(Arg::with_name("key")
             .short("k")
             .long("key")
             .value_name("FILE")
             .required(true)
             .help("The signing key for the transactions"))
        .arg(Arg::with_name("max-batch-size")
             .short("n")
             .long("max-batch-size")
             .value_name("NUMBER")
             .help("The maximum number of transactions to include in a batch; \
                    Defaults to 100."))
}

fn run_batch_command(args: &ArgMatches) -> Result<(), Box<Error>> {
    let max_txns: usize = match args.value_of("max-batch-size")
        .unwrap_or("100")
        .parse() {
            Ok(n) => n,
            Err(_) => 0
        };

    if max_txns == 0 {
        return arg_error("max-batch-size must be a number greater than 0");
    }

    let mut in_file = File::open(args.value_of("input").unwrap())?;
    let mut out_file = File::create(args.value_of("output").unwrap())?;

    let mut key_file = try!(File::open(args.value_of("key").unwrap()));

    let mut buf = String::new();
    try!(key_file.read_to_string(&mut buf));
    buf.pop(); // remove the new line

    let private_key = try!(
        Secp256k1PrivateKey::from_hex(&buf));
    let context = try!(signing::create_context("secp256k1"));

    if let Err(err) = generate_signed_batches(&mut in_file, &mut out_file,
                                              max_txns, context.as_ref(), &private_key) {
        return Err(Box::new(err));
    }

    Ok(())
}

fn create_submit_subcommand_args<'a, 'b>() -> App<'a, 'b> {
    SubCommand::with_name("submit")
        .about("Submits signed batches to one or more targets from batch input.\n \
               The batch input is expected to be length-delimited protobuf \
               Batch messages, which should also be pre-signed for \
               submission to the validator.")
        .arg(Arg::with_name("input")
             .short("i")
             .long("input")
             .value_name("FILE")
             .help("The source of batch transactions"))
        .arg(Arg::with_name("target")
             .short("t")
             .long("target")
             .value_name("TARGET")
             .help("A Sawtooth REST API endpoint"))
        .arg(Arg::with_name("rate")
             .short("r")
             .long("rate")
             .value_name("RATE")
             .help("The number of batches per second to submit to the target"))
}

fn run_submit_command(args: &ArgMatches) -> Result<(), Box<Error>> {
    let rate: usize = match args.value_of("rate")
        .unwrap_or("1")
        .parse() {
            Ok(n) => n,
            Err(_) => 0
        };

    if rate == 0 {
        return arg_error("rate must be a number greater than 0");
    }

    let target: String = match args.value_of("target")
        .unwrap_or("http://localhost:8008")
        .parse() {
            Ok(s) => s,
            Err(_) => String::new()
        };

    if target == "" {
        return arg_error("target must be a valid http uri");
    }

    let input: String = match args.value_of("input")
        .unwrap_or("")
        .parse() {
            Ok(s) => s,
            Err(_) => String::new()
        };

    if input == "" {
       return arg_error("an input file must be specified");
    }

    let mut in_file = File::open(args.value_of("input").unwrap())?;

    println!("Input: {} Target: {} Rate: {}", input, target, rate);

    if let Err(err) = submit_signed_batches(&mut in_file, target, rate) {
        return Err(Box::new(err));
    }

    Ok(())
}

fn create_playlist_subcommand_args<'a, 'b>() -> App<'a, 'b> {
    SubCommand::with_name("playlist")
        .subcommand(create_playlist_create_subcommand_args())
        .subcommand(create_playlist_process_subcommand_args())
}

fn create_playlist_create_subcommand_args<'a, 'b>() -> App<'a, 'b> {
    SubCommand::with_name("create")
        .about("Generates a smallbank transaction playlist.\n \
                A playlist is a series of transactions, described in \
                YAML.  This command generates a playlist and writes it \
                to file or statndard out.")
        .arg(Arg::with_name("output")
             .short("o")
             .long("output")
             .value_name("FILE")
             .help("The target for the generated playlist"))
        .arg(Arg::with_name("random_seed")
             .short("S")
             .long("seed")
             .value_name("NUMBER")
             .help("A random seed, which will generate the same output"))
        .arg(Arg::with_name("accounts")
             .short("a")
             .long("accounts")
             .value_name("NUMBER")
             .required(true)
             .help("The number of unique accounts to generate"))
        .arg(Arg::with_name("transactions")
             .short("n")
             .long("transactions")
             .value_name("NUMBER")
             .required(true)
             .help("The number of transactions generate, in \
                    addition to the created accounts"))
}

fn create_playlist_process_subcommand_args<'a, 'b>() -> App<'a, 'b> {
    SubCommand::with_name("process")
        .about("Processes a smallbank transaction playlist.\n \
                A playlist is a series of transactions, described in \
                YAML.  This command processes a playlist, converting it into \
                transactions and writes it to file or statndard out.")
        .arg(Arg::with_name("input")
             .short("i")
             .long("input")
             .value_name("FILE")
             .required(true)
             .help("The source of the input playlist yaml"))
        .arg(Arg::with_name("key")
             .short("k")
             .long("key")
             .value_name("FILE")
             .required(true)
             .help("The signing key for the transactions"))
        .arg(Arg::with_name("output")
             .short("o")
             .long("output")
             .value_name("FILE")
             .help("The target for the generated transactions"))
}

fn run_playlist_command(args: &ArgMatches) -> Result<(), Box<Error>> {
    match args.subcommand() {
        ("create", Some(args)) => run_playlist_create_command(args),
        ("process", Some(args)) => run_playlist_process_command(args),
        _ => panic!("Should have processed a subcommand or exited before here")
    }
}

fn run_playlist_create_command(args: &ArgMatches) -> Result<(), Box<Error>> {
    let num_accounts = match args.value_of("accounts").unwrap().parse() {
        Ok(n) => n,
        Err(_) => 0
    };

    if num_accounts < 2 {
        return arg_error("'accounts' must be a number greater than 2");
    }

    let num_transactions = match args.value_of("transactions").unwrap().parse() {
        Ok(n) => n,
        Err(_) => 0
    };

    if num_transactions == 0 {
        return arg_error("'transactions' must be a number greater than 0");
    }

    let random_seed = match args.value_of("random_seed") {
        Some(seed) => match seed.parse::<i32>() {
            Ok(n) => Some(n),
            Err(_) => return arg_error("'seed' must be a valid number"),
        },
        None => None
    };

    let mut output_writer: Box<Write>  = match args.value_of("output") {
        Some(file_name) => try!(File::create(file_name).map(Box::new)),
        None => Box::new(std::io::stdout())
    };

    try!(generate_smallbank_playlist(
        &mut *output_writer,
        num_accounts,
        num_transactions,
        random_seed));

    Ok(())
}

fn run_playlist_process_command(args: &ArgMatches) -> Result<(), Box<Error>> {
    let mut in_file = try!(File::open(args.value_of("input").unwrap()));

    let mut output_writer: Box<Write>  = match args.value_of("output") {
        Some(file_name) => try!(File::create(file_name).map(Box::new)),
        None => Box::new(std::io::stdout())
    };

    let mut key_file = try!(File::open(args.value_of("key").unwrap()));

    let mut buf = String::new();
    try!(key_file.read_to_string(&mut buf));
    buf.pop(); // remove the new line

    let context = try!(signing::create_context("secp256k1"));
    let private_key = try!(
        Secp256k1PrivateKey::from_hex(&buf));

    try!(process_smallbank_playlist(&mut output_writer, &mut in_file,
                                    context.as_ref(), &private_key));

    Ok(())
}

#[derive(Debug)]
enum CliError {
    ArgumentError(String),
}

impl std::fmt::Display for CliError {
    fn fmt(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
        match *self {
            CliError::ArgumentError(ref msg) =>
                write!(f, "ArgumentError: {}",  msg)
        }
    }
}

impl std::error::Error for CliError {
    fn description(&self) -> &str {
        match *self {
            CliError::ArgumentError(ref msg) => msg
        }
    }

    fn cause(&self) -> Option<&Error> {
        match * self {
            CliError::ArgumentError(_) => None
        }
    }
}

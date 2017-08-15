extern crate clap;
extern crate sawtooth_sdk;

mod batch_gen;

use std::fs::File;
use std::io;
use std::io::prelude::*;
use std::error::Error;

use batch_gen::generate_signed_batches;
use clap::{App, ArgMatches, AppSettings, Arg, SubCommand};

const APP_NAME: &'static str = env!("CARGO_PKG_NAME");
const VERSION: &'static str = env!("CARGO_PKG_VERSION");

fn main() {
    let arg_matches = 
        App::new(APP_NAME)
            .version(VERSION)
            .setting(AppSettings::SubcommandRequiredElseHelp)
            .subcommand(SubCommand::with_name("batch")
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
                        .arg(Arg::with_name("max-batch-size")
                             .short("n")
                             .long("max-batch-size")
                             .value_name("NUMBER")
                             .help("The maximum number of transactions to include in a batch; \
                             Defaults to 100.")))
            .get_matches();

    let result = match arg_matches.subcommand() {
        ("batch", Some(args)) => run_batch_command(args),
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

macro_rules! arg_error {
    ($msg:expr) => (Err(Box::new(CliError::ArgumentError(String::from($msg)))));
}

fn run_batch_command(args: &ArgMatches) -> Result<(), Box<Error>> {
    let max_txns: usize = match args.value_of("max-batch-size")
        .unwrap_or("100")
        .parse() {
            Ok(n) => n,
            Err(_) => 0
        };

    if max_txns == 0 {
        return arg_error!("max-batch-size must be a number greater than 0");
    }

    let mut in_file = File::open(args.value_of("input").unwrap())?;
    let mut out_file = File::create(args.value_of("output").unwrap())?;

    if let Err(err) = generate_signed_batches(&mut in_file, &mut out_file, max_txns) {
        return Err(Box::new(err));
    }

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

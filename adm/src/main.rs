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

#[macro_use]
extern crate serde_derive;

mod blockstore;
mod commands;
mod config;
mod database;
mod err;
mod proto;
mod wrappers;

use clap::{clap_app, ArgMatches};

#[cfg(feature = "client-cli")]
use clap::{AppSettings, Arg, SubCommand};

const VERSION: &str = env!("CARGO_PKG_VERSION");

fn main() {
    let args = parse_args();

    let result = match args.subcommand() {
        ("blockstore", Some(args)) => commands::blockstore::run(args),
        ("keygen", Some(args)) => commands::keygen::run(args),
        ("genesis", Some(args)) => commands::genesis::run(args),
        #[cfg(feature = "client-cli")]
        ("batch", Some(args)) => commands::batch::run(args),
        _ => {
            println!("Invalid subcommand; Pass --help for usage.");
            Ok(())
        }
    };

    std::process::exit(match result {
        Ok(_) => 0,
        Err(err) => {
            eprintln!("Error: {}", err);
            1
        }
    });
}

fn parse_args<'a>() -> ArgMatches<'a> {
    let app = clap_app!(sawadm =>
        (version: VERSION)
        (about: "Manage a local validator keys and data files")
        (@subcommand blockstore =>
            (about: "manage the blockstore database directly")
            (@subcommand backup =>
                (about: "backup the entire blockstore database to a file")
                (@arg output: +required "the file to backup the blockstore to"))
            (@subcommand restore =>
                (about: "restore the entire blockstore database from a file")
                (@arg input: +required "the file to restore the blockstore from"))
            (@subcommand list =>
                (about: "list blocks from the block store")
                (@arg count: --count +takes_value "the number of blocks to list")
                (@arg start: --start +takes_value "the first block to list"))
            (@subcommand show =>
                (about: "inspect a block in the blockstore")
                (@arg block: -b --block +takes_value conflicts_with[batch transaction height]
                    "show a block based on block id")
                (@arg batch: -B --batch +takes_value conflicts_with[block transaction height]
                    "show a block based on batch id")
                (@arg transaction: -T --transaction +takes_value conflicts_with[block batch height]
                    "show a block based on transaction id")
             (@arg blocknum: -n --("block-num")
              +takes_value conflicts_with[block batch transaction]
                    "show a block based on height"))
            (@subcommand prune =>
                (about: "remove a block and all children blocks from the blockstore")
                (@arg block: +required "the block to remove"))
            (@subcommand export =>
                (about: "write a block's packed representation to file or stdout")
                (@arg block: +required "the block to export")
                (@arg output: -o --output +takes_value "the file to export the block to"))
            (@subcommand import =>
                (about: "add a block to the blockstore; new block's parent must be the current chain head")
                (@arg blockfile: +required "a protobuf file containing the block to add"))
            (@subcommand stats =>
                (about: "print out database stats")
                (@arg extended: -x --extended "show extended stats about the blockstore")))
        (@subcommand keygen =>
            (about: "generates keys for the validator to use when signing blocks")
            (@arg key_name: +takes_value "name of the key to create")
            (@arg force: --force "overwrite files if they exist")
            (@arg quiet: -q --quiet "do not display output"))
        (@subcommand genesis =>
            (about: "creates the genesis.batch file for initializing the validator")
            (@arg input_file:
             +takes_value ... "file or files containing batches to add to the resulting")
            (@arg output: -o --output "choose the output file for GenesisData")
            (@arg ignore_required_settings: --("ignore-required-settings")
             "skip the check for settings that are required at genesis (necessary if using a
              settings transaction family other than sawtooth_settings)"))
        (@arg verbose: -v... "increase the logging level.")
    );

    #[cfg(feature = "client-cli")]
    let app = app.subcommand(
        SubCommand::with_name("batch")
            .about(
                "display batch information and submit batches to the
                    validator via the REST API",
            )
            .setting(AppSettings::SubcommandRequiredElseHelp)
            .subcommands(vec![
                SubCommand::with_name("list")
                    .about(
                        "display information about all committed Batches for \
                            the specified validator, including the Batch id, public \
                            keys of all signers, and number of transactions in each Batch",
                    )
                    .arg(Arg::with_name("url").long("url").takes_value(true).help(
                        "identify the URL of the validator's \
                            REST API (default: http://localhost:8008)",
                    ))
                    .arg(
                        Arg::with_name("username")
                            .long("user")
                            .short("u")
                            .takes_value(true)
                            .help(
                                "specify the user to authorize request; \
                                    format: USERNAME[:PASSWORD]",
                            ),
                    )
                    .arg(
                        Arg::with_name("format")
                            .long("format")
                            .short("F")
                            .takes_value(true)
                            .possible_values(&["csv", "json", "yaml", "default"])
                            .help("choose the output format"),
                    ),
                SubCommand::with_name("show")
                    .about("Displays information for the specified Batch.")
                    .arg(
                        Arg::with_name("batch_id")
                            .required(true)
                            .takes_value(true)
                            .help("id (header signature) of the batch"),
                    )
                    .arg(Arg::with_name("url").long("url").takes_value(true).help(
                        "identify the URL of the validator's \
                            REST API (default: http://localhost:8008)",
                    ))
                    .arg(
                        Arg::with_name("username")
                            .long("user")
                            .short("u")
                            .takes_value(true)
                            .help(
                                "specify the user to authorize request; \
                                    format: USERNAME[:PASSWORD]",
                            ),
                    )
                    .arg(
                        Arg::with_name("key")
                            .long("key")
                            .short("k")
                            .takes_value(true)
                            .possible_values(&[
                                "header",
                                "header_signature",
                                "trace",
                                "transactions",
                                "signer_public_key",
                                "transaction_ids",
                            ])
                            .help("show a single property from the batch or header"),
                    )
                    .arg(
                        Arg::with_name("format")
                            .long("format")
                            .short("F")
                            .takes_value(true)
                            .possible_values(&["json", "yaml"])
                            .help("choose the output format (default: yaml)"),
                    ),
                SubCommand::with_name("status")
                    .about("Displays the status of the specified Batch id or ids.")
                    .arg(
                        Arg::with_name("batch_ids")
                            .required(true)
                            .takes_value(true)
                            .help("single batch id or comma-separated list of batch ids"),
                    )
                    .arg(Arg::with_name("url").long("url").takes_value(true).help(
                        "identify the URL of the validator's \
                            REST API (default: http://localhost:8008)",
                    ))
                    .arg(
                        Arg::with_name("username")
                            .long("user")
                            .short("u")
                            .takes_value(true)
                            .help(
                                "specify the user to authorize request; \
                                format: USERNAME[:PASSWORD]",
                            ),
                    )
                    .arg(
                        Arg::with_name("wait")
                            .long("wait")
                            .takes_value(true)
                            .help("set time, in seconds, to wait for commit"),
                    )
                    .arg(
                        Arg::with_name("format")
                            .long("format")
                            .short("F")
                            .takes_value(true)
                            .possible_values(&["json", "yaml"])
                            .help("choose the output format (default: yaml)"),
                    ),
            ]),
    );
    app.get_matches()
}

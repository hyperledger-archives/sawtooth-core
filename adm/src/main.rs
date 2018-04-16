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
extern crate clap;
extern crate libc;
extern crate lmdb_zero;
extern crate protobuf;
extern crate sawtooth_sdk;
extern crate serde;
#[macro_use]
extern crate serde_derive;
extern crate serde_yaml;

mod blockstore;
mod commands;
mod config;
mod database;
mod err;
mod wrappers;

use clap::ArgMatches;

const VERSION: &str = env!("CARGO_PKG_VERSION");

fn main() {
    let args = parse_args();

    let result = match args.subcommand() {
        ("blockstore", Some(args)) => commands::blockstore::run(args),
        ("keygen", Some(args)) => commands::keygen::run(args),
        ("genesis", Some(args)) => commands::genesis::run(args),
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
            (@arg output: -o --output "choose the output file for GenesisData"))
        (@arg verbose: -v... "increase the logging level.")
    );
    app.get_matches()
}

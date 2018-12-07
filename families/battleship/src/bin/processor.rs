// Copyright 2018 Bitwise IO, Inc.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

#[macro_use]
extern crate clap;
extern crate battleship;
#[macro_use]
extern crate log;
extern crate log4rs;
extern crate sawtooth_sdk;

use log::LevelFilter;
use log4rs::append::console::ConsoleAppender;
use log4rs::config::{Appender, Config, Root};
use log4rs::encode::pattern::PatternEncoder;
use std::process;

use sawtooth_sdk::processor::TransactionProcessor;

use battleship::handler::BattleshipTransactionHandler;

fn main() {
    let matches = clap_app!(battleship =>
        (version: crate_version!())
        (about: "Battleship Transaction Processor (Rust)")
        (@arg connect: -C --connect +takes_value "connection endpoint for validator")
        (@arg verbose: -v --verbose +multiple "increase output verbosity")
    )
    .get_matches();

    let endpoint = matches
        .value_of("connect")
        .unwrap_or("tcp://localhost:4004");

    let console_log_level = match matches.occurrences_of("verbose") {
        0 => LevelFilter::Warn,
        1 => LevelFilter::Info,
        2 => LevelFilter::Debug,
        3 | _ => LevelFilter::Trace,
    };

    let stdout = ConsoleAppender::builder()
        .encoder(Box::new(PatternEncoder::new(
            "{h({l:5.5})} | {({M}:{L}):20.20} | {m}{n}",
        )))
        .build();

    let config = match Config::builder()
        .appender(Appender::builder().build("stdout", Box::new(stdout)))
        .build(Root::builder().appender("stdout").build(console_log_level))
    {
        Ok(x) => x,
        Err(_) => process::exit(1),
    };

    match log4rs::init_config(config) {
        Ok(_) => (),
        Err(_) => process::exit(1),
    }

    info!("Console logging level: {}", console_log_level);

    let handler = BattleshipTransactionHandler::new();
    let mut processor = TransactionProcessor::new(endpoint);

    processor.add_handler(&handler);
    processor.start();
}

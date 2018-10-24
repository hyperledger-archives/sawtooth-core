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

extern crate clap;
extern crate cpython;
#[macro_use]
extern crate log;

mod pylogger;
mod server;

use cpython::Python;
use server::cli;

use std::process;

fn main() {
    let gil = Python::acquire_gil();
    let py = gil.python();

    let args = cli::parse_args();

    let verbosity: u64 = args.occurrences_of("verbose");

    pylogger::set_up_logger(verbosity, py);

    let pydict = cli::wrap_in_pydict(py, &args)
        .map_err(|err| err.print(py))
        .unwrap();

    let cli = match py.import("sawtooth_validator.server.cli") {
        Ok(module) => module,
        Err(err) => {
            pylogger::exception(py, "failed to load sawtooth_validator.server.cli", err);
            process::exit(1);
        }
    };

    if let Err(err) = cli.call(py, "main", (pydict,), None) {
        pylogger::exception(py, "error executing main", err);
        process::exit(1);
    }
}

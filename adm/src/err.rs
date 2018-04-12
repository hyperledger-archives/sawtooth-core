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

use std;

#[derive(Debug)]
pub enum CliError {
    ArgumentError(String),
    EnvironmentError(String),
    ParseError(String),
}

impl std::fmt::Display for CliError {
    fn fmt(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
        match *self {
            CliError::ArgumentError(ref msg) => write!(f, "ArgumentError: {}", msg),
            CliError::EnvironmentError(ref msg) => write!(f, "EnvironmentError: {}", msg),
            CliError::ParseError(ref msg) => write!(f, "ParseError: {}", msg),
        }
    }
}

impl std::error::Error for CliError {
    fn description(&self) -> &str {
        match *self {
            CliError::ArgumentError(ref msg) => msg,
            CliError::EnvironmentError(ref msg) => msg,
            CliError::ParseError(ref msg) => msg,
        }
    }

    fn cause(&self) -> Option<&std::error::Error> {
        match *self {
            CliError::ArgumentError(_) => None,
            CliError::EnvironmentError(_) => None,
            CliError::ParseError(_) => None,
        }
    }
}

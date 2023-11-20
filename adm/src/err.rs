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

use thiserror::Error;

use crate::database;

#[derive(Error, Debug)]
pub enum CliError {
    #[error("Argument error: {0}")]
    Argument(String),

    #[error("Database error: {0}")]
    Database(#[from] database::error::DatabaseError),

    #[error("Environment error: {0}")]
    Environment(String),

    #[error("Io error: {0}")]
    Io(#[from] std::io::Error),

    #[error("Nul error: {0}")]
    Nul(#[from] std::ffi::NulError),

    #[error("Parse error: {0}")]
    Parse(String),

    #[error("Signing error: {0}")]
    Signing(#[from] sawtooth_sdk::signing::Error),
}

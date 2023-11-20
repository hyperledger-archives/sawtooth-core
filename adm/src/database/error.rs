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

use std::string::FromUtf8Error;

use thiserror::Error;

#[derive(Error, Debug)]
pub enum DatabaseError {
    #[error("Init error: {0}")]
    Init(String),

    #[error("LmDb error: {0}")]
    Lmdb(#[from] lmdb_zero::error::Error),

    #[error("Could not interpret stored data as a block: {0}")]
    Protobuf(#[from] protobuf::ProtobufError),

    #[error("Reader error: {0}")]
    Reader(String),

    #[error("Writer error: {0}")]
    Writer(String),

    #[error("Chain head block id is corrupt: {0}")]
    Corruption(#[from] FromUtf8Error),

    #[error("Unable to read chain head: {0}")]
    NotFound(String),
}

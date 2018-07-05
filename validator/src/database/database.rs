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
pub enum DatabaseError {
    InitError(String),
    ReaderError(String),
    WriterError(String),
    CorruptionError(String),
    NotFoundError(String),
    DuplicateEntry,
}

impl std::fmt::Display for DatabaseError {
    fn fmt(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
        match *self {
            DatabaseError::InitError(ref msg) => write!(f, "InitError: {}", msg),
            DatabaseError::ReaderError(ref msg) => write!(f, "ReaderError: {}", msg),
            DatabaseError::WriterError(ref msg) => write!(f, "WriterError: {}", msg),
            DatabaseError::CorruptionError(ref msg) => write!(f, "CorruptionError: {}", msg),
            DatabaseError::NotFoundError(ref msg) => write!(f, "NotFoundError: {}", msg),
            DatabaseError::DuplicateEntry => write!(f, "DuplicateEntry"),
        }
    }
}

impl std::error::Error for DatabaseError {
    fn description(&self) -> &str {
        match *self {
            DatabaseError::InitError(ref msg) => msg,
            DatabaseError::ReaderError(ref msg) => msg,
            DatabaseError::WriterError(ref msg) => msg,
            DatabaseError::CorruptionError(ref msg) => msg,
            DatabaseError::NotFoundError(ref msg) => msg,
            DatabaseError::DuplicateEntry => "DuplicateEntry",
        }
    }

    fn cause(&self) -> Option<&std::error::Error> {
        match *self {
            DatabaseError::InitError(_) => None,
            DatabaseError::ReaderError(_) => None,
            DatabaseError::WriterError(_) => None,
            DatabaseError::CorruptionError(_) => None,
            DatabaseError::NotFoundError(_) => None,
            DatabaseError::DuplicateEntry => None,
        }
    }
}

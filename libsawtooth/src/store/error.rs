// Copyright 2019 Cargill Incorporated
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

use std::error::Error;
use std::fmt::Debug;

#[derive(Debug)]
pub enum OrderedStoreError {
    BytesParsingFailed(String),
    InitializationFailed(String),
    Internal(Box<dyn Error>),
    LockPoisoned(String),
    StoreCorrupted(String),
    ValueAlreadyExistsAtIndex(Box<dyn Debug>),
    ValueAlreadyExistsForKey(Box<dyn Debug>),
}

impl Error for OrderedStoreError {
    fn source(&self) -> Option<&(dyn Error + 'static)> {
        match self {
            Self::BytesParsingFailed(_) => None,
            Self::InitializationFailed(_) => None,
            Self::Internal(err) => Some(&**err),
            Self::LockPoisoned(_) => None,
            Self::StoreCorrupted(_) => None,
            Self::ValueAlreadyExistsForKey(_) => None,
            Self::ValueAlreadyExistsAtIndex(_) => None,
        }
    }
}

impl std::fmt::Display for OrderedStoreError {
    fn fmt(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
        match self {
            Self::BytesParsingFailed(err) => write!(f, "failed to parse from bytes: {}", err),
            Self::InitializationFailed(err) => {
                write!(f, "failed to initialize ordered store: {}", err)
            }
            Self::Internal(err) => write!(f, "internal error occurred: {}", err),
            Self::LockPoisoned(err) => write!(f, "a lock was poisoned: {}", err),
            Self::StoreCorrupted(err) => write!(f, "ordered store is corrupted: {}", err),
            Self::ValueAlreadyExistsForKey(key) => {
                write!(f, "value already exists for key: {:?}", key)
            }
            Self::ValueAlreadyExistsAtIndex(idx) => {
                write!(f, "value already exists at index: {:?}", idx)
            }
        }
    }
}

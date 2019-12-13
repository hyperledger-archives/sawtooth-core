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

use crate::store::OrderedStoreError;

#[derive(Debug)]
pub enum TransactionReceiptStoreError {
    IdNotFound, // used by the `iter_since_id` method if the given ID is not in the store
    Internal(OrderedStoreError),
}

impl Error for TransactionReceiptStoreError {
    fn source(&self) -> Option<&(dyn Error + 'static)> {
        match self {
            Self::IdNotFound => None,
            Self::Internal(err) => Some(err),
        }
    }
}

impl std::fmt::Display for TransactionReceiptStoreError {
    fn fmt(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
        match self {
            Self::IdNotFound => write!(f, "id not found in the store"),
            Self::Internal(err) => write!(f, "an internal error occurred: {}", err),
        }
    }
}

impl From<OrderedStoreError> for TransactionReceiptStoreError {
    fn from(err: OrderedStoreError) -> Self {
        Self::Internal(err)
    }
}

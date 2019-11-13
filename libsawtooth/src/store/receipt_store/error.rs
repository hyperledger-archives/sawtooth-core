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
pub struct TransactionReceiptStoreError(OrderedStoreError);

impl Error for TransactionReceiptStoreError {
    fn source(&self) -> Option<&(dyn Error + 'static)> {
        Some(&self.0)
    }
}

impl std::fmt::Display for TransactionReceiptStoreError {
    fn fmt(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
        write!(f, "error in transaction receipt store: {}", self.0)
    }
}

impl From<OrderedStoreError> for TransactionReceiptStoreError {
    fn from(err: OrderedStoreError) -> Self {
        Self(err)
    }
}

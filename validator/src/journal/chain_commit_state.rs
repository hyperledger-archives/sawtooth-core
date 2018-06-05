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

use std::collections::HashSet;

use cpython;
use cpython::ObjectProtocol;

use batch::Batch;

pub struct TransactionCommitCache {
    committed: HashSet<String>,

    blockstore: cpython::PyObject,
}

impl TransactionCommitCache {
    pub fn new(blockstore: cpython::PyObject) -> Self {
        TransactionCommitCache {
            committed: HashSet::new(),
            blockstore,
        }
    }

    pub fn add(&mut self, transaction_id: String) {
        self.committed.insert(transaction_id);
    }

    pub fn add_batch(&mut self, batch: &Batch) {
        batch
            .transactions
            .iter()
            .for_each(|txn| self.add(txn.header_signature.clone()));
    }

    pub fn remove(&mut self, transaction_id: &str) {
        self.committed.remove(transaction_id);
    }

    pub fn remove_batch(&mut self, batch: &Batch) {
        batch
            .transactions
            .iter()
            .for_each(|txn| self.remove(txn.header_signature.as_str()));
    }

    pub fn contains(&self, transaction_id: &str) -> bool {
        self.committed.contains(transaction_id) || self.blockstore_has_txn(transaction_id)
    }

    fn blockstore_has_txn(&self, transaction_id: &str) -> bool {
        let gil = cpython::Python::acquire_gil();
        let py = gil.python();
        self.blockstore
            .call_method(py, "has_transaction", (transaction_id,), None)
            .unwrap()
            .extract::<bool>(py)
            .unwrap()
    }
}

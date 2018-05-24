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
use cpython::PyClone;

use batch::Batch;
use transaction::Transaction;

use journal::chain_commit_state::TransactionCommitCache;

use scheduler::Scheduler;

pub enum BlockPublisherError {
    ConsensusNotReady,
    NoPendingBatchesRemaining,
}

pub struct CandidateBlock {
    block_store: cpython::PyObject,
    consensus: cpython::PyObject,
    scheduler: Box<Scheduler>,
    max_batches: usize,
    block_builder: cpython::PyObject,
    batch_injectors: cpython::PyObject,
    identity_signer: cpython::PyObject,
    settings_view: cpython::PyObject,
    permission_verifier: cpython::PyObject,

    pending_batches: Vec<Batch>,
    pending_batch_ids: HashSet<String>,
    injected_batch_ids: HashSet<String>,

    committed_txn_cache: TransactionCommitCache,
}

impl CandidateBlock {
    pub fn new(
        block_store: cpython::PyObject,
        consensus: cpython::PyObject,
        scheduler: Box<Scheduler>,
        committed_txn_cache: TransactionCommitCache,
        block_builder: cpython::PyObject,
        max_batches: usize,
        batch_injectors: cpython::PyObject,
        identity_signer: cpython::PyObject,
        settings_view: cpython::PyObject,
        permission_verifier: cpython::PyObject,
    ) -> Self {
        CandidateBlock {
            block_store,
            consensus,
            scheduler,
            max_batches,
            committed_txn_cache,
            block_builder,
            batch_injectors,
            identity_signer,
            permission_verifier,
            settings_view,
            pending_batches: vec![],
            pending_batch_ids: HashSet::new(),
            injected_batch_ids: HashSet::new(),
        }
    }

    pub fn cancel(&mut self) {
        self.scheduler.cancel().unwrap();
    }

    pub fn previous_block_id(&self) -> String {
        let py = unsafe { cpython::Python::assume_gil_acquired() };
        self.block_builder
            .getattr(py, "previous_block_id")
            .expect("BlockBuilder has no attribute 'previous_block_id'")
            .extract::<String>(py)
            .unwrap()
    }

    pub fn last_batch(&self) -> Option<&Batch> {
        self.pending_batches.last()
    }

    pub fn can_add_batch(&self) -> bool {
        self.max_batches == 0 || self.pending_batches.len() < self.max_batches
    }

    fn check_batch_dependencies(&mut self, batch: &Batch) -> bool {
        for txn in &batch.transactions {
            if self.txn_is_already_committed(txn, &self.committed_txn_cache) {
                debug!(
                    "Transaction rejected as it is already in the chain {}",
                    txn.header_signature
                );
                return false;
            } else if !self.check_transaction_dependencies(txn) {
                self.committed_txn_cache.remove_batch(batch);
                return false;
            }
            self.committed_txn_cache.add(txn.header_signature.clone());
        }
        true
    }

    fn check_transaction_dependencies(&self, txn: &Transaction) -> bool {
        for dep in &txn.dependencies {
            if !self.committed_txn_cache.contains(dep.as_str()) {
                debug!(
                    "Transaction rejected due to missing dependency, transaction {} depends on {}",
                    txn.header_signature.as_str(),
                    dep.as_str()
                );
                return false;
            }
        }
        true
    }

    fn txn_is_already_committed(
        &self,
        txn: &Transaction,
        committed_txn_cache: &TransactionCommitCache,
    ) -> bool {
        committed_txn_cache.contains(txn.header_signature.as_str()) || {
            let py = unsafe { cpython::Python::assume_gil_acquired() };
            self.block_store
                .call_method(py, "has_batch", (txn.header_signature.as_str(),), None)
                .expect("Blockstore has no method 'has_batch'")
                .extract::<bool>(py)
                .unwrap()
        }
    }

    fn batch_is_already_committed(&self, batch: &Batch) -> bool {
        self.pending_batch_ids
            .contains(batch.header_signature.as_str()) || {
            let py = unsafe { cpython::Python::assume_gil_acquired() };
            self.block_store
                .call_method(py, "has_batch", (batch.header_signature.as_str(),), None)
                .expect("Blockstore has no method 'has_batch'")
                .extract::<bool>(py)
                .unwrap()
        }
    }
}

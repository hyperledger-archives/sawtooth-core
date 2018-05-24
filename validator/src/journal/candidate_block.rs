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
use cpython::ToPyObject;

use batch::Batch;
use transaction::Transaction;

use journal::chain_commit_state::TransactionCommitCache;

use pylogger;

use scheduler::Scheduler;

pub enum BlockPublisherError {
    ConsensusNotReady,
    NoPendingBatchesRemaining,
}

pub struct FinalizeBlockResult {
    block: Option<cpython::PyObject>,
    remaining_batches: Vec<Batch>,
    last_batch: Option<Batch>,
    injected_batch_ids: Vec<String>,
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

    fn poll_injectors<F: Fn(cpython::PyObject) -> Vec<cpython::PyObject>>(
        &self,
        poller: F,
    ) -> Vec<Batch> {
        let mut batches = vec![];
        let py = unsafe { cpython::Python::assume_gil_acquired() };
        for injector in self.batch_injectors
            .extract::<cpython::PyList>(py)
            .unwrap()
            .iter(py)
        {
            let inject_list = poller(injector);
            if !inject_list.is_empty() {
                for b in inject_list {
                    match b.extract(py) {
                        Ok(b) => batches.push(b),
                        Err(err) => pylogger::exception(py, "During batch injection", err),
                    }
                }
            }
        }
        batches
    }

    pub fn add_batch(&mut self, batch: Batch) {
        let batch_header_signature = batch.header_signature.clone();

        let py = unsafe { cpython::Python::assume_gil_acquired() };
        if batch.trace {
            debug!(
                "TRACE {}: {}",
                batch_header_signature.as_str(),
                "CandidateBlock, add_batch"
            );
        }

        if self.batch_is_already_committed(&batch) {
            debug!(
                "Dropping previously committed batch: {}",
                batch_header_signature.as_str()
            );
            return;
        } else if self.check_batch_dependencies(&batch) {
            let mut batches_to_add = vec![];

            // Inject blocks at the beginning of a Candidate Block
            if self.pending_batches.is_empty() {
                let mut injected_batches = self.poll_injectors(|injector: cpython::PyObject| {
                    match injector
                        .call_method(py, "block_start", (self.previous_block_id(),), None)
                        .expect("BlockInjector has not method 'block_start'")
                        .extract::<cpython::PyList>(py)
                    {
                        Ok(injected) => injected.iter(py).collect(),
                        Err(err) => {
                            pylogger::exception(
                                py,
                                "During block injection, calling block_start",
                                err,
                            );
                            vec![]
                        }
                    }
                });
                batches_to_add.append(&mut injected_batches);
            }

            let validation_enforcer = py.import(
                "sawtooth_validator.journal.validation_rule_inforcer",
            ).expect("Unable to import sawtooth_validator.journal.validation_rule_inforcer");
            let batches = cpython::PyList::new(
                py,
                &self.pending_batches
                    .iter()
                    .map(|b| b.to_py_object(py))
                    .chain(batches_to_add.iter().map(|b| b.to_py_object(py)))
                    .collect::<Vec<cpython::PyObject>>(),
            );
            let signer_pub_key = self.identity_signer
                .call_method(py, "get_public_key", cpython::NoArgs, None)
                .expect("IdentitySigner has no method 'get_public_key'")
                .call_method(py, "as_hex", cpython::NoArgs, None)
                .expect("PublicKey has no method 'as_hex'");
            if !validation_enforcer
                .call(
                    py,
                    "enforce_validation_rules",
                    (self.settings_view.clone_ref(py), signer_pub_key, batches),
                    None,
                )
                .expect(
                    "Module validation_rule_enforcer has no function 'enforce_validation_rules'",
                )
                .extract::<bool>(py)
                .unwrap()
            {
                return;
            }

            batches_to_add.push(batch);

            for b in batches_to_add {
                let batch_id = b.header_signature.clone();
                self.pending_batches.push(b.clone());
                self.pending_batch_ids.insert(batch_id.clone());

                let injected = self.injected_batch_ids.contains(batch_id.as_str());

                self.scheduler.add_batch(b, None, injected).unwrap()
            }
        } else {
            debug!(
                "Dropping batch due to missing dependencies: {}",
                batch_header_signature.as_str()
            );
        }
    }

    pub fn sign_block(&self, block_builder: &cpython::PyObject) {
        let py = unsafe { cpython::Python::assume_gil_acquired() };
        let header_bytes = block_builder
            .getattr(py, "block_header")
            .expect("BlockBuilder has no attribute 'block_header'")
            .call_method(py, "SerializeToString", cpython::NoArgs, None)
            .unwrap();
        let signature = self.identity_signer
            .call_method(py, "sign", (header_bytes,), None)
            .expect("Signer has no method 'sign'");
        block_builder
            .call_method(py, "set_signature", (signature,), None)
            .expect("BlockBuilder has no method 'set_signature'");
    }

    fn check_publish_block(&self, py: cpython::Python, block_builder: &cpython::PyObject) -> bool {
        self.consensus
            .call_method(
                py,
                "check_publish_block",
                (block_builder
                    .getattr(py, "block_header")
                    .expect("BlockBuilder has no attribute 'block_header'"),),
                None,
            )
            .expect("consensus has no method 'check_publish_block'")
            .extract::<bool>(py)
            .unwrap()
    }

    pub fn finalize(&mut self, force: bool) -> Result<FinalizeBlockResult, BlockPublisherError> {
        if !force || self.pending_batches.is_empty() {
            return Err(BlockPublisherError::NoPendingBatchesRemaining);
        }
        let py = unsafe { cpython::Python::assume_gil_acquired() };
        if !self.check_publish_block(py, &self.block_builder) {
            return Err(BlockPublisherError::ConsensusNotReady);
        }

        self.scheduler.finalize(true).unwrap();
        let execution_results = self.scheduler.complete(true).unwrap().unwrap();

        let mut committed_txn_cache = TransactionCommitCache::new(self.block_store.clone_ref(py));

        let batches_w_no_results: Vec<String> = execution_results
            .batch_results
            .iter()
            .filter(|(_, txns)| txns.is_none())
            .map(|(batch_id, _)| batch_id.clone())
            .collect();

        let valid_batch_ids: Vec<String> = execution_results
            .batch_results
            .into_iter()
            .filter(|(_, txns)| match txns {
                Some(t) => !t.iter().any(|t| !t.is_valid),
                None => false,
            })
            .map(|(b_id, _)| b_id)
            .collect();

        let builder = self.block_builder.clone_ref(py);

        let mut bad_batches = vec![];
        let mut pending_batches = vec![];

        for batch in self.pending_batches.clone() {
            let header_signature = &batch.header_signature.clone();
            if batch.trace {
                debug!("TRACE {} : CandidateBlock finalize", header_signature)
            }

            if batches_w_no_results.contains(&batch.header_signature) {
                if !self.injected_batch_ids
                    .contains(batch.header_signature.as_str())
                {
                    pending_batches.push(batch)
                } else {
                    warn! {
                        "Failed to inject batch {}",
                        header_signature
                    };
                }
            } else if valid_batch_ids.contains(&batch.header_signature) {
                if !self.check_batch_dependencies(&batch) {
                    debug!(
                        "Batch {} is invalid, due to missing txn dependency",
                        header_signature
                    );
                    bad_batches.push(batch.clone());
                    pending_batches.clear();
                    pending_batches.append(&mut self.pending_batches
                        .clone()
                        .into_iter()
                        .filter(|b| !bad_batches.contains(b))
                        .collect());
                    return Ok(self.build_result(None, pending_batches));
                } else {
                    builder
                        .call_method(py, "add_batch", (batch.clone(),), None)
                        .expect("BlockBuilder has no method 'add_batch'");
                    committed_txn_cache.add_batch(&batch.clone());
                }
            } else {
                bad_batches.push(batch.clone());
                debug!("Batch {} invalid, not added to block", header_signature);
            }
        }
        if execution_results.ending_state_hash.is_none()
            || builder
                .getattr(py, "batches")
                .expect("BlockBuilder has no attribute 'batches'")
                .extract::<cpython::PyList>(py)
                .unwrap()
                .len(py) == 0
        {
            debug!("Abandoning block, no batches added");
            return Ok(self.build_result(None, self.pending_batches.clone()));
        }
        let block_header = builder
            .getattr(py, "block_header")
            .expect("BlockBuilder has no attribute 'block_header'");
        if !self.consensus
            .call_method(py, "finalize_block", (block_header,), None)
            .expect("Consensus has no method 'finalize_block'")
            .extract::<bool>(py)
            .unwrap()
        {
            debug!("Abandoning block consensus failed to finalize it");
            pending_batches.clear();
            pending_batches.append(&mut self.pending_batches
                .clone()
                .into_iter()
                .filter(|b| !bad_batches.contains(b))
                .collect());
            return Ok(self.build_result(None, pending_batches));
        }

        builder
            .call_method(
                py,
                "set_state_hash",
                (execution_results.ending_state_hash.unwrap(),),
                None,
            )
            .expect("BlockBuilder has no method 'set_state_hash'");
        self.sign_block(&builder);

        Ok(self.build_result(
            Some(
                builder
                    .call_method(py, "build_block", cpython::NoArgs, None)
                    .expect("BlockBuilder has no method 'build_block'"),
            ),
            pending_batches,
        ))
    }

    fn build_result(
        &self,
        block: Option<cpython::PyObject>,
        remaining: Vec<Batch>,
    ) -> FinalizeBlockResult {
        FinalizeBlockResult {
            block,
            remaining_batches: remaining,
            last_batch: self.last_batch().cloned(),
            injected_batch_ids: self.injected_batch_ids
                .clone()
                .into_iter()
                .collect::<Vec<String>>(),
        }
    }
}

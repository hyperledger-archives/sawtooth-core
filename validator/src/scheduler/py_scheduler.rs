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

use std::error::Error;

use cpython;
use cpython::ObjectProtocol;
use cpython::PyResult;

use batch::Batch;

use protobuf::ProtobufError;

use scheduler::execution_result_ffi::{PyBatchExecutionResult, PyTxnExecutionResult};
use scheduler::{ExecutionResults, Scheduler, SchedulerError};

impl From<ProtobufError> for SchedulerError {
    fn from(other: ProtobufError) -> SchedulerError {
        SchedulerError::Other(other.description().into())
    }
}

impl From<cpython::PyErr> for SchedulerError {
    fn from(other: cpython::PyErr) -> SchedulerError {
        let gil = cpython::Python::acquire_gil();
        let py = gil.python();
        SchedulerError::Other(other.get_type(py).name(py).into_owned())
    }
}

type CombinedOptionalBatchResult = Vec<(
    Vec<PyTxnExecutionResult>,
    Option<PyBatchExecutionResult>,
    String,
)>;

pub struct PyScheduler {
    py_scheduler: cpython::PyObject,
    batch_ids: Vec<String>,
}

impl PyScheduler {
    pub fn new(py_scheduler: cpython::PyObject) -> PyScheduler {
        PyScheduler {
            py_scheduler,
            batch_ids: vec![],
        }
    }

    fn is_complete(&self, block: bool) -> Result<bool, SchedulerError> {
        let gil = cpython::Python::acquire_gil();
        let py = gil.python();
        Ok(self
            .py_scheduler
            .call_method(py, "complete", (block,), None)
            .expect("No method complete on python scheduler")
            .extract::<bool>(py)?)
    }
}

impl Scheduler for PyScheduler {
    fn add_batch(
        &mut self,
        batch: Batch,
        expected_state_hash: Option<&str>,
        required: bool,
    ) -> Result<(), SchedulerError> {
        let header_signature = batch.header_signature.clone();
        let gil = cpython::Python::acquire_gil();
        let py = gil.python();

        self.py_scheduler
            .call_method(
                py,
                "add_batch",
                (batch, expected_state_hash, required),
                None,
            ).expect("No method add_batch on python scheduler");

        self.batch_ids.push(header_signature);
        Ok(())
    }

    fn finalize(&mut self, unschedule_incomplete: bool) -> Result<(), SchedulerError> {
        let gil = cpython::Python::acquire_gil();
        let py = gil.python();

        if unschedule_incomplete {
            self.py_scheduler
                .call_method(py, "unschedule_incomplete_batches", cpython::NoArgs, None)
                .expect("No method unscheduler_incomplete_batches on python scheduler");
        }

        self.py_scheduler
            .call_method(py, "finalize", cpython::NoArgs, None)
            .expect("No method finalize on python scheduler");
        Ok(())
    }

    fn cancel(&mut self) -> Result<(), SchedulerError> {
        let gil = cpython::Python::acquire_gil();
        let py = gil.python();

        self.py_scheduler
            .call_method(py, "cancel", cpython::NoArgs, None)
            .expect("No method cancel on python scheduler");
        Ok(())
    }

    fn complete(&mut self, block: bool) -> Result<Option<ExecutionResults>, SchedulerError> {
        if self.is_complete(block)? {
            let results = self
                .batch_ids
                .iter()
                .map(|id| {
                    let gil = cpython::Python::acquire_gil();
                    let py = gil.python();
                    let batch_result: Option<PyBatchExecutionResult> = self
                        .py_scheduler
                        .call_method(py, "get_batch_execution_result", (id,), None)
                        .expect("No method get_batch_execution_result on python scheduler")
                        .extract(py)?;

                    if batch_result.is_some() {
                        let txn_results: Vec<PyTxnExecutionResult> = self
                            .py_scheduler
                            .call_method(py, "get_transaction_execution_results", (id,), None)
                            .expect(
                                "No method get_transaction_execution_results on python scheduler",
                            ).extract(py)?;

                        Ok((txn_results, batch_result, id.to_owned()))
                    } else {
                        Ok((vec![], None, id.to_owned()))
                    }
                }).collect::<PyResult<CombinedOptionalBatchResult>>()?;

            let beginning_state_hash = results
                .first()
                .map(|v| v.0.first().map(|r| r.state_hash.clone()).unwrap_or(None))
                .unwrap_or(None);

            let ending_state_hash = results
                .iter()
                .by_ref()
                .map(|val| val.1.clone())
                .filter(|batch_result| batch_result.is_some())
                .find(|batch_result| {
                    batch_result
                        .clone()
                        .expect("Failed to unwrap batch result to check state hash")
                        .state_hash
                        .is_some()
                }).map(|batch_result| {
                    batch_result
                        .expect("Failed to unwrap batch result to get state hash")
                        .state_hash
                }).unwrap_or(None);

            let batch_txn_results = results
                .into_iter()
                .map(|val| match val.1 {
                    Some(_) => (
                        val.2.clone(),
                        Some(
                            val.0
                                .into_iter()
                                .map(|v: PyTxnExecutionResult| v.into())
                                .collect(),
                        ),
                    ),
                    None => (val.2.clone(), None),
                }).collect();

            Ok(Some(ExecutionResults {
                beginning_state_hash: beginning_state_hash,
                ending_state_hash,
                batch_results: batch_txn_results,
            }))
        } else {
            Ok(None)
        }
    }
}

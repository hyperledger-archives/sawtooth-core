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

use scheduler::{BatchResult, TransactionResult};
use scheduler::{ExecutionResults, Scheduler, SchedulerError};

impl From<ProtobufError> for SchedulerError {
    fn from(other: ProtobufError) -> SchedulerError {
        SchedulerError::Other(other.description().into())
    }
}

impl From<cpython::PyErr> for SchedulerError {
    fn from(other: cpython::PyErr) -> SchedulerError {
        let py = unsafe { cpython::Python::assume_gil_acquired() };
        SchedulerError::Other(other.get_type(py).name(py).into_owned())
    }
}

type CombinedOptionalBatchResult = Vec<(Vec<TransactionResult>, Option<BatchResult>, String)>;

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
}

impl Scheduler for PyScheduler {
    fn add_batch(
        &mut self,
        batch: Batch,
        expected_state_hash: Option<&str>,
        required: bool,
    ) -> Result<(), SchedulerError> {
        let header_signature = batch.header_signature.clone();

        let state_hash_kwargs: Result<Option<cpython::PyDict>, cpython::PyErr> =
            expected_state_hash
                .map(|state_hash| {
                    let py = unsafe { cpython::Python::assume_gil_acquired() };
                    let kwargs = cpython::PyDict::new(py);
                    kwargs.set_item(py, "state_hash", state_hash)?;
                    kwargs.set_item(py, "required", required)?;
                    Ok(kwargs)
                })
                .map_or(Ok(None), |v: Result<cpython::PyDict, cpython::PyErr>| {
                    Ok(Some(v?))
                });
        let py = unsafe { cpython::Python::assume_gil_acquired() };
        self.py_scheduler
            .call_method(py, "add_batch", (batch,), state_hash_kwargs?.as_ref())
            .expect("No method add_batch on python scheduler");
        self.batch_ids.push(header_signature);
        Ok(())
    }

    fn finalize(&mut self, unschedule_incomplete: bool) -> Result<(), SchedulerError> {
        let py = unsafe { cpython::Python::assume_gil_acquired() };

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
        let py = unsafe { cpython::Python::assume_gil_acquired() };

        self.py_scheduler
            .call_method(py, "cancel", cpython::NoArgs, None)
            .expect("No method cancel on python scheduler");
        Ok(())
    }

    fn complete(&mut self, block: bool) -> Result<Option<ExecutionResults>, SchedulerError> {
        let py = unsafe { cpython::Python::assume_gil_acquired() };

        if self.py_scheduler
            .call_method(py, "complete", (block,), None)
            .expect("No method complete on python scheduler")
            .extract::<bool>(py)?
        {
            let r: PyResult<CombinedOptionalBatchResult> = self.batch_ids
                .iter()
                .map(|id| {
                    let batch_result: cpython::PyObject = self.py_scheduler
                        .call_method(py, "get_batch_execution_result", (id,), None)
                        .expect("No method get_batch_execution_result on python scheduler");
                    if batch_result.is_true(py).unwrap() {
                        let result = batch_result.extract::<BatchResult>(py).unwrap();

                        let txn_results: Vec<TransactionResult> = self.py_scheduler
                            .call_method(py, "get_transaction_execution_results", (id,), None)
                            .expect(
                                "No method get_transaction_execution_results on python scheduler",
                            )
                            .extract::<cpython::PyList>(py)?
                            .iter(py)
                            .map(|r| r.extract::<TransactionResult>(py))
                            .collect::<Result<Vec<TransactionResult>, cpython::PyErr>>()?;

                        Ok((txn_results, Some(result), id.to_owned()))
                    } else {
                        Ok((vec![], None, id.to_owned()))
                    }
                })
                .collect();

            let results = r?;

            let beginning_state_hash = results
                .first()
                .map(|v| v.0.first().map(|r| r.state_hash.clone()))
                .unwrap_or(None);

            let ending_state_hash = results
                .iter()
                .by_ref()
                .map(|val| val.1.clone())
                .filter(|batch_result| batch_result.is_some())
                .find(|batch_result| batch_result.clone().unwrap().state_hash.is_some())
                .map(|batch_result| batch_result.unwrap().state_hash)
                .unwrap_or(None);

            let batch_txn_results = results
                .into_iter()
                .map(|val| match val.1 {
                    Some(_) => (
                        val.2.clone(),
                        Some(
                            val.0
                                .into_iter()
                                .map(|v: TransactionResult| v.into())
                                .collect(),
                        ),
                    ),
                    None => (val.2.clone(), None),
                })
                .collect();

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

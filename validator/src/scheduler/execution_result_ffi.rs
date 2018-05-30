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

use cpython;
use cpython::FromPyObject;
use cpython::ObjectProtocol;

use proto::events::Event;
use proto::transaction_receipt::StateChange;

use scheduler::TxnExecutionResult;

#[derive(Clone)]
pub struct BatchResult {
    pub state_hash: Option<String>,
}

/// TransactionResult is a Rust struct that mirrors
/// what is passed from a Python Scheduler's get_transaction_execution_results
/// method.
pub struct TransactionResult {
    pub signature: String,
    pub is_valid: bool,
    pub state_hash: String,
    pub state_changes: Vec<StateChange>,
    pub events: Vec<Event>,
    pub data: Vec<(String, Vec<u8>)>,
    pub error_message: String,
    pub error_data: Vec<u8>,
}

impl<'source> FromPyObject<'source> for BatchResult {
    fn extract(py: cpython::Python, obj: &'source cpython::PyObject) -> cpython::PyResult<Self> {
        let state_hash = obj.getattr(py, "state_hash").unwrap();

        let sh = state_hash.extract::<String>(py)?;

        Ok(BatchResult {
            state_hash: Some(sh),
        })
    }
}

impl<'source> FromPyObject<'source> for TransactionResult {
    fn extract(py: cpython::Python, obj: &'source cpython::PyObject) -> cpython::PyResult<Self> {
        Ok(try_pyobj_to_transaction_result(py, obj)?)
    }
}

impl<'source> FromPyObject<'source> for TxnExecutionResult {
    fn extract(py: cpython::Python, obj: &'source cpython::PyObject) -> cpython::PyResult<Self> {
        Ok(TxnExecutionResult::from(try_pyobj_to_transaction_result(
            py, obj,
        )?))
    }
}

impl From<TransactionResult> for TxnExecutionResult {
    fn from(other: TransactionResult) -> Self {
        TxnExecutionResult {
            signature: other.signature,
            is_valid: other.is_valid,
            state_changes: other.state_changes,
            events: other.events,
            data: other.data,
            error_message: other.error_message,
            error_data: other.error_data,
        }
    }
}

fn try_pyobj_to_transaction_result(
    py: cpython::Python,
    pyobj: &cpython::PyObject,
) -> Result<TransactionResult, cpython::PyErr> {
    let signature = return_string_from_pyobj(pyobj, py, "signature")?;
    let is_valid = return_bool_from_pyobj(pyobj, py, "is_valid")?;
    let beginning_state_hash = return_string_from_pyobj(pyobj, py, "state_hash")?;
    let state_changes = return_statechanges_from_pyobj(pyobj, py, "state_changes")?;
    let events = return_events_from_pyobj(pyobj, py, "events")?;
    let data = return_data_from_pyobj(pyobj, py, "data")?;
    let error_message = return_string_from_pyobj(pyobj, py, "error_message")?;
    let error_data = return_owned_bytes_from_pyobj(pyobj, py, "error_data")?;

    Ok(TransactionResult {
        signature,
        is_valid,
        state_hash: beginning_state_hash,
        state_changes,
        events,
        data,
        error_message,
        error_data,
    })
}

fn return_string_from_pyobj(
    pydict: &cpython::PyObject,
    py: cpython::Python,
    item_name: &str,
) -> Result<String, cpython::PyErr> {
    Ok(pydict
        .getattr(py, item_name)
        .unwrap()
        .extract::<String>(py)?)
}

fn return_bool_from_pyobj(
    pydict: &cpython::PyObject,
    py: cpython::Python,
    item_name: &str,
) -> Result<bool, cpython::PyErr> {
    Ok(pydict.getattr(py, item_name).unwrap().extract::<bool>(py)?)
}

fn return_statechanges_from_pyobj(
    pydict: &cpython::PyObject,
    py: cpython::Python,
    item_name: &str,
) -> Result<Vec<StateChange>, cpython::PyErr> {
    pydict
        .getattr(py, item_name)?
        .extract::<cpython::PyList>(py)
        .unwrap()
        .iter(py)
        .map(|b| {
            let state_change_bytes = b.call_method(py, "SerializeToString", cpython::NoArgs, None)
                .unwrap()
                .extract::<Vec<u8>>(py)?;
            let state_change: StateChange =
                ::protobuf::parse_from_bytes(state_change_bytes.as_slice()).unwrap();
            Ok(state_change)
        })
        .collect::<Result<Vec<StateChange>, cpython::PyErr>>()
}

fn return_events_from_pyobj(
    pydict: &cpython::PyObject,
    py: cpython::Python,
    item_name: &str,
) -> Result<Vec<Event>, cpython::PyErr> {
    pydict
        .getattr(py, item_name)?
        .extract::<cpython::PyList>(py)?
        .iter(py)
        .map(|e| {
            let event_bytes = e.call_method(py, "SerializeToString", cpython::NoArgs, None)
                .unwrap()
                .extract::<Vec<u8>>(py)?;
            let event: Event = ::protobuf::parse_from_bytes(event_bytes.as_slice()).unwrap();
            Ok(event)
        })
        .collect::<Result<Vec<Event>, cpython::PyErr>>()
}

fn return_data_from_pyobj(
    pydict: &cpython::PyObject,
    py: cpython::Python,
    item_name: &str,
) -> Result<Vec<(String, Vec<u8>)>, cpython::PyErr> {
    pydict
        .getattr(py, item_name)
        .unwrap()
        .extract::<cpython::PyList>(py)?
        .iter(py)
        .map(|b| {
            let py_data = b.extract::<cpython::PyTuple>(py)?;
            Ok((
                py_data.get_item(py, 0).extract::<String>(py)?,
                py_data.get_item(py, 1).extract::<Vec<u8>>(py)?,
            ))
        })
        .collect::<Result<Vec<(String, Vec<u8>)>, cpython::PyErr>>()
}

fn return_owned_bytes_from_pyobj(
    pydict: &cpython::PyObject,
    py: cpython::Python,
    item_name: &str,
) -> Result<Vec<u8>, cpython::PyErr> {
    Ok(pydict
        .getattr(py, item_name)
        .unwrap()
        .extract::<cpython::PyBytes>(py)?
        .data(py)
        .to_owned())
}

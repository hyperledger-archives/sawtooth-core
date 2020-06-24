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
use sawtooth::scheduler::TxnExecutionResult;

use proto::events::{Event, Event_Attribute};
use proto::transaction_receipt::{StateChange, StateChange_Type};

#[derive(Clone)]
pub struct PyBatchExecutionResult {
    pub state_hash: Option<String>,
}

/// PyTxnExecutionResult is a Rust struct that mirrors
/// what is passed from a Python Scheduler's get_transaction_execution_results
/// method.
pub struct PyTxnExecutionResult {
    pub signature: String,
    pub is_valid: bool,
    pub state_hash: Option<String>,
    pub state_changes: Vec<StateChange>,
    pub events: Vec<Event>,
    pub data: Vec<Vec<u8>>,
    pub error_message: String,
    pub error_data: Vec<u8>,
}

impl<'source> FromPyObject<'source> for PyBatchExecutionResult {
    fn extract(py: cpython::Python, obj: &'source cpython::PyObject) -> cpython::PyResult<Self> {
        let state_hash = obj.getattr(py, "state_hash").unwrap();

        let sh: Option<String> = state_hash.extract(py)?;

        Ok(PyBatchExecutionResult { state_hash: sh })
    }
}

impl<'source> FromPyObject<'source> for PyTxnExecutionResult {
    fn extract(py: cpython::Python, obj: &'source cpython::PyObject) -> cpython::PyResult<Self> {
        Ok(try_pyobj_to_transaction_result(py, obj)?)
    }
}

impl From<PyTxnExecutionResult> for TxnExecutionResult {
    fn from(other: PyTxnExecutionResult) -> Self {
        TxnExecutionResult {
            signature: other.signature,
            is_valid: other.is_valid,
            state_changes: other
                .state_changes
                .into_iter()
                .map(|state_change| state_change.into())
                .collect(),
            events: other.events.into_iter().map(|event| event.into()).collect(),
            data: other.data,
            error_message: other.error_message,
            error_data: other.error_data,
        }
    }
}

fn try_pyobj_to_transaction_result(
    py: cpython::Python,
    pyobj: &cpython::PyObject,
) -> Result<PyTxnExecutionResult, cpython::PyErr> {
    let signature = pyobj.getattr(py, "signature")?.extract(py)?;
    let is_valid = pyobj.getattr(py, "is_valid")?.extract(py)?;
    let beginning_state_hash = pyobj.getattr(py, "state_hash")?.extract(py)?;
    let state_changes = pyobj.getattr(py, "state_changes")?.extract(py)?;
    let events = pyobj.getattr(py, "events")?.extract(py)?;
    let data = pyobj.getattr(py, "data")?.extract(py)?;
    let error_message = pyobj.getattr(py, "error_message")?.extract(py)?;
    let error_data = pyobj.getattr(py, "error_data")?.extract(py)?;

    Ok(PyTxnExecutionResult {
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

impl From<sawtooth::protos::transaction_receipt::StateChange> for StateChange {
    fn from(state_change: sawtooth::protos::transaction_receipt::StateChange) -> Self {
        let mut ret = StateChange::new();
        ret.set_address(state_change.address);
        ret.set_value(state_change.value);
        ret.set_field_type(match state_change.field_type {
            sawtooth::protos::transaction_receipt::StateChange_Type::TYPE_UNSET => {
                StateChange_Type::TYPE_UNSET
            }
            sawtooth::protos::transaction_receipt::StateChange_Type::SET => StateChange_Type::SET,
            sawtooth::protos::transaction_receipt::StateChange_Type::DELETE => {
                StateChange_Type::DELETE
            }
        });
        ret
    }
}
impl From<StateChange> for sawtooth::protos::transaction_receipt::StateChange {
    fn from(state_change: StateChange) -> Self {
        let mut ret = sawtooth::protos::transaction_receipt::StateChange::new();
        ret.set_address(state_change.address);
        ret.set_value(state_change.value);
        ret.set_field_type(match state_change.field_type {
            StateChange_Type::TYPE_UNSET => {
                sawtooth::protos::transaction_receipt::StateChange_Type::TYPE_UNSET
            }
            StateChange_Type::SET => sawtooth::protos::transaction_receipt::StateChange_Type::SET,
            StateChange_Type::DELETE => {
                sawtooth::protos::transaction_receipt::StateChange_Type::DELETE
            }
        });
        ret
    }
}

impl<'source> FromPyObject<'source> for StateChange {
    fn extract(py: cpython::Python, obj: &'source cpython::PyObject) -> cpython::PyResult<Self> {
        let state_change_bytes = obj
            .call_method(py, "SerializeToString", cpython::NoArgs, None)
            .unwrap()
            .extract::<Vec<u8>>(py)?;
        let state_change: StateChange =
            ::protobuf::parse_from_bytes(state_change_bytes.as_slice()).unwrap();
        Ok(state_change)
    }
}

impl From<sawtooth::protos::events::Event_Attribute> for Event_Attribute {
    fn from(attribute: sawtooth::protos::events::Event_Attribute) -> Self {
        let mut ret = Event_Attribute::new();
        ret.set_key(attribute.key);
        ret.set_value(attribute.value);
        ret
    }
}
impl From<Event_Attribute> for sawtooth::protos::events::Event_Attribute {
    fn from(attribute: Event_Attribute) -> Self {
        let mut ret = sawtooth::protos::events::Event_Attribute::new();
        ret.set_key(attribute.key);
        ret.set_value(attribute.value);
        ret
    }
}

impl From<sawtooth::protos::events::Event> for Event {
    fn from(event: sawtooth::protos::events::Event) -> Self {
        let mut ret = Event::new();
        ret.set_event_type(event.event_type);
        ret.set_attributes(
            event
                .attributes
                .into_iter()
                .map(|attribute| attribute.into())
                .collect(),
        );
        ret.set_data(event.data);
        ret
    }
}

impl From<Event> for sawtooth::protos::events::Event {
    fn from(event: Event) -> Self {
        let mut ret = sawtooth::protos::events::Event::new();
        ret.set_event_type(event.event_type);
        ret.set_attributes(
            event
                .attributes
                .into_iter()
                .map(|attribute| attribute.into())
                .collect(),
        );
        ret.set_data(event.data);
        ret
    }
}

impl<'source> FromPyObject<'source> for Event {
    fn extract(py: cpython::Python, obj: &'source cpython::PyObject) -> cpython::PyResult<Self> {
        let event_bytes = obj
            .call_method(py, "SerializeToString", cpython::NoArgs, None)
            .unwrap()
            .extract::<Vec<u8>>(py)?;
        let event: Event = ::protobuf::parse_from_bytes(event_bytes.as_slice()).unwrap();
        Ok(event)
    }
}

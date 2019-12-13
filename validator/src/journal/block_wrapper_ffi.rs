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
use cpython::{FromPyObject, ObjectProtocol, PyClone, PyObject, Python, ToPyObject};

use journal::block_wrapper::BlockStatus;
use journal::block_wrapper::BlockWrapper;

lazy_static! {
    static ref PY_BLOCK_WRAPPER: PyObject = Python::acquire_gil()
        .python()
        .import("sawtooth_validator.journal.block_wrapper")
        .expect("Unable to import block_wrapper")
        .get(Python::acquire_gil().python(), "BlockWrapper")
        .expect("Unable to get BlockWrapper");
}

lazy_static! {
    static ref PY_BLOCK_STATUS: PyObject = Python::acquire_gil()
        .python()
        .import("sawtooth_validator.journal.block_wrapper")
        .expect("Unable to import block_wrapper")
        .get(Python::acquire_gil().python(), "BlockStatus")
        .expect("Unable to get BlockStatus");
}

impl ToPyObject for BlockStatus {
    type ObjectType = cpython::PyObject;

    fn to_py_object(&self, py: Python) -> cpython::PyObject {
        match *self {
            BlockStatus::Unknown => PY_BLOCK_STATUS
                .getattr(py, "Unknown")
                .expect("No BlockStatus.Unknown"),
            BlockStatus::Invalid => PY_BLOCK_STATUS
                .getattr(py, "Invalid")
                .expect("No BlockStatus.Invalid"),
            BlockStatus::Valid => PY_BLOCK_STATUS
                .getattr(py, "Valid")
                .expect("No BlockStatus.Valid"),
            BlockStatus::Missing => PY_BLOCK_STATUS
                .getattr(py, "Missing")
                .expect("No BlockStatus.Missing"),
            BlockStatus::InValidation => PY_BLOCK_STATUS
                .getattr(py, "InValidation")
                .expect("No BlockStatus.InValidation"),
        }
    }
}

impl<'source> FromPyObject<'source> for BlockStatus {
    fn extract(py: Python, obj: &'source PyObject) -> cpython::PyResult<Self> {
        let enum_val: i32 = obj.extract(py)?;
        Ok(match enum_val {
            1 => BlockStatus::Invalid,
            2 => BlockStatus::Valid,
            3 => BlockStatus::Missing,
            5 => BlockStatus::InValidation,
            _ => BlockStatus::Unknown,
        })
    }
}

impl ToPyObject for BlockWrapper {
    type ObjectType = PyObject;

    fn to_py_object(&self, py: Python) -> PyObject {
        self.py_block_wrapper.clone_ref(py)
    }

    fn into_py_object(self, _: Python) -> PyObject {
        self.py_block_wrapper
    }
}

impl<'source> FromPyObject<'source> for BlockWrapper {
    fn extract(py: Python, obj: &'source PyObject) -> cpython::PyResult<Self> {
        Ok(BlockWrapper {
            py_block_wrapper: obj.clone_ref(py),
        })
    }
}

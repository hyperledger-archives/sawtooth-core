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

use cpython::{PyObject, Python, PythonObject, ToPyObject};

pub struct PyObjectWrapper {
    pub py_object: PyObject,
}

impl PyObjectWrapper {
    pub fn new(py_object: PyObject) -> Self {
        PyObjectWrapper { py_object }
    }
}

impl ToPyObject for PyObjectWrapper {
    type ObjectType = PyObject;

    fn to_py_object(&self, py: Python) -> PyObject {
        self.py_object
            .extract::<PyObject>(py)
            .expect("Unable to get PyObject")
    }
}

impl From<usize> for PyObjectWrapper {
    fn from(value: usize) -> Self {
        let gil = Python::acquire_gil();
        let py = gil.python();

        PyObjectWrapper::new(value.to_py_object(py).into_object())
    }
}

impl From<u64> for PyObjectWrapper {
    fn from(value: u64) -> Self {
        let gil = Python::acquire_gil();
        let py = gil.python();

        PyObjectWrapper::new(value.to_py_object(py).into_object())
    }
}

impl From<&str> for PyObjectWrapper {
    fn from(value: &str) -> Self {
        let gil = Python::acquire_gil();
        let py = gil.python();

        PyObjectWrapper::new(value.to_py_object(py).into_object())
    }
}

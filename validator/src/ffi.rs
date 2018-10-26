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

use cpython::{FromPyObject, NoArgs, ObjectProtocol, PyList, PyObject, Python, ToPyObject};
use py_ffi;
use pylogger;
use std::marker::PhantomData;

#[no_mangle]
pub unsafe extern "C" fn ffi_reclaim_string(s_ptr: *mut u8, s_len: usize, s_cap: usize) -> isize {
    String::from_raw_parts(s_ptr, s_len, s_cap);

    0
}

#[no_mangle]
pub unsafe extern "C" fn ffi_reclaim_vec(
    vec_ptr: *mut u8,
    vec_len: usize,
    vec_cap: usize,
) -> isize {
    Vec::from_raw_parts(vec_ptr, vec_len, vec_cap);

    0
}

pub struct PyIteratorWrapper<T> {
    py_iter: PyObject,
    target_type: PhantomData<T>,
    xform: Box<Fn(Python, PyObject) -> PyObject>,
}

impl<T> PyIteratorWrapper<T>
where
    for<'source> T: FromPyObject<'source>,
{
    pub fn new(py_iter: PyObject) -> Self {
        PyIteratorWrapper::with_xform(py_iter, Box::new(|_, obj| obj))
    }

    pub fn with_xform(py_iter: PyObject, xform: Box<Fn(Python, PyObject) -> PyObject>) -> Self {
        PyIteratorWrapper {
            py_iter,
            target_type: PhantomData,
            xform,
        }
    }
}

impl<T> Iterator for PyIteratorWrapper<T>
where
    for<'source> T: FromPyObject<'source>,
{
    type Item = T;

    fn next(&mut self) -> Option<Self::Item> {
        let gil_guard = Python::acquire_gil();
        let py = gil_guard.python();
        match self.py_iter.call_method(py, "__next__", NoArgs, None) {
            Ok(py_obj) => Some(
                (*self.xform)(py, py_obj)
                    .extract(py)
                    .expect("Unable to convert py obj"),
            ),
            Err(py_err) => {
                if py_err.get_type(py).name(py) != "StopIteration" {
                    pylogger::exception(py, "Unable to iterate; aborting", py_err);
                }
                None
            }
        }
    }
}

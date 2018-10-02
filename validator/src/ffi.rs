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

use cpython::{PyObject, Python};

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

pub fn py_import_class(module: &str, class: &str) -> PyObject {
    let gil = Python::acquire_gil();
    let python = gil.python();
    python
        .import(module)
        .expect(&format!("Unable to import '{}'", module))
        .get(python, class)
        .expect(&format!("Unable to import {} from '{}'", class, module))
}

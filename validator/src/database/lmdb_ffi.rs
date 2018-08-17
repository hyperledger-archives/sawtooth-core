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
use cpython::{PyList, PyObject, Python};
use database::lmdb::*;
use py_ffi;
use std::ffi::CStr;
use std::os::raw::{c_char, c_void};
use std::path::Path;

#[repr(u32)]
#[derive(Debug)]
pub enum ErrorCode {
    Success = 0,
    NullPointerProvided = 0x01,
    InvalidFilePath = 0x02,
    InvalidIndexString = 0x03,

    InitializeContextError = 0x11,
    InitializeDatabaseError = 0x12,
}

#[no_mangle]
pub unsafe extern "C" fn lmdb_database_new(
    path: *const c_char,
    file_size: usize,
    indexes_ptr: *mut py_ffi::PyObject,
    db_ptr: *mut *const c_void,
) -> ErrorCode {
    if path.is_null() {
        return ErrorCode::NullPointerProvided;
    }

    let indexes: Vec<String> = {
        let py = Python::assume_gil_acquired();
        let py_obj = PyObject::from_borrowed_ptr(py, indexes_ptr);
        let py_list: PyList = py_obj.extract(py).unwrap();
        py_list
            .iter(py)
            .map(|pyobj| pyobj.extract::<String>(py).unwrap())
            .collect()
    };

    let db_path = match CStr::from_ptr(path).to_str() {
        Ok(s) => s,
        Err(_) => return ErrorCode::InvalidFilePath,
    };

    let ctx = match LmdbContext::new(Path::new(&db_path), indexes.len(), Some(file_size)) {
        Ok(ctx) => ctx,
        Err(err) => {
            error!(
                "Unable to create LMDB context for db at {}: {:?}",
                db_path, err
            );
            return ErrorCode::InitializeContextError;
        }
    };

    match LmdbDatabase::new(ctx, &indexes) {
        Ok(db) => {
            *db_ptr = Box::into_raw(Box::new(db)) as *const c_void;

            ErrorCode::Success
        }
        Err(err) => {
            error!("Unable to create Database at {}: {:?}", db_path, err);
            ErrorCode::InitializeDatabaseError
        }
    }
}

#[no_mangle]
pub unsafe extern "C" fn lmdb_database_drop(lmdb_database: *mut c_void) -> ErrorCode {
    if lmdb_database.is_null() {
        return ErrorCode::NullPointerProvided;
    }

    Box::from_raw(lmdb_database as *mut LmdbDatabase);
    ErrorCode::Success
}

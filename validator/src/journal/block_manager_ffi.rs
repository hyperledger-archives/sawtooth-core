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

use std::ffi::CStr;
use std::os::raw::{c_char, c_void};
use std::slice;

use cpython::{PyList, PyObject, Python, ToPyObject};
use py_ffi;

use block::Block;
use journal::block_manager::{
    BlockManager, BlockManagerError, BranchDiffIterator, BranchIterator, GetBlockIterator,
};

#[repr(u32)]
#[derive(Debug)]
pub enum ErrorCode {
    Success = 0,
    NullPointerProvided = 0x01,
    MissingPredecessor = 0x02,
    MissingPredecessorInBranch = 0x03,
    MissingInput = 0x04,
    UnknownBlock = 0x05,
    Error = 0x06,
    InvalidPythonObject = 0x10,
    StopIteration = 0x11,
}

macro_rules! check_null {
    ($($arg:expr) , *) => {
        $(if $arg.is_null() { return ErrorCode::NullPointerProvided; })*
    }
}

#[no_mangle]
pub unsafe extern "C" fn block_manager_new(block_manager_ptr: *mut *const c_void) -> ErrorCode {
    let block_manager = BlockManager::new();

    *block_manager_ptr = Box::into_raw(Box::new(block_manager)) as *const c_void;

    ErrorCode::Success
}

#[no_mangle]
pub unsafe extern "C" fn block_manager_drop(block_manager: *mut c_void) -> ErrorCode {
    check_null!(block_manager);
    Box::from_raw(block_manager as *mut BlockManager);
    ErrorCode::Success
}

#[no_mangle]
pub unsafe extern "C" fn block_manager_put(
    block_manager: *mut c_void,
    branch: *mut py_ffi::PyObject,
) -> ErrorCode {
    check_null!(block_manager, branch);

    let gil = Python::acquire_gil();
    let py = gil.python();

    let py_branch = PyObject::from_borrowed_ptr(py, branch);

    let branch: Vec<Block> = py_branch
        .extract::<PyList>(py)
        .expect("Failed to extract PyList from Branch")
        .iter(py)
        .map(|b| {
            b.extract::<Block>(py)
                .expect("Unable to extract Block in PyList, py_branch")
        })
        .collect();

    match (*(block_manager as *mut BlockManager)).put(branch) {
        Err(BlockManagerError::MissingPredecessor(_)) => ErrorCode::MissingPredecessor,
        Err(BlockManagerError::MissingInput) => ErrorCode::MissingInput,
        Err(BlockManagerError::MissingPredecessorInBranch(_)) => {
            ErrorCode::MissingPredecessorInBranch
        }
        Err(_) => ErrorCode::Error,
        Ok(_) => ErrorCode::Success,
    }
}

#[no_mangle]
pub unsafe extern "C" fn block_manager_get_iterator_new(
    block_manager: *mut c_void,
    block_ids: *const *const c_char,
    block_ids_len: usize,
    iterator: *mut *const c_void,
) -> ErrorCode {
    check_null!(block_manager, block_ids);

    let block_ids = match slice::from_raw_parts(block_ids, block_ids_len)
        .iter()
        .map(|c_str| CStr::from_ptr(*c_str).to_str())
        .collect::<Result<Vec<&str>, _>>()
    {
        Ok(ids) => ids,
        Err(_) => return ErrorCode::InvalidPythonObject,
    };

    *iterator =
        Box::into_raw((*(block_manager as *mut BlockManager)).get(&block_ids)) as *const c_void;

    ErrorCode::Success
}

#[no_mangle]
pub unsafe extern "C" fn block_manager_get_iterator_drop(iterator: *mut c_void) -> ErrorCode {
    check_null!(iterator);

    Box::from_raw(iterator as *mut GetBlockIterator);
    ErrorCode::Success
}

#[no_mangle]
pub unsafe extern "C" fn block_manager_get_iterator_next(
    iterator: *mut c_void,
    block: *mut *const py_ffi::PyObject,
) -> ErrorCode {
    check_null!(iterator);

    *block = match (*(iterator as *mut GetBlockIterator)).next() {
        Some(b) => {
            let gil = Python::acquire_gil();
            let py = gil.python();
            b.to_py_object(py).steal_ptr()
        }
        None => return ErrorCode::StopIteration,
    };

    ErrorCode::Success
}

#[no_mangle]
pub unsafe extern "C" fn block_manager_branch_iterator_new(
    block_manager: *mut c_void,
    tip: *const c_char,
    iterator: *mut *const c_void,
) -> ErrorCode {
    check_null!(block_manager, tip);

    let tip = match CStr::from_ptr(tip).to_str() {
        Ok(s) => s,
        Err(_) => return ErrorCode::InvalidPythonObject,
    };

    *iterator = Box::into_raw((*(block_manager as *mut BlockManager)).branch(tip)) as *const c_void;
    ErrorCode::Success
}

#[no_mangle]
pub unsafe extern "C" fn block_manager_branch_iterator_drop(iterator: *mut c_void) -> ErrorCode {
    check_null!(iterator);
    Box::from_raw(iterator as *mut BranchIterator);
    ErrorCode::Success
}

#[no_mangle]
pub unsafe extern "C" fn block_manager_branch_iterator_next(
    iterator: *mut c_void,
    block: *mut *const py_ffi::PyObject,
) -> ErrorCode {
    check_null!(iterator);

    *block = match (*(iterator as *mut BranchIterator)).next() {
        Some(b) => {
            let gil = Python::acquire_gil();
            let py = gil.python();
            b.to_py_object(py).steal_ptr()
        }
        None => return ErrorCode::StopIteration,
    };
    ErrorCode::Success
}

#[no_mangle]
pub unsafe extern "C" fn block_manager_branch_diff_iterator_new(
    block_manager: *mut c_void,
    tip: *const c_char,
    exclude: *const c_char,
    iterator: *mut *const c_void,
) -> ErrorCode {
    check_null!(block_manager, tip, exclude);

    let tip = match CStr::from_ptr(tip).to_str() {
        Ok(s) => s,
        Err(_) => return ErrorCode::InvalidPythonObject,
    };

    let exclude = match CStr::from_ptr(exclude).to_str() {
        Ok(s) => s,
        Err(_) => return ErrorCode::InvalidPythonObject,
    };

    *iterator = Box::into_raw((*(block_manager as *mut BlockManager)).branch_diff(tip, exclude))
        as *const c_void;

    ErrorCode::Success
}

#[no_mangle]
pub unsafe extern "C" fn block_manager_branch_diff_iterator_drop(
    iterator: *mut c_void,
) -> ErrorCode {
    check_null!(iterator);
    Box::from_raw(iterator as *mut BranchDiffIterator);
    ErrorCode::Success
}

#[no_mangle]
pub unsafe extern "C" fn block_manager_branch_diff_iterator_next(
    iterator: *mut c_void,
    block: *mut *const py_ffi::PyObject,
) -> ErrorCode {
    check_null!(iterator);

    *block = match (*(iterator as *mut BranchDiffIterator)).next() {
        Some(b) => {
            let gil = Python::acquire_gil();
            let py = gil.python();
            b.to_py_object(py).steal_ptr()
        }
        None => return ErrorCode::StopIteration,
    };
    ErrorCode::Success
}

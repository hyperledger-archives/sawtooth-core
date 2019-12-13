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
use execution::py_executor::PyExecutor;
use gossip::permission_verifier::PyPermissionVerifier;
use journal::{
    block_manager::BlockManager,
    block_validator::{BlockValidationResultStore, BlockValidator},
};
use py_ffi;
use state::state_view_factory::StateViewFactory;
use std::os::raw::c_void;

#[repr(u32)]
#[derive(Debug)]
pub enum ErrorCode {
    Success = 0,
    NullPointerProvided = 0x01,
    ValidationFailure = 0x02,
    ValidationError = 0x03,
}

macro_rules! check_null {
    ($($arg:expr) , *) => {
        $(if $arg.is_null() { return ErrorCode::NullPointerProvided; })*
    }
}

#[no_mangle]
pub unsafe extern "C" fn block_status_store_new(
    block_status_store_ptr: *mut *const c_void,
) -> ErrorCode {
    let block_status_store = BlockValidationResultStore::new();

    *block_status_store_ptr = Box::into_raw(Box::new(block_status_store)) as *const c_void;
    ErrorCode::Success
}

#[no_mangle]
pub unsafe extern "C" fn block_status_store_drop(block_status_store_ptr: *mut c_void) -> ErrorCode {
    check_null!(block_status_store_ptr);

    Box::from_raw(block_status_store_ptr as *mut BlockValidationResultStore);
    ErrorCode::Success
}

#[no_mangle]
pub unsafe extern "C" fn block_validator_new(
    block_manager_ptr: *const c_void,
    transaction_executor_ptr: *mut py_ffi::PyObject,
    block_status_store_ptr: *const c_void,
    permission_verifier: *mut py_ffi::PyObject,
    view_factory_ptr: *const c_void,
    block_validator_ptr: *mut *const c_void,
) -> ErrorCode {
    check_null!(block_status_store_ptr, view_factory_ptr);

    let block_manager = (*(block_manager_ptr as *const BlockManager)).clone();

    let block_status_store =
        (*(block_status_store_ptr as *const BlockValidationResultStore)).clone();

    let view_factory = (*(view_factory_ptr as *const StateViewFactory)).clone();
    let gil = cpython::Python::acquire_gil();
    let py = gil.python();
    let ex = cpython::PyObject::from_borrowed_ptr(py, transaction_executor_ptr);

    let py_transaction_executor =
        PyExecutor::new(ex).expect("The PyExecutor could not be created from a PyObject");

    let py_permission_verifier: PyPermissionVerifier = PyPermissionVerifier::new(
        cpython::PyObject::from_borrowed_ptr(py, permission_verifier),
    );

    let block_validator = BlockValidator::new(
        block_manager,
        py_transaction_executor,
        block_status_store,
        py_permission_verifier,
        view_factory,
    );

    *block_validator_ptr = Box::into_raw(Box::new(block_validator)) as *const c_void;

    ErrorCode::Success
}

#[no_mangle]
pub unsafe extern "C" fn block_validator_start(block_validator_ptr: *mut c_void) -> ErrorCode {
    check_null!(block_validator_ptr);

    (*(block_validator_ptr as *mut BlockValidator<PyExecutor, PyPermissionVerifier>)).start();

    ErrorCode::Success
}

#[no_mangle]
pub unsafe extern "C" fn block_validator_stop(block_validator_ptr: *mut c_void) -> ErrorCode {
    check_null!(block_validator_ptr);
    (*(block_validator_ptr as *mut BlockValidator<PyExecutor, PyPermissionVerifier>)).stop();

    ErrorCode::Success
}

#[no_mangle]
pub unsafe extern "C" fn block_validator_drop(block_validator_ptr: *mut c_void) -> ErrorCode {
    check_null!(block_validator_ptr);

    Box::from_raw(block_validator_ptr as *mut BlockValidator<PyExecutor, PyPermissionVerifier>);

    ErrorCode::Success
}

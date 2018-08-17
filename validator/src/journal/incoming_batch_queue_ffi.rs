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
use py_ffi;
use std::ffi::CStr;
use std::os::raw::{c_char, c_void};

use cpython::{PyObject, Python};

use batch::Batch;
use journal::publisher::IncomingBatchSender;

macro_rules! check_null {
    ($($arg:expr) , *) => {
        $(if $arg.is_null() { return ErrorCode::NullPointerProvided; })*
    }
}

#[repr(u32)]
#[derive(Debug)]
pub enum ErrorCode {
    Success = 0,
    NullPointerProvided = 0x01,
    InvalidInput = 0x02,
    Disconnected = 0x03,
}

#[no_mangle]
pub unsafe extern "C" fn incoming_batch_sender_send(
    sender_ptr: *mut c_void,
    pyobj_ptr: *mut py_ffi::PyObject,
) -> ErrorCode {
    check_null!(sender_ptr);

    let gil = Python::acquire_gil();
    let py = gil.python();
    let batch: Batch = {
        let pyobj = PyObject::from_borrowed_ptr(py, pyobj_ptr);

        match pyobj.extract(py) {
            Ok(batch) => batch,
            Err(_) => {
                return ErrorCode::InvalidInput;
            }
        }
    };

    let mut sender = (*(sender_ptr as *mut IncomingBatchSender)).clone();

    py.allow_threads(move || match sender.put(batch) {
        Ok(()) => ErrorCode::Success,
        Err(_) => ErrorCode::Disconnected,
    })
}

#[no_mangle]
pub unsafe extern "C" fn incoming_batch_sender_has_batch(
    sender_ptr: *mut c_void,
    batch_id: *const c_char,
    has: *mut bool,
) -> ErrorCode {
    check_null!(sender_ptr, batch_id);

    let batch_id = match CStr::from_ptr(batch_id).to_str() {
        Ok(s) => s,
        Err(_) => return ErrorCode::InvalidInput,
    };

    *has = (*(sender_ptr as *mut IncomingBatchSender))
        .has_batch(batch_id)
        .unwrap_or_else(|e| {
            warn!("Unable to check for batch {:?}", e);
            false
        });

    ErrorCode::Success
}

#[no_mangle]
pub unsafe extern "C" fn incoming_batch_sender_drop(sender_ptr: *mut c_void) -> ErrorCode {
    if sender_ptr.is_null() {
        return ErrorCode::NullPointerProvided;
    }

    Box::from_raw(sender_ptr as *mut IncomingBatchSender);
    ErrorCode::Success
}

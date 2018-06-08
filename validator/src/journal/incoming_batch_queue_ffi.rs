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
use std::os::raw::c_void;

use cpython::{PyObject, Python};

use batch::Batch;
use journal::publisher::IncomingBatchSender;

#[repr(u32)]
#[derive(Debug)]
pub enum ErrorCode {
    Success = 0,
    NullPointerProvided = 0x01,
    InvalidInput = 0x02,
    Disconnected = 0x03,
}

#[no_mangle]
pub extern "C" fn incoming_batch_sender_send(
    sender_ptr: *mut c_void,
    pyobj_ptr: *mut py_ffi::PyObject,
) -> ErrorCode {
    if sender_ptr.is_null() {
        return ErrorCode::NullPointerProvided;
    }

    let batch: Batch = {
        let gil = Python::acquire_gil();
        let py = gil.python();
        let pyobj = unsafe { PyObject::from_borrowed_ptr(py, pyobj_ptr) };

        match pyobj.extract(py) {
            Ok(batch) => batch,
            Err(_) => {
                return ErrorCode::InvalidInput;
            }
        }
    };

    let mut sender = unsafe { Box::from_raw(sender_ptr as *mut IncomingBatchSender) };

    let result = match sender.put(batch) {
        Ok(()) => ErrorCode::Success,
        Err(_) => ErrorCode::Disconnected,
    };
    Box::into_raw(sender);
    result
}

#[no_mangle]
pub extern "C" fn incoming_batch_sender_drop(sender_ptr: *mut c_void) -> ErrorCode {
    if sender_ptr.is_null() {
        return ErrorCode::NullPointerProvided;
    }

    unsafe { Box::from_raw(sender_ptr as *mut IncomingBatchSender) };
    ErrorCode::Success
}

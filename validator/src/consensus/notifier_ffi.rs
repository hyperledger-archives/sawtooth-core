/*
 * Copyright 2018 Cargill Incorporated
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

use cpython::{NoArgs, ObjectProtocol, PyClone, PyObject, Python};
use protobuf::{self, Message, ProtobufEnum};
use py_ffi;

use block::Block;
use consensus::notifier::{
    BackgroundConsensusNotifier, ConsensusNotifier, NotifierService, NotifierServiceError,
};
use proto::validator::Message_MessageType as MessageType;
use proto::{self, consensus::ConsensusPeerMessage};
use pylogger;

pub struct PyNotifierService {
    py_notifier_service: PyObject,
}

impl PyNotifierService {
    pub fn new(py_notifier_service: PyObject) -> Self {
        PyNotifierService {
            py_notifier_service,
        }
    }
}

impl NotifierService for PyNotifierService {
    fn notify<T: Message>(
        &self,
        message_type: MessageType,
        message: T,
    ) -> Result<(), NotifierServiceError> {
        let payload = message
            .write_to_bytes()
            .map_err(|err| NotifierServiceError(format!("{:?}", err)))?;

        let gil_guard = Python::acquire_gil();
        let py = gil_guard.python();

        self.py_notifier_service
            .call_method(py, "notify", (message_type.value(), payload), None)
            .map(|_| ())
            .map_err(|py_err| {
                pylogger::exception(py, "Unable to notify consensus", py_err);
                NotifierServiceError("FFI error notifying consensus".into())
            })
    }

    fn notify_id<T: Message>(
        &self,
        message_type: MessageType,
        message: T,
        connection_id: String,
    ) -> Result<(), NotifierServiceError> {
        let payload = message
            .write_to_bytes()
            .map_err(|err| NotifierServiceError(format!("{:?}", err)))?;

        let gil_guard = Python::acquire_gil();
        let py = gil_guard.python();

        self.py_notifier_service
            .call_method(
                py,
                "notify_id",
                (message_type.value(), payload, connection_id),
                None,
            )
            .map(|_| ())
            .map_err(|py_err| {
                pylogger::exception(py, "Unable to notify consensus", py_err);
                NotifierServiceError("FFI error notifying consensus".into())
            })
    }

    fn get_peers_public_keys(&self) -> Result<Vec<String>, NotifierServiceError> {
        let gil_guard = Python::acquire_gil();
        let py = gil_guard.python();

        let res = self
            .py_notifier_service
            .call_method(py, "get_peers_public_keys", NoArgs, None)
            .map_err(|py_err| {
                pylogger::exception(
                    py,
                    "Unable to call py_notifier_service.get_peers_public_keys",
                    py_err,
                );
                NotifierServiceError(
                    "FFI error calling py_notifier_service.get_peers_public_keys".into(),
                )
            })?;

        res.extract::<Vec<String>>(py).map_err(|py_err| {
            pylogger::exception(
                py,
                "py_notifier_service.get_peers_public_keys did not return a valid string list",
                py_err,
            );
            NotifierServiceError(
                "py_notifier_service.get_peers_public_keys did not return a valid string list"
                    .into(),
            )
        })
    }

    fn get_public_key(&self) -> Result<String, NotifierServiceError> {
        let gil_guard = Python::acquire_gil();
        let py = gil_guard.python();

        let res = self
            .py_notifier_service
            .call_method(py, "get_public_key", NoArgs, None)
            .map_err(|py_err| {
                pylogger::exception(
                    py,
                    "Unable to call py_notifier_service.get_public_key",
                    py_err,
                );
                NotifierServiceError("FFI error calling py_notifier_service.get_public_key".into())
            })?;

        res.extract::<String>(py).map_err(|py_err| {
            pylogger::exception(
                py,
                "py_notifier_service.get_public_key did not return a valid string",
                py_err,
            );
            NotifierServiceError(
                "py_notifier_service.get_public_key did not return a valid string".into(),
            )
        })
    }
}

impl Clone for PyNotifierService {
    fn clone(&self) -> Self {
        let gil_guard = Python::acquire_gil();
        let py = gil_guard.python();

        PyNotifierService {
            py_notifier_service: self.py_notifier_service.clone_ref(py),
        }
    }
}

macro_rules! check_null {
    ($($arg:expr) , *) => {
        $(if $arg.is_null() { return ErrorCode::NullPointerProvided; })*
    }
}

#[repr(u32)]
#[derive(Debug)]
pub enum ErrorCode {
    Success = 0,

    // Input errors
    NullPointerProvided = 0x01,
    InvalidArgument = 0x02,
}

#[no_mangle]
pub unsafe extern "C" fn consensus_notifier_new(
    py_notifier_service_ptr: *mut py_ffi::PyObject,
    consensus_notifier_ptr: *mut *const c_void,
) -> ErrorCode {
    check_null!(py_notifier_service_ptr);

    let py = Python::assume_gil_acquired();
    let py_notifier_service = PyObject::from_borrowed_ptr(py, py_notifier_service_ptr);

    *consensus_notifier_ptr = Box::into_raw(Box::new(BackgroundConsensusNotifier::new(
        PyNotifierService::new(py_notifier_service),
    ))) as *const c_void;

    ErrorCode::Success
}

#[no_mangle]
pub unsafe extern "C" fn consensus_notifier_drop(notifier: *mut c_void) -> ErrorCode {
    check_null!(notifier);
    Box::from_raw(notifier as *mut BackgroundConsensusNotifier);
    ErrorCode::Success
}

#[no_mangle]
pub unsafe extern "C" fn consensus_notifier_notify_peer_connected(
    notifier: *mut c_void,
    peer_id: *const c_char,
) -> ErrorCode {
    check_null!(notifier, peer_id);

    match deref_cstr(peer_id) {
        Ok(peer_id) => {
            (*(notifier as *mut BackgroundConsensusNotifier)).notify_peer_connected(peer_id);
            ErrorCode::Success
        }
        Err(err) => err,
    }
}

#[no_mangle]
pub unsafe extern "C" fn consensus_notifier_notify_peer_disconnected(
    notifier: *mut c_void,
    peer_id: *const c_char,
) -> ErrorCode {
    check_null!(notifier, peer_id);

    match deref_cstr(peer_id) {
        Ok(peer_id) => {
            (*(notifier as *mut BackgroundConsensusNotifier)).notify_peer_disconnected(peer_id);
            ErrorCode::Success
        }
        Err(err) => err,
    }
}

#[no_mangle]
pub unsafe extern "C" fn consensus_notifier_notify_peer_message(
    notifier: *mut c_void,
    message_bytes: *const u8,
    message_len: usize,
    sender_id_bytes: *const u8,
    sender_id_len: usize,
) -> ErrorCode {
    check_null!(notifier, message_bytes, sender_id_bytes);

    let message_slice = slice::from_raw_parts(message_bytes, message_len);
    let message: ConsensusPeerMessage = match protobuf::parse_from_bytes(&message_slice) {
        Ok(message) => message,
        Err(err) => {
            error!("Failed to parse ConsensusPeerMessage: {:?}", err);
            return ErrorCode::InvalidArgument;
        }
    };

    let sender_id = slice::from_raw_parts(sender_id_bytes, sender_id_len);
    (*(notifier as *mut BackgroundConsensusNotifier)).notify_peer_message(message, &sender_id);

    ErrorCode::Success
}

#[no_mangle]
pub unsafe extern "C" fn consensus_notifier_notify_block_new(
    notifier: *mut c_void,
    block_bytes: *const u8,
    block_bytes_len: usize,
) -> ErrorCode {
    check_null!(notifier, block_bytes);

    let block: Block = {
        let data = slice::from_raw_parts(block_bytes, block_bytes_len);
        let proto_block: proto::block::Block = match protobuf::parse_from_bytes(&data) {
            Ok(block) => block,
            Err(err) => {
                error!("Failed to parse block bytes: {:?}", err);
                return ErrorCode::InvalidArgument;
            }
        };
        proto_block.into()
    };

    (*(notifier as *mut BackgroundConsensusNotifier)).notify_block_new(&block);

    ErrorCode::Success
}

#[no_mangle]
pub unsafe extern "C" fn consensus_notifier_notify_block_valid(
    notifier: *mut c_void,
    block_id: *const c_char,
) -> ErrorCode {
    check_null!(notifier, block_id);

    match deref_cstr(block_id) {
        Ok(block_id) => {
            (*(notifier as *mut BackgroundConsensusNotifier)).notify_block_valid(block_id);
            ErrorCode::Success
        }
        Err(err) => err,
    }
}

#[no_mangle]
pub unsafe extern "C" fn consensus_notifier_notify_block_invalid(
    notifier: *mut c_void,
    block_id: *const c_char,
) -> ErrorCode {
    check_null!(notifier, block_id);

    match deref_cstr(block_id) {
        Ok(block_id) => {
            (*(notifier as *mut BackgroundConsensusNotifier)).notify_block_invalid(block_id);
            ErrorCode::Success
        }
        Err(err) => err,
    }
}

#[no_mangle]
pub unsafe extern "C" fn consensus_notifier_notify_engine_activated(
    notifier: *mut c_void,
    block_bytes: *const u8,
    block_bytes_len: usize,
) -> ErrorCode {
    check_null!(notifier, block_bytes);

    let block: Block = {
        let data = slice::from_raw_parts(block_bytes, block_bytes_len);
        let proto_block: proto::block::Block = match protobuf::parse_from_bytes(&data) {
            Ok(block) => block,
            Err(err) => {
                error!("Failed to parse block bytes: {:?}", err);
                return ErrorCode::InvalidArgument;
            }
        };
        proto_block.into()
    };

    (*(notifier as *mut BackgroundConsensusNotifier)).notify_engine_activated(&block);
    ErrorCode::Success
}

#[no_mangle]
pub unsafe extern "C" fn consensus_notifier_notify_engine_deactivated(
    notifier: *mut c_void,
    connection_id: *const c_char,
) -> ErrorCode {
    check_null!(notifier, connection_id);

    match deref_cstr(connection_id) {
        Ok(connection_id) => {
            (*(notifier as *mut BackgroundConsensusNotifier))
                .notify_engine_deactivated(connection_id.to_string());
            ErrorCode::Success
        }
        Err(err) => err,
    }
}

unsafe fn deref_cstr<'a>(cstr: *const c_char) -> Result<&'a str, ErrorCode> {
    CStr::from_ptr(cstr)
        .to_str()
        .map_err(|_| ErrorCode::InvalidArgument)
}

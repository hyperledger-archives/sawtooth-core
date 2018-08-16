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

use block::Block;
use cpython;
use cpython::{ObjectProtocol, PyClone, PyList, PyObject, Python, PythonObject, ToPyObject};
use database::lmdb::LmdbDatabase;
use journal::block_manager::BlockManager;
use journal::block_validator::{BlockValidationResult, BlockValidator, ValidationError};
use journal::block_wrapper::{BlockStatus, BlockWrapper};
use journal::chain::*;
use journal::chain_head_lock::ChainHeadLock;
use py_ffi;
use pylogger;
use state::state_pruning_manager::StatePruningManager;
use std::ffi::CStr;
use std::mem;
use std::os::raw::{c_char, c_void};
use std::slice;
use std::sync::mpsc::Sender;
use std::thread;
use std::time::Duration;

use protobuf::{self, Message};

use proto;
use proto::transaction_receipt::TransactionReceipt;

#[repr(u32)]
#[derive(Debug)]
pub enum ErrorCode {
    Success = 0,
    NullPointerProvided = 0x01,
    InvalidDataDir = 0x02,
    InvalidPythonObject = 0x03,
    InvalidBlockId = 0x04,

    Unknown = 0xff,
}

macro_rules! check_null {
    ($($arg:expr) , *) => {
        $(if $arg.is_null() { return ErrorCode::NullPointerProvided; })*
    }
}

#[no_mangle]
pub extern "C" fn chain_controller_new(
    block_store: *mut py_ffi::PyObject,
    block_manager: *const c_void,
    block_validator: *mut py_ffi::PyObject,
    state_database: *const c_void,
    chain_head_lock: *const c_void,
    consensus_notifier: *mut py_ffi::PyObject,
    observers: *mut py_ffi::PyObject,
    state_pruning_block_depth: u32,
    fork_cache_keep_time: u32,
    data_directory: *const c_char,
    chain_controller_ptr: *mut *const c_void,
) -> ErrorCode {
    check_null!(
        block_store,
        block_manager,
        block_validator,
        state_database,
        chain_head_lock,
        consensus_notifier,
        observers,
        data_directory
    );

    let data_dir = unsafe {
        match CStr::from_ptr(data_directory).to_str() {
            Ok(s) => s,
            Err(_) => return ErrorCode::InvalidDataDir,
        }
    };

    let py = unsafe { Python::assume_gil_acquired() };

    let py_block_store_reader = unsafe { PyObject::from_borrowed_ptr(py, block_store) };
    let py_block_validator = unsafe { PyObject::from_borrowed_ptr(py, block_validator) };
    let py_observers = unsafe { PyObject::from_borrowed_ptr(py, observers) };
    let chain_head_lock_ref =
        unsafe { (chain_head_lock as *const ChainHeadLock).as_ref().unwrap() };
    let py_consensus_notifier = unsafe { PyObject::from_borrowed_ptr(py, consensus_notifier) };

    let observer_wrappers = if let Ok(py_list) = py_observers.extract::<PyList>(py) {
        let mut res: Vec<Box<ChainObserver>> = Vec::with_capacity(py_list.len(py));
        py_list
            .iter(py)
            .for_each(|pyobj| res.push(Box::new(PyChainObserver::new(pyobj))));
        res
    } else {
        return ErrorCode::InvalidPythonObject;
    };

    let block_manager = unsafe { (*(block_manager as *const BlockManager)).clone() };
    let state_database = unsafe { (*(state_database as *const LmdbDatabase)).clone() };

    let state_pruning_manager = StatePruningManager::new(state_database);

    let chain_controller = ChainController::new(
        block_manager,
        PyBlockValidator::new(py_block_validator),
        Box::new(PyBlockStore::new(py_block_store_reader)),
        chain_head_lock_ref.clone(),
        Box::new(PyConsensusNotifier::new(py_consensus_notifier)),
        data_dir.into(),
        state_pruning_block_depth,
        observer_wrappers,
        state_pruning_manager,
        Duration::from_secs(fork_cache_keep_time as u64),
    );

    unsafe {
        *chain_controller_ptr = Box::into_raw(Box::new(chain_controller)) as *const c_void;
    }

    ErrorCode::Success
}

#[no_mangle]
pub extern "C" fn chain_controller_drop(chain_controller: *mut c_void) -> ErrorCode {
    check_null!(chain_controller);

    unsafe { Box::from_raw(chain_controller as *mut ChainController<PyBlockValidator>) };
    ErrorCode::Success
}

#[no_mangle]
pub extern "C" fn chain_controller_start(chain_controller: *mut c_void) -> ErrorCode {
    check_null!(chain_controller);

    unsafe {
        (*(chain_controller as *mut ChainController<PyBlockValidator>)).start();
    }

    ErrorCode::Success
}

#[no_mangle]
pub unsafe extern "C" fn chain_controller_block_validation_result(
    chain_controller: *mut c_void,
    block_id: *const c_char,
    result: *mut i32,
) -> ErrorCode {
    let block_id = match CStr::from_ptr(block_id).to_str() {
        Ok(s) => s,
        Err(_) => return ErrorCode::InvalidBlockId,
    };

    let status = match (*(chain_controller as *mut ChainController<PyBlockValidator>))
        .block_validation_result(block_id)
    {
        Some(r) => r.status,
        None => BlockStatus::Unknown,
    };
    *result = status as i32;
    ErrorCode::Success
}

#[no_mangle]
pub extern "C" fn chain_controller_stop(chain_controller: *mut c_void) -> ErrorCode {
    check_null!(chain_controller);

    unsafe {
        (*(chain_controller as *mut ChainController<PyBlockValidator>)).stop();
    }
    ErrorCode::Success
}

macro_rules! chain_controller_block_ffi {
    ($ffi_fn_name:ident, $cc_fn_name:ident, $block:ident, $($block_args:tt)*) => {
        #[no_mangle]
        pub unsafe extern "C" fn $ffi_fn_name(
            chain_controller: *mut c_void,
            block_bytes: *const u8,
            block_bytes_len: usize,
        ) -> ErrorCode {
            check_null!(chain_controller, block_bytes);

            let $block: Block = {
                let data = slice::from_raw_parts(block_bytes, block_bytes_len);
                let proto_block: proto::block::Block = match protobuf::parse_from_bytes(&data) {
                    Ok(block) => block,
                    Err(err) => {
                        error!("Failed to parse block bytes: {:?}", err);
                        return ErrorCode::Unknown;
                    }
                };
                proto_block.into()
            };

            (*(chain_controller as *mut ChainController<PyBlockValidator>)).$cc_fn_name($($block_args)*);

            ErrorCode::Success
        }
    }
}

chain_controller_block_ffi!(chain_controller_ignore_block, ignore_block, block, &block);
chain_controller_block_ffi!(chain_controller_fail_block, fail_block, block, &block);
chain_controller_block_ffi!(chain_controller_commit_block, commit_block, block, block);

#[no_mangle]
pub extern "C" fn chain_controller_queue_block(
    chain_controller: *mut c_void,
    block_id: *const c_char,
) -> ErrorCode {
    check_null!(chain_controller, block_id);

    let block_id = unsafe {
        match CStr::from_ptr(block_id).to_str() {
            Ok(s) => s,
            Err(_) => return ErrorCode::InvalidBlockId,
        }
    };

    unsafe {
        (*(chain_controller as *mut ChainController<PyBlockValidator>)).queue_block(block_id);
    }

    ErrorCode::Success
}

/// This is only exposed for the current python tests, it should be removed
/// when proper rust tests are written for the ChainController
#[no_mangle]
pub extern "C" fn chain_controller_on_block_received(
    chain_controller: *mut c_void,
    block_id: *const c_char,
) -> ErrorCode {
    check_null!(chain_controller, block_id);

    let block_id = unsafe {
        match CStr::from_ptr(block_id).to_str() {
            Ok(s) => s,
            Err(_) => return ErrorCode::InvalidBlockId,
        }
    };

    unsafe {
        if let Err(err) = (*(chain_controller as *mut ChainController<PyBlockValidator>))
            .on_block_received(block_id.into())
        {
            error!("ChainController.on_block_received error: {:?}", err);
            return ErrorCode::Unknown;
        }
    }

    ErrorCode::Success
}

#[no_mangle]
pub unsafe extern "C" fn chain_controller_chain_head(
    chain_controller: *mut c_void,
    block: *mut *const u8,
    block_len: *mut usize,
    block_cap: *mut usize,
) -> ErrorCode {
    check_null!(chain_controller);

    let controller = (*(chain_controller as *mut ChainController<PyBlockValidator>)).light_clone();

    if let Some(chain_head) = controller.chain_head().map(proto::block::Block::from) {
        match chain_head.write_to_bytes() {
            Ok(payload) => {
                *block_cap = payload.capacity();
                *block_len = payload.len();
                *block = payload.as_slice().as_ptr();

                mem::forget(payload);

                ErrorCode::Success
            }
            Err(err) => {
                warn!("Failed to serialize Block proto to bytes: {}", err);
                ErrorCode::Unknown
            }
        }
    } else {
        *block = 0 as *const u8;
        *block_len = 0;
        ErrorCode::Success
    }
}

#[no_mangle]
pub extern "C" fn sender_drop(sender: *const c_void) -> ErrorCode {
    check_null!(sender);

    unsafe { Box::from_raw(sender as *mut Sender<BlockWrapper>) };

    ErrorCode::Success
}

#[no_mangle]
pub extern "C" fn sender_send(
    sender: *const c_void,
    validation_result: *mut py_ffi::PyObject,
) -> ErrorCode {
    check_null!(sender, validation_result);

    let gil_guard = Python::acquire_gil();
    let py = gil_guard.python();

    let py_result = unsafe { PyObject::from_borrowed_ptr(py, validation_result) };
    let result: BlockValidationResult = py_result.extract(py).expect("Unable to extract block");

    unsafe {
        let sender = (*(sender as *mut Sender<BlockValidationResult>)).clone();
        py.allow_threads(move || match sender.send(result) {
            Ok(_) => ErrorCode::Success,
            Err(err) => {
                error!("Unable to send validation result: {:?}", err);
                ErrorCode::Unknown
            }
        })
    }
}

struct PyBlockValidator {
    py_block_validator: PyObject,
    ctypes_c_void: PyObject,
    py_validation_response_sender: PyObject,
    py_callback_maker: PyObject,
}

impl PyBlockValidator {
    fn new(py_block_validator: PyObject) -> Self {
        let gil_guard = Python::acquire_gil();
        let py = gil_guard.python();

        let ctypes_module = py.import("ctypes").expect("Unable to import ctypes");

        let ctypes_c_void = ctypes_module
            .get(py, "c_void_p")
            .expect("Unable to get c_void_p");

        let chain_module = py
            .import("sawtooth_validator.journal.chain")
            .expect("Unable to import sawtooth_validator.journal.chain");
        let py_validation_response_sender = chain_module
            .get(py, "ValidationResponseSender")
            .expect("Unable to get ValidationResponseSender");

        let ffi_module = py
            .import("sawtooth_validator.ffi")
            .expect("Unable to import sawtooth_validator.ffi");
        let py_callback_maker = ffi_module
            .get(py, "python_to_sender_callback")
            .expect("Unable to get python_to_sender_callback");

        PyBlockValidator {
            py_block_validator,
            ctypes_c_void,
            py_validation_response_sender,
            py_callback_maker,
        }
    }
}

impl Clone for PyBlockValidator {
    fn clone(&self) -> Self {
        let gil_guard = Python::acquire_gil();
        let py = gil_guard.python();
        PyBlockValidator::new(self.py_block_validator.clone_ref(py))
    }
}

impl BlockValidator for PyBlockValidator {
    fn has_block(&self, block_id: &str) -> bool {
        let gil_guard = Python::acquire_gil();
        let py = gil_guard.python();

        match self
            .py_block_validator
            .call_method(py, "has_block", (block_id,), None)
        {
            Err(_) => {
                // Presumably a KeyError, so no
                false
            }
            Ok(py_bool) => py_bool.extract(py).expect("Unable to extract boolean"),
        }
    }

    fn validate_block(&self, block: Block) -> Result<(), ValidationError> {
        let gil_guard = Python::acquire_gil();
        let py = gil_guard.python();

        self.py_block_validator
            .call_method(py, "validate_block", (block,), None)
            .map(|_| ())
            .map_err(|py_err| {
                ValidationError::BlockValidationFailure(py_err.get_type(py).name(py).into_owned())
            })
    }

    fn submit_blocks_for_verification(
        &self,
        blocks: &[Block],
        response_sender: Sender<BlockValidationResult>,
    ) {
        let gil_guard = Python::acquire_gil();
        let py = gil_guard.python();

        let sender_ptr = Box::into_raw(Box::new(response_sender)) as u64;

        let sender_c_void = self
            .ctypes_c_void
            .call(py, (sender_ptr,), None)
            .expect("unable to create ctypes.c_void_p");

        let py_sender = self
            .py_validation_response_sender
            .call(py, (sender_c_void,), None)
            .expect("unable to create ValidationResponseSender");

        let py_callback = self
            .py_callback_maker
            .call(py, (py_sender,), None)
            .expect("Unable to create py_callback");

        self.py_block_validator
            .call_method(
                py,
                "submit_blocks_for_verification",
                (blocks, py_callback),
                None,
            )
            .map(|_| ())
            .map_err(|py_err| {
                pylogger::exception(py, "Unable to call submit_blocks_for_verification", py_err);
                ()
            })
            .unwrap_or(());
    }

    fn process_pending(&self, block: &Block, response_sender: Sender<BlockValidationResult>) {
        let gil_guard = Python::acquire_gil();
        let py = gil_guard.python();

        let sender_ptr = Box::into_raw(Box::new(response_sender)) as u64;

        let sender_c_void = self
            .ctypes_c_void
            .call(py, (sender_ptr,), None)
            .expect("unable to create ctypes.c_void_p");

        let py_sender = self
            .py_validation_response_sender
            .call(py, (sender_c_void,), None)
            .expect("unable to create ValidationResponseSender");

        let py_callback = self
            .py_callback_maker
            .call(py, (py_sender,), None)
            .expect("Unable to create py_callback");

        match self
            .py_block_validator
            .call_method(py, "process_pending", (block, py_callback), None)
        {
            Ok(_) => (),
            Err(py_err) => warn!("During call to process_pending: {:?}", py_err),
        }
    }
}

struct PyBlockStore {
    py_block_store: PyObject,
}

impl PyBlockStore {
    fn new(py_block_store: PyObject) -> Self {
        PyBlockStore { py_block_store }
    }
}

impl ChainReader for PyBlockStore {
    fn chain_head(&self) -> Result<Option<Block>, ChainReadError> {
        let gil_guard = Python::acquire_gil();
        let py = gil_guard.python();

        self.py_block_store
            .getattr(py, "chain_head")
            .and_then(|result| result.extract(py))
            .map(|bw: Option<BlockWrapper>| {
                if let Some(bw) = bw {
                    Some(bw.block())
                } else {
                    None
                }
            })
            .map_err(|py_err| {
                pylogger::exception(py, "Unable to call block_store.chain_head", py_err);
                ChainReadError::GeneralReadError("Unable to read from python block store".into())
            })
    }

    fn get_block_by_block_id(&self, block_id: &str) -> Result<Option<Block>, ChainReadError> {
        let gil_guard = Python::acquire_gil();
        let py = gil_guard.python();

        self.py_block_store
            .get_item(py, block_id)
            .and_then(|result| result.extract(py))
            .map(|bw: Option<BlockWrapper>| {
                if let Some(bw) = bw {
                    Some(bw.block())
                } else {
                    None
                }
            })
            .or_else(|py_err| {
                if py_err.get_type(py).name(py) == "KeyError" {
                    Ok(None)
                } else {
                    Err(py_err)
                }
            })
            .map_err(|py_err| {
                pylogger::exception(py, "Unable to call block_store.chain_head", py_err);
                ChainReadError::GeneralReadError("Unable to read from python block store".into())
            })
    }

    fn get_block_by_block_num(&self, block_num: u64) -> Result<Option<Block>, ChainReadError> {
        let gil_guard = Python::acquire_gil();
        let py = gil_guard.python();

        self.py_block_store
            .call_method(py, "get_block_by_number", (block_num,), None)
            .and_then(|result| result.extract(py))
            .map(|bw: Option<BlockWrapper>| {
                if let Some(bw) = bw {
                    Some(bw.block())
                } else {
                    None
                }
            })
            .or_else(|py_err| {
                if py_err.get_type(py).name(py) == "KeyError" {
                    Ok(None)
                } else {
                    Err(py_err)
                }
            })
            .map_err(|py_err| {
                pylogger::exception(py, "Unable to call block_store.chain_head", py_err);
                ChainReadError::GeneralReadError("Unable to read from python block store".into())
            })
    }

    fn count_committed_transactions(&self) -> Result<usize, ChainReadError> {
        let gil_guard = Python::acquire_gil();
        let py = gil_guard.python();

        self.py_block_store
            .call_method(py, "get_transaction_count", cpython::NoArgs, None)
            .and_then(|result| result.extract(py))
            .map_err(|py_err| {
                pylogger::exception(py, "Unable to call block_store.chain_head", py_err);
                ChainReadError::GeneralReadError("Unable to read from python block store".into())
            })
    }
}

struct PyChainObserver {
    py_observer: PyObject,
}

impl PyChainObserver {
    fn new(py_observer: PyObject) -> Self {
        PyChainObserver { py_observer }
    }
}

impl ChainObserver for PyChainObserver {
    fn chain_update(&mut self, block: &Block, receipts: &[TransactionReceipt]) {
        let gil_guard = Python::acquire_gil();
        let py = gil_guard.python();

        self.py_observer
            .call_method(py, "chain_update", (block, receipts), None)
            .map(|_| ())
            .map_err(|py_err| {
                pylogger::exception(py, "Unable to call observer.chain_update", py_err);
                ()
            })
            .unwrap_or(())
    }
}

struct PyConsensusNotifier {
    py_consensus_notifier: PyObject,
}

impl PyConsensusNotifier {
    fn new(py_consensus_notifier: PyObject) -> Self {
        PyConsensusNotifier {
            py_consensus_notifier,
        }
    }
}

impl Clone for PyConsensusNotifier {
    fn clone(&self) -> Self {
        let gil_guard = Python::acquire_gil();
        let py = gil_guard.python();

        PyConsensusNotifier {
            py_consensus_notifier: self.py_consensus_notifier.clone_ref(py),
        }
    }
}

impl ConsensusNotifier for PyConsensusNotifier {
    fn notify_block_new(&self, block: &Block) {
        let gil_guard = Python::acquire_gil();
        let py = gil_guard.python();

        self.py_consensus_notifier
            .call_method(py, "notify_block_new", (block,), None)
            .map(|_| ())
            .map_err(|py_err| {
                pylogger::exception(
                    py,
                    "Unable to call consensus_notifier.notify_block_new",
                    py_err,
                );
                ()
            })
            .unwrap_or(())
    }

    fn notify_block_valid(&self, block_id: &str) {
        let gil_guard = Python::acquire_gil();
        let py = gil_guard.python();

        self.py_consensus_notifier
            .call_method(py, "notify_block_valid", (block_id,), None)
            .map(|_| ())
            .map_err(|py_err| {
                pylogger::exception(
                    py,
                    "Unable to call consensus_notifier.notify_block_valid",
                    py_err,
                );
                ()
            })
            .unwrap_or(())
    }

    fn notify_block_invalid(&self, block_id: &str) {
        let gil_guard = Python::acquire_gil();
        let py = gil_guard.python();

        self.py_consensus_notifier
            .call_method(py, "notify_block_invalid", (block_id,), None)
            .map(|_| ())
            .map_err(|py_err| {
                pylogger::exception(
                    py,
                    "Unable to call consensus_notifier.notify_block_invalid",
                    py_err,
                );
                ()
            })
            .unwrap_or(())
    }

    fn notify_block_commit(&self, block_id: &str) {
        let gil_guard = Python::acquire_gil();
        let py = gil_guard.python();

        self.py_consensus_notifier
            .call_method(py, "notify_block_commit", (block_id,), None)
            .map(|_| ())
            .map_err(|py_err| {
                pylogger::exception(
                    py,
                    "Unable to call consensus_notifier.notify_block_commit",
                    py_err,
                );
                ()
            })
            .unwrap_or(())
    }
}

impl ToPyObject for TransactionReceipt {
    type ObjectType = PyObject;

    fn to_py_object(&self, py: Python) -> PyObject {
        let txn_receipt_protobuf_mod = py
            .import("sawtooth_validator.protobuf.transaction_receipt_pb2")
            .expect("Unable to import transaction_receipt_pb2");
        let py_txn_receipt_class = txn_receipt_protobuf_mod
            .get(py, "TransactionReceipt")
            .expect("Unable to get TransactionReceipt");

        let py_txn_receipt = py_txn_receipt_class
            .call(py, cpython::NoArgs, None)
            .expect("Unable to instantiate TransactionReceipt");
        py_txn_receipt
            .call_method(
                py,
                "ParseFromString",
                (cpython::PyBytes::new(py, &self.write_to_bytes().unwrap()).into_object(),),
                None,
            )
            .expect("Unable to ParseFromString");

        py_txn_receipt
    }
}

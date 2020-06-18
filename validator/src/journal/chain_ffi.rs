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

#![allow(unknown_lints)]

use block::Block;
use consensus::notifier::BackgroundConsensusNotifier;
use consensus::registry_ffi::PyConsensusRegistry;
use cpython::{self, ObjectProtocol, PyList, PyObject, Python, PythonObject, ToPyObject};
use database::lmdb::LmdbDatabase;
use execution::py_executor::PyExecutor;
use gossip::permission_verifier::PyPermissionVerifier;
use journal::block_manager::BlockManager;
use journal::block_validator::{BlockValidationResultStore, BlockValidator};
use journal::block_wrapper::BlockStatus;
use journal::chain::*;
use journal::chain_head_lock::ChainHeadLock;
use journal::commit_store::CommitStore;
use py_ffi;
use pylogger;
use state::state_pruning_manager::StatePruningManager;
use state::state_view_factory::StateViewFactory;
use std::ffi::CStr;
use std::mem;
use std::os::raw::{c_char, c_void};
use std::ptr;
use std::slice;
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
    UnknownBlock = 0x05,

    Unknown = 0xff,
}

macro_rules! check_null {
    ($($arg:expr) , *) => {
        $(if $arg.is_null() { return ErrorCode::NullPointerProvided; })*
    }
}

#[no_mangle]
pub unsafe extern "C" fn chain_controller_new(
    commit_store: *mut c_void,
    block_manager: *const c_void,
    block_validator: *const c_void,
    state_database: *const c_void,
    chain_head_lock: *const c_void,
    block_validation_result_cache: *const c_void,
    consensus_notifier_service: *mut c_void,
    observers: *mut py_ffi::PyObject,
    state_pruning_block_depth: u32,
    fork_cache_keep_time: u32,
    data_directory: *const c_char,
    chain_controller_ptr: *mut *const c_void,
    consensus_registry: *mut py_ffi::PyObject,
) -> ErrorCode {
    check_null!(
        commit_store,
        block_manager,
        block_validator,
        state_database,
        chain_head_lock,
        consensus_notifier_service,
        consensus_registry,
        observers,
        data_directory
    );

    let data_dir = match CStr::from_ptr(data_directory).to_str() {
        Ok(s) => s,
        Err(_) => return ErrorCode::InvalidDataDir,
    };

    let py = Python::assume_gil_acquired();

    let block_validator =
        (*(block_validator as *const BlockValidator<PyExecutor, PyPermissionVerifier>)).clone();

    let py_observers = PyObject::from_borrowed_ptr(py, observers);
    let chain_head_lock_ref = (chain_head_lock as *const ChainHeadLock).as_ref().unwrap();
    let consensus_notifier_service =
        Box::from_raw(consensus_notifier_service as *mut BackgroundConsensusNotifier);
    let py_consensus_registry = PyObject::from_borrowed_ptr(py, consensus_registry);

    let observer_wrappers = if let Ok(py_list) = py_observers.extract::<PyList>(py) {
        let mut res: Vec<Box<ChainObserver>> = Vec::with_capacity(py_list.len(py));
        py_list
            .iter(py)
            .for_each(|pyobj| res.push(Box::new(PyChainObserver::new(pyobj))));
        res
    } else {
        return ErrorCode::InvalidPythonObject;
    };

    let block_manager = (*(block_manager as *const BlockManager)).clone();
    let state_database = (*(state_database as *const LmdbDatabase)).clone();
    let results_cache =
        (*(block_validation_result_cache as *const BlockValidationResultStore)).clone();

    let state_view_factory = StateViewFactory::new(state_database.clone());

    let state_pruning_manager = StatePruningManager::new(state_database);

    let commit_store = Box::from_raw(commit_store as *mut CommitStore);

    let chain_controller = ChainController::new(
        block_manager,
        block_validator,
        commit_store.clone(),
        chain_head_lock_ref.clone(),
        results_cache,
        consensus_notifier_service.clone(),
        Box::new(PyConsensusRegistry::new(py_consensus_registry)),
        state_view_factory,
        data_dir.into(),
        state_pruning_block_depth,
        observer_wrappers,
        state_pruning_manager,
        Duration::from_secs(u64::from(fork_cache_keep_time)),
    );

    *chain_controller_ptr = Box::into_raw(Box::new(chain_controller)) as *const c_void;

    Box::into_raw(consensus_notifier_service);
    Box::into_raw(commit_store);

    ErrorCode::Success
}

#[no_mangle]
pub unsafe extern "C" fn chain_controller_drop(chain_controller: *mut c_void) -> ErrorCode {
    check_null!(chain_controller);

    Box::from_raw(chain_controller as *mut ChainController<PyExecutor, PyPermissionVerifier>);
    ErrorCode::Success
}

#[no_mangle]
pub unsafe extern "C" fn chain_controller_start(chain_controller: *mut c_void) -> ErrorCode {
    check_null!(chain_controller);

    (*(chain_controller as *mut ChainController<PyExecutor, PyPermissionVerifier>)).start();

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

    let status = match (*(chain_controller
        as *mut ChainController<PyExecutor, PyPermissionVerifier>))
        .block_validation_result(block_id)
    {
        Some(r) => r.status,
        None => BlockStatus::Unknown,
    };
    *result = status as i32;
    ErrorCode::Success
}

#[no_mangle]
pub unsafe extern "C" fn chain_controller_stop(chain_controller: *mut c_void) -> ErrorCode {
    check_null!(chain_controller);

    (*(chain_controller as *mut ChainController<PyExecutor, PyPermissionVerifier>)).stop();

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

            (*(chain_controller as *mut ChainController<PyExecutor, PyPermissionVerifier>)).$cc_fn_name($($block_args)*);

            ErrorCode::Success
        }
    }
}

chain_controller_block_ffi!(
    chain_controller_validate_block,
    validate_block,
    block,
    &block
);
chain_controller_block_ffi!(chain_controller_ignore_block, ignore_block, block, &block);
chain_controller_block_ffi!(chain_controller_fail_block, fail_block, block, &block);
chain_controller_block_ffi!(chain_controller_commit_block, commit_block, block, block);

#[no_mangle]
pub unsafe extern "C" fn chain_controller_queue_block(
    chain_controller: *mut c_void,
    block_id: *const c_char,
) -> ErrorCode {
    check_null!(chain_controller, block_id);

    let block_id = match CStr::from_ptr(block_id).to_str() {
        Ok(s) => s,
        Err(_) => return ErrorCode::InvalidBlockId,
    };

    (*(chain_controller as *mut ChainController<PyExecutor, PyPermissionVerifier>))
        .queue_block(block_id);

    ErrorCode::Success
}

/// This is only exposed for the current python tests, it should be removed
/// when proper rust tests are written for the ChainController
#[no_mangle]
pub unsafe extern "C" fn chain_controller_on_block_received(
    chain_controller: *mut c_void,
    block_id: *const c_char,
) -> ErrorCode {
    check_null!(chain_controller, block_id);

    let block_id = match CStr::from_ptr(block_id).to_str() {
        Ok(s) => s,
        Err(_) => return ErrorCode::InvalidBlockId,
    };

    if let Err(err) = (*(chain_controller
        as *mut ChainController<PyExecutor, PyPermissionVerifier>))
        .on_block_received(block_id)
    {
        error!("ChainController.on_block_received error: {:?}", err);
        return ErrorCode::Unknown;
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

    let controller = (*(chain_controller
        as *mut ChainController<PyExecutor, PyPermissionVerifier>))
        .light_clone();

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
        *block = ptr::null();
        *block_len = 0;
        ErrorCode::Success
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

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
use cpython::{
    self, FromPyObject, NoArgs, ObjectProtocol, PyClone, PyList, PyObject, Python, PythonObject,
    ToPyObject,
};
use database::lmdb::LmdbDatabase;
use execution::py_executor::PyExecutor;
use gossip::permission_verifier::PyPermissionVerifier;
use journal::block_manager::BlockManager;
use journal::block_store::{
    BatchIndex, BlockStore, BlockStoreError, IndexedBlockStore, TransactionIndex,
};
use journal::block_validator::{BlockValidationResultStore, BlockValidator};
use journal::block_wrapper::{BlockStatus, BlockWrapper};
use journal::chain::*;
use journal::chain_head_lock::ChainHeadLock;
use py_ffi;
use pylogger;
use state::state_pruning_manager::StatePruningManager;
use std::ffi::CStr;
use std::marker::PhantomData;
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
    block_store: *mut py_ffi::PyObject,
    block_manager: *const c_void,
    block_validator: *const c_void,
    state_database: *const c_void,
    chain_head_lock: *const c_void,
    block_validation_result_cache: *const c_void,
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

    let data_dir = match CStr::from_ptr(data_directory).to_str() {
        Ok(s) => s,
        Err(_) => return ErrorCode::InvalidDataDir,
    };

    let py = Python::assume_gil_acquired();

    let py_block_store_reader = PyObject::from_borrowed_ptr(py, block_store);

    let block_validator = (*(block_validator
        as *const BlockValidator<
            PyExecutor,
            PyPermissionVerifier,
            PyBlockStore,
            PyBlockStore,
            PyBlockStore,
        >))
        .clone();

    let py_observers = PyObject::from_borrowed_ptr(py, observers);
    let chain_head_lock_ref = (chain_head_lock as *const ChainHeadLock).as_ref().unwrap();
    let py_consensus_notifier = PyObject::from_borrowed_ptr(py, consensus_notifier);

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

    let state_pruning_manager = StatePruningManager::new(state_database);

    let chain_controller = ChainController::new(
        block_manager,
        block_validator,
        Box::new(PyBlockStore::new(py_block_store_reader)),
        chain_head_lock_ref.clone(),
        results_cache,
        Box::new(PyConsensusNotifier::new(py_consensus_notifier)),
        data_dir.into(),
        state_pruning_block_depth,
        observer_wrappers,
        state_pruning_manager,
        Duration::from_secs(u64::from(fork_cache_keep_time)),
    );

    *chain_controller_ptr = Box::into_raw(Box::new(chain_controller)) as *const c_void;

    ErrorCode::Success
}

#[no_mangle]
pub unsafe extern "C" fn chain_controller_drop(chain_controller: *mut c_void) -> ErrorCode {
    check_null!(chain_controller);

    Box::from_raw(
        chain_controller
            as *mut ChainController<
                PyExecutor,
                PyPermissionVerifier,
                PyBlockStore,
                PyBlockStore,
                PyBlockStore,
            >,
    );
    ErrorCode::Success
}

#[no_mangle]
pub unsafe extern "C" fn chain_controller_start(chain_controller: *mut c_void) -> ErrorCode {
    check_null!(chain_controller);

    (*(chain_controller
        as *mut ChainController<
            PyExecutor,
            PyPermissionVerifier,
            PyBlockStore,
            PyBlockStore,
            PyBlockStore,
        >))
        .start();

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
        as *mut ChainController<
            PyExecutor,
            PyPermissionVerifier,
            PyBlockStore,
            PyBlockStore,
            PyBlockStore,
        >))
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

    (*(chain_controller
        as *mut ChainController<
            PyExecutor,
            PyPermissionVerifier,
            PyBlockStore,
            PyBlockStore,
            PyBlockStore,
        >))
        .stop();

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

            (*(chain_controller as *mut ChainController<PyExecutor, PyPermissionVerifier, PyBlockStore, PyBlockStore, PyBlockStore>)).$cc_fn_name($($block_args)*);

            ErrorCode::Success
        }
    }
}

chain_controller_block_ffi!(chain_controller_ignore_block, ignore_block, block, &block);
chain_controller_block_ffi!(chain_controller_fail_block, fail_block, block, &block);
chain_controller_block_ffi!(chain_controller_commit_block, commit_block, block, block);

#[repr(C)]
#[derive(Debug)]
pub struct BlockPayload {
    block_bytes: *const u8,
    block_cap: usize,
    block_len: usize,
}

#[no_mangle]
pub unsafe extern "C" fn chain_controller_reclaim_block_payload_vec(
    vec_ptr: *mut BlockPayload,
    vec_len: usize,
    vec_cap: usize,
) -> isize {
    Vec::from_raw_parts(vec_ptr, vec_len, vec_cap);

    0
}

#[no_mangle]
pub unsafe extern "C" fn chain_controller_forks(
    chain_controller: *mut c_void,
    head: *const c_char,
    forks: *mut *const BlockPayload,
    forks_len: *mut usize,
    forks_cap: *mut usize,
) -> ErrorCode {
    check_null!(chain_controller, head);

    let head = match CStr::from_ptr(head).to_str() {
        Ok(s) => s,
        Err(_) => return ErrorCode::InvalidBlockId,
    };

    match (*(chain_controller
        as *mut ChainController<
            PyExecutor,
            PyPermissionVerifier,
            PyBlockStore,
            PyBlockStore,
            PyBlockStore,
        >))
        .forks(head)
    {
        None => ErrorCode::UnknownBlock,
        Some(blocks) => {
            let payloads: Vec<BlockPayload> = blocks
                .into_iter()
                .map(|block| {
                    let proto_block: proto::block::Block = block.into();
                    let bytes = proto_block
                        .write_to_bytes()
                        .expect("Failed to serialize proto Block");

                    let payload = BlockPayload {
                        block_cap: bytes.capacity(),
                        block_len: bytes.len(),
                        block_bytes: bytes.as_slice().as_ptr(),
                    };

                    mem::forget(bytes);

                    payload
                }).collect();

            *forks_cap = payloads.capacity();
            *forks_len = payloads.len();
            *forks = payloads.as_slice().as_ptr();

            mem::forget(payloads);

            ErrorCode::Success
        }
    }
}

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

    (*(chain_controller
        as *mut ChainController<
            PyExecutor,
            PyPermissionVerifier,
            PyBlockStore,
            PyBlockStore,
            PyBlockStore,
        >))
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
        as *mut ChainController<
            PyExecutor,
            PyPermissionVerifier,
            PyBlockStore,
            PyBlockStore,
            PyBlockStore,
        >))
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
        as *mut ChainController<
            PyExecutor,
            PyPermissionVerifier,
            PyBlockStore,
            PyBlockStore,
            PyBlockStore,
        >))
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

pub struct PyBlockStore {
    py_block_store: PyObject,
}

impl PyBlockStore {
    pub fn new(py_block_store: PyObject) -> Self {
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
            }).map_err(|py_err| {
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
            }).or_else(|py_err| {
                if py_err.get_type(py).name(py) == "KeyError" {
                    Ok(None)
                } else {
                    Err(py_err)
                }
            }).map_err(|py_err| {
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
            }).or_else(|py_err| {
                if py_err.get_type(py).name(py) == "KeyError" {
                    Ok(None)
                } else {
                    Err(py_err)
                }
            }).map_err(|py_err| {
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

impl BlockStore for PyBlockStore {
    fn get<'a>(
        &'a self,
        block_ids: &[&str],
    ) -> Result<Box<Iterator<Item = Block> + 'a>, BlockStoreError> {
        let gil_guard = Python::acquire_gil();
        let py = gil_guard.python();

        self.py_block_store
            .call_method(py, "get_blocks", (block_ids,), None)
            .and_then(|py_list| py_list.call_method(py, "__iter__", NoArgs, None))
            .and_then(|py_iter| {
                Ok(Box::new(PyIteratorWrapper::with_xform(
                    py_iter,
                    Box::new(unwrap_block),
                )) as Box<Iterator<Item = Block>>)
            }).map_err(|py_err| {
                pylogger::exception(py, "Unable to call block_store.get_blocks", py_err);
                BlockStoreError::Error(format!("Unable to read blocks: {:?}", block_ids))
            })
    }

    fn delete(&mut self, block_ids: &[&str]) -> Result<Vec<Block>, BlockStoreError> {
        let gil_guard = Python::acquire_gil();
        let py = gil_guard.python();
        let mut deleted_blocks = Vec::new();
        for block_id in block_ids {
            let block: Block = self
                .py_block_store
                .call_method(py, "get", (block_id,), None)
                // Unwrap the block wrapper
                .and_then(|blkw| blkw.getattr(py, "block"))
                .map_err(|py_err| {
                    pylogger::exception(py, "Unable to call block_store.get_blocks", py_err);
                    BlockStoreError::Error("Unable to get blocks".into())
                })?.extract(py)
                .expect("Unable to convert block from python");

            self.py_block_store
                .call_method(py, "__delitem__", (block_id,), None)
                .map_err(|py_err| {
                    pylogger::exception(py, "Unable to call block_store.get_blocks", py_err);
                    BlockStoreError::Error("Unable to delete blocks".into())
                })?;

            deleted_blocks.push(block);
        }

        Ok(deleted_blocks)
    }

    fn put(&mut self, blocks: Vec<Block>) -> Result<(), BlockStoreError> {
        let gil_guard = Python::acquire_gil();
        let py = gil_guard.python();
        for block in blocks {
            let block_wrapper = py
                .import("sawtooth_validator.journal.block_wrapper")
                .expect("Unable to import block_wrapper")
                .get(py, "BlockWrapper")
                .expect("Unable to import BlockWrapper");

            self.py_block_store
                .call_method(
                    py,
                    "__setitem__",
                    (
                        &block.header_signature,
                        block_wrapper
                            .call(py, (&block,), None)
                            .expect("Unable to wrap block."),
                    ),
                    None,
                ).map_err(|py_err| {
                    pylogger::exception(py, "Unable to call block_store.get_blocks", py_err);
                    BlockStoreError::Error("Unable to put blocks".into())
                })?;
        }

        Ok(())
    }

    fn iter(&self) -> Result<Box<Iterator<Item = Block>>, BlockStoreError> {
        let gil_guard = Python::acquire_gil();
        let py = gil_guard.python();

        self.py_block_store
            .call_method(py, "__iter__", NoArgs, None)
            .and_then(|py_iter| {
                Ok(Box::new(PyIteratorWrapper::with_xform(
                    py_iter,
                    Box::new(unwrap_block),
                )) as Box<Iterator<Item = Block>>)
            }).map_err(|py_err| {
                let py = unsafe { Python::assume_gil_acquired() };
                pylogger::exception(py, "Unable to call iter(block_store)", py_err);
                BlockStoreError::Error("Unable to iterate block store".into())
            })
    }
}

#[allow(needless_pass_by_value)]
fn unwrap_block(py: Python, block_wrapper: PyObject) -> PyObject {
    block_wrapper
        .getattr(py, "block")
        .expect("Unable to get block from block wrapper")
}

struct PyIteratorWrapper<T> {
    py_iter: PyObject,
    target_type: PhantomData<T>,
    xform: Box<Fn(Python, PyObject) -> PyObject>,
}

impl<T> PyIteratorWrapper<T>
where
    for<'source> T: FromPyObject<'source>,
{
    fn with_xform(py_iter: PyObject, xform: Box<Fn(Python, PyObject) -> PyObject>) -> Self {
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

impl BatchIndex for PyBlockStore {
    fn contains(&self, id: &str) -> Result<bool, BlockStoreError> {
        let gil_guard = Python::acquire_gil();
        let py = gil_guard.python();
        self.py_block_store
            .call_method(py, "has_batch", (id,), None)
            .map_err(|py_err| {
                BlockStoreError::Error(format!(
                    "Error calling has_batch on the block store: {:?}",
                    py_err
                ))
            })?.extract::<bool>(py)
            .map_err(|py_err| {
                BlockStoreError::Error(format!("Error extracting bool: {:?}", py_err))
            })
    }

    fn get_block_by_id(&self, id: &str) -> Result<Option<Block>, BlockStoreError> {
        let gil_guard = Python::acquire_gil();
        let py = gil_guard.python();
        self.py_block_store
            .call_method(py, "get_block_by_batch_id", (id,), None)
            .and_then(|r| r.extract(py))
            .map(|bw: Option<BlockWrapper>| {
                if let Some(bw) = bw {
                    Some(bw.block())
                } else {
                    None
                }
            }).or_else(|py_err| {
                if py_err.get_type(py).name(py) == "ValueError" {
                    Ok(None)
                } else {
                    Err(BlockStoreError::Error(format!(
                        "Error calling get_block_by_batch_id: {:?}",
                        py_err
                    )))
                }
            })
    }
}

impl TransactionIndex for PyBlockStore {
    fn contains(&self, id: &str) -> Result<bool, BlockStoreError> {
        let gil_guard = Python::acquire_gil();
        let py = gil_guard.python();
        self.py_block_store
            .call_method(py, "has_transaction", (id,), None)
            .map_err(|py_err| {
                BlockStoreError::Error(format!(
                    "Error calling has_transaction on the block store: {:?}",
                    py_err
                ))
            })?.extract::<bool>(py)
            .map_err(|py_err| {
                BlockStoreError::Error(format!("Error extracting bool: {:?}", py_err))
            })
    }

    fn get_block_by_id(&self, id: &str) -> Result<Option<Block>, BlockStoreError> {
        let gil_guard = Python::acquire_gil();
        let py = gil_guard.python();
        self.py_block_store
            .call_method(py, "get_block_by_transaction_id", (id,), None)
            .and_then(|r| r.extract(py))
            .map(|bw: Option<BlockWrapper>| {
                if let Some(bw) = bw {
                    Some(bw.block())
                } else {
                    None
                }
            }).or_else(|py_err| {
                if py_err.get_type(py).name(py) == "ValueError" {
                    Ok(None)
                } else {
                    Err(BlockStoreError::Error(format!(
                        "Error calling get_block_by_transaction_id: {:?}",
                        py_err
                    )))
                }
            })
    }
}

impl IndexedBlockStore for PyBlockStore {}

impl Clone for PyBlockStore {
    fn clone(&self) -> Self {
        let gil_guard = Python::acquire_gil();
        let py = gil_guard.python();
        PyBlockStore {
            py_block_store: self.py_block_store.clone_ref(py),
        }
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
            }).unwrap_or(())
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
            }).unwrap_or(())
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
            }).unwrap_or(())
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
            }).unwrap_or(())
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
            }).unwrap_or(())
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
            ).expect("Unable to ParseFromString");

        py_txn_receipt
    }
}

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
use cpython::{ObjectProtocol, PyClone, PyList, PyObject, Python, PythonObject, ToPyObject};
use database::lmdb::LmdbDatabase;
use ffi::PyIteratorWrapper;
use journal::block_validator::{BlockValidator, ValidationError};
use journal::block_wrapper::BlockWrapper;
use journal::chain::*;
use journal::chain_head_lock::ChainHeadLock;
use py_ffi;
use pylogger;
use state::state_pruning_manager::StatePruningManager;
use std::ffi::CStr;
use std::mem;
use std::os::raw::{c_char, c_void};
use std::sync::mpsc::Sender;
use std::thread;

use protobuf::Message;

use proto::block::Block;
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
    block_cache: *mut py_ffi::PyObject,
    block_validator: *mut py_ffi::PyObject,
    state_database: *const c_void,
    chain_head_lock: *const c_void,
    consensus_notifier: *mut py_ffi::PyObject,
    observers: *mut py_ffi::PyObject,
    state_pruning_block_depth: u32,
    data_directory: *const c_char,
    chain_controller_ptr: *mut *const c_void,
) -> ErrorCode {
    check_null!(
        block_store,
        block_cache,
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
    let py_block_store_writer = unsafe { PyObject::from_borrowed_ptr(py, block_store) };
    let py_block_cache = unsafe { PyObject::from_borrowed_ptr(py, block_cache) };
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

    let state_database = unsafe { (*(state_database as *const LmdbDatabase)).clone() };

    let state_pruning_manager = StatePruningManager::new(state_database);

    let chain_controller = ChainController::new(
        PyBlockCache::new(py_block_cache),
        PyBlockValidator::new(py_block_validator),
        Box::new(PyBlockStore::new(py_block_store_writer)),
        Box::new(PyBlockStore::new(py_block_store_reader)),
        chain_head_lock_ref.clone(),
        Box::new(PyConsensusNotifier::new(py_consensus_notifier)),
        data_dir.into(),
        state_pruning_block_depth,
        observer_wrappers,
        state_pruning_manager,
    );

    unsafe {
        *chain_controller_ptr = Box::into_raw(Box::new(chain_controller)) as *const c_void;
    }

    ErrorCode::Success
}

#[no_mangle]
pub extern "C" fn chain_controller_drop(chain_controller: *mut c_void) -> ErrorCode {
    check_null!(chain_controller);

    unsafe {
        Box::from_raw(chain_controller as *mut ChainController<PyBlockCache, PyBlockValidator>)
    };
    ErrorCode::Success
}

#[no_mangle]
pub extern "C" fn chain_controller_start(chain_controller: *mut c_void) -> ErrorCode {
    check_null!(chain_controller);

    unsafe {
        (*(chain_controller as *mut ChainController<PyBlockCache, PyBlockValidator>)).start();
    }

    ErrorCode::Success
}

#[no_mangle]
pub extern "C" fn chain_controller_stop(chain_controller: *mut c_void) -> ErrorCode {
    check_null!(chain_controller);

    unsafe {
        (*(chain_controller as *mut ChainController<PyBlockCache, PyBlockValidator>)).stop();
    }
    ErrorCode::Success
}

#[no_mangle]
pub extern "C" fn chain_controller_has_block(
    chain_controller: *mut c_void,
    block_id: *const c_char,
    result: *mut bool,
) -> ErrorCode {
    check_null!(chain_controller, block_id);

    let block_id = unsafe {
        match CStr::from_ptr(block_id).to_str() {
            Ok(s) => s,
            Err(_) => return ErrorCode::InvalidBlockId,
        }
    };

    unsafe {
        *result = (*(chain_controller as *mut ChainController<PyBlockCache, PyBlockValidator>))
            .has_block(block_id);
    }

    ErrorCode::Success
}

macro_rules! chain_controller_block_ffi {
    ($ffi_fn_name:ident, $cc_fn_name:ident, $block:ident, $($block_args:tt)*) => {
        #[no_mangle]
        pub extern "C" fn $ffi_fn_name(
            chain_controller: *mut c_void,
            block: *mut py_ffi::PyObject,
        ) -> ErrorCode {
            check_null!(chain_controller, block);

            let gil_guard = Python::acquire_gil();
            let py = gil_guard.python();

            let mut $block: BlockWrapper = unsafe {
                match PyObject::from_borrowed_ptr(py, block).extract(py) {
                    Ok(val) => val,
                    Err(py_err) => {
                        pylogger::exception(
                            py,
                            "chain_controller_queue_block: unable to get block",
                            py_err,
                        );
                        return ErrorCode::InvalidPythonObject;
                    }
                }
            };

            unsafe {
                let controller = (*(chain_controller
                    as *mut ChainController<PyBlockCache, PyBlockValidator>))
                    .light_clone();

                py.allow_threads(move || {
                    controller.$cc_fn_name($($block_args)*);
                });
            }

            ErrorCode::Success
        }
    }
}

chain_controller_block_ffi!(chain_controller_ignore_block, ignore_block, block, &block);
chain_controller_block_ffi!(chain_controller_fail_block, fail_block, block, &mut block);
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

    let block_wrappers =
        (*(chain_controller as *mut ChainController<PyBlockCache, PyBlockValidator>)).forks();

    let payloads: Vec<BlockPayload> = block_wrappers
        .into_iter()
        .map(|block_wrapper| {
            let proto_block: Block = block_wrapper.block().into();
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

#[no_mangle]
pub extern "C" fn chain_controller_queue_block(
    chain_controller: *mut c_void,
    block: *mut py_ffi::PyObject,
) -> ErrorCode {
    check_null!(chain_controller, block);

    let gil_guard = Python::acquire_gil();
    let py = gil_guard.python();

    let block: BlockWrapper = unsafe {
        match PyObject::from_borrowed_ptr(py, block).extract(py) {
            Ok(val) => val,
            Err(py_err) => {
                pylogger::exception(
                    py,
                    "chain_controller_queue_block: unable to get block",
                    py_err,
                );
                return ErrorCode::InvalidPythonObject;
            }
        }
    };
    unsafe {
        let controller = (*(chain_controller
            as *mut ChainController<PyBlockCache, PyBlockValidator>))
            .light_clone();

        py.allow_threads(move || {
            let builder = thread::Builder::new().name("ChainController.queue_block".into());
            builder
                .spawn(move || {
                    controller.queue_block(block);
                }).unwrap()
                .join()
                .unwrap();
        });
    }

    ErrorCode::Success
}

#[no_mangle]
pub extern "C" fn chain_controller_submit_blocks_for_verification(
    chain_controller: *mut c_void,
    blocks: *mut py_ffi::PyObject,
) -> ErrorCode {
    check_null!(chain_controller, blocks);

    let gil_guard = Python::acquire_gil();
    let py = gil_guard.python();

    let blocks: Vec<BlockWrapper> = unsafe {
        match PyObject::from_borrowed_ptr(py, blocks).extract(py) {
            Ok(val) => val,
            Err(py_err) => {
                pylogger::exception(
                    py,
                    "chain_controller_on_block_received: unable to get block",
                    py_err,
                );
                return ErrorCode::InvalidPythonObject;
            }
        }
    };
    unsafe {
        let controller = (*(chain_controller
            as *mut ChainController<PyBlockCache, PyBlockValidator>))
            .light_clone();

        py.allow_threads(move || {
            // A thread has to be spawned here, otherwise, any subsequent attempt to
            // re-acquire the GIL and import of python modules will fail.
            let builder = thread::Builder::new()
                .name("ChainController.submit_blocks_for_verification".into());
            builder
                .spawn(
                    move || match controller.submit_blocks_for_verification(&blocks) {
                        Ok(_) => ErrorCode::Success,
                        Err(err) => {
                            error!("Unable to call submit_blocks_for_verification: {:?}", err);
                            ErrorCode::Unknown
                        }
                    },
                ).unwrap()
                .join()
                .unwrap()
        })
    }
}

/// This is only exposed for the current python tests, it should be removed
/// when proper rust tests are written for the ChainController
#[no_mangle]
pub extern "C" fn chain_controller_on_block_received(
    chain_controller: *mut c_void,
    block: *mut py_ffi::PyObject,
) -> ErrorCode {
    check_null!(chain_controller, block);

    let gil_guard = Python::acquire_gil();
    let py = gil_guard.python();

    let block: BlockWrapper = unsafe {
        match PyObject::from_borrowed_ptr(py, block).extract(py) {
            Ok(val) => val,
            Err(py_err) => {
                pylogger::exception(
                    py,
                    "chain_controller_on_block_received: unable to get block",
                    py_err,
                );
                return ErrorCode::InvalidPythonObject;
            }
        }
    };
    unsafe {
        let mut controller = (*(chain_controller
            as *mut ChainController<PyBlockCache, PyBlockValidator>))
            .light_clone();

        py.allow_threads(move || {
            // A thread has to be spawned here, otherwise, any subsequent attempt to
            // re-acquire the GIL and import of python modules will fail.
            let builder = thread::Builder::new().name("ChainController.on_block_received".into());
            builder
                .spawn(move || match controller.on_block_received(block) {
                    Ok(_) => ErrorCode::Success,
                    Err(err) => {
                        error!("Unable to call on_block_received: {:?}", err);
                        ErrorCode::Unknown
                    }
                }).unwrap()
                .join()
                .unwrap()
        })
    }
}

#[no_mangle]
pub extern "C" fn chain_controller_chain_head(
    chain_controller: *mut c_void,
    block: *mut *const py_ffi::PyObject,
) -> ErrorCode {
    check_null!(chain_controller);
    unsafe {
        let gil_guard = Python::acquire_gil();
        let py = gil_guard.python();

        let controller = (*(chain_controller
            as *mut ChainController<PyBlockCache, PyBlockValidator>))
            .light_clone();

        let chain_head = py.allow_threads(move || controller.chain_head());

        // This is relying on the BlockWrapper being backed by a PyObject and `into_py_object()`
        // not incrementing the reference count on the PyObject when passing up to Python. If these
        // changes are invalidated, memory leaks may occur to BlockWrappers with incorrect
        // reference counts never being cleaned up.
        *block = chain_head.into_py_object(py).as_ptr();
    }
    ErrorCode::Success
}

#[no_mangle]
pub extern "C" fn sender_drop(sender: *const c_void) -> ErrorCode {
    check_null!(sender);

    unsafe { Box::from_raw(sender as *mut Sender<BlockWrapper>) };

    ErrorCode::Success
}

#[no_mangle]
pub extern "C" fn sender_send(sender: *const c_void, block: *mut py_ffi::PyObject) -> ErrorCode {
    check_null!(sender, block);

    let gil_guard = Python::acquire_gil();
    let py = gil_guard.python();

    let py_block_wrapper = unsafe { PyObject::from_borrowed_ptr(py, block) };
    let block: BlockWrapper = py_block_wrapper
        .extract(py)
        .expect("Unable to extract block");

    unsafe {
        let sender = (*(sender as *mut Sender<BlockWrapper>)).clone();
        py.allow_threads(move || match sender.send(block) {
            Ok(_) => ErrorCode::Success,
            Err(err) => {
                error!("Unable to send validation result: {:?}", err);
                ErrorCode::Unknown
            }
        })
    }
}

struct PyBlockCache {
    py_block_cache: PyObject,
}

impl PyBlockCache {
    fn new(py_block_cache: PyObject) -> Self {
        PyBlockCache { py_block_cache }
    }
}

impl BlockCache for PyBlockCache {
    fn contains(&self, block_id: &str) -> bool {
        let gil_guard = Python::acquire_gil();
        let py = gil_guard.python();

        match self
            .py_block_cache
            .call_method(py, "__contains__", (block_id,), None)
        {
            Err(py_err) => {
                pylogger::exception(py, "Unable to call __contains__ on BlockCache", py_err);
                false
            }
            Ok(py_bool) => py_bool.extract(py).expect("Unable to extract boolean"),
        }
    }

    fn put(&mut self, block: BlockWrapper) {
        let gil_guard = Python::acquire_gil();
        let py = gil_guard.python();

        match self
            .py_block_cache
            .set_item(py, block.header_signature(), &block)
        {
            Err(py_err) => {
                pylogger::exception(py, "Unable to call __setitem__ on BlockCache", py_err);
                ()
            }
            Ok(_) => (),
        }
    }

    fn get(&self, block_id: &str) -> Option<BlockWrapper> {
        let gil_guard = Python::acquire_gil();
        let py = gil_guard.python();

        match self.py_block_cache.get_item(py, block_id) {
            Err(_) => {
                // This is probably a key error, so we can return none
                None
            }
            Ok(res) => Some(res.extract(py).expect("Unable to extract block")),
        }
    }

    fn iter(&self) -> Box<Iterator<Item = BlockWrapper>> {
        let gil_guard = Python::acquire_gil();
        let py = gil_guard.python();

        match self
            .py_block_cache
            .call_method(py, "block_iter", cpython::NoArgs, None)
        {
            Err(py_err) => {
                pylogger::exception(py, "Unable to call __iter__ on BlockCache", py_err);
                Box::new(Vec::new().into_iter())
            }
            Ok(py_iter) => Box::new(PyIteratorWrapper::new(py_iter)),
        }
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

    fn validate_block(&self, block: BlockWrapper) -> Result<(), ValidationError> {
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
        blocks: &[BlockWrapper],
        response_sender: Sender<BlockWrapper>,
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
            ).map(|_| ())
            .map_err(|py_err| {
                pylogger::exception(py, "Unable to call submit_blocks_for_verification", py_err);
                ()
            }).unwrap_or(());
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

impl ChainWriter for PyBlockStore {
    fn update_chain(
        &mut self,
        new_chain: &[BlockWrapper],
        old_chain: &[BlockWrapper],
    ) -> Result<(), ChainControllerError> {
        let gil_guard = Python::acquire_gil();
        let py = gil_guard.python();

        self.py_block_store
            .call_method(py, "update_chain", (new_chain, old_chain), None)
            .map(|_| ())
            .map_err(|py_err| {
                ChainControllerError::ChainUpdateError(format!(
                    "An error occurred while executing update_chain: {}",
                    py_err.get_type(py).name(py)
                ))
            })
    }
}

impl ChainReader for PyBlockStore {
    fn chain_head(&self) -> Result<Option<BlockWrapper>, ChainReadError> {
        let gil_guard = Python::acquire_gil();
        let py = gil_guard.python();

        self.py_block_store
            .getattr(py, "chain_head")
            .and_then(|result| result.extract(py))
            .map_err(|py_err| {
                pylogger::exception(py, "Unable to call block_store.chain_head", py_err);
                ChainReadError::GeneralReadError("Unable to read from python block store".into())
            })
    }

    fn get_block_by_block_num(
        &self,
        block_num: u64,
    ) -> Result<Option<BlockWrapper>, ChainReadError> {
        let gil_guard = Python::acquire_gil();
        let py = gil_guard.python();

        self.py_block_store
            .call_method(py, "get_block_by_number", (block_num,), None)
            .and_then(|result| result.extract(py))
            .or_else(|py_err| {
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

struct PyChainObserver {
    py_observer: PyObject,
}

impl PyChainObserver {
    fn new(py_observer: PyObject) -> Self {
        PyChainObserver { py_observer }
    }
}

impl ChainObserver for PyChainObserver {
    fn chain_update(&mut self, block: &BlockWrapper, receipts: &[&TransactionReceipt]) {
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
    fn notify_block_new(&self, block: &BlockWrapper) {
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

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
use cpython::{FromPyObject, ObjectProtocol, PyList, PyObject, Python, PythonObject, ToPyObject};
use journal::block_validator::{BlockValidationResult, BlockValidator, ValidationError};
use journal::block_wrapper::BlockWrapper;
use journal::chain::*;
use py_ffi;
use pylogger;
use std::ffi::CStr;
use std::os::raw::{c_char, c_void};
use std::sync::mpsc::Sender;
use std::thread;

use batch::Batch;

use protobuf::Message;

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
    chain_head_lock: *mut py_ffi::PyObject,
    on_chain_updated: *mut py_ffi::PyObject,
    observers: *mut py_ffi::PyObject,
    data_directory: *const c_char,
    chain_controller_ptr: *mut *const c_void,
) -> ErrorCode {
    check_null!(
        block_store,
        block_cache,
        block_validator,
        chain_head_lock,
        on_chain_updated,
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
    let py_on_chain_updated = unsafe { PyObject::from_borrowed_ptr(py, on_chain_updated) };
    let py_observers = unsafe { PyObject::from_borrowed_ptr(py, observers) };
    let chain_head_lock = PyLock {
        py_lock: unsafe { PyObject::from_borrowed_ptr(py, chain_head_lock) },
    };

    let observer_wrappers = if let Ok(py_list) = py_observers.extract::<PyList>(py) {
        let mut res: Vec<Box<ChainObserver>> = Vec::with_capacity(py_list.len(py));
        py_list
            .iter(py)
            .for_each(|pyobj| res.push(Box::new(PyChainObserver::new(pyobj))));
        res
    } else {
        return ErrorCode::InvalidPythonObject;
    };

    let chain_controller = ChainController::new(
        PyBlockCache::new(py_block_cache),
        PyBlockValidator::new(py_block_validator),
        PyBlockStore::new(py_block_store_writer),
        Box::new(PyBlockStore::new(py_block_store_reader)),
        Box::new(chain_head_lock),
        data_dir.into(),
        Box::new(PyChainHeadUpdateObserver::new(py_on_chain_updated)),
        observer_wrappers,
    );

    unsafe {
        *chain_controller_ptr = Box::into_raw(Box::new(chain_controller)) as *const c_void;
    }

    ErrorCode::Success
}

#[no_mangle]
pub extern "C" fn chain_controller_drop(chain_controller: *mut c_void) -> ErrorCode {
    check_null!(chain_controller);

    unsafe { Box::from_raw(chain_controller) };
    ErrorCode::Success
}

#[no_mangle]
pub extern "C" fn chain_controller_start(chain_controller: *mut c_void) -> ErrorCode {
    check_null!(chain_controller);

    unsafe {
        (*(chain_controller as *mut ChainController<PyBlockCache, PyBlockValidator, PyBlockStore>))
            .start();
    }

    ErrorCode::Success
}

#[no_mangle]
pub extern "C" fn chain_controller_stop(chain_controller: *mut c_void) -> ErrorCode {
    check_null!(chain_controller);

    unsafe {
        (*(chain_controller as *mut ChainController<PyBlockCache, PyBlockValidator, PyBlockStore>))
            .stop();
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
        *result = (*(chain_controller
            as *mut ChainController<PyBlockCache, PyBlockValidator, PyBlockStore>))
            .has_block(block_id);
    }

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
            as *mut ChainController<PyBlockCache, PyBlockValidator, PyBlockStore>))
            .light_clone();

        py.allow_threads(move || {
            let builder = thread::Builder::new().name("ChainController.queue_block".into());
            builder
                .spawn(move || {
                    controller.queue_block(block);
                })
                .unwrap()
                .join()
                .unwrap();
        });
    }

    ErrorCode::Success
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
            as *mut ChainController<PyBlockCache, PyBlockValidator, PyBlockStore>))
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
                })
                .unwrap()
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
        let chain_head = (*(chain_controller
            as *mut ChainController<PyBlockCache, PyBlockValidator, PyBlockStore>))
            .chain_head();

        let gil_guard = Python::acquire_gil();
        let py = gil_guard.python();

        *block = chain_head.to_py_object(py).steal_ptr();
    }
    ErrorCode::Success
}

#[no_mangle]
pub extern "C" fn sender_drop(sender: *const c_void) -> ErrorCode {
    check_null!(sender);

    unsafe { Box::from_raw(sender as *mut Sender<(bool, BlockValidationResult)>) };

    ErrorCode::Success
}

#[no_mangle]
pub extern "C" fn sender_send(
    sender: *const c_void,
    result_tuple: *mut py_ffi::PyObject,
) -> ErrorCode {
    check_null!(sender, result_tuple);

    let gil_guard = Python::acquire_gil();
    let py = gil_guard.python();

    let py_result_tuple = unsafe { PyObject::from_borrowed_ptr(py, result_tuple) };
    let (can_commit, result): (bool, BlockValidationResult) = py_result_tuple
        .extract(py)
        .expect("Unable to extract result tuple");

    unsafe {
        match (*(sender as *mut Sender<(bool, BlockValidationResult)>)).send((can_commit, result)) {
            Ok(_) => ErrorCode::Success,
            Err(err) => {
                error!("Unable to send validation result: {:?}", err);
                ErrorCode::Unknown
            }
        }
    }
}

struct PyLock {
    py_lock: PyObject,
}

impl ExternalLock for PyLock {
    fn lock(&self) -> Box<ExternalLockGuard> {
        let gil_guard = Python::acquire_gil();
        let py = gil_guard.python();
        self.py_lock
            .call_method(py, "acquire", cpython::NoArgs, None)
            .expect("Unable to call release on python lock");

        let py_release_fn = self.py_lock
            .getattr(py, "release")
            .expect("unable to get release function");
        Box::new(PyExternalLockGuard { py_release_fn })
    }
}

struct PyExternalLockGuard {
    py_release_fn: PyObject,
}

impl ExternalLockGuard for PyExternalLockGuard {
    fn release(&self) {
        let gil_guard = Python::acquire_gil();
        let py = gil_guard.python();
        self.py_release_fn
            .call(py, cpython::NoArgs, None)
            .expect("Unable to call release on python lock");
    }
}

impl Drop for PyExternalLockGuard {
    fn drop(&mut self) {
        self.release();
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

        match self.py_block_cache
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

        match self.py_block_cache
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

        let chain_module = py.import("sawtooth_validator.journal.chain")
            .expect("Unable to import sawtooth_validator.journal.chain");
        let py_validation_response_sender = chain_module
            .get(py, "ValidationResponseSender")
            .expect("Unable to get ValidationResponseSender");

        let ffi_module = py.import("sawtooth_validator.ffi")
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

    fn query_block_status(&self, fn_name: &str, block_id: &str) -> bool {
        let gil_guard = Python::acquire_gil();
        let py = gil_guard.python();

        match self.py_block_validator
            .call_method(py, fn_name, (block_id,), None)
        {
            Err(_) => {
                // Presumably a KeyError, so no
                false
            }
            Ok(py_bool) => py_bool.extract(py).expect("Unable to extract boolean"),
        }
    }
}

impl BlockValidator for PyBlockValidator {
    fn in_process(&self, block_id: &str) -> bool {
        self.query_block_status("in_process", block_id)
    }

    fn in_pending(&self, block_id: &str) -> bool {
        self.query_block_status("in_pending", block_id)
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
        response_sender: Sender<(bool, BlockValidationResult)>,
    ) {
        let gil_guard = Python::acquire_gil();
        let py = gil_guard.python();

        let sender_ptr = Box::into_raw(Box::new(response_sender)) as u64;

        let sender_c_void = self.ctypes_c_void
            .call(py, (sender_ptr,), None)
            .expect("unable to create ctypes.c_void_p");

        let py_sender = self.py_validation_response_sender
            .call(py, (sender_c_void,), None)
            .expect("unable to create ValidationResponseSender");

        let py_callback = self.py_callback_maker
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
            })
            .unwrap_or(())
    }
}

struct PyChainHeadUpdateObserver {
    py_on_chain_updated: PyObject,
}

impl PyChainHeadUpdateObserver {
    fn new(py_on_chain_updated: PyObject) -> Self {
        PyChainHeadUpdateObserver {
            py_on_chain_updated,
        }
    }
}

impl ChainHeadUpdateObserver for PyChainHeadUpdateObserver {
    fn on_chain_head_updated(
        &mut self,
        block: BlockWrapper,
        committed_batches: Vec<Batch>,
        uncommitted_batches: Vec<Batch>,
    ) {
        let gil_guard = Python::acquire_gil();
        let py = gil_guard.python();

        self.py_on_chain_updated
            .call(py, (block, committed_batches, uncommitted_batches), None)
            .map(|_| ())
            .map_err(|py_err| {
                pylogger::exception(
                    py,
                    "Unable to call chain head observer on_chain_updated",
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
        let txn_receipt_protobuf_mod = py.import(
            "sawtooth_validator.protobuf.transaction_receipt_pb2",
        ).expect("Unable to import transaction_receipt_pb2");
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

impl<'source> FromPyObject<'source> for BlockValidationResult {
    fn extract(py: Python, obj: &'source PyObject) -> cpython::PyResult<Self> {
        Ok(BlockValidationResult {
            chain_head: obj.getattr(py, "chain_head")?.extract(py)?,
            block: obj.getattr(py, "block")?.extract(py)?,
            transaction_count: obj.getattr(py, "transaction_count")?.extract(py)?,
            new_chain: obj.getattr(py, "new_chain")?.extract(py)?,
            current_chain: obj.getattr(py, "current_chain")?.extract(py)?,

            committed_batches: obj.getattr(py, "committed_batches")?.extract(py)?,
            uncommitted_batches: obj.getattr(py, "uncommitted_batches")?.extract(py)?,
        })
    }
}

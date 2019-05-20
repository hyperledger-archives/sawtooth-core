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
use std::mem;
use std::os::raw::{c_char, c_void};
use std::slice;

use cpython::{ObjectProtocol, PyClone, PyList, PyObject, Python};

use batch::Batch;
use block::Block;
use execution::py_executor::PyExecutor;
use ffi::py_import_class;
use journal::block_manager::BlockManager;
use journal::commit_store::CommitStore;
use journal::publisher::{
    BatchObserver, BlockPublisher, FinalizeBlockError, IncomingBatchSender, InitializeBlockError,
};

use state::state_view_factory::StateViewFactory;

lazy_static! {
    static ref PY_BATCH_PUBLISHER_CLASS: PyObject = py_import_class(
        "sawtooth_validator.journal.consensus.batch_publisher",
        "BatchPublisher"
    );
}

#[repr(u32)]
#[derive(Debug)]
pub enum ErrorCode {
    Success = 0,
    NullPointerProvided = 0x01,
    InvalidInput = 0x02,
    BlockInProgress = 0x03,
    BlockNotInitialized = 0x04,
    BlockEmpty = 0x05,
    MissingPredecessor = 0x07,
}

macro_rules! check_null {
    ($($arg:expr) , *) => {
        $(if $arg.is_null() { return ErrorCode::NullPointerProvided; })*
    }
}

#[no_mangle]
pub unsafe extern "C" fn block_publisher_new(
    commit_store_ptr: *mut c_void,
    block_manager_ptr: *const c_void,
    transaction_executor_ptr: *mut py_ffi::PyObject,
    state_view_factory_ptr: *const c_void,
    block_sender_ptr: *mut py_ffi::PyObject,
    batch_sender_ptr: *mut py_ffi::PyObject,
    chain_head_ptr: *mut py_ffi::PyObject,
    identity_signer_ptr: *mut py_ffi::PyObject,
    data_dir_ptr: *mut py_ffi::PyObject,
    config_dir_ptr: *mut py_ffi::PyObject,
    permission_verifier_ptr: *mut py_ffi::PyObject,
    batch_observers_ptr: *mut py_ffi::PyObject,
    batch_injector_factory_ptr: *mut py_ffi::PyObject,
    block_publisher_ptr: *mut *const c_void,
) -> ErrorCode {
    check_null!(
        commit_store_ptr,
        block_manager_ptr,
        transaction_executor_ptr,
        state_view_factory_ptr,
        block_sender_ptr,
        batch_sender_ptr,
        chain_head_ptr,
        identity_signer_ptr,
        data_dir_ptr,
        config_dir_ptr,
        permission_verifier_ptr,
        batch_observers_ptr,
        batch_injector_factory_ptr
    );

    let py = Python::assume_gil_acquired();

    let commit_store = (*(commit_store_ptr as *mut CommitStore)).clone();
    let block_manager = (*(block_manager_ptr as *mut BlockManager)).clone();
    let transaction_executor = PyObject::from_borrowed_ptr(py, transaction_executor_ptr);
    let state_view_factory = (state_view_factory_ptr as *const StateViewFactory)
        .as_ref()
        .unwrap();
    let block_sender = PyObject::from_borrowed_ptr(py, block_sender_ptr);
    let batch_sender = PyObject::from_borrowed_ptr(py, batch_sender_ptr);
    let chain_head = PyObject::from_borrowed_ptr(py, chain_head_ptr);
    let identity_signer = PyObject::from_borrowed_ptr(py, identity_signer_ptr);
    let data_dir = PyObject::from_borrowed_ptr(py, data_dir_ptr);
    let config_dir = PyObject::from_borrowed_ptr(py, config_dir_ptr);
    let permission_verifier = PyObject::from_borrowed_ptr(py, permission_verifier_ptr);
    let batch_observers = PyObject::from_borrowed_ptr(py, batch_observers_ptr);
    let batch_injector_factory = PyObject::from_borrowed_ptr(py, batch_injector_factory_ptr);

    let chain_head = if chain_head == Python::None(py) {
        None
    } else {
        chain_head
            .extract(py)
            .expect("Got chain head that wasn't a BlockWrapper")
    };

    let batch_observers = if let Ok(py_list) = batch_observers.extract::<PyList>(py) {
        let mut res: Vec<Box<BatchObserver>> = Vec::with_capacity(py_list.len(py));
        py_list
            .iter(py)
            .for_each(|pyobj| res.push(Box::new(PyBatchObserver::new(pyobj))));
        res
    } else {
        return ErrorCode::InvalidInput;
    };

    let batch_publisher = PY_BATCH_PUBLISHER_CLASS
        .call(py, (identity_signer.clone_ref(py), batch_sender), None)
        .expect("Unable to create BatchPublisher");

    let publisher = BlockPublisher::new(
        commit_store,
        block_manager,
        Box::new(
            PyExecutor::new(transaction_executor)
                .expect("Failed to create python transaction executor"),
        ),
        state_view_factory.clone(),
        block_sender,
        batch_publisher,
        chain_head,
        identity_signer,
        data_dir,
        config_dir,
        permission_verifier,
        batch_observers,
        batch_injector_factory,
    );

    *block_publisher_ptr = Box::into_raw(Box::new(publisher)) as *const c_void;

    ErrorCode::Success
}

#[no_mangle]
pub unsafe extern "C" fn block_publisher_drop(publisher: *mut c_void) -> ErrorCode {
    check_null!(publisher);
    Box::from_raw(publisher as *mut BlockPublisher);
    ErrorCode::Success
}

// block_publisher_on_batch_received is used in tests
#[no_mangle]
pub unsafe extern "C" fn block_publisher_on_batch_received(
    publisher: *mut c_void,
    batch: *mut py_ffi::PyObject,
) -> ErrorCode {
    check_null!(publisher, batch);
    let gil = Python::acquire_gil();
    let py = gil.python();
    let batch = PyObject::from_borrowed_ptr(py, batch)
        .extract::<Batch>(py)
        .unwrap();
    let publisher = (*(publisher as *mut BlockPublisher)).clone();
    py.allow_threads(move || publisher.publisher.on_batch_received(batch));
    ErrorCode::Success
}

#[no_mangle]
pub unsafe extern "C" fn block_publisher_start(
    publisher: *mut c_void,
    incoming_batch_sender: *mut *const c_void,
) -> ErrorCode {
    check_null!(publisher);
    let batch_tx = (*(publisher as *mut BlockPublisher)).start();
    let batch_tx_ptr: *mut IncomingBatchSender = Box::into_raw(Box::new(batch_tx));

    *incoming_batch_sender = batch_tx_ptr as *const c_void;

    ErrorCode::Success
}

#[no_mangle]
pub unsafe extern "C" fn block_publisher_stop(publisher: *mut c_void) -> ErrorCode {
    check_null!(publisher);
    (*(publisher as *mut BlockPublisher)).stop();
    ErrorCode::Success
}

#[no_mangle]
pub unsafe extern "C" fn block_publisher_chain_head_lock(
    publisher_ptr: *mut c_void,
    chain_head_lock_ptr: *mut *const c_void,
) -> ErrorCode {
    check_null!(publisher_ptr);
    let chain_head_lock = Box::new((*(publisher_ptr as *mut BlockPublisher)).chain_head_lock());

    *chain_head_lock_ptr = Box::into_raw(chain_head_lock) as *const c_void;
    ErrorCode::Success
}

#[no_mangle]
pub unsafe extern "C" fn block_publisher_pending_batch_info(
    publisher: *mut c_void,
    length: *mut i32,
    limit: *mut i32,
) -> ErrorCode {
    check_null!(publisher);

    let info = (*(publisher as *mut BlockPublisher)).pending_batch_info();
    *length = info.0;
    *limit = info.1;

    ErrorCode::Success
}

#[no_mangle]
pub unsafe extern "C" fn block_publisher_initialize_block(
    publisher: *mut c_void,
    previous_block: *mut py_ffi::PyObject,
) -> ErrorCode {
    let gil = Python::acquire_gil();
    let py = gil.python();
    let block = PyObject::from_borrowed_ptr(py, previous_block)
        .extract::<Block>(py)
        .unwrap();

    let publisher = (*(publisher as *mut BlockPublisher)).clone();
    py.allow_threads(move || match publisher.initialize_block(&block) {
        Err(InitializeBlockError::BlockInProgress) => ErrorCode::BlockInProgress,
        Err(InitializeBlockError::MissingPredecessor) => ErrorCode::MissingPredecessor,
        Ok(_) => ErrorCode::Success,
    })
}

#[no_mangle]
pub unsafe extern "C" fn block_publisher_finalize_block(
    publisher: *mut c_void,
    consensus: *const u8,
    consensus_len: usize,
    force: bool,
    result: *mut *const u8,
    result_len: *mut usize,
) -> ErrorCode {
    check_null!(publisher, consensus);
    let consensus = slice::from_raw_parts(consensus, consensus_len);
    match (*(publisher as *mut BlockPublisher)).finalize_block(consensus, force) {
        Err(FinalizeBlockError::BlockNotInitialized) => ErrorCode::BlockNotInitialized,
        Err(FinalizeBlockError::BlockEmpty) => ErrorCode::BlockEmpty,
        Ok(block_id) => {
            *result = block_id.as_ptr();
            *result_len = block_id.as_bytes().len();

            mem::forget(block_id);

            ErrorCode::Success
        }
    }
}

#[no_mangle]
pub unsafe extern "C" fn block_publisher_summarize_block(
    publisher: *mut c_void,
    force: bool,
    result: *mut *const u8,
    result_len: *mut usize,
) -> ErrorCode {
    check_null!(publisher);

    match (*(publisher as *mut BlockPublisher)).summarize_block(force) {
        Err(FinalizeBlockError::BlockEmpty) => ErrorCode::BlockEmpty,
        Err(FinalizeBlockError::BlockNotInitialized) => ErrorCode::BlockNotInitialized,
        Ok(consensus) => {
            *result = consensus.as_ptr();
            *result_len = consensus.as_slice().len();

            mem::forget(consensus);

            ErrorCode::Success
        }
    }
}

// convert_on_chain_updated_args is used in tests
pub unsafe fn convert_on_chain_updated_args(
    py: Python,
    chain_head_ptr: *mut py_ffi::PyObject,
    committed_batches_ptr: *mut py_ffi::PyObject,
    uncommitted_batches_ptr: *mut py_ffi::PyObject,
) -> (Block, Vec<Batch>, Vec<Batch>) {
    let chain_head = PyObject::from_borrowed_ptr(py, chain_head_ptr);
    let py_committed_batches = PyObject::from_borrowed_ptr(py, committed_batches_ptr);
    let committed_batches: Vec<Batch> = if py_committed_batches == Python::None(py) {
        Vec::new()
    } else {
        py_committed_batches
            .extract::<PyList>(py)
            .expect("Failed to extract PyList from committed_batches")
            .iter(py)
            .map(|pyobj| pyobj.extract::<Batch>(py).unwrap())
            .collect()
    };
    let py_uncommitted_batches = PyObject::from_borrowed_ptr(py, uncommitted_batches_ptr);
    let uncommitted_batches: Vec<Batch> = if py_uncommitted_batches == Python::None(py) {
        Vec::new()
    } else {
        py_uncommitted_batches
            .extract::<PyList>(py)
            .expect("Failed to extract PyList from uncommitted_batches")
            .iter(py)
            .map(|pyobj| pyobj.extract::<Batch>(py).unwrap())
            .collect()
    };
    let chain_head = chain_head
        .extract(py)
        .expect("Got a new chain head that wasn't a BlockWrapper");

    (chain_head, committed_batches, uncommitted_batches)
}

// block_publisher_on_chain_updated is used in tests
#[no_mangle]
pub unsafe extern "C" fn block_publisher_on_chain_updated(
    publisher: *mut c_void,
    chain_head_ptr: *mut py_ffi::PyObject,
    committed_batches_ptr: *mut py_ffi::PyObject,
    uncommitted_batches_ptr: *mut py_ffi::PyObject,
) -> ErrorCode {
    check_null!(
        publisher,
        chain_head_ptr,
        committed_batches_ptr,
        uncommitted_batches_ptr
    );

    let gil = Python::acquire_gil();
    let py = gil.python();
    let (chain_head, committed_batches, uncommitted_batches) = {
        convert_on_chain_updated_args(
            py,
            chain_head_ptr,
            committed_batches_ptr,
            uncommitted_batches_ptr,
        )
    };

    let mut publisher = (*(publisher as *mut BlockPublisher)).clone();
    py.allow_threads(move || {
        publisher.publisher.on_chain_updated_internal(
            chain_head,
            committed_batches,
            uncommitted_batches,
        )
    });

    ErrorCode::Success
}

#[no_mangle]
pub unsafe extern "C" fn block_publisher_has_batch(
    publisher: *mut c_void,
    batch_id: *const c_char,
    has: *mut bool,
) -> ErrorCode {
    check_null!(publisher, batch_id);
    let batch_id = match CStr::from_ptr(batch_id).to_str() {
        Ok(s) => s,
        Err(_) => return ErrorCode::InvalidInput,
    };

    *has = (*(publisher as *mut BlockPublisher)).has_batch(batch_id);

    ErrorCode::Success
}

#[no_mangle]
pub unsafe extern "C" fn block_publisher_cancel_block(publisher: *mut c_void) -> ErrorCode {
    check_null!(publisher);

    match (*(publisher as *mut BlockPublisher)).cancel_block() {
        Ok(_) => ErrorCode::Success,
        Err(_) => ErrorCode::BlockNotInitialized,
    }
}

struct PyBatchObserver {
    py_batch_observer: PyObject,
}

impl PyBatchObserver {
    fn new(py_batch_observer: PyObject) -> Self {
        PyBatchObserver { py_batch_observer }
    }
}

impl BatchObserver for PyBatchObserver {
    fn notify_batch_pending(&self, batch: &Batch) {
        let gil = Python::acquire_gil();
        let py = gil.python();
        self.py_batch_observer
            .call_method(py, "notify_batch_pending", (batch,), None)
            .expect("BatchObserver has no method notify_batch_pending");
    }
}

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

use std::ffi::CStr;
use std::os::raw::{c_char, c_void};
use std::slice;

use cpython::{FromPyObject, NoArgs, ObjectProtocol, PyList, PyObject, Python, ToPyObject};
use py_ffi;
use pylogger;

use block::Block;
use ffi::PyIteratorWrapper;
use journal::block_manager::{
    BlockManager, BlockManagerError, BranchDiffIterator, BranchIterator, GetBlockIterator,
};
use journal::block_store::{BlockStore, BlockStoreError};

#[repr(u32)]
#[derive(Debug)]
pub enum ErrorCode {
    Success = 0,
    NullPointerProvided = 0x01,
    MissingPredecessor = 0x02,
    MissingPredecessorInBranch = 0x03,
    MissingInput = 0x04,
    UnknownBlock = 0x05,
    InvalidBlockStoreName = 0x06,
    Error = 0x07,
    InvalidPythonObject = 0x10,
    StopIteration = 0x11,
}

macro_rules! check_null {
    ($($arg:expr) , *) => {
        $(if $arg.is_null() { return ErrorCode::NullPointerProvided; })*
    }
}

#[no_mangle]
pub unsafe extern "C" fn block_manager_new(block_manager_ptr: *mut *const c_void) -> ErrorCode {
    let block_manager = BlockManager::new();

    *block_manager_ptr = Box::into_raw(Box::new(block_manager)) as *const c_void;

    ErrorCode::Success
}

#[no_mangle]
pub unsafe extern "C" fn block_manager_drop(block_manager: *mut c_void) -> ErrorCode {
    check_null!(block_manager);
    Box::from_raw(block_manager as *mut BlockManager);
    ErrorCode::Success
}

#[no_mangle]
pub unsafe extern "C" fn block_manager_add_store(
    block_manager: *mut c_void,
    block_store_name: *const c_char,
    block_store: *mut py_ffi::PyObject,
) -> ErrorCode {
    check_null!(block_manager, block_store_name, block_store);

    let gil = Python::acquire_gil();
    let py = gil.python();
    let py_block_store = PyBlockStore::new(PyObject::from_borrowed_ptr(py, block_store));

    let name = match CStr::from_ptr(block_store_name).to_str() {
        Ok(s) => s,
        Err(_) => return ErrorCode::InvalidBlockStoreName,
    };

    (*(block_manager as *mut BlockManager))
        .add_store(name, Box::new(py_block_store))
        .map(|_| ErrorCode::Success)
        .unwrap_or(ErrorCode::Error)
}

#[no_mangle]
pub unsafe extern "C" fn block_manager_put(
    block_manager: *mut c_void,
    branch: *mut py_ffi::PyObject,
) -> ErrorCode {
    check_null!(block_manager, branch);

    let gil = Python::acquire_gil();
    let py = gil.python();

    let py_branch = PyObject::from_borrowed_ptr(py, branch);

    let branch: Vec<Block> = py_branch
        .extract::<PyList>(py)
        .expect("Failed to extract PyList from Branch")
        .iter(py)
        .map(|b| {
            b.extract::<Block>(py)
                .expect("Unable to extract Block in PyList, py_branch")
        }).collect();

    match (*(block_manager as *mut BlockManager)).put(branch) {
        Err(BlockManagerError::MissingPredecessor(_)) => ErrorCode::MissingPredecessor,
        Err(BlockManagerError::MissingInput) => ErrorCode::MissingInput,
        Err(BlockManagerError::MissingPredecessorInBranch(_)) => {
            ErrorCode::MissingPredecessorInBranch
        }
        Err(_) => ErrorCode::Error,
        Ok(_) => ErrorCode::Success,
    }
}

#[no_mangle]
pub unsafe extern "C" fn block_manager_get_iterator_new(
    block_manager: *mut c_void,
    block_ids: *const *const c_char,
    block_ids_len: usize,
    iterator: *mut *const c_void,
) -> ErrorCode {
    check_null!(block_manager, block_ids);

    let block_ids = match slice::from_raw_parts(block_ids, block_ids_len)
        .iter()
        .map(|c_str| CStr::from_ptr(*c_str).to_str())
        .collect::<Result<Vec<&str>, _>>()
    {
        Ok(ids) => ids,
        Err(_) => return ErrorCode::InvalidPythonObject,
    };

    *iterator =
        Box::into_raw((*(block_manager as *mut BlockManager)).get(&block_ids)) as *const c_void;

    ErrorCode::Success
}

#[no_mangle]
pub unsafe extern "C" fn block_manager_get_iterator_drop(iterator: *mut c_void) -> ErrorCode {
    check_null!(iterator);

    Box::from_raw(iterator as *mut GetBlockIterator);
    ErrorCode::Success
}

#[no_mangle]
pub unsafe extern "C" fn block_manager_get_iterator_next(
    iterator: *mut c_void,
    block: *mut *const py_ffi::PyObject,
) -> ErrorCode {
    check_null!(iterator);

    *block = match (*(iterator as *mut GetBlockIterator)).next() {
        Some(b) => {
            let gil = Python::acquire_gil();
            let py = gil.python();
            b.to_py_object(py).steal_ptr()
        }
        None => return ErrorCode::StopIteration,
    };

    ErrorCode::Success
}

#[no_mangle]
pub unsafe extern "C" fn block_manager_branch_iterator_new(
    block_manager: *mut c_void,
    tip: *const c_char,
    iterator: *mut *const c_void,
) -> ErrorCode {
    check_null!(block_manager, tip);

    let tip = match CStr::from_ptr(tip).to_str() {
        Ok(s) => s,
        Err(_) => return ErrorCode::InvalidPythonObject,
    };

    *iterator = Box::into_raw((*(block_manager as *mut BlockManager)).branch(tip)) as *const c_void;
    ErrorCode::Success
}

#[no_mangle]
pub unsafe extern "C" fn block_manager_branch_iterator_drop(iterator: *mut c_void) -> ErrorCode {
    check_null!(iterator);
    Box::from_raw(iterator as *mut BranchIterator);
    ErrorCode::Success
}

#[no_mangle]
pub unsafe extern "C" fn block_manager_branch_iterator_next(
    iterator: *mut c_void,
    block: *mut *const py_ffi::PyObject,
) -> ErrorCode {
    check_null!(iterator);

    *block = match (*(iterator as *mut BranchIterator)).next() {
        Some(b) => {
            let gil = Python::acquire_gil();
            let py = gil.python();
            b.to_py_object(py).steal_ptr()
        }
        None => return ErrorCode::StopIteration,
    };
    ErrorCode::Success
}

#[no_mangle]
pub unsafe extern "C" fn block_manager_branch_diff_iterator_new(
    block_manager: *mut c_void,
    tip: *const c_char,
    exclude: *const c_char,
    iterator: *mut *const c_void,
) -> ErrorCode {
    check_null!(block_manager, tip, exclude);

    let tip = match CStr::from_ptr(tip).to_str() {
        Ok(s) => s,
        Err(_) => return ErrorCode::InvalidPythonObject,
    };

    let exclude = match CStr::from_ptr(exclude).to_str() {
        Ok(s) => s,
        Err(_) => return ErrorCode::InvalidPythonObject,
    };

    *iterator = Box::into_raw((*(block_manager as *mut BlockManager)).branch_diff(tip, exclude))
        as *const c_void;

    ErrorCode::Success
}

#[no_mangle]
pub unsafe extern "C" fn block_manager_branch_diff_iterator_drop(
    iterator: *mut c_void,
) -> ErrorCode {
    check_null!(iterator);
    Box::from_raw(iterator as *mut BranchDiffIterator);
    ErrorCode::Success
}

#[no_mangle]
pub unsafe extern "C" fn block_manager_branch_diff_iterator_next(
    iterator: *mut c_void,
    block: *mut *const py_ffi::PyObject,
) -> ErrorCode {
    check_null!(iterator);

    *block = match (*(iterator as *mut BranchDiffIterator)).next() {
        Some(b) => {
            let gil = Python::acquire_gil();
            let py = gil.python();
            b.to_py_object(py).steal_ptr()
        }
        None => return ErrorCode::StopIteration,
    };
    ErrorCode::Success
}

struct PyBlockStore {
    py_block_store: PyObject,
}

impl PyBlockStore {
    fn new(py_block_store: PyObject) -> Self {
        PyBlockStore { py_block_store }
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
            let block: Block = self.py_block_store
                .call_method(py, "get", (block_id,), None)
                // Unwrap the block wrapper
                .and_then(|blkw| blkw.getattr(py, "block"))
                .map_err(|py_err| {
                    pylogger::exception(py, "Unable to call block_store.get_blocks", py_err);
                    BlockStoreError::Error(format!("Unable to get blocks"))
                })?
                .extract(py)
                .expect("Unable to convert block from python");

            self.py_block_store
                .call_method(py, "__delitem__", (block_id,), None)
                .map_err(|py_err| {
                    pylogger::exception(py, "Unable to call block_store.get_blocks", py_err);
                    BlockStoreError::Error(format!("Unable to delete blocks"))
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
                    BlockStoreError::Error(format!("Unable to put blocks"))
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
                BlockStoreError::Error(format!("Unable to iterate block store"))
            })
    }
}

fn unwrap_block(py: Python, block_wrapper: PyObject) -> PyObject {
    block_wrapper
        .getattr(py, "block")
        .expect("Unable to get block from block wrapper")
}

#[cfg(test)]
mod test {
    use super::*;
    use block::Block;
    use journal::NULL_BLOCK_IDENTIFIER;
    use proto::block::BlockHeader;

    use cpython::{NoArgs, ObjectProtocol, PyObject, Python};

    use protobuf;
    use protobuf::Message;

    use std::env;
    use std::fs::remove_file;
    use std::panic;
    use std::thread;

    const TEST_DB_SIZE: usize = 10 * 1024 * 1024;

    /// This test matches the basic test in journal::block_store.
    /// It creates a Python-backed block store, inserts several blocks,
    /// retrieves them, iterates on them, and deletes one.
    #[test]
    fn py_block_store() {
        run_test(|db_path| {
            let mut store = PyBlockStore::new(create_block_store(db_path));

            let block_a = create_block("A", 1, NULL_BLOCK_IDENTIFIER);
            let block_b = create_block("B", 2, "A");
            let block_c = create_block("C", 3, "B");

            store
                .put(vec![block_a.clone(), block_b.clone(), block_c.clone()])
                .unwrap();
            assert_eq!(store.get(&["A"]).unwrap().next().unwrap(), block_a);

            {
                let mut iterator = store.iter().unwrap();

                assert_eq!(iterator.next().unwrap(), block_c);
                assert_eq!(iterator.next().unwrap(), block_b);
                assert_eq!(iterator.next().unwrap(), block_a);
                assert_eq!(iterator.next(), None);
            }

            assert_eq!(store.delete(&["C"]).unwrap(), vec![block_c]);
        })
    }

    fn create_block(header_signature: &str, block_num: u64, previous_block_id: &str) -> Block {
        let mut block_header = BlockHeader::new();
        block_header.set_previous_block_id(previous_block_id.to_string());
        block_header.set_block_num(block_num);
        block_header.set_state_root_hash(format!("state-{}", block_num));
        Block {
            header_signature: header_signature.into(),
            previous_block_id: block_header.get_previous_block_id().to_string(),
            block_num,
            batches: vec![],
            state_root_hash: block_header.get_state_root_hash().to_string(),
            consensus: vec![],
            batch_ids: vec![],
            signer_public_key: "".into(),
            header_bytes: block_header.write_to_bytes().unwrap(),
        }
    }

    fn create_block_store(db_path: &str) -> PyObject {
        let gil_guard = Python::acquire_gil();
        let py = gil_guard.python();

        let block_store_mod = py.import("sawtooth_validator.journal.block_store").unwrap();
        let block_store = block_store_mod.get(py, "BlockStore").unwrap();

        let db_mod = py
            .import("sawtooth_validator.database.indexed_database")
            .unwrap();
        let indexed_database = db_mod.get(py, "IndexedDatabase").unwrap();

        let db_instance = indexed_database
            .call(
                py,
                (
                    db_path,
                    block_store.getattr(py, "serialize_block").unwrap(),
                    block_store.getattr(py, "deserialize_block").unwrap(),
                    block_store
                        .call_method(py, "create_index_configuration", NoArgs, None)
                        .unwrap(),
                    "c",
                    TEST_DB_SIZE,
                ),
                None,
            ).unwrap();

        block_store.call(py, (db_instance,), None).unwrap()
    }

    fn run_test<T>(test: T) -> ()
    where
        T: FnOnce(&str) -> () + panic::UnwindSafe,
    {
        let dbpath = temp_db_path();

        let testpath = dbpath.clone();
        let result = panic::catch_unwind(move || test(&testpath));

        remove_file(dbpath).unwrap();

        assert!(result.is_ok())
    }

    fn temp_db_path() -> String {
        let mut temp_dir = env::temp_dir();

        let thread_id = thread::current().id();
        temp_dir.push(format!("merkle-{:?}.lmdb", thread_id));
        temp_dir.to_str().unwrap().to_string()
    }
}

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

use crate::batch::Batch;
use crate::block::Block;
use std::fmt;

use cpython::{self, ObjectProtocol, PyClone, PyObject};

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum BlockStatus {
    Unknown = 0,
    Invalid = 1,
    Valid = 2,
    Missing = 3,
    InValidation = 5,
}

impl Default for BlockStatus {
    fn default() -> Self {
        BlockStatus::Unknown
    }
}

#[derive(Debug)]
pub struct BlockWrapper {
    pub(super) py_block_wrapper: PyObject,
}

impl Clone for BlockWrapper {
    fn clone(&self) -> Self {
        let gil = cpython::Python::acquire_gil();
        let py = gil.python();

        BlockWrapper {
            py_block_wrapper: self.py_block_wrapper.clone_ref(py),
        }
    }
}

impl BlockWrapper {
    pub fn header_signature(&self) -> String {
        let gil = cpython::Python::acquire_gil();
        let py = gil.python();

        self.py_block_wrapper
            .getattr(py, "header_signature")
            .expect("Failed to get BlockWrapper.header_signature")
            .extract(py)
            .expect("Failed to extract BlockWrapper.header_signature")
    }

    pub fn previous_block_id(&self) -> String {
        let gil = cpython::Python::acquire_gil();
        let py = gil.python();
        self.py_block_wrapper
            .getattr(py, "previous_block_id")
            .expect("Failed to get BlockWrapper.previous_block_id")
            .extract(py)
            .expect("Failed to extract BlockWrapper.previous_block_id")
    }

    pub fn block_num(&self) -> u64 {
        let gil = cpython::Python::acquire_gil();
        let py = gil.python();
        self.py_block_wrapper
            .getattr(py, "block_num")
            .expect("Failed to get BlockWrapper.block_num")
            .extract(py)
            .expect("Failed to extract BlockWrapper.block_num")
    }

    pub fn batches(&self) -> Vec<Batch> {
        let gil = cpython::Python::acquire_gil();
        let py = gil.python();
        self.py_block_wrapper
            .getattr(py, "batches")
            .expect("Failed to get BlockWrapper.batches")
            .extract(py)
            .expect("Failed to extract BlockWrapper.batches")
    }

    pub fn state_root_hash(&self) -> String {
        let gil = cpython::Python::acquire_gil();
        let py = gil.python();
        self.py_block_wrapper
            .getattr(py, "state_root_hash")
            .expect("Failed to get BlockWrapper.state_root_hash")
            .extract(py)
            .expect("Failed to extract BlockWrapper.state_root_hash")
    }

    pub fn block(&self) -> Block {
        let gil = cpython::Python::acquire_gil();
        let py = gil.python();
        self.py_block_wrapper
            .getattr(py, "block")
            .expect("Failed to get BlockWrapper.block")
            .extract(py)
            .expect("Failed to extract BlockWrapper.block")
    }
}

impl fmt::Display for BlockWrapper {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        write!(f, "{}", self.block())
    }
}

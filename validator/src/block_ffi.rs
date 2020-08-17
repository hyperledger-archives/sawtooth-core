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
use crate::py_object_wrapper::PyObjectWrapper;
use cpython;
use cpython::{ObjectProtocol, Python, PythonObject, ToPyObject};

use sawtooth::{
    protocol::block::BlockPair,
    protos::{FromBytes, IntoBytes},
};

impl From<PyObjectWrapper> for BlockPair {
    fn from(py_object_wrapper: PyObjectWrapper) -> Self {
        let gil = Python::acquire_gil();
        let py = gil.python();
        let py_obj = py_object_wrapper.to_py_object(py);

        let bytes: Vec<u8> = py_obj
            .call_method(py, "SerializeToString", cpython::NoArgs, None)
            .expect("Unable to serialize PyObject")
            .extract(py)
            .expect("Unable to extract bytes from PyObject");

        BlockPair::from_bytes(&bytes).expect("Unable to parse block from bytes")
    }
}

impl From<BlockPair> for PyObjectWrapper {
    fn from(native_block: BlockPair) -> Self {
        let gil = Python::acquire_gil();
        let py = gil.python();

        let block_pb2 = py
            .import("sawtooth_validator.protobuf.block_pb2")
            .expect("Unable to import block_pb2");
        let block = block_pb2
            .call(py, "Block", cpython::NoArgs, None)
            .expect("Unable to get Block");

        block
            .call_method(
                py,
                "ParseFromString",
                (cpython::PyBytes::new(py, &native_block.into_bytes().unwrap()).into_object(),),
                None,
            )
            .expect("Unable to ParseFromString");
        PyObjectWrapper::new(block)
    }
}

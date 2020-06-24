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
use protobuf;
use protobuf::Message;

use sawtooth::{
    batch::Batch,
    block::Block,
    protos::block::{Block as ProtoBlock, BlockHeader},
};

impl From<PyObjectWrapper> for Block {
    fn from(py_object_wrapper: PyObjectWrapper) -> Self {
        let gil = Python::acquire_gil();
        let py = gil.python();
        let py_obj = py_object_wrapper.to_py_object(py);

        let bytes: Vec<u8> = py_obj
            .call_method(py, "SerializeToString", cpython::NoArgs, None)
            .expect("Unable to serialize PyObject")
            .extract(py)
            .expect("Unable to extract bytes from PyObject");

        let mut proto_block: ProtoBlock = protobuf::parse_from_bytes(&bytes)
            .expect("Unable to parse protobuf bytes from python protobuf object");

        let mut block_header: BlockHeader = protobuf::parse_from_bytes(proto_block.get_header())
            .expect("Unable to parse protobuf bytes from python protobuf object");

        Block {
            header_signature: proto_block.take_header_signature(),
            header_bytes: proto_block.take_header(),
            state_root_hash: block_header.take_state_root_hash(),
            consensus: block_header.take_consensus(),
            batch_ids: block_header.take_batch_ids().into_vec(),
            signer_public_key: block_header.take_signer_public_key(),
            previous_block_id: block_header.take_previous_block_id(),
            block_num: block_header.get_block_num(),

            batches: proto_block
                .take_batches()
                .into_iter()
                .map(Batch::from)
                .collect(),
        }
    }
}

impl From<Block> for PyObjectWrapper {
    fn from(native_block: Block) -> Self {
        let gil = Python::acquire_gil();
        let py = gil.python();

        let block_proto = ProtoBlock::from(native_block);
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
                (cpython::PyBytes::new(py, &block_proto.write_to_bytes().unwrap()).into_object(),),
                None,
            )
            .expect("Unable to ParseFromString");
        PyObjectWrapper::new(block)
    }
}

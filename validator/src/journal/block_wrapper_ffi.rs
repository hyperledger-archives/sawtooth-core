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
use cpython::{FromPyObject, ObjectProtocol, PyClone, PyObject, Python, PythonObject, ToPyObject};

use journal::block_wrapper::BlockStatus;
use journal::block_wrapper::BlockWrapper;

use batch::Batch;
use block::Block;
use transaction::Transaction;

use protobuf;
use protobuf::Message;

use proto::batch::Batch as ProtoBatch;
use proto::batch::BatchHeader;
use proto::block::Block as ProtoBlock;
use proto::block::BlockHeader;
use proto::transaction::Transaction as ProtoTxn;
use proto::transaction::TransactionHeader;
use pylogger;

lazy_static! {
    static ref PY_BLOCK_WRAPPER: PyObject = Python::acquire_gil()
        .python()
        .import("sawtooth_validator.journal.block_wrapper")
        .expect("Unable to import block_wrapper")
        .get(Python::acquire_gil().python(), "BlockWrapper")
        .expect("Unable to get BlockWrapper");
}

lazy_static! {
    static ref PY_BLOCK_STATUS: PyObject = Python::acquire_gil()
        .python()
        .import("sawtooth_validator.journal.block_wrapper")
        .expect("Unable to import block_wrapper")
        .get(Python::acquire_gil().python(), "BlockStatus")
        .expect("Unable to get BlockStatus");
}

impl ToPyObject for BlockStatus {
    type ObjectType = cpython::PyObject;

    fn to_py_object(&self, py: Python) -> cpython::PyObject {
        match self {
            &BlockStatus::Unknown => PY_BLOCK_STATUS
                .getattr(py, "Unknown")
                .expect("No BlockStatus.Unknown"),
            &BlockStatus::Invalid => PY_BLOCK_STATUS
                .getattr(py, "Invalid")
                .expect("No BlockStatus.Invalid"),
            &BlockStatus::Valid => PY_BLOCK_STATUS
                .getattr(py, "Valid")
                .expect("No BlockStatus.Valid"),
            &BlockStatus::Missing => PY_BLOCK_STATUS
                .getattr(py, "Missing")
                .expect("No BlockStatus.Missing"),
        }
    }
}

impl<'source> FromPyObject<'source> for BlockStatus {
    fn extract(py: Python, obj: &'source PyObject) -> cpython::PyResult<Self> {
        let enum_val: i32 = obj.extract(py)?;
        Ok(match enum_val {
            1 => BlockStatus::Invalid,
            2 => BlockStatus::Valid,
            3 => BlockStatus::Missing,
            _ => BlockStatus::Unknown,
        })
    }
}

impl ToPyObject for BlockWrapper {
    type ObjectType = PyObject;

    fn to_py_object(&self, py: Python) -> PyObject {
        self.py_block_wrapper.clone_ref(py)
    }

    fn into_py_object(self, py: Python) -> PyObject {
        self.py_block_wrapper
    }
}

impl<'source> FromPyObject<'source> for BlockWrapper {
    fn extract(py: Python, obj: &'source PyObject) -> cpython::PyResult<Self> {
        Ok(BlockWrapper {
            py_block_wrapper: obj.clone_ref(py),
        })
    }
}

fn proto_batch_to_batch(proto_batch: &mut ProtoBatch) -> Batch {
    let mut batch_header: BatchHeader = protobuf::parse_from_bytes(proto_batch.get_header())
        .expect("Unable to parse protobuf bytes from python protobuf object");
    Batch {
        header_signature: proto_batch.take_header_signature(),
        header_bytes: proto_batch.take_header(),
        signer_public_key: batch_header.take_signer_public_key(),
        transaction_ids: batch_header.take_transaction_ids().into_vec(),
        trace: proto_batch.get_trace(),

        transactions: proto_batch
            .take_transactions()
            .iter_mut()
            .map(proto_txn_to_txn)
            .collect(),
    }
}

fn proto_txn_to_txn(proto_txn: &mut ProtoTxn) -> Transaction {
    let mut txn_header: TransactionHeader = protobuf::parse_from_bytes(proto_txn.get_header())
        .expect("Unable to parse protobuf bytes from python protobuf object");

    Transaction {
        header_signature: proto_txn.take_header_signature(),
        header_bytes: proto_txn.take_header(),
        payload: proto_txn.take_payload(),
        batcher_public_key: txn_header.take_batcher_public_key(),
        dependencies: txn_header.take_dependencies().into_vec(),
        family_name: txn_header.take_family_name(),
        family_version: txn_header.take_family_version(),
        inputs: txn_header.take_inputs().into_vec(),
        outputs: txn_header.take_outputs().into_vec(),
        nonce: txn_header.take_nonce(),
        payload_sha512: txn_header.take_payload_sha512(),
        signer_public_key: txn_header.take_signer_public_key(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use block::Block;
    use cpython::{FromPyObject, PyObject, Python, ToPyObject};
    use journal::block_wrapper::{BlockStatus, BlockWrapper};

    #[test]
    fn to_from_python() {
        let gil_guard = Python::acquire_gil();
        let py = gil_guard.python();

        let block_wrapper = BlockWrapper {
            py_block_wrapper: PY_BLOCK_WRAPPER
                .call(py, (Block::default(), 0, BlockStatus::Valid), None)
                .unwrap(),
        };

        let py_block_wrapper = block_wrapper.to_py_object(py);
        let round_trip_obj: BlockWrapper = py_block_wrapper.extract(py).unwrap();

        assert_eq!(BlockStatus::Valid, round_trip_obj.status());
    }
}

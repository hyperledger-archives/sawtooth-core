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
use batch::Batch;
use block::Block;
use cpython;
use cpython::{FromPyObject, ObjectProtocol, PyObject, Python, PythonObject, ToPyObject};
use proto::batch::Batch as ProtoBatch;
use proto::batch::BatchHeader;
use proto::block::Block as ProtoBlock;
use proto::block::BlockHeader;
use proto::transaction::Transaction as ProtoTxn;
use proto::transaction::TransactionHeader;
use protobuf;
use protobuf::Message;
use transaction::Transaction;

impl<'source> FromPyObject<'source> for Block {
    fn extract(py: Python, obj: &'source PyObject) -> cpython::PyResult<Self> {
        let bytes: Vec<u8> = obj
            .call_method(py, "SerializeToString", cpython::NoArgs, None)?
            .extract(py)?;

        let mut proto_block: ProtoBlock = protobuf::parse_from_bytes(&bytes)
            .expect("Unable to parse protobuf bytes from python protobuf object");

        let mut block_header: BlockHeader = protobuf::parse_from_bytes(proto_block.get_header())
            .expect("Unable to parse protobuf bytes from python protobuf object");
        let block = Block {
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
                .iter_mut()
                .map(proto_batch_to_batch)
                .collect(),
        };

        Ok(block)
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

impl ToPyObject for Block {
    type ObjectType = PyObject;

    fn to_py_object(&self, py: Python) -> PyObject {
        let block_protobuf_mod = py
            .import("sawtooth_validator.protobuf.block_pb2")
            .expect("Unable to import block_pb2");
        let py_block = block_protobuf_mod
            .get(py, "Block")
            .expect("Unable to get Block");

        let mut proto_block = ProtoBlock::new();
        proto_block.set_header(self.header_bytes.clone());
        proto_block.set_header_signature(self.header_signature.clone());

        let proto_batches = self
            .batches
            .iter()
            .map(|batch| {
                let mut proto_batch = ProtoBatch::new();
                proto_batch.set_header(batch.header_bytes.clone());
                proto_batch.set_header_signature(batch.header_signature.clone());

                let proto_txns = batch
                    .transactions
                    .iter()
                    .map(|txn| {
                        let mut proto_txn = ProtoTxn::new();
                        proto_txn.set_header(txn.header_bytes.clone());
                        proto_txn.set_header_signature(txn.header_signature.clone());
                        proto_txn.set_payload(txn.payload.clone());
                        proto_txn
                    })
                    .collect::<Vec<_>>();

                proto_batch.set_transactions(protobuf::RepeatedField::from_vec(proto_txns));

                proto_batch
            })
            .collect::<Vec<_>>();

        proto_block.set_batches(protobuf::RepeatedField::from_vec(proto_batches));

        let block = py_block
            .call(py, cpython::NoArgs, None)
            .expect("Unable to instantiate Block");
        block
            .call_method(
                py,
                "ParseFromString",
                (cpython::PyBytes::new(py, &proto_block.write_to_bytes().unwrap()).into_object(),),
                None,
            )
            .expect("Unable to ParseFromString");
        block
    }
}

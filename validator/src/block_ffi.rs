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
use cpython::{FromPyObject, ObjectProtocol, PyObject, Python};
use proto::batch::Batch as ProtoBatch;
use proto::batch::BatchHeader;
use proto::block::Block as ProtoBlock;
use proto::block::BlockHeader;
use proto::transaction::Transaction as ProtoTxn;
use proto::transaction::TransactionHeader;
use protobuf;
use transaction::Transaction;

impl<'source> FromPyObject<'source> for Block {
    fn extract(py: Python, obj: &'source PyObject) -> cpython::PyResult<Self> {
        let py_block = obj.getattr(py, "block")
            .expect("Unable to get block from BlockWrapper");

        let bytes: Vec<u8> = py_block
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

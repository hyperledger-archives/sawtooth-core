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
use cpython::FromPyObject;
use cpython::ObjectProtocol;
use cpython::PythonObject;
use cpython::ToPyObject;
use protobuf::Message;

use batch::Batch;
use proto;
use transaction::Transaction;

impl ToPyObject for Batch {
    type ObjectType = cpython::PyObject;

    fn to_py_object(&self, py: cpython::Python) -> Self::ObjectType {
        let mut rust_batch = proto::batch::Batch::new();
        rust_batch.set_header(self.header_bytes.clone());
        let proto_txns = self.transactions
            .iter()
            .map(|txn| {
                let mut proto_txn = proto::transaction::Transaction::new();
                proto_txn.set_header(txn.header_bytes.clone());
                proto_txn.set_header_signature(txn.header_signature.clone());
                proto_txn.set_payload(txn.payload.clone());
                proto_txn
            })
            .collect::<Vec<_>>();
        rust_batch.set_transactions(::protobuf::RepeatedField::from_vec(proto_txns));
        rust_batch.set_trace(self.trace);
        rust_batch.set_header_signature(self.header_signature.clone());

        let batch_pb2 = py.import("sawtooth_validator.protobuf.batch_pb2")
            .expect("unable for python to import sawtooth_validator.protobuf.batch_pb2");
        let batch = batch_pb2
            .call(py, "Batch", cpython::NoArgs, None)
            .expect("No Batch in batch_pb2");
        batch
            .call_method(
                py,
                "ParseFromString",
                cpython::PyTuple::new(
                    py,
                    &[
                        cpython::PyBytes::new(py, &rust_batch.write_to_bytes().unwrap())
                            .into_object(),
                    ],
                ),
                None,
            )
            .unwrap();
        batch
    }
}

impl<'source> FromPyObject<'source> for Batch {
    fn extract(py: cpython::Python, obj: &'source cpython::PyObject) -> cpython::PyResult<Self> {
        let batch_bytes = obj.call_method(py, "SerializeToString", cpython::NoArgs, None)
            .unwrap()
            .extract::<Vec<u8>>(py)
            .unwrap();
        let mut proto_batch: proto::batch::Batch =
            ::protobuf::parse_from_bytes(batch_bytes.as_slice()).unwrap();
        let mut proto_batch_header: proto::batch::BatchHeader =
            ::protobuf::parse_from_bytes(proto_batch.get_header()).unwrap();
        Ok(Batch {
            header_signature: proto_batch.take_header_signature(),
            header_bytes: proto_batch.take_header(),
            transactions: proto_batch
                .transactions
                .iter_mut()
                .map(|t| {
                    let mut proto_header: proto::transaction::TransactionHeader =
                        ::protobuf::parse_from_bytes(t.get_header()).unwrap();
                    Ok(Transaction {
                        header_signature: t.take_header_signature(),
                        header_bytes: t.take_header(),
                        payload: t.take_payload(),
                        batcher_public_key: proto_header.take_batcher_public_key(),
                        dependencies: proto_header.take_dependencies().to_vec(),
                        family_name: proto_header.take_family_name(),
                        family_version: proto_header.take_family_version(),
                        inputs: proto_header.take_inputs().to_vec(),
                        outputs: proto_header.take_outputs().to_vec(),
                        nonce: proto_header.take_nonce(),
                        payload_sha512: proto_header.take_payload_sha512(),
                        signer_public_key: proto_header.take_signer_public_key(),
                    })
                })
                .collect::<cpython::PyResult<Vec<_>>>()?,
            signer_public_key: proto_batch_header.take_signer_public_key(),
            transaction_ids: proto_batch_header.take_transaction_ids().to_vec(),
            trace: proto_batch.get_trace(),
        })
    }
}

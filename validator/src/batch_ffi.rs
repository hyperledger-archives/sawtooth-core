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
        let proto_txns = self
            .transactions
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

        let batch_pb2 = py
            .import("sawtooth_validator.protobuf.batch_pb2")
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
        let batch_bytes = obj
            .call_method(py, "SerializeToString", cpython::NoArgs, None)
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

#[cfg(test)]
mod tests {

    use super::Batch;
    use cpython;
    use cpython::ToPyObject;
    use proto;
    use protobuf::Message;
    use transaction::Transaction;

    fn create_batch() -> Batch {
        let mut batch_header = proto::batch::BatchHeader::new();
        batch_header.set_signer_public_key("C".into());
        batch_header.set_transaction_ids(::protobuf::RepeatedField::from_vec(vec!["B".into()]));
        Batch {
            header_signature: "A".into(),
            transactions: vec![create_txn()],
            signer_public_key: "C".into(),
            transaction_ids: vec!["B".into()],
            trace: true,

            header_bytes: batch_header.write_to_bytes().unwrap(),
        }
    }

    fn create_txn() -> Transaction {
        let mut txn_header = proto::transaction::TransactionHeader::new();
        txn_header.set_batcher_public_key("C".into());
        txn_header.set_dependencies(::protobuf::RepeatedField::from_vec(vec!["D".into()]));
        txn_header.set_family_name("test".into());
        txn_header.set_family_version("1.0".into());
        txn_header.set_inputs(::protobuf::RepeatedField::from_vec(vec!["P".into()]));
        txn_header.set_outputs(::protobuf::RepeatedField::from_vec(vec!["P".into()]));
        txn_header.set_nonce("N".into());
        txn_header.set_payload_sha512("E".into());
        txn_header.set_signer_public_key("T".into());

        Transaction {
            header_signature: "B".into(),
            payload: vec![1, 2, 3],
            batcher_public_key: "C".into(),
            dependencies: vec!["D".into()],
            family_name: "test".into(),
            family_version: "1.0".into(),
            inputs: vec!["P".into()],
            outputs: vec!["P".into()],
            nonce: "N".into(),
            payload_sha512: "E".into(),
            signer_public_key: "T".into(),

            header_bytes: txn_header.write_to_bytes().unwrap(),
        }
    }

    #[test]
    fn test_basic() {
        let gil = cpython::Python::acquire_gil();
        let py = gil.python();

        let batch = create_batch();
        let resulting_batch = batch.to_py_object(py).extract::<Batch>(py).unwrap();
        assert_eq!(batch, resulting_batch);
    }
}

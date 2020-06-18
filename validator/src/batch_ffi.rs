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

use cpython::{self, ObjectProtocol, Python, PythonObject, ToPyObject};
use protobuf::Message;
use sawtooth::{batch::Batch, protos, transaction::Transaction};

use crate::py_object_wrapper::PyObjectWrapper;

impl From<Batch> for PyObjectWrapper {
    fn from(native_batch: Batch) -> Self {
        let gil = Python::acquire_gil();
        let py = gil.python();

        let batch_proto = protos::batch::Batch::from(native_batch);
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
                        cpython::PyBytes::new(py, &batch_proto.write_to_bytes().unwrap())
                            .into_object(),
                    ],
                ),
                None,
            )
            .unwrap();
        PyObjectWrapper::new(batch)
    }
}

impl From<PyObjectWrapper> for Batch {
    fn from(py_object_wrapper: PyObjectWrapper) -> Self {
        let gil = Python::acquire_gil();
        let py = gil.python();
        let py_obj = py_object_wrapper.to_py_object(py);

        let bytes: Vec<u8> = py_obj
            .call_method(py, "SerializeToString", cpython::NoArgs, None)
            .expect("Unable to serialize PyObject to string")
            .extract(py)
            .expect("Unable to extract bytes from PyObject string");

        let mut proto_batch: protos::batch::Batch = protobuf::parse_from_bytes(&bytes)
            .expect("Unable to parse protobuf bytes from python protobuf object");
        let mut batch_header: protos::batch::BatchHeader =
            protobuf::parse_from_bytes(proto_batch.get_header())
                .expect("Unable to parse protobuf bytes from python protobuf object");

        Batch {
            header_signature: proto_batch.take_header_signature(),
            header_bytes: proto_batch.take_header(),
            signer_public_key: batch_header.take_signer_public_key(),
            transaction_ids: batch_header.take_transaction_ids().into_vec(),
            trace: proto_batch.get_trace(),

            transactions: proto_batch
                .take_transactions()
                .into_iter()
                .map(Transaction::from)
                .collect(),
        }
    }
}

#[cfg(test)]
mod tests {

    use protobuf::Message;
    use py_object_wrapper::PyObjectWrapper;
    use sawtooth::{batch::Batch, protos, transaction::Transaction};

    fn create_batch() -> Batch {
        let mut batch_header = protos::batch::BatchHeader::new();
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
        let mut txn_header = protos::transaction::TransactionHeader::new();
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
        let batch = create_batch();
        let py_obj_wrapper = PyObjectWrapper::from(batch.clone());
        let extracted_batch = Batch::from(py_obj_wrapper);
        assert_eq!(batch, extracted_batch);
    }
}

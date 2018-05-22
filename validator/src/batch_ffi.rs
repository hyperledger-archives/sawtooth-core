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
use cpython::ObjectProtocol;
use cpython::PythonObject;
use cpython::ToPyObject;
use protobuf::Message;

use batch::Batch;
use proto;

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

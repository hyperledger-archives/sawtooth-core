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
use sawtooth::protos::{FromBytes, IntoBytes};
use transact::protocol::batch::Batch;

use crate::py_object_wrapper::PyObjectWrapper;

impl From<Batch> for PyObjectWrapper {
    fn from(native_batch: Batch) -> Self {
        let gil = Python::acquire_gil();
        let py = gil.python();

        let batch_pb2 = py
            .import("sawtooth_validator.protobuf.batch_pb2")
            .expect("Unable to import batch_pb2");
        let batch = batch_pb2
            .call(py, "Batch", cpython::NoArgs, None)
            .expect("No Batch in batch_pb2");

        batch
            .call_method(
                py,
                "ParseFromString",
                (cpython::PyBytes::new(py, &native_batch.into_bytes().unwrap()).into_object(),),
                None,
            )
            .expect("Unable to ParseFromString");
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
            .expect("Unable to serialize PyObject")
            .extract(py)
            .expect("Unable to extract bytes from PyObject");

        Batch::from_bytes(&bytes).expect("Unable to parse batch from bytes")
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    use cylinder::{secp256k1::Secp256k1Context, Context, Signer};
    use transact::protocol::{
        batch::BatchBuilder,
        transaction::{HashMethod, TransactionBuilder},
    };

    #[test]
    fn test_basic() {
        let signer = new_signer();
        let txn = TransactionBuilder::new()
            .with_family_name("test".into())
            .with_family_version("1.0".into())
            .with_inputs(vec![])
            .with_outputs(vec![])
            .with_payload_hash_method(HashMethod::SHA512)
            .with_payload(vec![])
            .build(&*signer)
            .expect("Failed to build transaction");
        let batch = BatchBuilder::new()
            .with_transactions(vec![txn])
            .build(&*signer)
            .expect("Failed to build batch");

        let py_obj_wrapper = PyObjectWrapper::from(batch.clone());
        let extracted_batch = Batch::from(py_obj_wrapper);

        assert_eq!(batch, extracted_batch);
    }

    fn new_signer() -> Box<dyn Signer> {
        let context = Secp256k1Context::new();
        let key = context.new_random_private_key();
        context.new_signer(key)
    }
}

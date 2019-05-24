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

use cpython::{self, ObjectProtocol, PyClone};

use batch::Batch;

pub trait PermissionVerifier: Sync + Send {
    fn is_batch_signer_authorized(&self, batch: &Batch, state_root: &str) -> bool;
}

pub struct PyPermissionVerifier {
    verifier: cpython::PyObject,
}

impl PyPermissionVerifier {
    pub fn new(verifier: cpython::PyObject) -> Self {
        PyPermissionVerifier { verifier }
    }
}

impl PermissionVerifier for PyPermissionVerifier {
    fn is_batch_signer_authorized(&self, batch: &Batch, state_root: &str) -> bool {
        let gil = cpython::Python::acquire_gil();
        let py = gil.python();

        self.verifier
            .call_method(py, "is_batch_signer_authorized", (batch, state_root), None)
            .expect("PermissionVerifier has no method `is_batch_signer_authorized`")
            .extract(py)
            .expect("Unable to extract bool from `is_batch_signer_authorized`")
    }
}

impl Clone for PyPermissionVerifier {
    fn clone(&self) -> Self {
        let gil = cpython::Python::acquire_gil();
        let py = gil.python();

        PyPermissionVerifier::new(self.verifier.clone_ref(py))
    }
}

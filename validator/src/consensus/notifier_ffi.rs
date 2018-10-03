/*
 * Copyright 2018 Cargill Incorporated
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

use cpython::{ObjectProtocol, PyClone, PyObject, Python, ToPyObject};

use block::Block;
use consensus::notifier::ConsensusNotifier;
use pylogger;

pub struct PyConsensusNotifier {
    py_consensus_notifier: PyObject,
}

impl PyConsensusNotifier {
    pub fn new(py_consensus_notifier: PyObject) -> Self {
        PyConsensusNotifier {
            py_consensus_notifier,
        }
    }

    fn call_py_fn<T: ToPyObject>(&self, py_fn_name: &str, obj: T) {
        let gil_guard = Python::acquire_gil();
        let py = gil_guard.python();

        self.py_consensus_notifier
            .call_method(py, py_fn_name, (obj,), None)
            .map(|_| ())
            .map_err(|py_err| {
                pylogger::exception(
                    py,
                    &format!("Unable to call consensus_notifier.{}", py_fn_name),
                    py_err,
                );
                ()
            }).unwrap_or(())
    }
}

impl Clone for PyConsensusNotifier {
    fn clone(&self) -> Self {
        let gil_guard = Python::acquire_gil();
        let py = gil_guard.python();

        PyConsensusNotifier {
            py_consensus_notifier: self.py_consensus_notifier.clone_ref(py),
        }
    }
}

impl ConsensusNotifier for PyConsensusNotifier {
    fn notify_block_new(&self, block: &Block) {
        self.call_py_fn("notify_block_new", block)
    }

    fn notify_block_valid(&self, block_id: &str) {
        self.call_py_fn("notify_block_valid", block_id)
    }

    fn notify_block_invalid(&self, block_id: &str) {
        self.call_py_fn("notify_block_invalid", block_id)
    }

    fn notify_block_commit(&self, block_id: &str) {
        self.call_py_fn("notify_block_commit", block_id)
    }

    fn notify_batch_new(&self, batch_id: &str) {
        self.call_py_fn("notify_batch_new", batch_id)
    }

    fn notify_batch_invalid(&self, batch_id: &str) {
        self.call_py_fn("notify_batch_invalid", batch_id)
    }
}

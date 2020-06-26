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
use cpython::{ObjectProtocol, PyClone};
use sawtooth::{
    execution::execution_platform::{ExecutionPlatform, ExecutionPlatformError},
    scheduler::Scheduler,
};

use scheduler::py_scheduler::PyScheduler;

pub struct PyExecutor {
    executor: cpython::PyObject,
}

impl PyExecutor {
    pub fn new(executor: cpython::PyObject) -> Result<PyExecutor, cpython::PyErr> {
        Ok(PyExecutor { executor })
    }
}

impl ExecutionPlatform for PyExecutor {
    fn create_scheduler(
        &self,
        state_hash: &str,
    ) -> Result<Box<dyn Scheduler>, ExecutionPlatformError> {
        let gil = cpython::Python::acquire_gil();
        let py = gil.python();
        let scheduler = self
            .executor
            .call_method(py, "create_scheduler", (state_hash,), None)
            .expect(
                "no method create_scheduler on sawtooth_validator.execution.py_executor.PyExecutor",
            );
        Ok(Box::new(PyScheduler::new(scheduler)))
    }
}

impl Clone for PyExecutor {
    fn clone(&self) -> Self {
        let gil = cpython::Python::acquire_gil();
        let py = gil.python();

        PyExecutor {
            executor: self.executor.clone_ref(py),
        }
    }
}

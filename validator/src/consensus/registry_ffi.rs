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

use cpython::{NoArgs, ObjectProtocol, PyClone, PyObject, Python};

use consensus::registry::{ConsensusRegistry, ConsensusRegistryError, EngineInfo};
use pylogger;

pub struct PyConsensusRegistry {
    py_consensus_registry: PyObject,
}

impl PyConsensusRegistry {
    pub fn new(py_consensus_registry: PyObject) -> Self {
        PyConsensusRegistry {
            py_consensus_registry,
        }
    }
}

impl Clone for PyConsensusRegistry {
    fn clone(&self) -> Self {
        let gil_guard = Python::acquire_gil();
        let py = gil_guard.python();

        PyConsensusRegistry {
            py_consensus_registry: self.py_consensus_registry.clone_ref(py),
        }
    }
}

impl ConsensusRegistry for PyConsensusRegistry {
    fn activate_engine(&self, name: &str, version: &str) -> Result<(), ConsensusRegistryError> {
        let gil_guard = Python::acquire_gil();
        let py = gil_guard.python();

        self.py_consensus_registry
            .call_method(py, "activate_engine", (name, version), None)
            .map(|_| ())
            .map_err(|py_err| {
                pylogger::exception(
                    py,
                    "Unable to call consensus_registry.activate_engine",
                    py_err,
                );
                ConsensusRegistryError(
                    "FFI error calling consensus_registry.activate_engine".into(),
                )
            })
    }

    fn get_active_engine_info(&self) -> Result<Option<EngineInfo>, ConsensusRegistryError> {
        let gil_guard = Python::acquire_gil();
        let py = gil_guard.python();

        let res = self
            .py_consensus_registry
            .call_method(py, "get_active_engine_info", NoArgs, None)
            .map_err(|py_err| {
                pylogger::exception(
                    py,
                    "Unable to call consensus_registry.get_active_engine_info",
                    py_err,
                );
                ConsensusRegistryError(
                    "FFI error calling consensus_registry.get_active_engine_info".into(),
                )
            })?;

        res.extract::<(String, String, String)>(py)
            .map(|tuple| {
                Some(EngineInfo {
                    connection_id: tuple.0,
                    name: tuple.1,
                    version: tuple.2,
                })
            })
            // get_active_engine_info returns None if no engine is active
            .or(Ok(None))
    }

    fn is_active_engine_name_version(
        &self,
        name: &str,
        version: &str,
    ) -> Result<bool, ConsensusRegistryError> {
        let gil_guard = Python::acquire_gil();
        let py = gil_guard.python();

        let res = self
            .py_consensus_registry
            .call_method(py, "is_active_engine_name_version", (name, version), None)
            .map_err(|py_err| {
                pylogger::exception(
                    py,
                    "Unable to call consensus_registry.is_active_engine_name_version",
                    py_err,
                );
                ConsensusRegistryError(
                    "FFI error calling consensus_registry.is_active_engine_name_version".into(),
                )
            })?;

        res.extract::<bool>(py).map_err(|py_err| {
            pylogger::exception(
                py,
                "consensus_registry.is_active_engine_name_version did not return a valid bool",
                py_err,
            );
            ConsensusRegistryError(
                "consensus_registry.is_active_engine_name_version did not return a valid bool"
                    .into(),
            )
        })
    }
}

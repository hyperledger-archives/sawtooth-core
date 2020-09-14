// Copyright 2018 Intel Corporation
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
// ------------------------------------------------------------------------------

use cpython::{ObjectProtocol, PyObject, Python};
use metrics::{Key, Recorder, SetRecorderError};

// This is used in main but clippy says it is unused
#[allow(dead_code)]
pub fn set_up_metrics(py: Python) {
    PyRecorder::init(py).expect("Failed to initialize metrics");
}

#[no_mangle]
pub extern "C" fn pymetrics_init() {
    let gil = Python::acquire_gil();
    let py = gil.python();
    if PyRecorder::init(py).is_err() {
        warn!("Attempted to initialize metrics recorder twice; ignoring");
    }
}

pub struct PyRecorder {
    py_collector: PyObject,
}

impl PyRecorder {
    fn new(py: Python) -> Self {
        let py_collector = py
            .import("sawtooth_validator.metrics")
            .expect("Failed to import sawtooth_validator.metrics module")
            .call(py, "get_collector", cpython::NoArgs, None)
            .expect("Failed to call metrics.get_collector()");
        Self { py_collector }
    }

    pub fn init(py: Python) -> Result<(), SetRecorderError> {
        metrics::set_boxed_recorder(Box::new(Self::new(py)))
    }
}

impl Recorder for PyRecorder {
    fn increment_counter(&self, key: Key, value: u64) {
        let gil = Python::acquire_gil();
        let py = gil.python();
        self.py_collector
            .call_method(py, "counter", (key.name(),), None)
            .expect("Failed to create new metric")
            .call_method(py, "inc", (value,), None)
            .expect("Failed to call Counter.inc()");
    }

    fn update_gauge(&self, key: Key, value: i64) {
        let gil = Python::acquire_gil();
        let py = gil.python();
        self.py_collector
            .call_method(py, "gauge", (key.name(),), None)
            .expect("Failed to create new metric")
            .call_method(py, "set_value", (value,), None)
            .expect("Failed to call Gauge.set_value()");
    }

    fn record_histogram(&self, _key: Key, _value: u64) {}
}

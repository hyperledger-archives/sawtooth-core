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

use std::collections::HashMap;

use cpython::{NoArgs, ObjectProtocol, PyDict, PyModule, PyObject, Python, ToPyObject};

pub fn get_collector<S: AsRef<str>>(name: S) -> MetricsCollectorHandle {
    let gil = Python::acquire_gil();
    let py = gil.python();
    let py_metrics = py
        .import("sawtooth_validator.metrics")
        .expect("Failed to import sawtooth_validator.metrics module");
    let py_collector = py_metrics
        .call(py, "get_collector", (name.as_ref(),), None)
        .expect("Failed to call metrics.get_collector()");
    MetricsCollectorHandle {
        py_collector,
        py_metrics,
    }
}

#[derive(Copy, Clone)]
pub enum Level {
    Info,
}

impl Default for Level {
    fn default() -> Self {
        Level::Info
    }
}

fn into_level_str(level: Level) -> &'static str {
    use self::Level::*;
    match level {
        Info => "INFO",
    }
}

pub struct MetricsCollectorHandle {
    py_collector: PyObject,
    py_metrics: PyModule,
}

impl MetricsCollectorHandle {
    pub fn counter<S: AsRef<str>>(
        &self,
        metric_name: S,
        level: Option<Level>,
        tags: Option<HashMap<String, String>>,
    ) -> Counter {
        Counter {
            py_counter: self.create_metric("counter", metric_name, level, tags),
        }
    }

    pub fn gauge<S: AsRef<str>>(
        &self,
        metric_name: S,
        level: Option<Level>,
        tags: Option<HashMap<String, String>>,
    ) -> Gauge {
        Gauge {
            py_gauge: self.create_metric("gauge", metric_name, level, tags),
        }
    }

    fn create_metric<S: AsRef<str>>(
        &self,
        metric_type: &str,
        metric_name: S,
        level: Option<Level>,
        tags: Option<HashMap<String, String>>,
    ) -> PyObject {
        let gil = Python::acquire_gil();
        let py = gil.python();

        let py_level = self
            .py_metrics
            .get(py, into_level_str(level.unwrap_or_default()))
            .expect("Failed to get metric level");
        let py_tags: PyDict = tags.unwrap_or_else(HashMap::new).into_py_object(py);
        let kwargs = PyDict::new(py);
        kwargs.set_item(py, "level", py_level).unwrap();
        kwargs.set_item(py, "tags", py_tags).unwrap();

        self.py_collector
            .call_method(py, metric_type, (metric_name.as_ref(),), Some(&kwargs))
            .expect("Failed to create new metric")
    }
}

pub struct Gauge {
    py_gauge: PyObject,
}

impl Gauge {
    pub fn set_value<T: ToPyObject>(&mut self, value: T) {
        let gil = Python::acquire_gil();
        let py = gil.python();
        self.py_gauge
            .call_method(py, "set_value", (value,), None)
            .expect("Failed to call Gauge.set_value()");
    }
}

pub struct Counter {
    py_counter: PyObject,
}

impl Counter {
    pub fn inc(&mut self) {
        let gil = Python::acquire_gil();
        let py = gil.python();
        self.py_counter
            .call_method(py, "inc", NoArgs, None)
            .expect("Failed to call Counter.inc()");
    }

    pub fn inc_n(&mut self, value: usize) {
        let gil = Python::acquire_gil();
        let py = gil.python();
        self.py_counter
            .call_method(py, "inc", (value,), None)
            .expect("Failed to call Counter.inc()");
    }

    pub fn dec_n(&mut self, value: usize) {
        let gil = Python::acquire_gil();
        let py = gil.python();
        self.py_counter
            .call_method(py, "dec", (value,), None)
            .expect("Failed to call Counter.dec()");
    }
}

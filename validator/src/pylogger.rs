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

use cpython::{
    ObjectProtocol, PyDict, PyErr, PyModule, PyObject, PyResult, PyTuple, Python, PythonObject,
    ToPyObject,
};
use log;
use log::{Level, Log, Metadata, Record, SetLoggerError};

pub fn set_up_logger(verbosity: u64, py: Python) {
    let verbosity_level: Level = determine_log_level(verbosity);

    PyLogger::init(verbosity_level, py).expect("Failed to set logger");

    let server_log = py
        .import("sawtooth_validator.server.log")
        .map_err(|err| err.print(py))
        .unwrap();

    server_log
        .call(py, "init_console_logging", (verbosity,), None)
        .map_err(|err| err.print(py))
        .unwrap();

    warn!("Started logger at level {}", verbosity_level);
}

#[no_mangle]
#[allow(unused)]
pub extern "C" fn pylogger_init(verbosity: usize) {
    let gil = Python::acquire_gil();
    let py = gil.python();
    if let Err(_) = PyLogger::init(determine_log_level(verbosity as u64), py) {
        warn!("Attempted to initialize logger twice; ignoring");
    }
}

pub fn exception(py: Python, msg: &str, err: PyErr) {
    let logger = PyLogger::new(py).expect("Failed to create new PyLogger");
    logger.exception(py, msg, err);
}

struct PyLogger {
    logger: PyObject,
    logging: PyModule,
}

impl PyLogger {
    fn new(py: Python) -> PyResult<Self> {
        let logging = py.import("logging")?;
        let logger = logging.call(py, "getLogger", PyTuple::new(py, &[]), None)?;
        Ok(PyLogger { logger, logging })
    }

    fn init(verbosity: Level, py: Python) -> Result<(), SetLoggerError> {
        let logger =
            PyLogger::new(py).expect("Failed to instantiate Python logger; check library paths.");

        log::set_boxed_logger(Box::new(logger))?;

        log::set_max_level(verbosity.to_level_filter());

        Ok(())
    }

    pub fn exception(&self, py: Python, msg: &str, mut err: PyErr) {
        let kwargs = PyDict::new(py);
        let exc_info = (
            err.get_type(py),
            err.instance(py),
            err.ptraceback.unwrap_or_else(|| py.None()),
        );
        kwargs.set_item(py, "exc_info", exc_info).unwrap();
        self.logger
            .call_method(py, "error", (msg,), Some(&kwargs))
            .unwrap();
    }
}

fn determine_log_level(verbosity: u64) -> Level {
    match verbosity {
        0 => Level::Warn,
        1 => Level::Info,
        _ => Level::Debug,
    }
}

fn into_level_string(level: Level) -> &'static str {
    match level {
        Level::Error => "ERROR",
        Level::Warn => "WARN",
        Level::Info => "INFO",
        Level::Debug => "DEBUG",
        Level::Trace => "DEBUG",
    }
}

fn into_level_method(level: Level) -> &'static str {
    match level {
        Level::Error => "error",
        Level::Warn => "warn",
        Level::Info => "info",
        Level::Debug => "debug",
        Level::Trace => "debug",
    }
}

impl Log for PyLogger {
    fn enabled(&self, metadata: &Metadata) -> bool {
        let gil = Python::acquire_gil();
        let py = gil.python();

        let level = into_level_string(metadata.level());
        let pylevel = self.logging.get(py, level).unwrap();

        self.logger
            .call_method(py, "isEnabledFor", PyTuple::new(py, &[pylevel]), None)
            .unwrap()
            .extract(py)
            .unwrap()
    }

    fn log(&self, record: &Record) {
        let gil = Python::acquire_gil();
        let py = gil.python();

        if !self.enabled(record.metadata()) {
            return;
        }

        let method = into_level_method(record.level());
        let record = format!(
            "[{}: {}] {}",
            record.file().unwrap_or("unknown file"),
            record.line().unwrap_or(0),
            record.args()
        );

        self.logger
            .call_method(
                py,
                method,
                PyTuple::new(py, &[record.to_py_object(py).into_object()]),
                None,
            ).unwrap();
    }

    fn flush(&self) {
        let gil = Python::acquire_gil();
        let py = gil.python();
        self.logger
            .call_method(py, "flush", PyTuple::new(py, &[]), None)
            .unwrap();
    }
}

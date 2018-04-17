extern crate cpython;

use cpython::{PyString, Python};

fn main() {
    let gil = Python::acquire_gil();
    let py = &mut gil.python();

    let mut args: Vec<PyString> = std::env::args()
        .skip(1)
        .map(|s| PyString::new(*py, &s))
        .collect();

    args.insert(0, PyString::new(*py, env!("CARGO_PKG_NAME")));

    let cli = py.import("sawtooth_validator.server.cli")
        .map_err(|err| err.print(*py))
        .unwrap();
    cli.call(*py, "main", (args,), None)
        .map_err(|err| err.print(*py))
        .unwrap();
}

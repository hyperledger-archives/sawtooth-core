extern crate clap;
extern crate cpython;
#[macro_use]
extern crate log;

mod pylogger;
mod server;

use server::cli;
use cpython::{ObjectProtocol, Python};

fn main() {
    let gil = Python::acquire_gil();
    let py = &mut gil.python();

    let args = cli::parse_args();

    let verbosity: u64 = args.occurrences_of("verbose");
    pylogger::set_up_logger(verbosity, py);

    let py_cli_module = py.import("sawtooth_validator.server.cli")
        .map_err(|err| err.print(*py))
        .unwrap();

    let args_dict = cli::wrap_in_pydict(py, &args)
        .map_err(|err| err.print(*py))
        .unwrap();

    let path_config = py_cli_module
        .call(*py, "get_path_config", (args.value_of("config_dir"),), None)
        .map_err(|err| err.print(*py))
        .unwrap();

    let config_dir = path_config
        .getattr(*py, "config_dir")
        .map_err(|err| err.print(*py))
        .unwrap();

    let validator_config = py_cli_module
        .call(*py, "get_validator_config", (&args_dict, &config_dir), None)
        .map_err(|err| err.print(*py))
        .unwrap();

    let identity_signer = py_cli_module
        .call(*py, "get_identity_signer", (&path_config,), None)
        .map_err(|err| err.print(*py))
        .unwrap();

    py_cli_module
        .call(
            *py,
            "main",
            (
                &path_config,
                &validator_config,
                &identity_signer,
                &verbosity,
            ),
            None,
        )
        .map_err(|err| err.print(*py))
        .unwrap();
}

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

    // Process initial initialization errors, delaying the exit(1)
    // until all errors have been reported to the user. This is
    // intended to provide enough information to the user so they can
    // correct multiple errors before restarting the validator.
    let mut init_errors = !identity_signer
        .is_true(*py)
        .map_err(|err| err.print(*py))
        .unwrap();

    py_cli_module
        .call(
            *py,
            "configure_logging",
            (&path_config, &init_errors, &verbosity),
            None,
        )
        .map_err(|err| err.print(*py))
        .unwrap();

    py_cli_module
        .call(*py, "log_version", cpython::NoArgs, None)
        .map_err(|err| err.print(*py))
        .unwrap();

    py_cli_module
        .call(*py, "log_path_config", (&path_config,), None)
        .map_err(|err| err.print(*py))
        .unwrap();

    let check_directories_result = py_cli_module
        .call(*py, "check_directories", (&path_config,), None)
        .map_err(|err| err.print(*py))
        .unwrap();

    init_errors = init_errors
        || check_directories_result
            .is_true(*py)
            .map_err(|err| err.print(*py))
            .unwrap();

    let endpoint = {
        let config_endpoint = validator_config
            .getattr(*py, "endpoint")
            .map_err(|err| err.print(*py))
            .unwrap();

        if config_endpoint
            .is_true(*py)
            .map_err(|err| err.print(*py))
            .unwrap()
        {
            config_endpoint
        } else {
            let bind_endpoint = validator_config
                .getattr(*py, "bind_network")
                .map_err(|err| err.print(*py))
                .unwrap();

            let check_interfaces_result = py_cli_module
                .call(*py, "check_interfaces", (&bind_endpoint,), None)
                .map_err(|err| err.print(*py))
                .unwrap();

            init_errors = init_errors
                || check_interfaces_result
                    .is_true(*py)
                    .map_err(|err| err.print(*py))
                    .unwrap();

            bind_endpoint
        }
    };

    py_cli_module
        .call(*py, "exit_if_errors", (init_errors,), None)
        .map_err(|err| err.print(*py))
        .unwrap();

    if !validator_config
        .getattr(*py, "network_public_key")
        .map_err(|err| err.print(*py))
        .unwrap()
        .is_true(*py)
        .map_err(|err| err.print(*py))
        .unwrap()
        || !validator_config
            .getattr(*py, "network_private_key")
            .map_err(|err| err.print(*py))
            .unwrap()
            .is_true(*py)
            .map_err(|err| err.print(*py))
            .unwrap()
    {
        warn!(
            "Network key pair is not configured; \
             network communications between validators \
             will not be authenticated or encrypted"
        );
    }

    let metrics_reporter = py_cli_module
        .call(*py, "start_metrics", (&validator_config,), None)
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
                &endpoint,
                &metrics_reporter,
            ),
            None,
        )
        .map_err(|err| err.print(*py))
        .unwrap();
}

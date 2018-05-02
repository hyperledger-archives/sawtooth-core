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

    macro_rules! py_unwrap {
        ($expr:expr) => {
            $expr.map_err(|err| err.print(*py)).unwrap()
        }
    }

    macro_rules! py_import {
        ($module_name:expr) => {
            py_unwrap!(py.import($module_name))
        }
    }

    macro_rules! py_call {
        // Call $function with no arguments
        ($module:expr, $function:expr) => {
            py_unwrap!($module.call(*py, $function, cpython::NoArgs, None))
        };

        // Call $function with tuple $args
        ($module:expr, $function:expr, $args:expr) => {
            py_unwrap!($module.call(*py, $function, $args, None))
        }
    }

    macro_rules! py_getattr {
        ($obj:expr, $attr:expr) => {
            py_unwrap!($obj.getattr(*py, $attr))
        }
    }

    macro_rules! py_is_true {
        ($obj:expr) => {
            py_unwrap!($obj.is_true(*py))
        }
    }

    let args = cli::parse_args();

    let verbosity: u64 = args.occurrences_of("verbose");
    pylogger::set_up_logger(verbosity, py);

    let py_cli_module = py_import!("sawtooth_validator.server.cli");

    let args_dict = py_unwrap!(cli::wrap_in_pydict(py, &args));

    let path_config = py_call!(
        py_cli_module,
        "get_path_config",
        (args.value_of("config_dir"),)
    );

    let config_dir = py_getattr!(path_config, "config_dir");

    let validator_config = py_call!(
        py_cli_module,
        "get_validator_config",
        (&args_dict, &config_dir,)
    );

    let identity_signer = py_call!(py_cli_module, "get_identity_signer", (&path_config,));

    // Process initial initialization errors, delaying the exit(1)
    // until all errors have been reported to the user. This is
    // intended to provide enough information to the user so they can
    // correct multiple errors before restarting the validator.
    let mut init_errors = !py_is_true!(identity_signer);

    py_call!(
        py_cli_module,
        "configure_logging",
        (&path_config, &init_errors, &verbosity)
    );

    py_call!(py_cli_module, "log_version");

    py_call!(py_cli_module, "log_path_config", (&path_config,));

    let check_directories_result = py_call!(py_cli_module, "check_directories", (&path_config,));

    init_errors = init_errors || py_is_true!(check_directories_result);

    let endpoint = {
        let config_endpoint = py_getattr!(validator_config, "endpoint");

        if py_is_true!(config_endpoint) {
            config_endpoint
        } else {
            let bind_endpoint = py_getattr!(validator_config, "bind_network");

            let check_interfaces_result =
                py_call!(py_cli_module, "check_interfaces", (&bind_endpoint,));

            init_errors = init_errors || py_is_true!(check_interfaces_result);

            bind_endpoint
        }
    };

    py_call!(py_cli_module, "exit_if_errors", (init_errors,));

    if !py_is_true!(py_getattr!(validator_config, "network_public_key"))
        || !py_is_true!(py_getattr!(validator_config, "network_private_key"))
    {
        warn!(
            "Network key pair is not configured; \
             network communications between validators \
             will not be authenticated or encrypted"
        );
    }

    let metrics_reporter = py_call!(py_cli_module, "start_metrics", (&validator_config,));

    // Verify state integrity before startup
    py_call!(
        py_cli_module,
        "verify_state",
        (&path_config, &validator_config)
    );

    let validator = py_call!(
        py_cli_module,
        "make_validator",
        (&path_config, &validator_config, &identity_signer, &endpoint)
    );

    py_call!(
        py_cli_module,
        "run_validator",
        (&validator, &metrics_reporter)
    );
}

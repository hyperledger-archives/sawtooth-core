# Copyright 2016 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ------------------------------------------------------------------------------

import logging
import sys
import argparse
import os
import pkg_resources
import netifaces

import sawtooth_signing as signing

from sawtooth_validator.config.path import load_path_config
from sawtooth_validator.config.validator import load_default_validator_config
from sawtooth_validator.config.validator import load_toml_validator_config
from sawtooth_validator.config.validator import merge_validator_config
from sawtooth_validator.config.validator import ValidatorConfig
from sawtooth_validator.config.logs import get_log_config
from sawtooth_validator.server.core import Validator
from sawtooth_validator.server.keys import load_identity_signing_key
from sawtooth_validator.server.log import init_console_logging
from sawtooth_validator.server.log import log_configuration
from sawtooth_validator.exceptions import GenesisError
from sawtooth_validator.exceptions import LocalConfigurationError


LOGGER = logging.getLogger(__name__)
DISTRIBUTION_NAME = 'sawtooth-validator'


def parse_args(args):
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument('--config-dir',
                        help='Configuration directory',
                        type=str)
    parser.add_argument('-B', '--bind',
                        help='Set the endpoint url for the network and the '
                             'validator component service endpoints. Multiple '
                             '--bind arguments should be provided in the '
                             'format network:endpoint and component:endpoint.',
                        action='append',
                        type=str)
    parser.add_argument('-P', '--peering',
                        help='The type of peering approach the validator '
                             'should take. Choices are \'static\' which '
                             'only attempts to peer with candidates '
                             'provided with the --peers option, and '
                             '\'dynamic\' which will do topology buildouts. '
                             'If \'dynamic\' is provided, any static peers '
                             'will be processed first, prior to the topology '
                             'buildout starting',
                        choices=['static', 'dynamic'],
                        type=str)
    parser.add_argument('-E', '--endpoint',
                        help='Advertised network endpoint URL',
                        type=str)
    parser.add_argument('-s', '--seeds',
                        help='uri(s) to connect to in order to initially '
                             'connect to the validator network, in the '
                             'format tcp://hostname:port. Multiple --seeds '
                             'arguments can be provided, and a single '
                             '--seeds argument will accept a comma separated '
                             'list of tcp://hostname:port,tcp://hostname:port '
                             'parameters',
                        action='append',
                        type=str)
    parser.add_argument('-p', '--peers',
                        help='A list of peers to attempt to connect to '
                             'in the format tcp://hostname:port. Multiple '
                             '--peers arguments can be provided, and a single '
                             '--peers argument will accept a comma separated '
                             'list of tcp://hostname:port,tcp://hostname:port '
                             'parameters',
                        action='append',
                        type=str)
    parser.add_argument('-v', '--verbose',
                        action='count',
                        default=0,
                        help='Increase output sent to stderr')

    try:
        version = pkg_resources.get_distribution(DISTRIBUTION_NAME).version
    except pkg_resources.DistributionNotFound:
        version = 'UNKNOWN'

    parser.add_argument(
        '-V', '--version',
        action='version',
        version=(DISTRIBUTION_NAME + ' (Hyperledger Sawtooth) version {}')
        .format(version),
        help='print version information')

    return parser.parse_args(args)


def check_directory(path, human_readable_name):
    """Verify that the directory exists and is readable and writable.

    Args:
        path (str): a directory which should exist and be writable
        human_readable_name (str): a human readable string for the directory
            which is used in logging statements

    Returns:
        bool: False if an error exists, True otherwise.
    """
    if not os.path.exists(path):
        LOGGER.error("%s directory does not exist: %s",
                     human_readable_name,
                     path)
        return False

    if not os.path.isdir(path):
        LOGGER.error("%s directory is not a directory: %s",
                     human_readable_name,
                     path)
        return False

    errors = True
    if not os.access(path, os.R_OK):
        LOGGER.error("%s directory is not readable: %s",
                     human_readable_name,
                     path)
        errors = False
    if not os.access(path, os.W_OK):
        LOGGER.error("%s directory is not writable: %s",
                     human_readable_name,
                     path)
        errors = False
    return errors


def _split_comma_append_args(arg_list):
    new_arg_list = []

    for arg in arg_list:
        new_arg_list.extend([x.strip() for x in arg.split(',')])

    return new_arg_list


def load_validator_config(first_config, config_dir):
    default_validator_config = load_default_validator_config()
    conf_file = os.path.join(config_dir, 'validator.toml')

    toml_config = load_toml_validator_config(conf_file)

    return merge_validator_config(
        configs=[first_config, toml_config, default_validator_config])


def create_validator_config(opts):
    bind_network = None
    bind_component = None
    if opts.bind:
        for bind in opts.bind:
            if "network" in bind:
                bind_network = bind[bind.find(":")+1:]
            if "component" in bind:
                bind_component = bind[bind.find(":")+1:]
    return ValidatorConfig(
        bind_network=bind_network,
        bind_component=bind_component,
        endpoint=opts.endpoint,
        peering=opts.peering,
        seeds=opts.seeds,
        peers=opts.peers)


def main(args=None):
    if args is None:
        args = sys.argv[1:]
    opts = parse_args(args)
    verbose_level = opts.verbose

    # Determine if any args which support delimited lists should be
    # modified
    if opts.peers:
        opts.peers = _split_comma_append_args(opts.peers)

    if opts.seeds:
        opts.seeds = _split_comma_append_args(opts.seeds)

    init_console_logging(verbose_level=verbose_level)

    try:
        path_config = load_path_config(config_dir=opts.config_dir)
    except LocalConfigurationError as local_config_err:
        LOGGER.error(str(local_config_err))
        sys.exit(1)

    try:
        opts_config = create_validator_config(opts)
        validator_config = \
            load_validator_config(opts_config, path_config.config_dir)
    except LocalConfigurationError as local_config_err:
        LOGGER.error(str(local_config_err))
        sys.exit(1)

    # Process initial initialization errors, delaying the sys.exit(1) until
    # all errors have been reported to the user (via LOGGER.error()).  This
    # is intended to provide enough information to the user so they can correct
    # multiple errors before restarting the validator.
    init_errors = False

    try:
        identity_signing_key = load_identity_signing_key(
            key_dir=path_config.key_dir,
            key_name='validator')
        pubkey = signing.generate_pubkey(identity_signing_key)
    except LocalConfigurationError as e:
        log_configuration(log_dir=path_config.log_dir,
                          name="validator")
        LOGGER.error(str(e))
        init_errors = True

    log_config = get_log_config()
    if not init_errors:
        if log_config is not None:
            log_configuration(log_config=log_config)
            if log_config.get('root') is not None:
                init_console_logging(verbose_level=verbose_level)
        else:
            log_configuration(log_dir=path_config.log_dir,
                              name="validator-" + pubkey[:8])

    for line in path_config.to_toml_string():
        LOGGER.info("config [path]: %s", line)

    if not check_directory(path=path_config.data_dir,
                           human_readable_name='Data'):
        init_errors = True
    if not check_directory(path=path_config.log_dir,
                           human_readable_name='Log'):
        init_errors = True

    endpoint = validator_config.endpoint
    if endpoint is None:
        # Need to use join here to get the string "0.0.0.0". Otherwise,
        # bandit thinks we are binding to all interfaces and returns a
        # Medium security risk.
        interfaces = ["*", ".".join(["0", "0", "0", "0"])]
        interfaces += netifaces.interfaces()
        endpoint = validator_config.bind_network
        for interface in interfaces:
            if interface in validator_config.bind_network:
                LOGGER.error("Endpoint must be set when using %s", interface)
                init_errors = True
                break

    if init_errors:
        LOGGER.error("Initialization errors occurred (see previous log "
                     "ERROR messages), shutting down.")
        sys.exit(1)

    bind_network = validator_config.bind_network
    bind_component = validator_config.bind_component

    if "tcp://" not in bind_network:
        bind_network = "tcp://" + bind_network

    if "tcp://" not in bind_component:
        bind_component = "tcp://" + bind_component

    if validator_config.network_public_key is None or \
            validator_config.network_private_key is None:
        LOGGER.warning("Network key pair is not configured, Network "
                       "communications between validators will not be "
                       "authenticated or encrypted.")

    validator = Validator(bind_network,
                          bind_component,
                          endpoint,
                          validator_config.peering,
                          validator_config.seeds,
                          validator_config.peers,
                          path_config.data_dir,
                          path_config.config_dir,
                          identity_signing_key,
                          validator_config.network_public_key,
                          validator_config.network_private_key)

    # pylint: disable=broad-except
    try:
        validator.start()
    except KeyboardInterrupt:
        LOGGER.info("Initiating graceful "
                    "shutdown (press Ctrl+C again to force)")
    except LocalConfigurationError as local_config_err:
        LOGGER.error(str(local_config_err))
        sys.exit(1)
    except GenesisError as genesis_err:
        LOGGER.error(str(genesis_err))
        sys.exit(1)
    except Exception as e:
        LOGGER.exception(e)
        sys.exit(1)
    finally:
        validator.stop()

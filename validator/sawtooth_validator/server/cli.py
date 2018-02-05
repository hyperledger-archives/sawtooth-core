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
from urllib.parse import urlparse
import pkg_resources

from pyformance import MetricsRegistry
from pyformance.reporters import InfluxReporter
import netifaces

from sawtooth_validator.config.path import load_path_config
from sawtooth_validator.config.validator import load_default_validator_config
from sawtooth_validator.config.validator import load_toml_validator_config
from sawtooth_validator.config.validator import merge_validator_config
from sawtooth_validator.config.validator import ValidatorConfig
from sawtooth_validator.config.logs import get_log_config
from sawtooth_validator.server.core import Validator
from sawtooth_validator.server.keys import load_identity_signer
from sawtooth_validator.server.log import init_console_logging
from sawtooth_validator.server.log import log_configuration
from sawtooth_validator.exceptions import GenesisError
from sawtooth_validator.exceptions import LocalConfigurationError
from sawtooth_validator.metrics.wrappers import MetricsRegistryWrapper


LOGGER = logging.getLogger(__name__)
DISTRIBUTION_NAME = 'sawtooth-validator'


def parse_args(args):
    parser = argparse.ArgumentParser(
        description='Configures and starts a Sawtooth validator.',
        formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument('--config-dir',
                        help='specify the configuration directory',
                        type=str)
    parser.add_argument('-B', '--bind',
                        help='set the URL for the network or validator '
                        'component service endpoints with the format '
                        'network:<endpoint> or component:<endpoint>. '
                        'Use two --bind options to specify both '
                        'endpoints.',
                        action='append',
                        type=str)
    parser.add_argument('-P', '--peering',
                        help='determine peering type for the validator: '
                        '\'static\' (must use --peers to list peers) or '
                        '\'dynamic\' (processes any static peers first, '
                        'then starts topology buildout).',
                        choices=['static', 'dynamic'],
                        type=str)
    parser.add_argument('-E', '--endpoint',
                        help='specifies the advertised network endpoint URL',
                        type=str)
    parser.add_argument('-s', '--seeds',
                        help='provide URI(s) for the initial connection to '
                        'the validator network, in the format '
                        'tcp://<hostname>:<port>. Specify multiple URIs '
                        'in a comma-separated list. Repeating the --seeds '
                             'option is also accepted.',
                        action='append',
                        type=str)
    parser.add_argument('-p', '--peers',
                        help='list static peers to attempt to connect to '
                        'in the format tcp://<hostname>:<port>. Specify '
                        'multiple peers in a comma-separated list. '
                        'Repeating the --peers option is also accepted.',
                        action='append',
                        type=str)
    parser.add_argument('-v', '--verbose',
                        action='count',
                        default=0,
                        help='enable more verbose output to stderr')
    parser.add_argument('--scheduler',
                        choices=['serial', 'parallel'],
                        help='set scheduler type: serial or parallel')
    parser.add_argument('--network-auth',
                        choices=['trust', 'challenge'],
                        help='identify type of authorization required to join '
                             'validator network.')
    parser.add_argument('--opentsdb-url',
                        help='specify host and port for Open TSDB database \
                        used for metrics',
                        type=str)
    parser.add_argument('--opentsdb-db',
                        help='specify name of database used for storing \
                        metrics',
                        type=str)
    parser.add_argument('--minimum-peer-connectivity',
                        help='set the minimum number of peers required before \
                        stopping peer search',
                        type=int)
    parser.add_argument('--maximum-peer-connectivity',
                        help='set the maximum number of peers to accept',
                        type=int)

    try:
        version = pkg_resources.get_distribution(DISTRIBUTION_NAME).version
    except pkg_resources.DistributionNotFound:
        version = 'UNKNOWN'

    parser.add_argument(
        '-V', '--version',
        action='version',
        version=(DISTRIBUTION_NAME + ' (Hyperledger Sawtooth) version {}')
        .format(version),
        help='display version information')

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
                bind_network = bind[bind.find(":") + 1:]
            if "component" in bind:
                bind_component = bind[bind.find(":") + 1:]
    return ValidatorConfig(
        bind_network=bind_network,
        bind_component=bind_component,
        endpoint=opts.endpoint,
        peering=opts.peering,
        seeds=opts.seeds,
        peers=opts.peers,
        scheduler=opts.scheduler,
        roles=opts.network_auth,
        opentsdb_url=opts.opentsdb_url,
        opentsdb_db=opts.opentsdb_db,
        minimum_peer_connectivity=opts.minimum_peer_connectivity,
        maximum_peer_connectivity=opts.maximum_peer_connectivity
    )


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

    if opts.network_auth:
        opts.network_auth = {"network": opts.network_auth}

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
        identity_signer = load_identity_signer(
            key_dir=path_config.key_dir,
            key_name='validator')
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
                              name="validator")

    try:
        version = pkg_resources.get_distribution(DISTRIBUTION_NAME).version
    except pkg_resources.DistributionNotFound:
        version = 'UNKNOWN'
    LOGGER.info(
        '%s (Hyperledger Sawtooth) version %s', DISTRIBUTION_NAME, version)

    if LOGGER.isEnabledFor(logging.INFO):
        LOGGER.info(
            '; '.join([
                'config [path]: {}'.format(line)
                for line in path_config.to_toml_string()
            ])
        )

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

    wrapped_registry = None
    metrics_reporter = None
    if validator_config.opentsdb_url:
        LOGGER.info("Adding metrics reporter: url=%s, db=%s",
                    validator_config.opentsdb_url,
                    validator_config.opentsdb_db)

        url = urlparse(validator_config.opentsdb_url)
        proto, db_server, db_port, = url.scheme, url.hostname, url.port

        registry = MetricsRegistry()
        wrapped_registry = MetricsRegistryWrapper(registry)

        metrics_reporter = InfluxReporter(
            registry=registry,
            reporting_interval=10,
            database=validator_config.opentsdb_db,
            prefix="sawtooth_validator",
            port=db_port,
            protocol=proto,
            server=db_server,
            username=validator_config.opentsdb_username,
            password=validator_config.opentsdb_password)
        metrics_reporter.start()

    validator = Validator(
        bind_network,
        bind_component,
        endpoint,
        validator_config.peering,
        validator_config.seeds,
        validator_config.peers,
        path_config.data_dir,
        path_config.config_dir,
        identity_signer,
        validator_config.scheduler,
        validator_config.permissions,
        validator_config.minimum_peer_connectivity,
        validator_config.maximum_peer_connectivity,
        validator_config.network_public_key,
        validator_config.network_private_key,
        roles=validator_config.roles,
        metrics_registry=wrapped_registry)

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
        if metrics_reporter:
            metrics_reporter.stop()
        validator.stop()

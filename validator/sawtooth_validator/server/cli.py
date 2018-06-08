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
from sawtooth_validator.server import state_verifier
from sawtooth_validator.exceptions import GenesisError
from sawtooth_validator.exceptions import LocalConfigurationError
from sawtooth_validator import metrics


LOGGER = logging.getLogger(__name__)
DISTRIBUTION_NAME = 'sawtooth-validator'


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


def load_validator_config(first_config, config_dir):
    default_validator_config = load_default_validator_config()
    conf_file = os.path.join(config_dir, 'validator.toml')

    toml_config = load_toml_validator_config(conf_file)

    return merge_validator_config(
        configs=[first_config, toml_config, default_validator_config])


def main(args):
    try:
        path_config = load_path_config(config_dir=args['config_dir'])
    except LocalConfigurationError as local_config_err:
        LOGGER.error(str(local_config_err))
        sys.exit(1)

    try:
        opts_config = ValidatorConfig(
            bind_component=args['bind_component'],
            bind_network=args['bind_network'],
            bind_consensus=args['bind_consensus'],
            endpoint=args['endpoint'],
            maximum_peer_connectivity=args['maximum_peer_connectivity'],
            minimum_peer_connectivity=args['minimum_peer_connectivity'],
            roles=args['roles'],
            opentsdb_db=args['opentsdb_db'],
            opentsdb_url=args['opentsdb_url'],
            peering=args['peering'],
            peers=args['peers'],
            scheduler=args['scheduler'],
            seeds=args['seeds'],
        )

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
                init_console_logging(verbose_level=args['verbose'])
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
        parsed_endpoint = urlparse(validator_config.bind_network)
        for interface in interfaces:
            if interface == parsed_endpoint.hostname:
                LOGGER.error("Endpoint must be set when using %s", interface)
                init_errors = True

    if init_errors:
        LOGGER.error("Initialization errors occurred (see previous log "
                     "ERROR messages), shutting down.")
        sys.exit(1)
    bind_network = validator_config.bind_network
    bind_component = validator_config.bind_component
    bind_consensus = validator_config.bind_consensus

    if "tcp://" not in bind_network:
        bind_network = "tcp://" + bind_network

    if "tcp://" not in bind_component:
        bind_component = "tcp://" + bind_component

    if bind_consensus and "tcp://" not in bind_consensus:
        bind_consensus = "tcp://" + bind_consensus

    if validator_config.network_public_key is None or \
            validator_config.network_private_key is None:
        LOGGER.warning("Network key pair is not configured, Network "
                       "communications between validators will not be "
                       "authenticated or encrypted.")

    metrics_reporter = None
    if validator_config.opentsdb_url:
        LOGGER.info("Adding metrics reporter: url=%s, db=%s",
                    validator_config.opentsdb_url,
                    validator_config.opentsdb_db)

        url = urlparse(validator_config.opentsdb_url)
        proto, db_server, db_port, = url.scheme, url.hostname, url.port

        registry = MetricsRegistry()
        metrics.init_metrics(registry=registry)

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
    else:
        metrics.init_metrics()

    # Verify state integrity before startup
    global_state_db, blockstore = state_verifier.get_databases(
        bind_network,
        path_config.data_dir)

    state_verifier.verify_state(
        global_state_db,
        blockstore,
        bind_component,
        validator_config.scheduler)

    # Explicitly drop this, so there are not two db instances
    global_state_db.drop()
    global_state_db = None

    LOGGER.info(
        'Starting validator with %s scheduler',
        validator_config.scheduler)

    validator = Validator(
        bind_network,
        bind_component,
        bind_consensus,
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
        validator_config.state_pruning_block_depth,
        validator_config.network_public_key,
        validator_config.network_private_key,
        roles=validator_config.roles)

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

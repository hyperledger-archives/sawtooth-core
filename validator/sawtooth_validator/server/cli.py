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

from sawtooth_validator.config.path import load_path_config
from sawtooth_validator.server.core import Validator
from sawtooth_validator.server.keys import load_identity_signing_key
from sawtooth_validator.server.log import init_console_logging
from sawtooth_validator.exceptions import GenesisError
from sawtooth_validator.exceptions import LocalConfigurationError


LOGGER = logging.getLogger(__name__)


def parse_args(args):
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument('--config-dir',
                        help='Configuration directory',
                        type=str)
    parser.add_argument('--network-endpoint',
                        help='Network endpoint URL',
                        default='tcp://*:8800',
                        type=str)
    parser.add_argument('--component-endpoint',
                        help='Validator component service endpoint',
                        default='tcp://0.0.0.0:40000',
                        type=str)
    parser.add_argument('--peers',
                        help='A list of peers to attempt to connect to '
                             'in the format tcp://hostname:port',
                        nargs='+')
    parser.add_argument('-v', '--verbose',
                        action='count',
                        default=0,
                        help='Increase output sent to stderr')

    return parser.parse_args(args)


def check_directory(path, human_readable_name):
    """Verify that the directory exists and is readable and writable.

    Args:
        path (str): a directory which should exist and be writable
        human_readable_name (str): a human readable string for the directory
            which is used in logging statements

    Returns:
        bool: True if an error exists, False otherwise.
    """
    if not os.path.exists(path):
        LOGGER.error("%s directory does not exist: %s",
                     human_readable_name,
                     path)
        return True

    if not os.path.isdir(path):
        LOGGER.error("%s directory is not a directory: %s",
                     human_readable_name,
                     path)
        return True

    errors = False
    if not os.access(path, os.R_OK):
        LOGGER.error("%s directory is not readable: %s",
                     human_readable_name,
                     path)
        errors = True
    if not os.access(path, os.W_OK):
        LOGGER.error("%s directory is not writable: %s",
                     human_readable_name,
                     path)
        errors = True
    return errors


def main(args=sys.argv[1:]):
    opts = parse_args(args)
    verbose_level = opts.verbose

    init_console_logging(verbose_level=verbose_level)

    try:
        path_config = load_path_config(config_dir=opts.config_dir)
    except LocalConfigurationError as local_config_err:
        LOGGER.error(str(local_config_err))
        sys.exit(1)

    for line in path_config.to_toml_string():
        LOGGER.info("config [path]: %s", line)

    # Process initial initialization errors, delaying the sys.exit(1) until
    # all errors have been reported to the user (via LOGGER.error()).  This
    # is intended to provide enough information to the user so they can correct
    # multiple errors before restarting the validator.
    init_errors = False

    if check_directory(path=path_config.data_dir, human_readable_name='Data'):
        init_errors = True
    if check_directory(path=path_config.log_dir, human_readable_name='Log'):
        init_errors = True

    try:
        identity_signing_key = load_identity_signing_key(
            key_dir=path_config.key_dir,
            key_name='validator')
    except LocalConfigurationError as e:
        LOGGER.error(str(e))
        init_errors = True

    if init_errors:
        LOGGER.error("Initialization errors occurred (see previous log "
                     "ERROR messages), shutting down.")
        sys.exit(1)

    validator = Validator(opts.network_endpoint,
                          opts.component_endpoint,
                          opts.peers,
                          path_config.data_dir,
                          identity_signing_key)

    # pylint: disable=broad-except
    try:
        validator.start()
    except KeyboardInterrupt:
        print("Interrupted!", file=sys.stderr)
        sys.exit(1)
    except LocalConfigurationError as local_config_err:
        LOGGER.error(str(local_config_err))
        sys.exit(1)
    except GenesisError as genesis_err:
        LOGGER.error(str(genesis_err))
        sys.exit(1)
    except Exception as e:
        LOGGER.exception(e)
        sys.exit(1)

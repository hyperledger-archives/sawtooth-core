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

from sawtooth_validator.server.core import Validator
from sawtooth_validator.server.log import init_console_logging
from sawtooth_validator.exceptions import GenesisError
from sawtooth_validator.exceptions import LocalConfigurationError


LOGGER = logging.getLogger(__name__)


def parse_args(args):
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter)

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


def ensure_directory(sawtooth_home_path, posix_fallback_path):
    """Ensures the one of the given sets of directories exists.

    The directory in sawtooth_home_path is ensured to exist, if `SAWTOOTH_HOME`
    exists. If the host operating system is windows, `SAWTOOTH_HOME` is
    defaulted to `C:\\Program Files (x86)\\Intel\\sawtooth-validator`,
    Otherwise, the given posix fallback path is ensured to exist.

    Args:
        sawtooth_home_dirs (str): Subdirectory of `SAWTOOTH_HOME`.
        posix_fallback_dir (str): Fallback directory path if `SAWTOOTH_HOME` is
            unset on posix host system.

    Returns:
        str: The path determined to exist.
    """
    if 'SAWTOOTH_HOME' in os.environ:
        sawtooth_home_dirs = sawtooth_home_path.split('/')
        sawtooth_dir = os.path.join(os.environ['SAWTOOTH_HOME'],
                                    *sawtooth_home_dirs)
    elif os.name == 'nt':
        default_win_home = \
            'C:\\Program Files (x86)\\Intel\\sawtooth-validator\\'
        sawtooth_home_dirs = sawtooth_home_path.split('/')
        sawtooth_dir = os.path.join(default_win_home, *sawtooth_home_dirs)
    else:
        sawtooth_dir = posix_fallback_path

    if not os.path.exists(sawtooth_dir):
        try:
            os.makedirs(sawtooth_dir, exist_ok=True)
        except OSError as e:
            print('Unable to create {}: {}'.format(sawtooth_dir, e),
                  file=sys.stderr)
            sys.exit(1)

    return sawtooth_dir


def main(args=sys.argv[1:]):
    opts = parse_args(args)
    verbose_level = opts.verbose

    init_console_logging(verbose_level=verbose_level)

    data_dir = ensure_directory('data', '/var/lib/sawtooth')
    key_dir = ensure_directory('etc/keys', '/etc/sawtooth/keys')

    validator = Validator(opts.network_endpoint,
                          opts.component_endpoint,
                          opts.peers,
                          data_dir,
                          key_dir)

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

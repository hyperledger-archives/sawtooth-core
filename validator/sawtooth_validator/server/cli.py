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

import sys
import argparse

from sawtooth_validator.server.core import Validator
from sawtooth_validator.server.log import init_console_logging
from sawtooth_validator.exceptions import GenesisError
from sawtooth_validator.exceptions import LocalConfigurationError


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


def main(args=sys.argv[1:]):
    opts = parse_args(args)
    verbose_level = opts.verbose

    init_console_logging(verbose_level=verbose_level)

    validator = Validator(opts.network_endpoint,
                          opts.component_endpoint,
                          opts.peers)

    try:
        validator.start()
    except KeyboardInterrupt:
        print("Interrupted!", file=sys.stderr)
    except LocalConfigurationError as local_config_err:
        print(local_config_err, file=sys.stderr)
    except GenesisError as genesis_err:
        print(genesis_err, file=sys.stderr)
    finally:
        validator.stop()

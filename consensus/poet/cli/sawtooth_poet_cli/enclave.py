# Copyright 2017 Intel Corporation
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

from sawtooth_poet_cli import config
from sawtooth_poet_cli.poet_enclave_module_wrapper import \
    PoetEnclaveModuleWrapper


def add_enclave_parser(subparsers):
    """Add argument parser arguments for the `poet enclave` sub-command.
    """
    description = 'Generates enclave setup information'

    parser = subparsers.add_parser(
        'enclave',
        help=description,
        description=description + '.')

    parser.add_argument(
        '--enclave-module',
        default='simulator',
        choices=['simulator', 'sgx'],
        type=str,
        help='identify the enclave module to query')
    parser.add_argument(
        'characteristic',
        choices=['measurement', 'basename'],
        type=str,
        help='enclave characteristic to retrieve')


def do_enclave(args):
    """Executes the `poet enclave` sub-command.

    This command reads the appropriate characteristic from the enclave.  The
    available characteristics are:
    measurement - the enclave measurement (also know as mr_enclave)
    basename - the enclave basename

    The resulting characteristic value is printed to stdout
    """
    with PoetEnclaveModuleWrapper(
            enclave_module=args.enclave_module,
            config_dir=config.get_config_dir(),
            data_dir=config.get_data_dir()) as poet_enclave_module:
        if args.characteristic == 'measurement':
            print(poet_enclave_module.get_enclave_measurement())
        elif args.characteristic == 'basename':
            print(poet_enclave_module.get_enclave_basename())
        else:
            AssertionError(
                'Unknown enclave characteristic type: {}'.format(args.type))

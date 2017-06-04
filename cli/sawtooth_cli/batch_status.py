# Copyright 2017 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the 'License');
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

from sys import maxsize

from sawtooth_cli import format_utils as fmt
from sawtooth_cli.rest_client import RestClient
from sawtooth_cli.parent_parsers import base_http_parser


def add_batch_status_parser(subparsers, parent_parser):
    """Adds arguments parsers for the batch-status commands

        Args:
            subparsers: Add parsers to this subparser object
            parent_parser: The parent argparse.ArgumentParser object
    """
    epilog = '''details:
        Fetches the statuses for a set of batches.
    '''
    parser = subparsers.add_parser(
        'batch-status', epilog=epilog,
        parents=[base_http_parser(), parent_parser])

    parser.add_argument(
        '--wait',
        nargs='?',
        const=maxsize,
        type=int,
        help='a time in seconds to wait for commit')

    parser.add_argument(
        'batch_ids',
        type=str,
        help='a comma-separated list of batch ids')

    parser.add_argument(
        '-F', '--format',
        action='store',
        default='yaml',
        choices=['yaml', 'json'],
        help='the format to use for printing the output (defaults to yaml)')


def do_batch_status(args):
    """Runs the batch-status command, printing output to the console

        Args:
            args: The parsed arguments sent to the command at runtime
    """
    rest_client = RestClient(args.url, args.user)
    batch_ids = args.batch_ids.split(',')

    if args.wait and args.wait > 0:
        statuses = rest_client.get_statuses(batch_ids, args.wait)
    else:
        statuses = rest_client.get_statuses(batch_ids)

    if args.format == 'yaml':
        fmt.print_yaml(statuses)
    elif args.format == 'json':
        fmt.print_json(statuses)
    else:
        raise AssertionError('Missing handler: {}'.format(args.format))

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

import argparse
from base64 import b64decode
from sawtooth_cli import format_utils as fmt
from sawtooth_cli.rest_client import RestClient
from sawtooth_cli.exceptions import CliException
from sawtooth_cli.parent_parsers import base_http_parser
from sawtooth_cli.parent_parsers import base_list_parser


def add_state_parser(subparsers, parent_parser):
    """Adds arguments parsers for the state list and state show commands

        Args:
            subparsers: Add parsers to this subparser object
            parent_parser: The parent argparse.ArgumentParser object
    """
    parser = subparsers.add_parser(
        'state',
        help='Displays information on the entries in state',
        description='Provides subcommands to display information about the '
        'state entries in the current blockchain state.')

    grand_parsers = parser.add_subparsers(
        title='subcommands',
        dest='subcommand')

    grand_parsers.required = True

    list_parser = grand_parsers.add_parser(
        'list',
        description='Lists all state entries in the current blockchain.',
        parents=[base_http_parser(), base_list_parser()],
        formatter_class=argparse.RawDescriptionHelpFormatter)

    list_parser.add_argument(
        'subtree',
        type=str,
        nargs='?',
        default=None,
        help='address of a subtree to filter the list by')

    list_parser.add_argument(
        '--head',
        action='store',
        default=None,
        help='specify the id of the block to set as the chain head')

    show_parser = grand_parsers.add_parser(
        'show',
        description='Displays information for the specified state address in '
        'the current blockchain.',
        parents=[base_http_parser()],
        formatter_class=argparse.RawDescriptionHelpFormatter)

    show_parser.add_argument(
        'address',
        type=str,
        help='address of the leaf')

    show_parser.add_argument(
        '--head',
        action='store',
        default=None,
        help='specify the id of the block to set as the chain head')


def do_state(args):
    """Runs the batch list or batch show command, printing output to the
    console

        Args:
            args: The parsed arguments sent to the command at runtime
    """
    rest_client = RestClient(args.url, args.user)

    if args.subcommand == 'list':
        response = rest_client.list_state(args.subtree, args.head)
        leaves = response['data']
        head = response['head']
        keys = ('address', 'size', 'data')
        headers = tuple(k.upper() for k in keys)

        def parse_leaf_row(leaf, decode=True):
            decoded = b64decode(leaf['data'])
            return (
                leaf['address'],
                len(decoded),
                str(decoded) if decode else leaf['data'])

        if args.format == 'default':
            fmt.print_terminal_table(headers, leaves, parse_leaf_row)
            print('HEAD BLOCK: "{}"'.format(head))

        elif args.format == 'csv':
            fmt.print_csv(headers, leaves, parse_leaf_row)
            print('(data for head block: "{}")'.format(head))

        elif args.format == 'json' or args.format == 'yaml':
            state_data = {
                'head': head,
                'data': [{k: d for k, d in zip(keys, parse_leaf_row(l, False))}
                         for l in leaves]}

            if args.format == 'yaml':
                fmt.print_yaml(state_data)
            elif args.format == 'json':
                fmt.print_json(state_data)
            else:
                raise AssertionError('Missing handler: {}'.format(args.format))

        else:
            raise AssertionError('Missing handler: {}'.format(args.format))

    if args.subcommand == 'show':
        output = rest_client.get_leaf(args.address, args.head)
        if output is not None:
            print('DATA: "{}"'.format(b64decode(output['data'])))
            print('HEAD: "{}"'.format(output['head']))
        else:
            raise CliException('No data available at {}'.format(args.address))

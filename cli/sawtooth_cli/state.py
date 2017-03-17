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

import sys
from base64 import b64decode

import csv
import json
import yaml

from sawtooth_cli import tty
from sawtooth_cli.rest_client import RestClient
from sawtooth_cli.exceptions import CliException


def add_state_parser(subparsers, parent_parser):
    """Adds arguments parsers for the batch list and batch show commands

        Args:
            subparsers: Add parsers to this subparser object
            parent_parser: The parent argparse.ArgumentParser object
    """
    parser = subparsers.add_parser('state')

    grand_parsers = parser.add_subparsers(title='grandchildcommands',
                                          dest='subcommand')
    grand_parsers.required = True
    epilog = '''details:
        Lists state in the form of leaves from the merkle tree. List can be
    narrowed using the address of a subtree.
    '''

    list_parser = grand_parsers.add_parser('list', epilog=epilog)
    list_parser.add_argument(
        'subtree',
        type=str,
        nargs='?',
        default=None,
        help='the address of a subtree to filter list by')
    list_parser.add_argument(
        '--url',
        type=str,
        help="the URL of the validator's REST API")
    list_parser.add_argument(
        '--head',
        action='store',
        default=None,
        help='the id of the block to set as the chain head')
    list_parser.add_argument(
        '-F', '--format',
        action='store',
        default='default',
        choices=['csv', 'json', 'yaml', 'default'],
        help='the format of the output, options: csv, json or yaml')

    epilog = '''details:
        Shows the data for a single leaf on the merkle tree.
    '''
    show_parser = grand_parsers.add_parser('show', epilog=epilog)
    show_parser.add_argument(
        'address',
        type=str,
        help='the address of the leaf')
    show_parser.add_argument(
        '--url',
        type=str,
        help="the URL of the validator's REST API")
    show_parser.add_argument(
        '--head',
        action='store',
        default=None,
        help='the id of the block to set as the chain head')


def do_state(args):
    """Runs the batch list or batch show command, printing output to the console

        Args:
            args: The parsed arguments sent to the command at runtime
    """
    rest_client = RestClient(args.url)

    def print_json(data):
        print(json.dumps(
            data,
            indent=2,
            separators=(',', ': '),
            sort_keys=True))

    def print_yaml(data):
        print(yaml.dump(data, default_flow_style=False)[0:-1])

    if args.subcommand == 'list':
        response = rest_client.list_state(args.subtree, args.head)
        leaves = response['data']
        head = response['head']
        keys = ('address', 'size', 'data')
        headers = (k.upper() for k in keys)

        def get_leaf_data(leaf, decode=True):
            decoded = b64decode(leaf['data'])
            return (
                leaf['address'],
                len(decoded),
                str(decoded) if decode else leaf['data'])

        if args.format == 'default':
            # Set column widths based on window and data size
            window_width = tty.width()

            try:
                addr_width = len(leaves[0]['address'])
                data_width = len(str(b64decode(leaves[0]['data'])))
            except IndexError:
                # if no data was returned, use short default widths
                addr_width = 30
                data_width = 15

            if sys.stdout.isatty():
                adjusted = int(window_width) - addr_width - 11
                adjusted = 6 if adjusted < 6 else adjusted
            else:
                adjusted = data_width

            fmt_string = '{{:{a}.{a}}}  {{:<4}}  {{:{j}.{j}}}'\
                .format(a=addr_width, j=adjusted)

            # Print data in rows and columns
            print(fmt_string.format(*headers))
            for leaf in leaves:
                print(fmt_string.format(*get_leaf_data(leaf)) +
                      ('...' if adjusted < data_width and data_width else ''))
            print('HEAD BLOCK: "{}"'.format(head))

        elif args.format == 'csv':
            try:
                writer = csv.writer(sys.stdout)
                writer.writerow(headers)
                for leaf in leaves:
                    writer.writerow(get_leaf_data(leaf))
            except csv.Error as e:
                raise CliException('Error writing CSV: {}'.format(e))
            print('(data for head block: "{}")'.format(head))

        elif args.format == 'json' or args.format == 'yaml':
            state_data = {
                'head': head,
                'data': [{k: d for k, d in
                         zip(keys, get_leaf_data(l, False))}
                         for l in leaves]}

            if args.format == 'yaml':
                print_yaml(state_data)
            elif args.format == 'json':
                print_json(state_data)
            else:
                raise AssertionError('Missing handler: {}'.format(args.format))

        else:
            raise AssertionError('Missing handler: {}'.format(args.format))

    if args.subcommand == 'show':
        leaf = rest_client.get_leaf(args.address, args.head)
        if leaf is not None:
            print('DATA: "{}"'.format(b64decode(leaf['data'])))
            print('HEAD: "{}"'.format(leaf['head']))
        else:
            raise CliException('No data available at {}'.format(args.address))

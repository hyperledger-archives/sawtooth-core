# Copyright 2016 Intel Corporation
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

from sawtooth_cli.rest_client import RestClient
from sawtooth_cli.exceptions import CliException


def add_state_parser(subparsers, parent_parser):
    parser = subparsers.add_parser('state')

    grand_parsers = parser.add_subparsers(title='grandchildcommands',
                                          dest='subcommand')

    epilog = '''
    details:
        Lists leaves on the merkle tree, storing state. List can be
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
        '--format',
        action='store',
        default='default',
        help='the format of the output, options: csv, json or yaml')

    epilog = '''
    details:
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
        max_data_width = 15
        format_string = '{{:{addr}.{addr}}} {{:<4}} {{!s:.{data}}}'.format(
            addr=len(leaves[0]['address']) if len(leaves) > 0 else 30,
            data=max_data_width)

        def get_leaf_data(leaf, use_decoded=True):
            data = leaf['data']
            decoded_data = b64decode(data)
            return (
                leaf['address'],
                len(decoded_data),
                decoded_data if use_decoded else data)

        if args.format == 'default':
            print(format_string.format(*headers))
            for leaf in leaves:
                print_string = format_string.format(*get_leaf_data(leaf))
                if len(str(leaf['data'])) > max_data_width:
                    print_string += '...'
                print(print_string)
            print('HEAD BLOCK: "{}"'.format(head))

        elif args.format == 'csv':
            try:
                writer = csv.writer(sys.stdout)
                writer.writerow(headers)
                for leaf in leaves:
                    writer.writerow(get_leaf_data(leaf))
            except csv.Error:
                raise CliException('Error writing CSV.')
            print('(data for head block: "{}")'.format(head))

        elif args.format == 'json' or args.format == 'yaml':
            state_data = {
                'head': head,
                'data': list(map(
                    lambda b: dict(zip(keys, get_leaf_data(b, False))),
                    leaves))}

            if args.format == 'json':
                print_json(state_data)
            else:
                print_yaml(state_data)

        else:
            raise CliException('Unknown format: {}'.format(args.format))

    if args.subcommand == 'show':
        leaf = rest_client.get_leaf(args.address, args.head)
        print('DATA: "{}"'.format(b64decode(leaf['data'])))
        print('HEAD: "{}"'.format(leaf['head']))

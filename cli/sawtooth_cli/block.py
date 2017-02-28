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
from functools import reduce

import csv
import json
import yaml

from sawtooth_cli.rest_client import RestClient
from sawtooth_cli.exceptions import CliException


def add_block_parser(subparsers, parent_parser):
    parser = subparsers.add_parser('block')

    grand_parsers = parser.add_subparsers(title='grandchildcommands',
                                          dest='subcommand')

    epilog = '''
    details:
        Lists committed blocks from the newest to the oldest, including
    their id (i.e. header signature), batch and transaction count, and
    their signer's public key.
    '''

    list_parser = grand_parsers.add_parser('list', epilog=epilog)
    list_parser.add_argument(
        '--url',
        type=str,
        help="the URL of the validator's REST API")
    list_parser.add_argument(
        '--format',
        action='store',
        default='default',
        help='the format of the output, options: csv, json or yaml')

    epilog = '''
    details:
        Shows the data for a single block, or for a particular property within
    that block or its header. Displays data in YAML (default), or JSON formats.
    '''
    show_parser = grand_parsers.add_parser('show', epilog=epilog)
    show_parser.add_argument(
        'block_id',
        type=str,
        help='the id (i.e. header_signature) of the block')
    show_parser.add_argument(
        '-k', '--key',
        type=str,
        help='specficy to show a single property from the block or header')
    show_parser.add_argument(
        '--url',
        type=str,
        help="the URL of the validator's REST API")
    show_parser.add_argument(
        '--format',
        action='store',
        default='yaml',
        help='the format of the output, options: yaml (default), or json')


def do_block(args):
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
        blocks = rest_client.list_blocks()
        keys = ('num', 'block_id', 'batches', 'txns', 'signer')
        headers = (k.upper() if k != 'batches' else 'BATS' for k in keys)

        def get_block_data(block):
            batches = block.get('batches', [])
            txn_count = reduce(
                lambda t, b: t + len(b.get('transactions', [])),
                batches,
                0)

            return (
                block['header'].get('block_num', 0),
                block['header_signature'],
                len(batches),
                txn_count,
                block['header']['signer_pubkey']
            )

        if args.format == 'default':
            # Fit within 150 chars, without truncating block id
            print('{:<3}  {:128.128}  {:<4}  {:<4}  {:11.11}'.format(*headers))
            for block in blocks:
                print('{:<3}  {:128.128}  {:<4}  {:<4}  {:8.8}...'.format(
                    *get_block_data(block)))

        elif args.format == 'csv':
            try:
                writer = csv.writer(sys.stdout)
                writer.writerow(headers)
                for block in blocks:
                    writer.writerow(get_block_data(block))
            except csv.Error:
                raise CliException('Error writing CSV.')

        elif args.format == 'json' or args.format == 'yaml':
            block_data = list(map(
                lambda b: dict(zip(keys, get_block_data(b))),
                blocks
            ))

            if args.format == 'json':
                print_json(block_data)
            else:
                print_yaml(block_data)

        else:
            raise CliException('unknown format: {}'.format(args.format))

    if args.subcommand == 'show':
        block = rest_client.get_block(args.block_id)

        if args.key:
            if args.key in block:
                print(block[args.key])
            elif args.key in block['header']:
                print(block['header'][args.key])
            else:
                raise CliException(
                    'key "{}" not found in block or header'.format(args.key))
        else:
            if args.format == 'yaml':
                print_yaml(block)
            elif args.format == 'json':
                print_json(block)
            else:
                raise CliException('unknown format: {}'.format(args.format))

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
import csv
import json
import yaml

from sawtooth_cli import tty
from sawtooth_cli.rest_client import RestClient
from sawtooth_cli.exceptions import CliException


def add_block_parser(subparsers, parent_parser):
    """Adds arguments parsers for the batch list and batch show commands

        Args:
            subparsers: Add parsers to this subparser object
            parent_parser: The parent argparse.ArgumentParser object
    """
    parser = subparsers.add_parser('block')

    grand_parsers = parser.add_subparsers(title='grandchildcommands',
                                          dest='subcommand')
    grand_parsers.required = True
    epilog = '''details:
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
        '-F', '--format',
        action='store',
        default='default',
        choices=['csv', 'json', 'yaml', 'default'],
        help='the format of the output, options: csv, json or yaml')

    epilog = '''details:
        Shows the data for a single block, or for a particular property within
    that block or its header. Displays data in YAML (default), or JSON formats.
    '''
    show_parser = grand_parsers.add_parser('show', epilog=epilog)
    show_parser.add_argument(
        'block_id',
        type=str,
        help='the id (i.e. header_signature) of the block')
    show_parser.add_argument(
        '--url',
        type=str,
        help="the URL of the validator's REST API")
    show_parser.add_argument(
        '-k', '--key',
        type=str,
        help='specify to show a single property from the block or header')
    show_parser.add_argument(
        '-F', '--format',
        action='store',
        default='yaml',
        choices=['yaml', 'json'],
        help='the format of the output, options: yaml (default), or json')


def do_block(args):
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
        blocks = rest_client.list_blocks()
        keys = ('num', 'block_id', 'batches', 'txns', 'signer')
        headers = (k.upper() if k != 'batches' else 'BATS' for k in keys)

        def get_data(block):
            batches = block.get('batches', [])
            txns = [t for b in batches for t in b['transactions']]
            return (
                block['header'].get('block_num', 0),
                block['header_signature'],
                len(batches),
                len(txns),
                block['header']['signer_pubkey'])

        if args.format == 'default':
            # Set column widths based on window and data size
            window_width = tty.width()

            try:
                id_width = len(blocks[0]['header_signature'])
                sign_width = len(blocks[0]['header']['signer_pubkey'])
            except IndexError:
                # if no data was returned, use short default widths
                id_width = 30
                sign_width = 15

            if sys.stdout.isatty():
                adjusted = int(window_width) - id_width - 22
                adjusted = 6 if adjusted < 6 else adjusted
            else:
                adjusted = sign_width

            fmts = '{{:<3}}  {{:{i}.{i}}}  {{:<4}}  {{:<4}}  {{:{a}.{a}}}'\
                .format(i=id_width, a=adjusted)

            # Print data in rows and columns
            print(fmts.format(*headers))
            for block in blocks:
                print(fmts.format(*get_data(block)) +
                      ('...' if adjusted < sign_width and sign_width else ''))

        elif args.format == 'csv':
            try:
                writer = csv.writer(sys.stdout)
                writer.writerow(headers)
                for block in blocks:
                    writer.writerow(get_data(block))
            except csv.Error as e:
                raise CliException('Error writing CSV: {}'.format(e))

        elif args.format == 'json' or args.format == 'yaml':
            data = [{k: d for k, d in zip(keys, get_data(b))} for b in blocks]

            if args.format == 'yaml':
                print_yaml(data)
            elif args.format == 'json':
                print_json(data)
            else:
                raise AssertionError('Missing handler: {}'.format(args.format))

        else:
            raise AssertionError('Missing handler: {}'.format(args.format))

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
                raise AssertionError('Missing handler: {}'.format(args.format))

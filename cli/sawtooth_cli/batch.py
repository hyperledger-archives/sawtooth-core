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


def add_batch_parser(subparsers, parent_parser):
    """Adds arguments parsers for the batch list and batch show commands

        Args:
            subparsers: Add parsers to this subparser object
            parent_parser: The parent argparse.ArgumentParser object
    """
    parser = subparsers.add_parser('batch')

    grand_parsers = parser.add_subparsers(title='grandchildcommands',
                                          dest='subcommand')
    grand_parsers.required = True
    epilog = '''details:
        Lists committed batches from newest to oldest, including their id (i.e.
    header signature), transaction count, and their signer's public key.
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
        Shows the data for a single batch, or for a particular property within
    that batch or its header. Displays data in YAML (default), or JSON formats.
    '''
    show_parser = grand_parsers.add_parser('show', epilog=epilog)
    show_parser.add_argument(
        'batch_id',
        type=str,
        help='the id (i.e. header_signature) of the batch')
    show_parser.add_argument(
        '--url',
        type=str,
        help="the URL of the validator's REST API")
    show_parser.add_argument(
        '-k', '--key',
        type=str,
        help='specify to show a single property from the batch or header')
    show_parser.add_argument(
        '-F', '--format',
        action='store',
        default='yaml',
        choices=['yaml', 'json'],
        help='the format of the output, options: yaml (default), or json')


def do_batch(args):
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
        batches = rest_client.list_batches()
        keys = ('batch_id', 'txns', 'signer')
        headers = (k.upper() for k in keys)

        def get_data(batch):
            return (
                batch['header_signature'],
                len(batch.get('transactions', [])),
                batch['header']['signer_pubkey'])

        if args.format == 'default':
            # Set column widths based on window and data size
            window_width = tty.width()

            try:
                id_width = len(batches[0]['header_signature'])
                sign_width = len(batches[0]['header']['signer_pubkey'])
            except IndexError:
                # if no data was returned, use short default widths
                id_width = 30
                sign_width = 15

            if sys.stdout.isatty():
                adjusted = int(window_width) - id_width - 11
                adjusted = 6 if adjusted < 6 else adjusted
            else:
                adjusted = sign_width

            fmt_string = '{{:{i}.{i}}}  {{:<4}}  {{:{a}.{a}}}'\
                .format(i=id_width, a=adjusted)

            # Print data in rows and columns
            print(fmt_string.format(*headers))
            for batch in batches:
                print(fmt_string.format(*get_data(batch)) +
                      ('...' if adjusted < sign_width and sign_width else ''))

        elif args.format == 'csv':
            try:
                writer = csv.writer(sys.stdout)
                writer.writerow(headers)
                for batch in batches:
                    writer.writerow(get_data(batch))
            except csv.Error as e:
                raise CliException('Error writing CSV: {}'.format(e))

        elif args.format == 'json' or args.format == 'yaml':
            data = [{k: d for k, d in zip(keys, get_data(b))} for b in batches]

            if args.format == 'yaml':
                print_yaml(data)
            elif args.format == 'json':
                print_json(data)
            else:
                raise AssertionError('Missing handler: {}'.format(args.format))

        else:
            raise AssertionError('Missing handler: {}'.format(args.format))

    if args.subcommand == 'show':
        batch = rest_client.get_batch(args.batch_id)

        if args.key:
            if args.key in batch:
                print(batch[args.key])
            elif args.key in batch['header']:
                print(batch['header'][args.key])
            else:
                raise CliException(
                    'key "{}" not found in batch or header'.format(args.key))
        else:
            if args.format == 'yaml':
                print_yaml(batch)
            elif args.format == 'json':
                print_json(batch)
            else:
                raise AssertionError('Missing handler: {}'.format(args.format))

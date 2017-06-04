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
from sawtooth_cli.parent_parsers import base_show_parser


def add_transaction_parser(subparsers, parent_parser):
    """Adds argument parsers for the transaction list and show commands

        Args:
            subparsers: Add parsers to this subparser object
            parent_parser: The parent argparse.ArgumentParser object
    """
    parser = subparsers.add_parser('transaction')

    grand_parsers = parser.add_subparsers(title='grandchildcommands',
                                          dest='subcommand')
    grand_parsers.required = True

    epilog = '''details:
        Lists committed transactions from newest to oldest, including their id
    (i.e. header_signature), transaction family and version, and their payload.
    '''
    grand_parsers.add_parser(
        'list', epilog=epilog,
        parents=[base_http_parser(), base_list_parser()],
        formatter_class=argparse.RawDescriptionHelpFormatter)

    epilog = '''details:
        Shows the data for a single transaction, or for a particular property
    within that transaction or its header. Displays data in YAML (default),
    or JSON formats.
    '''
    show_parser = grand_parsers.add_parser(
        'show', epilog=epilog,
        parents=[base_http_parser(), base_show_parser()],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    show_parser.add_argument(
        'transaction_id',
        type=str,
        help='the id (i.e. header_signature) of the transaction')


def do_transaction(args):
    """Runs the transaction list or show command, printing to the console

        Args:
            args: The parsed arguments sent to the command at runtime
    """
    rest_client = RestClient(args.url, args.user)

    if args.subcommand == 'list':
        transactions = rest_client.list_transactions()
        keys = ('transaction_id', 'family', 'version', 'size', 'payload')
        headers = tuple(k.upper() if k != 'version' else 'VERS' for k in keys)

        def parse_txn_row(transaction, decode=True):
            decoded = b64decode(transaction['payload'])
            return (
                transaction['header_signature'],
                transaction['header']['family_name'],
                transaction['header']['family_version'],
                len(decoded),
                str(decoded) if decode else transaction['payload'])

        if args.format == 'default':
            fmt.print_terminal_table(headers, transactions, parse_txn_row)

        elif args.format == 'csv':
            fmt.print_csv(headers, transactions, parse_txn_row)

        elif args.format == 'json' or args.format == 'yaml':
            data = [{k: d for k, d in zip(keys, parse_txn_row(b, False))}
                    for b in transactions]

            if args.format == 'yaml':
                fmt.print_yaml(data)
            elif args.format == 'json':
                fmt.print_json(data)
            else:
                raise AssertionError('Missing handler: {}'.format(args.format))

        else:
            raise AssertionError('Missing handler: {}'.format(args.format))

    if args.subcommand == 'show':
        output = rest_client.get_transaction(args.transaction_id)

        if args.key:
            if args.key == 'payload':
                output = b64decode(output['payload'])
            elif args.key in output:
                output = output[args.key]
            elif args.key in output['header']:
                output = output['header'][args.key]
            else:
                raise CliException(
                    'Key "{}" not found in transaction or header'.format(
                        args.key))

        if args.format == 'yaml':
            fmt.print_yaml(output)
        elif args.format == 'json':
            fmt.print_json(output)
        else:
            raise AssertionError('Missing handler: {}'.format(args.format))

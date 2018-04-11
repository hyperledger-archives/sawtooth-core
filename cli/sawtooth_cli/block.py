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
from sawtooth_cli import format_utils as fmt
from sawtooth_cli.rest_client import RestClient
from sawtooth_cli.exceptions import CliException
from sawtooth_cli.parent_parsers import base_http_parser
from sawtooth_cli.parent_parsers import base_list_parser
from sawtooth_cli.parent_parsers import base_show_parser


def add_block_parser(subparsers, parent_parser):
    """Adds arguments parsers for the block list and block show commands

        Args:
            subparsers: Add parsers to this subparser object
            parent_parser: The parent argparse.ArgumentParser object
    """
    parser = subparsers.add_parser(
        'block',
        description='Provides subcommands to display information about the '
        'blocks in the current blockchain.',
        help='Displays information on blocks in the current blockchain')

    grand_parsers = parser.add_subparsers(
        title='subcommands',
        dest='subcommand')

    grand_parsers.required = True

    description = (
        'Displays information for all blocks on the current '
        'blockchain, including the block id and number, public keys all '
        'of allsigners, and number of transactions and batches.')

    list_parser = grand_parsers.add_parser(
        'list',
        help='Displays information for all blocks on the current blockchain',
        description=description,
        parents=[base_http_parser(), base_list_parser()],
        formatter_class=argparse.RawDescriptionHelpFormatter)

    list_parser.add_argument(
        '-n',
        '--count',
        default=100,
        type=int,
        help='the number of blocks to list',
    )

    description = (
        'Displays information about the specified block on '
        'the current blockchain')

    show_parser = grand_parsers.add_parser(
        'show',
        help=description,
        description=description + '.',
        parents=[base_http_parser(), base_show_parser()],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    show_parser.add_argument(
        'block_id',
        type=str,
        help='id (header_signature) of the block')


def do_block(args):
    """Runs the block list or block show command, printing output to the
    console

        Args:
            args: The parsed arguments sent to the command at runtime
    """
    rest_client = RestClient(args.url, args.user)

    if args.subcommand == 'list':
        block_generator = rest_client.list_blocks()
        blocks = []
        left = args.count
        for block in block_generator:
            blocks.append(block)
            left -= 1
            if left <= 0:
                break

        keys = ('num', 'block_id', 'batches', 'txns', 'signer')
        headers = tuple(k.upper() if k != 'batches' else 'BATS' for k in keys)

        def parse_block_row(block):
            batches = block.get('batches', [])
            txns = [t for b in batches for t in b['transactions']]
            return (
                block['header'].get('block_num', 0),
                block['header_signature'],
                len(batches),
                len(txns),
                block['header']['signer_public_key'])

        if args.format == 'default':
            fmt.print_terminal_table(headers, blocks, parse_block_row)

        elif args.format == 'csv':
            fmt.print_csv(headers, blocks, parse_block_row)

        elif args.format == 'json' or args.format == 'yaml':
            data = [{k: d for k, d in zip(keys, parse_block_row(b))}
                    for b in blocks]

            if args.format == 'yaml':
                fmt.print_yaml(data)
            elif args.format == 'json':
                fmt.print_json(data)
            else:
                raise AssertionError('Missing handler: {}'.format(args.format))

        else:
            raise AssertionError('Missing handler: {}'.format(args.format))

    if args.subcommand == 'show':
        output = rest_client.get_block(args.block_id)

        if args.key:
            if args.key in output:
                output = output[args.key]
            elif args.key in output['header']:
                output = output['header'][args.key]
            else:
                raise CliException(
                    'key "{}" not found in block or header'.format(args.key))

        if args.format == 'yaml':
            fmt.print_yaml(output)
        elif args.format == 'json':
            fmt.print_json(output)
        else:
            raise AssertionError('Missing handler: {}'.format(args.format))

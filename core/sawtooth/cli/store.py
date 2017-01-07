# Copyright 2016 Intel Corporation
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

from __future__ import print_function

from gossip.common import pretty_print_dict

from sawtooth.client import SawtoothClient

from sawtooth.exceptions import MessageException

from sawtooth.cli.exceptions import CliException


def add_store_parser(subparsers, parent_parser):
    parser = subparsers.add_parser('store')

    grand_parsers = parser.add_subparsers(title='grandchildcommands',
                                          dest='subcommand')
    list_parser = grand_parsers.add_parser('list')
    list_parser.add_argument(
        '--url',
        type=str,
        help='the URL to the validator')

    show_parser = grand_parsers.add_parser('show')
    show_parser.add_argument(
        'transactionTypeName',
        type=str,
        help='the name of the transaction type')
    show_parser.add_argument(
        '-k', '--key',
        type=str,
        help='the key within the store')
    show_parser.add_argument(
        '--blockID',
        type=str,
        help='the id of the block')
    show_parser.add_argument(
        '--incremental',
        action='store_true',
        help='incremental')
    show_parser.add_argument(
        '--url',
        type=str,
        help='the URL to the validator')


def do_store(args):
    subcommands = ['list', 'show']

    if args.subcommand not in subcommands:
        print('Unknown sub-command, expecting one of {0}'.format(
            subcommands))
        return

    if args.url is not None:
        url = args.url
    else:
        url = 'http://localhost:8800'

    web_client = SawtoothClient(url)

    try:
        if args.subcommand == 'list':
            transaction_type_name = web_client.get_store_list()
            print(pretty_print_dict(transaction_type_name))
            return
        elif args.subcommand == 'show':
            store_info = \
                web_client.get_store_by_name(
                    txn_type_or_name=args.transactionTypeName,
                    key=args.key,
                    block_id=args.blockID,
                    delta=args.incremental)
            print(pretty_print_dict(store_info))
            return

    except MessageException as e:
        raise CliException(e)

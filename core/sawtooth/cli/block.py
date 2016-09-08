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


from gossip.common import pretty_print_dict

from sawtooth.client import LedgerWebClient
from sawtooth.exceptions import MessageException

from sawtooth.cli.exceptions import CliException


def add_block_parser(subparsers, parent_parser):
    parser = subparsers.add_parser('block')

    grand_parsers = parser.add_subparsers(title='grandchildcommands',
                                          dest='subcommand')

    epilog = '''
    details:
      list the committed block IDs from the newest to the oldest.
    '''

    list_parser = grand_parsers.add_parser('list', epilog=epilog)
    list_parser.add_argument(
        '--url',
        type=str,
        help='the URL to the validator')
    list_parser.add_argument(
        '--blockcount',
        type=int,
        default=10,
        help='list the maximum number of committed block IDs. Default: 10')
    list_parser.add_argument(
        '-a', '--all',
        action='store_true',
        help='list all of committed block IDs')

    epilog = '''
    details:
      show the contents of block or the value associated with key
      within the block.
    '''
    show_parser = grand_parsers.add_parser('show', epilog=epilog)
    show_parser.add_argument(
        'blockID',
        type=str,
        help='the id of the block')
    show_parser.add_argument(
        '-k', '--key',
        type=str,
        help='the key within the block')
    show_parser.add_argument(
        '--url',
        type=str,
        help='the URL to the validator')


def do_block(args):
    subcommands = ['list', 'show']
    if args.subcommand not in subcommands:
        print 'Unknown sub-command, expecting one of {0}'.format(
            subcommands)
        return

    if args.url is not None:
        url = args.url
    else:
        url = 'http://localhost:8800'

    web_client = LedgerWebClient(url)

    try:
        if args.subcommand == 'list':
            if args.all:
                blockids = web_client.get_block_list()
            else:
                blockids = web_client.get_block_list(args.blockcount)
            for block_id in blockids:
                print block_id
            return
        elif args.subcommand == 'show':
            if args.key is not None:
                block_info = web_client.get_block(args.blockID, args.key)
            else:
                block_info = web_client.get_block(args.blockID)
            print pretty_print_dict(block_info)
            return

    except MessageException as e:
        raise CliException(e)

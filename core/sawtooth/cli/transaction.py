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

from journal import transaction

from sawtooth.client import LedgerWebClient

from sawtooth.exceptions import MessageException

from sawtooth.cli.exceptions import CliException


def add_transaction_parser(subparsers, parent_parser):
    parser = subparsers.add_parser('transaction')

    grand_parsers = parser.add_subparsers(title='grandchildcommands',
                                          dest='subcommand')

    epilog = '''
    details:
      list the transaction IDs from the newest to the oldest.
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
        help='list the maximum number of transaction IDs. Default: 10')
    list_parser.add_argument(
        '-a', '--all',
        action='store_true',
        help='list all of transaction IDs')

    epilog = '''
    details:
      show the contents of transaction or the value associated with key
      within the transaction.
    '''
    show_parser = grand_parsers.add_parser('show', epilog=epilog)
    show_parser.add_argument(
        'transactionID',
        type=str,
        help='the id of the transaction')
    show_parser.add_argument(
        '-k', '--key',
        type=str,
        help='the key within the transaction')
    show_parser.add_argument(
        '--url',
        type=str,
        help='the URL to the validator')

    epilog = '''
    details:
      show the status of a specific transaction id.
    '''
    status_parser = grand_parsers.add_parser('status', epilog=epilog)
    status_parser.add_argument(
        'transactionID',
        type=str,
        help='the id of the transaction')
    status_parser.add_argument(
        '--url',
        type=str,
        help='the URL to the validator')


def do_transaction(args):
    subcommands = ['list', 'show', 'status']

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
                tsctids = web_client.get_transaction_list()
            else:
                tsctids = web_client.get_transaction_list(args.blockcount)
            for txn_id in tsctids:
                print txn_id
            return
        elif args.subcommand == 'show':
            if args.key is not None:
                tsct_info = web_client.get_transaction(args.transactionID,
                                                       args.key)
            else:
                tsct_info = web_client.get_transaction(args.transactionID)
            print pretty_print_dict(tsct_info)
            return
        elif args.subcommand == 'status':
            tsct_status = web_client.get_transaction_status(args.transactionID)
            if tsct_status == transaction.Status.committed:
                print 'transaction committed'
            elif tsct_status == transaction.Status.pending:
                print 'transaction still uncommitted'
            elif tsct_status == transaction.Status.unknown:
                print 'unknown transaction'
            elif tsct_status == transaction.Status.failed:
                print 'transaction failed to validate.'
            else:
                print 'transaction returned unexpected status code {0}'\
                    .format(tsct_status)
            return

    except MessageException as e:
        raise CliException(e)

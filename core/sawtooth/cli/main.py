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


import argparse
import importlib
import getpass
import logging
import os
import traceback
import sys

from colorlog import ColoredFormatter

from gossip.common import json2dict, pretty_print_dict

from journal import transaction

from sawtooth.client import LedgerWebClient
from sawtooth.client import SawtoothClient

from sawtooth.exceptions import ClientException
from sawtooth.exceptions import InvalidTransactionError
from sawtooth.exceptions import MessageException

from sawtooth.cli.exceptions import CliException
from sawtooth.cli.keygen import add_keygen_parser
from sawtooth.cli.keygen import do_keygen


LOGGER = logging.getLogger(__name__)


class FakeJournal(object):
    """Used to determine details of a transaction family."""

    def __init__(self):
        self.msg_class = None
        self.store_class = None

    def register_message_handler(self, msg_class, handler):
        if self.msg_class is not None:
            raise CliException("multiple message classes are unsupported")
        self.msg_class = msg_class

    def add_transaction_store(self, store_class):
        if self.store_class is not None:
            raise CliException("multiple store classes are unsupported")
        self.store_class = store_class


def create_console_handler(verbose_level):
    clog = logging.StreamHandler()
    formatter = ColoredFormatter(
        "%(log_color)s[%(asctime)s %(levelname)-8s%(module)s]%(reset)s "
        "%(white)s%(message)s",
        datefmt="%H:%M:%S",
        reset=True,
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red',
        })

    clog.setFormatter(formatter)

    if verbose_level == 0:
        clog.setLevel(logging.WARN)
    elif verbose_level == 1:
        clog.setLevel(logging.INFO)
    else:
        clog.setLevel(logging.DEBUG)

    return clog


def setup_loggers(verbose_level):
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logger.addHandler(create_console_handler(verbose_level))


def add_submit_parser(subparsers, parent_parser):
    epilog = '''
details:
  A single dash '-' can be specified for FILENAME to read input from
  stdin.

examples:
  # sawtooth submit -F sawtooth_xo --wait -f transactions.js
  # cat transactions.js | sawtooth submit --wait -F sawtooth_xo -f -
'''

    parser = subparsers.add_parser(
        'submit',
        parents=[parent_parser],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=epilog)

    parser.add_argument(
        '-F', '--family',
        required=True,
        type=str,
        help='the transaction family')

    parser.add_argument(
        '-f', '--filename',
        required=True,
        type=str,
        help='a file containing the transaction JSON')

    parser.add_argument(
        '--key',
        type=str,
        help='the signing key')

    parser.add_argument(
        '--url',
        type=str,
        help='the URL to the validator')

    parser.add_argument(
        '--wait',
        action='store_true',
        default=False,
        help='wait for this commit before exiting')


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


def create_parent_parser(prog_name):
    parent_parser = argparse.ArgumentParser(prog=prog_name, add_help=False)
    parent_parser.add_argument(
        '-v', '--verbose',
        action='count',
        help='enable more verbose output')

    return parent_parser


def create_parser(prog_name):
    parent_parser = create_parent_parser(prog_name)

    parser = argparse.ArgumentParser(
        parents=[parent_parser],
        formatter_class=argparse.RawDescriptionHelpFormatter)

    subparsers = parser.add_subparsers(title='subcommands', dest='command')

    add_keygen_parser(subparsers, parent_parser)
    add_submit_parser(subparsers, parent_parser)
    add_block_parser(subparsers, parent_parser)
    add_transaction_parser(subparsers, parent_parser)
    add_store_parser(subparsers, parent_parser)

    return parser


def do_submit(args):
    if args.key is not None:
        key_name = args.key
    else:
        key_name = getpass.getuser()

    if args.url is not None:
        url = args.url
    else:
        url = 'http://localhost:8800'

    filename = args.filename
    family_name = args.family

    # If we have a '/' in the key name, treat it as the full path to
    # a wif file, without modification.  If it does not, then assume
    # it is in ~/.sawtooth/keys/.
    if '/' in key_name:
        key_file = key_name
    else:
        key_dir = os.path.join(os.path.expanduser('~'), '.sawtooth', 'keys')
        key_file = os.path.join(key_dir, key_name + '.wif')

    if not os.path.exists(key_file):
        raise ClientException('no such file: {}'.format(key_file))

    try:
        if filename == '-':
            json_content = sys.stdin.read()
        else:
            with open(filename) as fd:
                json_content = fd.read()
    except IOError, e:
        raise CliException(str(e))

    try:
        txn_content = json2dict(json_content)
    except ValueError, e:
        raise CliException("Decoding JSON: {}".format(str(e)))

    try:
        txnfamily = importlib.import_module(family_name)
    except ImportError:
        raise CliException(
            "transaction family not found: {}".format(family_name))

    fake_journal = FakeJournal()
    txnfamily.register_transaction_types(fake_journal)

    client = SawtoothClient(
        base_url=url,
        keyfile=key_file,
        store_name=fake_journal.store_class.__name__)

    client.sendtxn(
        fake_journal.store_class,
        fake_journal.msg_class,
        txn_content)

    if args.wait:
        if not client.wait_for_commit():
            raise CliException("transaction was not successfully committed")


def _get_webclient(args):
    if args.url is not None:
        url = args.url
    else:
        url = 'http://localhost:8800'

    return LedgerWebClient(url)


def do_block(args):
    subcommands = ['list', 'show']
    if args.subcommand not in subcommands:
        print 'Unknown sub-command, expecting one of {0}'.format(
            subcommands)
        return

    web_client = _get_webclient(args)

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


def do_transaction(args):
    subcommands = ['list', 'show', 'status']

    if args.subcommand not in subcommands:
        print 'Unknown sub-command, expecting one of {0}'.format(
            subcommands)
        return

    web_client = _get_webclient(args)

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


def do_store(args):
    subcommands = ['list', 'show']

    if args.subcommand not in subcommands:
        print 'Unknown sub-command, expecting one of {0}'.format(
            subcommands)
        return

    web_client = _get_webclient(args)

    try:
        if args.subcommand == 'list':
            transaction_type_name = web_client.get_store_by_name()
            print pretty_print_dict(transaction_type_name)
            return
        elif args.subcommand == 'show':
            if args.blockID is not None:
                block_id = args.blockID
            else:
                block_id = ''

            if args.key is not None:
                key = args.key
            else:
                key = ''

            store_info = web_client.get_store_by_name(args.transactionTypeName,
                                                      key,
                                                      block_id,
                                                      args.incremental)
            print pretty_print_dict(store_info)
            return

    except MessageException as e:
        raise CliException(e)


def main(prog_name=os.path.basename(sys.argv[0]), args=sys.argv[1:]):
    parser = create_parser(prog_name)
    args = parser.parse_args(args)

    if args.verbose is None:
        verbose_level = 0
    else:
        verbose_level = args.verbose

    setup_loggers(verbose_level=verbose_level)

    if args.command == 'keygen':
        do_keygen(args)
    elif args.command == 'submit':
        do_submit(args)
    elif args.command == 'block':
        do_block(args)
    elif args.command == 'transaction':
        do_transaction(args)
    elif args.command == 'store':
        do_store(args)
    else:
        raise CliException("invalid command: {}".format(args.command))


def main_wrapper():
    # pylint: disable=bare-except
    try:
        main()
    except CliException as e:
        print >>sys.stderr, "Error: {}".format(e)
        sys.exit(1)
    except InvalidTransactionError as e:
        print >>sys.stderr, "Error: {}".format(e)
        sys.exit(1)
    except ClientException as e:
        print >>sys.stderr, "Error: {}".format(e)
        sys.exit(1)
    except KeyboardInterrupt:
        pass
    except SystemExit as e:
        raise e
    except:
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

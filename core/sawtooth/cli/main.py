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

from gossip.common import json2dict

from sawtooth.client import SawtoothClient

from sawtooth.exceptions import ClientException
from sawtooth.exceptions import InvalidTransactionError

from sawtooth.cli.block import add_block_parser
from sawtooth.cli.block import do_block
from sawtooth.cli.exceptions import CliException
from sawtooth.cli.keygen import add_keygen_parser
from sawtooth.cli.keygen import do_keygen
from sawtooth.cli.store import add_store_parser
from sawtooth.cli.store import do_store
from sawtooth.cli.transaction import add_transaction_parser
from sawtooth.cli.transaction import do_transaction


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

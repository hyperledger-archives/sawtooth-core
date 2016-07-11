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
import pybitcointools

from colorlog import ColoredFormatter

from gossip.common import json2dict
from sawtooth.client import SawtoothClient
from sawtooth.exceptions import ClientException
from sawtooth.exceptions import InvalidTransactionError


LOGGER = logging.getLogger(__name__)


class CliException(Exception):
    def __init__(self, msg):
        super(CliException, self).__init__(msg)


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


def add_keygen_parser(subparsers, parent_parser):
    parser = subparsers.add_parser('keygen', parents=[parent_parser])

    parser.add_argument(
        'key_name',
        help='name of the key to create',
        nargs='?')

    parser.add_argument(
        '--key-dir',
        help="directory to write key files")

    parser.add_argument(
        '--force',
        help="overwrite files if they exist",
        action='store_true')

    parser.add_argument(
        '-q',
        '--quiet',
        help="print no output",
        action='store_true')


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

    return parser


def do_keygen(args):
    if args.key_name is not None:
        key_name = args.key_name
    else:
        key_name = getpass.getuser()

    if args.key_dir is not None:
        key_dir = args.key_dir
        if not os.path.exists(key_dir):
            raise ClientException('no such directory: {}'.format(key_dir))
    else:
        key_dir = os.path.join(os.path.expanduser('~'), '.sawtooth', 'keys')
        if not os.path.exists(key_dir):
            if not args.quiet:
                print 'creating key directory: {}'.format(key_dir)
            try:
                os.makedirs(key_dir)
            except IOError, e:
                raise ClientException('IOError: {}'.format(str(e)))

    wif_filename = os.path.join(key_dir, key_name + '.wif')
    addr_filename = os.path.join(key_dir, key_name + '.addr')

    if not args.force:
        file_exists = False
        for filename in [wif_filename, addr_filename]:
            if os.path.exists(filename):
                file_exists = True
                print >>sys.stderr, 'file exists: {}'.format(filename)
        if file_exists:
            raise ClientException(
                'files exist, rerun with --force to overwrite existing files')

    privkey = pybitcointools.random_key()
    encoded = pybitcointools.encode_privkey(privkey, 'wif')
    addr = pybitcointools.privtoaddr(privkey)

    try:
        wif_exists = os.path.exists(wif_filename)
        with open(wif_filename, 'w') as wif_fd:
            if not args.quiet:
                if wif_exists:
                    print 'overwriting file: {}'.format(wif_filename)
                else:
                    print 'writing file: {}'.format(wif_filename)
            wif_fd.write(encoded)
            wif_fd.write('\n')

        addr_exists = os.path.exists(addr_filename)
        with open(addr_filename, 'w') as addr_fd:
            if not args.quiet:
                if addr_exists:
                    print 'overwriting file: {}'.format(addr_filename)
                else:
                    print 'writing file: {}'.format(addr_filename)
            addr_fd.write(addr)
            addr_fd.write('\n')
    except IOError, ioe:
        raise ClientException('IOError: {}'.format(str(ioe)))


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

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
import ConfigParser
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


def add_init_parser(subparsers, parent_parser):
    parser = subparsers.add_parser('init', parents=[parent_parser])

    parser.add_argument(
        '--username',
        type=str,
        help='the name of the player')


def add_submit_parser(subparsers, parent_parser):
    parser = subparsers.add_parser('submit', parents=[parent_parser])

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
        '--username',
        type=str,
        help='the name of the player')

    parser.add_argument(
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

    add_init_parser(subparsers, parent_parser)
    add_submit_parser(subparsers, parent_parser)

    return parser


def do_init(args, config):
    username = config.get('DEFAULT', 'username')
    if args.username is not None:
        username = args.username

    config.set('DEFAULT', 'username', username)
    print "set username: {}".format(username)

    save_config(config)

    wif_filename = config.get('DEFAULT', 'key_file')
    if wif_filename.endswith(".wif"):
        addr_filename = wif_filename[0:-len(".wif")] + ".addr"
    else:
        addr_filename = wif_filename + ".addr"

    if not os.path.exists(wif_filename):
        try:
            if not os.path.exists(os.path.dirname(wif_filename)):
                os.makedirs(os.path.dirname(wif_filename))

            privkey = pybitcointools.random_key()
            encoded = pybitcointools.encode_privkey(privkey, 'wif')
            addr = pybitcointools.privtoaddr(privkey)

            with open(wif_filename, "w") as wif_fd:
                print "writing file: {}".format(wif_filename)
                wif_fd.write(encoded)
                wif_fd.write("\n")

            with open(addr_filename, "w") as addr_fd:
                print "writing file: {}".format(addr_filename)
                addr_fd.write(addr)
                addr_fd.write("\n")
        except IOError, ioe:
            raise ClientException("IOError: {}".format(str(ioe)))


def do_submit(args, config):
    username = config.get('DEFAULT', 'username')
    if args.username is not None:
        username = args.username

        # need to set url in config for substitution in key_file
        config.set('DEFAULT', 'username', username)

    url = config.get('DEFAULT', 'url')
    if args.url is not None:
        url = args.url

    key_file = config.get('DEFAULT', 'key_file')

    filename = args.filename
    family_name = args.family

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
            "transaction family not found: {}".format(txnfamily))

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


def load_config():
    home = os.path.expanduser("~")
    real_user = getpass.getuser()

    config_file = os.path.join(home, ".sawtooth", "sawtooth.cfg")
    key_dir = os.path.join(home, ".sawtooth", "keys")

    config = ConfigParser.SafeConfigParser()
    config.set('DEFAULT', 'url', 'http://localhost:8800')
    config.set('DEFAULT', 'key_dir', key_dir)
    config.set('DEFAULT', 'key_file', '%(key_dir)s/%(username)s.wif')
    config.set('DEFAULT', 'username', real_user)
    if os.path.exists(config_file):
        config.read(config_file)

    return config


def save_config(config):
    home = os.path.expanduser("~")

    config_file = os.path.join(home, ".sawtooth", "sawtooth.cfg")
    if not os.path.exists(os.path.dirname(config_file)):
        os.makedirs(os.path.dirname(config_file))

    with open("{}.new".format(config_file), "w") as fd:
        config.write(fd)
    os.rename("{}.new".format(config_file), config_file)


def main(prog_name=os.path.basename(sys.argv[0]), args=sys.argv[1:]):
    parser = create_parser(prog_name)
    args = parser.parse_args(args)

    if args.verbose is None:
        verbose_level = 0
    else:
        verbose_level = args.verbose

    setup_loggers(verbose_level=verbose_level)

    config = load_config()

    if args.command == 'init':
        do_init(args, config)
    elif args.command == 'submit':
        do_submit(args, config)
    else:
        raise CliException("invalid command: {}".format(args.command))


def main_wrapper():
    # pylint: disable=bare-except
    try:
        main()
    except CliException as e:
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

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
import os
import sys

from gossip.common import json2dict

from sawtooth.client import SawtoothClient

from sawtooth.exceptions import ClientException

from sawtooth.cli.exceptions import CliException


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
    # a priv file, without modification.  If it does not, then assume
    # it is in ~/.sawtooth/keys/.
    if '/' in key_name:
        key_file = key_name
    else:
        key_dir = os.path.join(os.path.expanduser('~'), '.sawtooth', 'keys')
        key_file = os.path.join(key_dir, key_name + '.priv')

    if not os.path.exists(key_file):
        raise ClientException('no such file: {}'.format(key_file))

    try:
        if filename == '-':
            json_content = sys.stdin.read()
        else:
            with open(filename) as fd:
                json_content = fd.read()
    except IOError as e:
        raise CliException(str(e))

    try:
        txn_content = json2dict(json_content)
    except ValueError as e:
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

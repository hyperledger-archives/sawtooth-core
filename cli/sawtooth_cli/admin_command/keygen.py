# Copyright 2017 Intel Corporation
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

import os
import sys

from sawtooth_cli.exceptions import CliException
from sawtooth_cli.admin_command.config import get_key_dir
import sawtooth_signing as signing


def add_keygen_parser(subparsers, parent_parser):
    """Adds subparser command and flags for 'keygen' command.

    Args:
        subparsers (:obj:`ArguementParser`): The subcommand parsers.
        parent_parser (:obj:`ArguementParser`): The parent of the subcomman
            parsers.
    """
    parser = subparsers.add_parser('keygen', parents=[parent_parser])

    parser.add_argument(
        'key_name',
        help='name of the key to create',
        nargs='?')

    parser.add_argument(
        '--force',
        help="overwrite files if they exist",
        action='store_true')

    parser.add_argument(
        '-q',
        '--quiet',
        help="print no output",
        action='store_true')


def do_keygen(args):
    """Executes the key generation operation, given the parsed arguments.

    Args:
        args (:obj:`Namespace`): The parsed args.
    """
    if args.key_name is not None:
        key_name = args.key_name
    else:
        key_name = 'validator'

    key_dir = get_key_dir()

    if not os.path.exists(key_dir):
        raise CliException(
            "Key directory does not exist: {}".format(key_dir))

    wif_filename = os.path.join(key_dir, key_name + '.wif')
    addr_filename = os.path.join(key_dir, key_name + '.addr')

    if not args.force:
        file_exists = False
        for filename in [wif_filename, addr_filename]:
            if os.path.exists(filename):
                file_exists = True
                print('file exists: {}'.format(filename), file=sys.stderr)
        if file_exists:
            raise CliException(
                'files exist, rerun with --force to overwrite existing files')

    privkey = signing.generate_privkey()
    encoded = signing.encode_privkey(privkey)
    pubkey = signing.generate_pubkey(privkey)
    addr = signing.generate_identifier(pubkey)

    try:
        wif_exists = os.path.exists(wif_filename)
        with open(wif_filename, 'w') as wif_fd:
            if not args.quiet:
                if wif_exists:
                    print('overwriting file: {}'.format(wif_filename))
                else:
                    print('writing file: {}'.format(wif_filename))
            wif_fd.write(encoded)
            wif_fd.write('\n')

        addr_exists = os.path.exists(addr_filename)
        with open(addr_filename, 'w') as addr_fd:
            if not args.quiet:
                if addr_exists:
                    print('overwriting file: {}'.format(addr_filename))
                else:
                    print('writing file: {}'.format(addr_filename))
            addr_fd.write(addr)
            addr_fd.write('\n')
    except IOError as ioe:
        raise CliException('IOError: {}'.format(str(ioe)))

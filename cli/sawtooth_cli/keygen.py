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

import getpass
import os
import sys

from sawtooth_cli.exceptions import CliException
import sawtooth_signing as signing


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


def do_keygen(args):
    if args.key_name is not None:
        key_name = args.key_name
    else:
        key_name = getpass.getuser()

    if args.key_dir is not None:
        key_dir = args.key_dir
        if not os.path.exists(key_dir):
            raise CliException('no such directory: {}'.format(key_dir))
    else:
        key_dir = os.path.join(os.path.expanduser('~'), '.sawtooth', 'keys')
        if not os.path.exists(key_dir):
            if not args.quiet:
                print('creating key directory: {}'.format(key_dir))
            try:
                os.makedirs(key_dir)
            except IOError as e:
                raise CliException('IOError: {}'.format(str(e)))

    priv_filename = os.path.join(key_dir, key_name + '.priv')
    pub_filename = os.path.join(key_dir, key_name + '.pub')

    if not args.force:
        file_exists = False
        for filename in [priv_filename, pub_filename]:
            if os.path.exists(filename):
                file_exists = True
                print('file exists: {}'.format(filename), file=sys.stderr)
        if file_exists:
            raise CliException(
                'files exist, rerun with --force to overwrite existing files')

    private_key = signing.generate_private_key()
    public_key = signing.generate_public_key(private_key)

    try:
        priv_exists = os.path.exists(priv_filename)
        with open(priv_filename, 'w') as priv_fd:
            if not args.quiet:
                if priv_exists:
                    print('overwriting file: {}'.format(priv_filename))
                else:
                    print('writing file: {}'.format(priv_filename))
            priv_fd.write(private_key)
            priv_fd.write('\n')

        pub_exists = os.path.exists(pub_filename)
        with open(pub_filename, 'w') as pub_fd:
            if not args.quiet:
                if pub_exists:
                    print('overwriting file: {}'.format(pub_filename))
                else:
                    print('writing file: {}'.format(pub_filename))
            pub_fd.write(public_key)
            pub_fd.write('\n')

    except IOError as ioe:
        raise CliException('IOError: {}'.format(str(ioe)))

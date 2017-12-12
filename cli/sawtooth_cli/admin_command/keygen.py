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
from sawtooth_signing import create_context


def add_keygen_parser(subparsers, parent_parser):
    """Adds subparser command and flags for 'keygen' command.

    Args:
        subparsers (:obj:`ArguementParser`): The subcommand parsers.
        parent_parser (:obj:`ArguementParser`): The parent of the subcomman
            parsers.
    """
    description = 'Generates keys for the validator to use when signing blocks'

    epilog = (
        'The private and public key pair is stored in '
        '/etc/sawtooth/keys/<key-name>.priv and '
        '/etc/sawtooth/keys/<key-name>.pub.'
    )

    parser = subparsers.add_parser(
        'keygen',
        help=description,
        description=description + '.',
        epilog=epilog,
        parents=[parent_parser])

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
        help="do not display output",
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
        raise CliException("Key directory does not exist: {}".format(key_dir))

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

    context = create_context('secp256k1')

    private_key = context.new_random_private_key()
    public_key = context.get_public_key(private_key)

    try:
        priv_exists = os.path.exists(priv_filename)
        with open(priv_filename, 'w') as priv_fd:
            if not args.quiet:
                if priv_exists:
                    print('overwriting file: {}'.format(priv_filename))
                else:
                    print('writing file: {}'.format(priv_filename))
            priv_fd.write(private_key.as_hex())
            priv_fd.write('\n')
            # Get the uid and gid of the key directory
            keydir_info = os.stat(key_dir)
            keydir_gid = keydir_info.st_gid
            keydir_uid = keydir_info.st_uid
            # Set user and group on keys to the user/group of the key directory
            os.chown(priv_filename, keydir_uid, keydir_gid)
            # Set the private key u+rw g+r
            os.chmod(priv_filename, 0o640)

        pub_exists = os.path.exists(pub_filename)
        with open(pub_filename, 'w') as pub_fd:
            if not args.quiet:
                if pub_exists:
                    print('overwriting file: {}'.format(pub_filename))
                else:
                    print('writing file: {}'.format(pub_filename))
            pub_fd.write(public_key.as_hex())
            pub_fd.write('\n')
            # Set user and group on keys to the user/group of the key directory
            os.chown(pub_filename, keydir_uid, keydir_gid)
            # Set the public key u+rw g+r o+r
            os.chmod(pub_filename, 0o644)

    except IOError as ioe:
        raise CliException('IOError: {}'.format(str(ioe)))

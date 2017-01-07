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

import os
import re


from sawtooth.cli.exceptions import CliException
from sawtooth.config import ArgparseOptionsConfig
from sawtooth.validator_config import get_validator_configuration


def add_clean_parser(subparsers, parent_parser):

    epilog = '''
        details:
          --config accepts a comma-separated list.
          alternatively, multiple --config options
          can be specified
        '''

    parser = subparsers.add_parser('clean', epilog=epilog)

    parser.add_argument(
        '--keys',
        action='store_true',
        help='delete validator signing keys')

    parser.add_argument('--state',
                        action='store_true',
                        help='clean validator state')

    parser.add_argument('--config',
                        help='config files to load',
                        action='append')

    parser.add_argument('--key-dir', help='path to key directory')

    parser.add_argument('--conf-dir', help='name of the config directory')

    parser.add_argument('--data-dir', help='name of the data directory')

    parser.add_argument(
        '--dry-run', '-n',
        action='store_true',
        help='show objects that would be removed')


def purge(directory, files):
    for f in files:
        full_path = os.path.join(directory, f)
        print("Removing {}".format(full_path))
        os.remove(full_path)


def get_purge_files(directory, pattern):
    # Searches for files in passed directory, and returns list of files.
    matched_files = []
    for f in os.listdir(directory):
        if re.search(pattern, f):
            matched_files.append(f)
    return matched_files


def do_clean(args):
    # Intercept the config
    # Set default config file if not specified by user
    if args.config is None:
        args.config = ['txnvalidator.js']

    # Convert any comma-delimited argument strings to list elements
    for arglist in [args.config]:
        if arglist is not None:
            for arg in arglist:
                if ',' in arg:
                    loc = arglist.index(arg)
                    arglist.pop(loc)
                    for element in reversed(arg.split(',')):
                        arglist.insert(loc, element)

    options_config = ArgparseOptionsConfig(
        [
            ('conf_dir', 'ConfigDirectory'),
            ('data_dir', 'DataDirectory'),
            ('log_config', 'LogConfigFile'),
            ('key_dir', 'KeyDirectory'),
            ('verbose', 'Verbose')
        ], args)
    cfg = get_validator_configuration(args.config, options_config)

    if args.state is True:
        do_clean_state(cfg, args)

    if args.keys is True:
        do_delete_keys(cfg, args)

    if args.state is False and args.keys is False:
        raise CliException("Please specify at least one object to clean.")


def do_clean_state(cfg, args):
    # Use regex to specify state files to remove
    data_directory = cfg.get("DataDirectory")
    files = get_purge_files(data_directory, r'\.shelf')
    files.extend(get_purge_files(data_directory, r'\.json'))
    files.extend(get_purge_files(data_directory, r'\.dbm'))

    if args.dry_run is True:
        try:
            for f in files:
                print("Would remove {}".format(f))
        except OSError as err:
            raise CliException("OS error: {0}".format(err))

    else:
        try:
            files = get_purge_files(data_directory, '.*')
            purge(data_directory, files)

        except OSError as err:
            raise CliException("OS error: {0}".format(err))


def do_delete_keys(cfg, args):
    # Use regex to specify which signing key files to remove
    key_directory = cfg.get("KeyDirectory")
    files = get_purge_files(key_directory, r'\.addr')
    files.extend(get_purge_files(key_directory, r'\.wif'))

    if args.dry_run is True:
        try:
            for f in files:
                print("Would remove {}".format(f))

        except OSError as err:
            raise CliException("OS error: {0}".format(err))

    else:
        try:
            purge(key_directory, files)

        except OSError as err:
            raise CliException("OS error: {0}".format(err))

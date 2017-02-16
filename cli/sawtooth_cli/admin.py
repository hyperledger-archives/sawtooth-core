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

from sawtooth_cli.admin_command.genesis import add_genesis_parser
from sawtooth_cli.admin_command.genesis import do_genesis


def do_admin(args):
    if 'SAWTOOTH_HOME' in os.environ:
        data_dir = os.path.join(os.environ['SAWTOOTH_HOME'], 'data')
    else:
        data_dir = '/var/lib/sawtooth'

    try:
        os.makedirs(data_dir, exist_ok=True)
    except OSError as e:
        print('Unable to create {}: {}'.format(data_dir, e), file=sys.stderr)
        return

    if args.admin_cmd == 'genesis':
        do_genesis(args, data_dir)
    else:
        raise CliException("invalid command: {}".format(args.command))


def add_admin_parser(subparsers, parent_parser):
    parser = subparsers.add_parser('admin')
    admin_sub = parser.add_subparsers(title='admin_commands', dest='admin_cmd')

    add_genesis_parser(admin_sub, parser)

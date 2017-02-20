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

from sawtooth_cli.exceptions import CliException

from sawtooth_cli.admin_command.genesis import add_genesis_parser
from sawtooth_cli.admin_command.genesis import do_genesis
from sawtooth_cli.admin_command.keygen import add_keygen_parser
from sawtooth_cli.admin_command.keygen import do_keygen
from sawtooth_cli.admin_command.utils import ensure_directory


def do_admin(args):
    data_dir = ensure_directory('data', '/var/lib/sawtooth')

    if args.admin_cmd == 'genesis':
        do_genesis(args, data_dir)
    elif args.admin_cmd == 'keygen':
        do_keygen(args)
    else:
        raise CliException("invalid command: {}".format(args.admin_cmd))


def add_admin_parser(subparsers, parent_parser):
    parser = subparsers.add_parser('admin', parents=[parent_parser])
    admin_sub = parser.add_subparsers(title='admin_commands', dest='admin_cmd')

    add_genesis_parser(admin_sub, parent_parser)
    add_keygen_parser(admin_sub, parent_parser)

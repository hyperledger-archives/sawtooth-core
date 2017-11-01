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


from sawtooth_cli.admin_command.genesis import add_genesis_parser
from sawtooth_cli.admin_command.genesis import do_genesis
from sawtooth_cli.admin_command.keygen import add_keygen_parser
from sawtooth_cli.admin_command.keygen import do_keygen


def do_admin(args):
    if args.subcommand == 'genesis':
        do_genesis(args)
    elif args.subcommand == 'keygen':
        do_keygen(args)
    else:
        raise AssertionError("invalid command: {}".format(args.subcommand))


def add_admin_parser(subparsers, parent_parser):
    parser = subparsers.add_parser(
        'admin',
        help='Create validator keys and help create the genesis block',
        description='Provides subcommands to create validator keys and '
        'help create the genesis block',
        parents=[parent_parser])
    admin_sub = parser.add_subparsers(title='subcommands', dest='subcommand')
    admin_sub.required = True
    add_genesis_parser(admin_sub, parent_parser)
    add_keygen_parser(admin_sub, parent_parser)

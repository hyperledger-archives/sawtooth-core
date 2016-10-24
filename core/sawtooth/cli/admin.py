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
import logging

from sawtooth.cli.exceptions import CliException
from sawtooth.cli.admin_sub.poet0_genesis import add_poet0_genesis_parser
from sawtooth.cli.admin_sub.poet0_genesis import do_poet0_genesis
from sawtooth.cli.admin_sub.poet1_genesis import add_poet1_genesis_parser
from sawtooth.cli.admin_sub.poet1_genesis import do_poet1_genesis

LOGGER = logging.getLogger(__name__)


def do_admin(args):
    if args.admin_cmd == 'poet0-genesis':
        do_poet0_genesis(args)
    elif args.admin_cmd == 'poet1-genesis':
        do_poet1_genesis(args)
    else:
        raise CliException("invalid command: {}".format(args.command))


def add_admin_parser(subparsers, parent_parser):
    parser = subparsers.add_parser('admin')
    admin_sub = parser.add_subparsers(title='admin_commands', dest='admin_cmd')
    add_poet0_genesis_parser(admin_sub, parser)
    add_poet1_genesis_parser(admin_sub, parser)

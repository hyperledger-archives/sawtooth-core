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
from sawtooth.cli.admin_sub.dev_mode_genesis import add_dev_mode_genesis_parser
from sawtooth.cli.admin_sub.dev_mode_genesis import do_dev_mode_genesis
from sawtooth.cli.admin_sub.poet1_genesis import add_poet_genesis_parser
from sawtooth.cli.admin_sub.poet1_genesis import do_poet_genesis
from sawtooth.cli.admin_sub.permissioned_validator_registry\
    import add_validator_parser
from sawtooth.cli.admin_sub.permissioned_validator_registry\
    import do_validator_registry
from sawtooth.cli.admin_sub.clean import add_clean_parser
from sawtooth.cli.admin_sub.clean import do_clean

LOGGER = logging.getLogger(__name__)


def do_admin(args):
    if args.admin_cmd == 'dev-mode-genesis':
        do_dev_mode_genesis(args)
    elif args.admin_cmd == 'poet-genesis':
        do_poet_genesis(args)
    elif args.admin_cmd == 'validator-registry':
        do_validator_registry(args)
    elif args.admin_cmd == 'clean':
        do_clean(args)
    else:
        raise CliException("invalid command: {}".format(args.command))


def add_admin_parser(subparsers, parent_parser):
    parser = subparsers.add_parser('admin')
    admin_sub = parser.add_subparsers(title='admin_commands', dest='admin_cmd')
    add_dev_mode_genesis_parser(admin_sub, parser)
    add_poet_genesis_parser(admin_sub, parser)
    add_validator_parser(admin_sub, parser)
    add_clean_parser(admin_sub, parser)

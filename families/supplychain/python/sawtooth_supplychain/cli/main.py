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

from __future__ import print_function

import argparse
import configparser
import getpass
import logging
import os
import traceback
import sys

from colorlog import ColoredFormatter


from sawtooth_supplychain.common.exceptions import SupplyChainException
from sawtooth_supplychain.cli.agent import add_agent_parser
from sawtooth_supplychain.cli.agent import do_agent
from sawtooth_supplychain.cli.application import add_application_parser
from sawtooth_supplychain.cli.application import do_application
from sawtooth_supplychain.cli.init import add_init_parser
from sawtooth_supplychain.cli.init import do_init
from sawtooth_supplychain.cli.record import add_record_parser
from sawtooth_supplychain.cli.record import do_record
from sawtooth_supplychain.cli.reset import add_reset_parser
from sawtooth_supplychain.cli.reset import do_reset


def create_console_handler(verbose_level):
    clog = logging.StreamHandler()
    formatter = ColoredFormatter(
        "%(log_color)s[%(asctime)s %(levelname)-8s%(module)s]%(reset)s "
        "%(white)s%(message)s",
        datefmt="%H:%M:%S",
        reset=True,
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red',
        })

    clog.setFormatter(formatter)

    if verbose_level == 0:
        clog.setLevel(logging.WARN)
    elif verbose_level == 1:
        clog.setLevel(logging.INFO)
    else:
        clog.setLevel(logging.DEBUG)

    return clog


def setup_loggers(verbose_level):
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logger.addHandler(create_console_handler(verbose_level))


def create_parent_parser(program_name):
    parent_parser = argparse.ArgumentParser(prog=program_name, add_help=False)
    parent_parser.add_argument(
        '-v', '--verbose',
        action='count',
        help='enable more verbose output')

    parent_parser.add_argument(
        '--wait',
        action='store_true',
        default=False,
        help='wait for this operation to commit before exiting')
    return parent_parser


def create_parser(program_name):
    parent_parser = create_parent_parser(program_name)

    parser = argparse.ArgumentParser(
        parents=[parent_parser],
        formatter_class=argparse.RawDescriptionHelpFormatter)

    subparsers = parser.add_subparsers(title='subcommands', dest='command')

    add_agent_parser(subparsers, parent_parser)
    add_application_parser(subparsers, parent_parser)
    add_init_parser(subparsers, parent_parser)
    add_record_parser(subparsers, parent_parser)
    add_reset_parser(subparsers, parent_parser)

    return parser


def load_config():
    home = os.path.expanduser("~")
    real_user = getpass.getuser()

    config_file = os.path.join(home, ".sawtooth", "supplychain.cfg")
    key_dir = os.path.join(home, ".sawtooth", "keys")

    config = configparser.ConfigParser()
    config.set('DEFAULT', 'url', '127.0.0.1:8080')
    config.set('DEFAULT', 'key_dir', key_dir)
    config.set('DEFAULT', 'key_file', '%(key_dir)s/%(username)s.priv')
    config.set('DEFAULT', 'username', real_user)
    if os.path.exists(config_file):
        config.read(config_file)

    return config


def main(program_name, args):
    parser = create_parser(program_name)
    args = parser.parse_args(args)

    if args.verbose is None:
        verbose_level = 0
    else:
        verbose_level = args.verbose

    setup_loggers(verbose_level=verbose_level)

    config = load_config()

    if args.command == 'agent':
        do_agent(args, config)
    elif args.command == 'application':
        do_application(args, config)
    elif args.command == 'init':
        do_init(args, config)
    elif args.command == 'record':
        do_record(args, config)
    elif args.command == 'reset':
        do_reset(args, config)
    else:
        raise SupplyChainException("invalid command: {}".format(args.command))


def main_wrapper():
    try:
        program_name = os.path.basename(sys.argv[0])
        args = sys.argv[1:]
        main(program_name, args)
    except SupplyChainException as err:
        print("Error: {}".format(err), file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        pass
    except SystemExit as err:
        raise err
    except BaseException as err:
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

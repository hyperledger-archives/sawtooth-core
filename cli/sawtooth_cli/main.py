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
import logging
import os
import traceback
import sys

from colorlog import ColoredFormatter

from sawtooth_cli.exceptions import CliException

from sawtooth_cli.admin import add_admin_parser
from sawtooth_cli.admin import do_admin
from sawtooth_cli.keygen import add_keygen_parser
from sawtooth_cli.keygen import do_keygen
from sawtooth_cli.config import add_config_parser
from sawtooth_cli.config import do_config
from sawtooth_cli.block import add_block_parser
from sawtooth_cli.block import do_block
from sawtooth_cli.state import add_state_parser
from sawtooth_cli.state import do_state
from sawtooth_cli.cluster import add_cluster_parser
from sawtooth_cli.cluster import do_cluster


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


def create_parent_parser(prog_name):
    parent_parser = argparse.ArgumentParser(prog=prog_name, add_help=False)
    parent_parser.add_argument(
        '-v', '--verbose',
        action='count',
        help='enable more verbose output')

    return parent_parser


def create_parser(prog_name):
    parent_parser = create_parent_parser(prog_name)

    parser = argparse.ArgumentParser(
        parents=[parent_parser],
        formatter_class=argparse.RawDescriptionHelpFormatter)

    subparsers = parser.add_subparsers(title='subcommands', dest='command')

    add_keygen_parser(subparsers, parent_parser)
    add_admin_parser(subparsers, parent_parser)
    add_config_parser(subparsers, parent_parser)
    add_block_parser(subparsers, parent_parser)
    add_state_parser(subparsers, parent_parser)
    add_cluster_parser(subparsers, parent_parser)

    return parser


def main(prog_name=os.path.basename(sys.argv[0]), args=sys.argv[1:],
         with_loggers=True):
    parser = create_parser(prog_name)
    args = parser.parse_args(args)

    if with_loggers is True:
        if args.verbose is None:
            verbose_level = 0
        else:
            verbose_level = args.verbose
        setup_loggers(verbose_level=verbose_level)

    if args.command == 'admin':
        do_admin(args)
    elif args.command == 'keygen':
        do_keygen(args)
    elif args.command == 'config':
        do_config(args)
    elif args.command == 'block':
        do_block(args)
    elif args.command == 'state':
        do_state(args)
    elif args.command == 'cluster':
        do_cluster(args)
    else:
        raise AssertionError("invalid command: {}".format(args.command))


def main_wrapper():
    # pylint: disable=bare-except
    try:
        main()
    except CliException as e:
        print("Error: {}".format(e), file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        pass
    except SystemExit as e:
        raise e
    except:
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

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


import argparse
import logging
import os
import traceback
import sys

from colorlog import ColoredFormatter

from sawtooth.exceptions import ClientException
from sawtooth.exceptions import InvalidTransactionError

from sawtooth.cli.block import add_block_parser
from sawtooth.cli.block import do_block
from sawtooth.cli.exceptions import CliException
from sawtooth.cli.keygen import add_keygen_parser
from sawtooth.cli.keygen import do_keygen
from sawtooth.cli.docker import add_docker_parser
from sawtooth.cli.docker import do_docker
from sawtooth.cli.store import add_store_parser
from sawtooth.cli.store import do_store
from sawtooth.cli.submit import add_submit_parser
from sawtooth.cli.submit import do_submit
from sawtooth.cli.transaction import add_transaction_parser
from sawtooth.cli.transaction import do_transaction


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
    add_docker_parser(subparsers, parent_parser)
    add_submit_parser(subparsers, parent_parser)
    add_block_parser(subparsers, parent_parser)
    add_transaction_parser(subparsers, parent_parser)
    add_store_parser(subparsers, parent_parser)

    return parser


def main(prog_name=os.path.basename(sys.argv[0]), args=sys.argv[1:]):
    parser = create_parser(prog_name)
    args = parser.parse_args(args)

    if args.verbose is None:
        verbose_level = 0
    else:
        verbose_level = args.verbose

    setup_loggers(verbose_level=verbose_level)

    if args.command == 'keygen':
        do_keygen(args)
    elif args.command == 'docker':
        do_docker(args)
    elif args.command == 'submit':
        do_submit(args)
    elif args.command == 'block':
        do_block(args)
    elif args.command == 'transaction':
        do_transaction(args)
    elif args.command == 'store':
        do_store(args)
    else:
        raise CliException("invalid command: {}".format(args.command))


def main_wrapper():
    # pylint: disable=bare-except
    try:
        main()
    except CliException as e:
        print >>sys.stderr, "Error: {}".format(e)
        sys.exit(1)
    except InvalidTransactionError as e:
        print >>sys.stderr, "Error: {}".format(e)
        sys.exit(1)
    except ClientException as e:
        print >>sys.stderr, "Error: {}".format(e)
        sys.exit(1)
    except KeyboardInterrupt:
        pass
    except SystemExit as e:
        raise e
    except:
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

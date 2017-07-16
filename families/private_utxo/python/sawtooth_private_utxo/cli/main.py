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
import logging
import os
import traceback
import sys

from colorlog import ColoredFormatter


from sawtooth_private_utxo.common.exceptions import PrivateUtxoException

from sawtooth_private_utxo.cli.convert_from_utxo import \
    CONVERT_FROM_UTXO_HANDLER
from sawtooth_private_utxo.cli.convert_to_utxo import\
    CONVERT_TO_UTXO_HANDLER

from sawtooth_private_utxo.cli.common import get_config_file_name
from sawtooth_private_utxo.cli.common import get_key_dir
from sawtooth_private_utxo.cli.common import get_user

from sawtooth_private_utxo.cli.init import INIT_HANDLER
from sawtooth_private_utxo.cli.issue_asset import ISSUE_ASSET_HANDLER
from sawtooth_private_utxo.cli.holdings import HOLDINGS_HANDLER
from sawtooth_private_utxo.cli.reset import RESET_HANDLER
from sawtooth_private_utxo.cli.show_document import SHOW_DOCUMENT_HANDLER
from sawtooth_private_utxo.cli.transfer_asset import TRANSFER_ASSET_HANDLER
from sawtooth_private_utxo.cli.transfer_utxo import TRANSFER_UTXO_HANDLER


LOGGER = logging.getLogger(__name__)


HANDLERS = [
    CONVERT_FROM_UTXO_HANDLER,
    CONVERT_TO_UTXO_HANDLER,
    INIT_HANDLER,
    ISSUE_ASSET_HANDLER,
    HOLDINGS_HANDLER,
    RESET_HANDLER,
    SHOW_DOCUMENT_HANDLER,
    TRANSFER_ASSET_HANDLER,
    TRANSFER_UTXO_HANDLER,
]


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
        '-u', '--user',
        help='the user to run the command as.')

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

    subparsers = parser.add_subparsers(
        title='subcommands',
        dest='command')
    subparsers.required = True

    for handler in HANDLERS:
        handler['parser'](subparsers, parent_parser)

    return parser


def load_config(args):

    config_file = get_config_file_name(args)

    key_dir = get_key_dir()

    config = configparser.ConfigParser()
    config.set('DEFAULT', 'url', '127.0.0.1:8080')
    config.set('DEFAULT', 'key_dir', key_dir)
    config.set('DEFAULT', 'key_file', '%(key_dir)s/%(username)s.priv')
    config.set('DEFAULT', 'username', get_user(args))
    if os.path.exists(config_file):
        config.read(config_file)

    return config


def main(program_name, args):
    parser = create_parser(program_name)
    args = parser.parse_args(args)

    verbose_level = 0
    if args.verbose is not None:
        verbose_level = args.verbose

    setup_loggers(verbose_level=verbose_level)

    config = load_config(args)

    for handler in HANDLERS:
        if handler['name'] == args.command:
            handler['run'](args, config)
            return 0

    raise PrivateUtxoException("invalid command: {}".format(args.command))


def main_wrapper():
    try:
        program_name = os.path.basename(sys.argv[0])
        args = sys.argv[1:]
        return main(program_name, args)
    except PrivateUtxoException as err:
        print("Error: {}".format(err), file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        pass
    except SystemExit as err:
        raise err
    except BaseException as err:
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

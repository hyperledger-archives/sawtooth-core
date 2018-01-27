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

import argparse
import logging
import os
import sys
import pkg_resources

from colorlog import ColoredFormatter

from sawtooth_sdk.processor.core import TransactionProcessor
from sawtooth_sdk.processor.log import init_console_logging
from sawtooth_sdk.processor.log import log_configuration
from sawtooth_sdk.processor.config import get_log_config
from sawtooth_sdk.processor.config import get_log_dir
from sawtooth_sdk.processor.config import get_config_dir
from sawtooth_settings.processor.handler import SettingsTransactionHandler
from sawtooth_settings.processor.config.settings import SettingsConfig
from sawtooth_settings.processor.config.settings import \
    load_default_settings_config
from sawtooth_settings.processor.config.settings import \
    load_toml_settings_config
from sawtooth_settings.processor.config.settings import \
    merge_settings_config


DISTRIBUTION_NAME = 'sawtooth-settings'


def create_console_handler(verbose_level):
    clog = logging.StreamHandler()
    formatter = ColoredFormatter(
        "%(log_color)s[%(asctime)s.%(msecs)03d "
        "%(levelname)-8s %(module)s]%(reset)s "
        "%(white)s%(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
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


def setup_loggers(verbose_level, processor):
    log_config = get_log_config(filename="settings_log_config.toml")

    # If no toml, try loading yaml
    if log_config is None:
        log_config = get_log_config(filename="settings_log_config.yaml")

    if log_config is not None:
        log_configuration(log_config=log_config)
    else:
        log_dir = get_log_dir()
        # use the transaction processor zmq identity for filename
        log_configuration(
            log_dir=log_dir,
            name="settings-" + str(processor.zmq_id)[2:-1])

    init_console_logging(verbose_level=verbose_level)


def create_parser(prog_name):
    parser = argparse.ArgumentParser(
        prog=prog_name,
        description='Starts a Settings transaction processor (settings-tp).',
        epilog='This process is required to apply any changes to on-chain '
               'settings used by the Sawtooth platform.',
        formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument(
        '-C', '--connect',
        help='specify the endpoint for the validator connection (default: '
             'tcp://localhost:4004) ')

    parser.add_argument(
        '-v', '--verbose',
        action='count',
        default=0,
        help='enable more verbose output to stderr')

    try:
        version = pkg_resources.get_distribution(DISTRIBUTION_NAME).version
    except pkg_resources.DistributionNotFound:
        version = 'UNKNOWN'

    parser.add_argument(
        '-V', '--version',
        action='version',
        version=(DISTRIBUTION_NAME + ' (Hyperledger Sawtooth) version {}')
        .format(version),
        help='display version information')

    return parser


def load_settings_config(first_config):
    default_settings_config = \
        load_default_settings_config()
    conf_file = os.path.join(get_config_dir(), 'settings.toml')

    toml_config = load_toml_settings_config(conf_file)

    return merge_settings_config(
        configs=[first_config, toml_config, default_settings_config])


def create_settings_config(args):
    return SettingsConfig(connect=args.connect)


def main(prog_name=os.path.basename(sys.argv[0]), args=None,
         with_loggers=True):
    if args is None:
        args = sys.argv[1:]
    parser = create_parser(prog_name)
    args = parser.parse_args(args)

    arg_config = create_settings_config(args)
    settings_config = load_settings_config(arg_config)
    processor = TransactionProcessor(url=settings_config.connect)

    if with_loggers is True:
        if args.verbose is None:
            verbose_level = 0
        else:
            verbose_level = args.verbose
        setup_loggers(verbose_level=verbose_level, processor=processor)

    handler = SettingsTransactionHandler()

    processor.add_handler(handler)

    try:
        processor.start()
    except KeyboardInterrupt:
        pass
    finally:
        processor.stop()

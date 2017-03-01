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

import hashlib
import sys
import argparse
import logging

from colorlog import ColoredFormatter

from sawtooth_sdk.processor.core import TransactionProcessor
from sawtooth_intkey.processor.handler import IntkeyTransactionHandler


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


def init_console_logging(verbose_level=2):
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    if verbose_level > 0:
        logger.addHandler(create_console_handler(verbose_level))


def parse_args(args):
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument('endpoint',
                        nargs='?',
                        default='localhost:40000',
                        help='Endpoint for the validator connection')
    parser.add_argument('-v', '--verbose',
                        action='count',
                        default=0,
                        help='Increase output sent to stderr')

    return parser.parse_args(args)


def main(args=sys.argv[1:]):
    opts = parse_args(args)

    init_console_logging(verbose_level=opts.verbose)

    processor = TransactionProcessor(url=opts.endpoint)

    # The prefix should eventually be looked up from the
    # validator's namespace registry.
    battleship_prefix = hashlib.sha512('intkey'.encode()).hexdigest()[0:6]
    handler = IntkeyTransactionHandler(namespace_prefix=battleship_prefix)

    processor.add_handler(handler)

    try:
        processor.start()
    except KeyboardInterrupt:
        pass
    finally:
        processor.stop()

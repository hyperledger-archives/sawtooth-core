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

import os
import sys
import argparse
import logging
import traceback

from colorlog import ColoredFormatter

from sawtooth.simulator import SawtoothWorkloadSimulator


def create_console_handler(verbose_level):
    logger = logging.StreamHandler()
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

    logger.setFormatter(formatter)

    if verbose_level == 0:
        logger.setLevel(logging.WARN)
    elif verbose_level == 1:
        logger.setLevel(logging.INFO)
    else:
        logger.setLevel(logging.DEBUG)

    return logger


def setup_loggers(verbose_level):
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logger.addHandler(create_console_handler(verbose_level))


def parse_args(args):
    parser = argparse.ArgumentParser()

    parser.add_argument('--url',
                        metavar="",
                        help='Base validator URL (default: %(default)s)',
                        default="http://127.0.0.1:8800")
    parser.add_argument('--workload',
                        help='Transaction workload (default: %(default)s)',
                        default='sawtooth_xo.xo_workload.XoWorkload')
    parser.add_argument('--rate',
                        help='Transaction rate in transactions per minute '
                             '(default: %(default)s transactions/minute)',
                        type=int,
                        default=12)
    parser.add_argument('--discover',
                        help='How often, in minutes, to refresh validators '
                             'list (default: every %(default)s minute(s))',
                        type=int,
                        default=15)
    parser.add_argument('-v', '--verbose',
                        action='count',
                        help='enable more verbose output')

    opts = parser.parse_args(args)

    if opts.rate <= 0:
        parser.error("Transaction rate must be greater than zero")
    if opts.discover <= 0:
        parser.error("Validator discovery period must be greater than 0")

    return opts


def main(name=os.path.basename(sys.argv[0]), args=sys.argv[1:]):

    opts = parse_args(args)

    level = 0 if opts.verbose is None else opts.verbose
    setup_loggers(verbose_level=level)

    simulator = SawtoothWorkloadSimulator(opts)

    # pylint: disable=bare-except
    try:
        simulator.run()
    except KeyboardInterrupt:
        pass
    except SystemExit as e:
        raise e
    except:
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

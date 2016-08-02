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
import ConfigParser

from colorlog import ColoredFormatter

from sawtooth.simulator import SawtoothWorkloadSimulator

LOGGER = logging.getLogger(__name__)


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
                        help='Base validator URL')
    parser.add_argument('--workload',
                        help='Transaction workload')
    parser.add_argument('--rate',
                        help='Transaction rate in transactions per minute',
                        type=int)
    parser.add_argument('--discover',
                        help='How often, in minutes, to refresh validators '
                             'list',
                        type=int)
    parser.add_argument('--config',
                        help='Config file to provide base configuration for '
                             'the simulator and (possibly) the workload '
                             'generator.  Command-line options override '
                             'corresponding values in the configuration file')
    parser.add_argument('-v', '--verbose',
                        action='count',
                        help='Enable more verbose output')

    opts = parser.parse_args(args)

    if opts.rate is not None and opts.rate <= 0:
        parser.error("Transaction rate must be greater than zero")
    if opts.discover is not None and opts.discover <= 0:
        parser.error("Validator discovery period must be greater than 0")

    return opts


def load_configuration(opts):
    """
    Loads the configuration file, if it exists.  Otherwise, creates a default
    configuration and saves it.  It then applies any command-line argument
    overrides that exist.

    Args:
        opts: Command-line options

    Returns:
        A dictionary of key/value pairs that represent the base configuration
    """

    # Set up a configuration parser with default values
    config = ConfigParser.SafeConfigParser()
    config.add_section('Simulator')
    config.set('Simulator', 'url', 'http://127.0.0.1:8800')
    config.set('Simulator',
               'workload',
               'txnintegration.integer_key_workload.IntegerKeyWorkload')
    config.set('Simulator', 'rate', '12')
    config.set('Simulator', 'discover', '15')
    config.set('Simulator', 'verbose', '1')

    # If there was a configuration file command-line option, then we
    # will read it to override any of the defaults
    if opts.config is not None:
        if os.path.exists(opts.config):
            config.read(opts.config)
        else:
            raise Exception("Config file does not exist: {}".format(
                opts.config))

    # Otherwise, we are going to look in the default area
    # <user home>/.sawtooth/simulator.cfg) and if it is there, we are going
    # to read it.  If the file does not exist, go ahead and create a default
    # one for the user.
    else:
        config_file = \
            os.path.join(
                os.path.expanduser("~"),
                ".sawtooth",
                "simulator.cfg")
        if os.path.exists(config_file):
            config.read(config_file)
        else:
            if not os.path.exists(os.path.dirname(config_file)):
                os.makedirs(os.path.dirname(config_file))

            with open("{}.new".format(config_file), "w") as fd:
                config.write(fd)
            os.rename("{}.new".format(config_file), config_file)

    # Now override any configuration values with corresponding command-line
    # options that exist.
    if opts.url is not None:
        config.set('Simulator', 'url', opts.url)
    if opts.workload is not None:
        config.set('Simulator', 'workload', opts.workload)
    if opts.rate is not None:
        config.set('Simulator', 'rate', str(opts.rate))
    if opts.discover is not None:
        config.set('Simulator', 'discover', str(opts.discover))
    if opts.verbose is not None:
        config.set('Simulator', 'verbose', str(opts.verbose))

    return config


def main(name=os.path.basename(sys.argv[0]), args=sys.argv[1:]):

    opts = parse_args(args)
    config = load_configuration(opts)

    setup_loggers(verbose_level=config.getint('Simulator', 'verbose'))

    LOGGER.info('Simulator configuration:')
    for section in config.sections():
        for name, value in config.items(section):
            LOGGER.info('%s: %s = %s', section, name, value)

    simulator = SawtoothWorkloadSimulator(config)

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

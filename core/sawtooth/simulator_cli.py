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
import logging.handlers
import traceback
import ConfigParser
import time

from colorlog import ColoredFormatter
from sawtooth.simulator import SawtoothWorkloadSimulator

LOGGER = logging.getLogger(__name__)


def create_console_handler():
    logger = logging.StreamHandler()
    formatter = ColoredFormatter(
        fmt='%(log_color)s[%(asctime)s %(levelname)-8s%(module)s]%(reset)s '
            '%(white)s%(message)s',
        datefmt='%H:%M:%S',
        reset=True,
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red',
        })
    logger.setFormatter(formatter)

    return logger


def create_file_handler(config):
    # Make sure that the log dir exists before trying to create the logger
    log_dir = config.get('Simulator', 'log_dir')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Set up a rotating file handler.  We need to convert the log file max
    # size from MB to bytes (thus the multiply by 1024^2).  Note that if
    # maxBytes is zero, automatic rotation will not happen (zero is the
    # default value for 'log_max_size' if it is not set).
    logger = \
        logging.handlers.RotatingFileHandler(
            filename=os.path.join(
                log_dir,
                config.get('Simulator', 'log_file')),
            maxBytes=config.getint('Simulator', 'log_max_size') * 1024 * 1024,
            backupCount=config.getint('Simulator', 'log_backup_count'))
    formatter = \
        logging.Formatter(
            fmt='%(asctime)s.%(msecs).03d,%(levelname)s,%(module)s,'
                '%(message)s',
            datefmt='%Y-%m-%dT%H:%M:%S')

    formatter.converter = time.gmtime

    logger.setFormatter(formatter)

    return logger


def set_up_loggers(config):
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    # Convert the configuration verbose level to a logging module level
    logging_level = logging.DEBUG
    verbose_level = config.getint('Simulator', 'verbose')
    if verbose_level == 0:
        logging_level = logging.WARN
    elif verbose_level == 1:
        logging_level = logging.INFO

    # Create a logger for console and add it as a handler
    console_logger = create_console_handler()
    console_logger.setLevel(logging_level)
    logger.addHandler(console_logger)

    # Only add a file handler if the option has been specified
    # to do so.
    if config.getboolean('Simulator', 'log_file_enable'):
        file_logger = create_file_handler(config)
        file_logger.setLevel(logging_level)
        logger.addHandler(file_logger)

    return logger


def parse_args(args):
    parser = argparse.ArgumentParser()

    parser.add_argument('--url',
                        metavar="",
                        help='Base validator URL')
    parser.add_argument('--workload',
                        help='Transaction workload')
    parser.add_argument('--rate',
                        type=int,
                        help='Transaction rate in transactions per minute')
    parser.add_argument('--discover',
                        type=int,
                        help='How often, in minutes, to refresh validators '
                             'list')
    parser.add_argument('--config',
                        help='Config file to provide base configuration for '
                             'the simulator and (possibly) the workload '
                             'generator.  Command-line options override '
                             'corresponding values in the configuration file.')
    parser.add_argument('--log-file-enable',
                        help='Log all console messages to a file also.  If '
                             'this option is not specified or log_file_enable '
                             'is not set to True in the configuration file, '
                             'all other log file related options are ignored.',
                        action='store_true',
                        default=None)
    parser.add_argument('--log-file',
                        help='Name of file used for logging.')
    parser.add_argument('--log-dir',
                        help='Name of directory into which log file will be '
                             'saved.')
    parser.add_argument('--log-max-size',
                        type=int,
                        help='The maximum size, in MB, of the log file '
                             'before it is rotated.  A value of 0 indicates '
                             'no maximum size.  If this option is '
                             'not specified on the command line, is 0, or '
                             'log_max_size is not specified in the '
                             'configuration file the log file is not '
                             'rotated and --log-backup-count is ignored.  '
                             'Ignored if --log-file-enable is not specified.')
    parser.add_argument('--log-backup-count',
                        type=int,
                        help='The number of backup log files to retain.  If '
                             'the --log-max-size option is not provided on '
                             'the command line with a non-zero value and '
                             'log_max_size is not set to a non-zero value '
                             'in the configuration file, this option is '
                             'ignored.')
    parser.add_argument('-u', '--update-frequency',
                        help='time in seconds between display of transaction '
                             'rate updates.')
    parser.add_argument('-v', '--verbose',
                        action='count',
                        help='Enable more verbose output (can be specified '
                             'multiple times to generate more verbose logging'
                             ').')

    opts = parser.parse_args(args)

    if opts.rate is not None and opts.rate <= 0:
        parser.error('Transaction rate must be greater than zero')
    if opts.discover is not None and opts.discover <= 0:
        parser.error('Validator discovery period must be greater than 0')
    if opts.log_max_size is not None and opts.log_max_size < 0:
        parser.error('Maximum log size must be greater than or equal to 0')
    if opts.log_backup_count is not None and opts.log_backup_count <= 0:
        parser.error('Backup count must be greater than 0')

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
    config.set('Simulator', 'log_file_enable', 'False')
    config.set('Simulator', 'log_file', 'simulator.log')
    config.set(
        'Simulator',
        'log_dir',
        os.path.join(os.path.expanduser('~'), '.sawtooth/logs'))
    config.set('Simulator', 'log_max_size', '0')
    config.set('Simulator', 'log_backup_count', '10')
    config.set('Simulator', 'verbose', '0')
    config.set('Simulator', 'update_frequency', '60')

    # If there was a configuration file command-line option, then we
    # will read it to override any of the defaults
    if opts.config is not None:
        if os.path.exists(opts.config):
            config.read(opts.config)
        else:
            raise Exception('Config file does not exist: {}'.format(
                opts.config))

    # Otherwise, we are going to look in the default area
    # <user home>/.sawtooth/simulator.cfg) and if it is there, we are going
    # to read it.  If the file does not exist, go ahead and create a default
    # one for the user.
    else:
        config_file = \
            os.path.join(
                os.path.expanduser('~'),
                '.sawtooth',
                'simulator.cfg')
        if os.path.exists(config_file):
            config.read(config_file)
        else:
            if not os.path.exists(os.path.dirname(config_file)):
                os.makedirs(os.path.dirname(config_file))

            with open('{}.new'.format(config_file), 'w') as fd:
                config.write(fd)
            os.rename('{}.new'.format(config_file), config_file)

    if config.getint('Simulator', 'rate') <= 0:
        raise ConfigParser.ParsingError(
            'Transaction rate in config file must be greater than zero')
    if config.getint('Simulator', 'discover') <= 0:
        raise ConfigParser.ParsingError(
            'Discovery rate in config file must be greater than zero')
    if config.getint('Simulator', 'log_max_size') < 0:
        raise ConfigParser.ParsingError(
            'Maximum log file size in config file must be greater than or '
            'equal to zero')
    if config.getint('Simulator', 'log_backup_count') <= 0:
        raise ConfigParser.ParsingError(
            'Log file backup count in config file must be greater than zero')
    if config.getint('Simulator', 'verbose') < 0:
        raise ConfigParser.ParsingError(
            'Log file verbosity in config file must be greater than or '
            'equal to zero')

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
    if opts.log_file_enable is not None:
        config.set('Simulator', 'log_file_enable', str(opts.log_file_enable))
    if opts.log_file is not None:
        config.set('Simulator', 'log_file', opts.log_file)
    if opts.log_dir is not None:
        config.set('Simulator', 'log_dir', opts.log_dir)
    if opts.log_max_size is not None:
        config.set('Simulator', 'log_max_size', str(opts.log_max_size))
    if opts.log_backup_count is not None:
        config.set('Simulator', 'log_backup_count', str(opts.log_backup_count))
    if opts.update_frequency is not None:
        config.set('Simulator', 'update_frequency', str(opts.update_frequency))

    return config


def main(name=os.path.basename(sys.argv[0]), args=sys.argv[1:]):

    opts = parse_args(args)
    config = load_configuration(opts)
    set_up_loggers(config)

    LOGGER.info('Simulator configuration:')
    for section in config.sections():
        for name, value in config.items(section):
            LOGGER.warn('%s: %s = %s', section, name, value)

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

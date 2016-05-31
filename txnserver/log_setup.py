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
import os
import sys
import warnings

from colorlog import ColoredFormatter


class LogWriter(object):
    def __init__(self, logger, level):
        self.logger = logger
        self.level = level

    def write(self, line):
        if line != '\n':
            self.logger.log(self.level, line.rstrip())


def create_file_handler(logfile, loglevel):
    if logfile == '-':
        flog = logging.StreamHandler(sys.stdout)
    else:
        if not os.path.isdir(os.path.abspath(os.path.dirname(logfile))):
            warnings.warn("Logging directory {0} does not exist".format(
                os.path.abspath(os.path.dirname(logfile))))
            sys.exit(-1)

        flog = logging.FileHandler(logfile)
    flog.setFormatter(logging.Formatter(
        '[%(asctime)s %(name)s %(levelname)s] %(message)s', "%H:%M:%S"))
    flog.setLevel(loglevel)

    return flog


def create_console_handler(config, verbose_level):
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


def setup_loggers(config, verbose_level=2, capture_std_output=False):
    loglevel = getattr(
        logging, config["LogLevel"]) if 'LogLevel' in config else logging.WARN
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    logfile = config['LogFile']
    if 'LogFile' in config:
        if config['LogFile'] == '__screen__':
            raise Exception("LogFile __screen__ no longer supported, "
                            "use --verbose instead.")
        else:
            logger.addHandler(create_file_handler(logfile, loglevel))

    if verbose_level > 0:
        logger.addHandler(create_console_handler(config, verbose_level))

    if capture_std_output:
        sys.stdout = LogWriter(logging.getLogger("STDOUT"), logging.INFO)
        sys.stderr = LogWriter(logging.getLogger("STDERR"), logging.ERROR)

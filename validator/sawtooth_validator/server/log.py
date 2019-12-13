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
import logging.config
import sys
import os

from colorlog import ColoredFormatter
from sawtooth_validator.exceptions import LocalConfigurationError


class LogWriter:
    def __init__(self, logger, level):
        self.logger = logger
        self.level = level

    def write(self, line):
        if line != '\n':
            self.logger.log(self.level, line.rstrip())


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


def init_console_logging(verbose_level=2, capture_std_output=False):
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    logger.addHandler(create_console_handler(verbose_level))

    if capture_std_output:
        sys.stdout = LogWriter(logging.getLogger("STDOUT"), logging.INFO)
        sys.stderr = LogWriter(logging.getLogger("STDERR"), logging.ERROR)


def log_configuration(log_config=None, log_dir=None, name=None):
    if log_config is not None:
        logging.config.dictConfig(log_config)
    else:
        try:
            log_filename = os.path.join(log_dir, name)
            debug_handler = logging.FileHandler(log_filename + "-debug.log")
            debug_handler.setFormatter(logging.Formatter(
                '[%(asctime)s.%(msecs)03d [%(threadName)s] %(module)s'
                ' %(levelname)s] %(message)s', "%H:%M:%S"))
            debug_handler.setLevel(logging.DEBUG)

            error_handler = logging.FileHandler(log_filename + "-error.log")
            error_handler.setFormatter(logging.Formatter(
                '[%(asctime)s.%(msecs)03d [%(threadName)s] %(module)s'
                ' %(levelname)s] %(message)s', "%H:%M:%S"))
            error_handler.setLevel(logging.ERROR)
        except IOError as e:
            raise LocalConfigurationError("Error: {}".format(str(e)))

        logging.getLogger().addHandler(error_handler)
        logging.getLogger().addHandler(debug_handler)

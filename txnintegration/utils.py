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

import json
import logging
import os
import random
import re
import string
import sys
import time
import warnings

import pybitcointools
from colorlog import ColoredFormatter


class ExitError(Exception):
    def __init__(self, what):
        self.what = what

    def __str__(self):
        return self.what


class Progress:
    def __init__(self, msg=None):
        if msg:
            sys.stdout.write(msg + ": ")

    def __enter__(self):
        self.start = time.time()
        return self

    def __exit__(self, type, value, traceback):
        sys.stdout.write(" {0:.2f}S \n".format(time.time() - self.start))
        sys.stdout.flush()

    def step(self):
        sys.stdout.write(".")
        sys.stdout.flush()


suffixes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']


def human_size(nbytes):
    if nbytes == 0:
        return '0 B'
    i = 0
    while nbytes >= 1024 and i < len(suffixes) - 1:
        nbytes /= 1024.
        i += 1
    f = ('%.2f' % nbytes).rstrip('0').rstrip('.')
    return '%s %s' % (f, suffixes[i])


class Timer:
    def __init__(self):
        pass

    def __enter__(self):
        self.start = time.time()
        return self

    def __exit__(self, type, value, traceback):
        print time.time() - self.start

    def elapsed(self):
        return time.time() - self.start


class TimeOut:
    def __init__(self, wait):
        self.WaitTime = wait
        self.ExpireTime = time.time() + wait

    def is_timed_out(self):
        return time.time() > self.ExpireTime

    def __call__(self, *args, **kwargs):
        return time.time() > self.ExpireTime


def generate_private_key():
    return pybitcointools.encode_privkey(pybitcointools.random_key(), 'wif')


def get_address_from_private_key_wif(key):
    return pybitcointools.privtoaddr(pybitcointools.decode_privkey(key, 'wif'))


def read_key_file(keyfile):
    with open(keyfile, "r") as fd:
        key = fd.read().strip()
    return key


def write_key_file(keyfile, key):
    with open(keyfile, "w") as wif_fd:
        wif_fd.write(key)
        wif_fd.write("\n")


def random_name(len=16):
    return '/' + ''.join(
        random.SystemRandom().choice(string.ascii_uppercase + string.digits)
        for _ in range(len))


def parse_configuration_file(filename):
    cpattern = re.compile('##.*$')

    with open(filename) as fp:
        lines = fp.readlines()

    text = ""
    for line in lines:
        text += re.sub(cpattern, '', line) + ' '

    return json.loads(text)


def prompt_yes_no(question):
    # raw_input returns the empty string for "enter"
    yes = {'yes', 'y', 'ye', ''}
    no = {'no', 'n'}

    while True:
        sys.stdout.write("{} ('yes' or 'no')[yes]?".format(question))
        choice = raw_input().lower()
        if choice in yes:
            return True
        elif choice in no:
            return False


def find_txn_validator():
    validator = None
    scriptDir = os.path.dirname(os.path.realpath(__file__))
    search_path = ""
    if "CURRENCYHOME" in os.environ:
        search_path = os.path.join(
            os.environ['CURRENCYHOME'], 'bin') \
            + os.pathsep \
            + os.path.realpath(os.path.join(scriptDir, '..', 'bin'))
    else:
        search_path = os.path.realpath(
            os.path.join(scriptDir, '..', 'bin'))

    if 'PATH' in os.environ:
        search_path = search_path + os.pathsep + os.environ['PATH']

    for directory in search_path.split(os.pathsep):
        if os.path.exists(os.path.join(directory, 'txnvalidator')):
            validator = os.path.join(directory, 'txnvalidator')
            return validator

    if validator is None:
        print("txnvalidator: {}".format(validator))
        raise ExitError("Could not find txnvalidator in your $PATH")

    return validator


def setup_loggers(config):
    loglevel = getattr(
        logging, config["LogLevel"]) if 'LogLevel' in config else logging.WARN
    logger = logging.getLogger()
    logger.setLevel(loglevel)

    if 'LogFile' in config and config['LogFile'] != '__screen__':
        logfile = config['LogFile']
        if not os.path.isdir(os.path.dirname(logfile)):
            warnings.warn("Logging directory {0} does not exist".format(
                os.path.abspath(os.path.dirname(logfile))))
            sys.exit(-1)

        flog = logging.FileHandler(logfile)
        flog.setFormatter(logging.Formatter(
            '[%(asctime)s, %(levelno)d, %(module)s] %(message)s', "%H:%M:%S"))
        logger.addHandler(flog)
    else:
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
        clog.setLevel(loglevel)
        logger.addHandler(clog)

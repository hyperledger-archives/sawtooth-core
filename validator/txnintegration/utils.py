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

from __future__ import print_function

import json
import logging
import os
import random
import re
import string
import sys
import time
import warnings

from colorlog import ColoredFormatter
import yaml

from sawtooth_signing import pbct_nativerecover as signing
from txnintegration.exceptions import ExitError
from sawtooth.cli.main import main as sawtooth_cli_entry_point
from sawtooth.client import SawtoothClient


def sawtooth_cli_intercept(cmd_string):
    '''
    Isolates code intercepts of the sawtooth cli command line interface.  We
    rely on the sawtooth cli to sanitize input via its argparse derivation.
    Args:
        cmd_string: (str)
    Returns:
        None
    '''
    sawtooth_cli_entry_point(args=cmd_string.split(), with_loggers=False)


def get_blocklists(urls):
    ret = [(SawtoothClient(base_url=u)).get_block_list() for u in urls]
    for arr in ret:
        arr.reverse()
    return ret


def is_convergent(urls, tolerance=2, standard=5, verbose=False):
    '''
    Args:
        urls (list<str>):   List of validator urls whose chains are expected
            to converge
        tolerance (int):    Length in blocks of permissible intra-validator
            forks
        standard (int):     A variable intended to guarantee that our block
            level identity checks have significant data to operate on.
            Conceptually, depends on the value of tolerance:
                case(tolerance):
                    0:          minimum # of blocks required per validator
                    otherwise:  minimum # of converged blocks required per
                                divergent block (per validator)
            Motivation: We want to compare identity across the network on
            some meaningfully large set of blocks.  Introducing fork
            tolerance is problematic: the variable tolerance which is used
            to trim the ends of each ledger's block-chain could be abused
            to trivialize the test.  Therefore, as tolerance is increased
            (if non-zero), we use standard to proportionally increase the
            minimum number of overall blocks required by the test.
    Returns:
        (bool)
    '''
    # check for block id convergence across network:
    sample_size = max(1, tolerance) * standard
    if verbose is True:
        print("testing block-level convergence with min sample size:", end=' ')
        print(" %s (after tolerance: %s)" % (sample_size, tolerance))
    # ...get all blockids from each server, newest last
    block_lists = get_blocklists(urls)
    # ...establish preconditions
    max_mag = len(max(block_lists, key=len))
    min_mag = len(min(block_lists, key=len))
    if max_mag - min_mag > tolerance:
        if verbose is True:
            print('block list magnitude differences (%s) '
                  'exceed tolerance (%s)' % (max_mag - min_mag, tolerance))
        return False
    effective_sample_size = max_mag - tolerance
    if verbose is True:
        print('effective sample size: %s' % effective_sample_size)
    if effective_sample_size < sample_size:
        if verbose is True:
            print('not enough target samples to determine convergence')
        return False
    # ...(optionally) permit reasonable forks by normalizing lists
    if tolerance > 0:
        block_lists = [
            block_list[0:effective_sample_size]
            for block_list in block_lists
        ]
    # ...id-check (possibly normalized) cross-server block chains
    for (i, block_list) in enumerate(block_lists):
        if block_lists[0] != block_list:
            if verbose is True:
                print('%s is divergent:\n\t%s vs.\n\t%s' % (
                    urls[i], block_lists[0], block_list))
            return False
    if verbose is True:
        print('network exhibits tolerable convergence')
    return True


def get_statuslist(urls):
    ret = None
    try:
        ret = [(SawtoothClient(base_url=u)).get_status() for u in urls]
    except Exception as e:
        print(e)
        raise
    return ret


def sit_rep(urls, verbosity=1):
    def print_helper(data, tag, key):
        print(tag)
        for x in data:
            print('\t%s: %s' % (x['Status']['Name'], x['Status'][key]))
    statuslist = get_statuslist(urls)
    reports = [{'Status': statuslist[i]} for i in range(len(urls))]
    blocklists = get_blocklists(urls)
    for (idx, rpt) in enumerate(reports):
        rpt['Name'] = rpt['Status']['Name']
        rpt['Status']['Blocks'] = [x[:4] for x in blocklists[idx]]
    if verbosity > 1:
        print_helper(reports, 'blacklist', "Blacklist")
        print_helper(reports, 'allpeers', "AllPeers")
    if verbosity > 0:
        print_helper(reports, 'peers', "Peers")
        print_helper(reports, 'blocks', "Blocks")
    return reports


class StaticNetworkConfig(object):
    def __init__(self, n, q=None, base_name='validator', base_port=9000,
                 base_http_port=8000):
        self.n_mag = n
        assert self.n_mag >= 1
        self.q_mag = n if q is None else q
        assert self.q_mag >= 1
        assert self.q_mag <= n
        self.keys = [generate_private_key() for _ in range(n)]
        self.nodes = [
            {
                "NodeName": "{0}-{1}".format(base_name, idx),
                "Identifier": get_address_from_private_key_wif(wif),
                "Host": "localhost",
                "Port": base_port + idx,
                "HttpPort": base_http_port + idx,
            }
            for (idx, wif) in enumerate(self.keys)
        ]

    def get_nodes(self):
        return self.nodes

    def get_node(self, idx):
        return self.nodes[idx]

    def get_key(self, idx):
        return self.keys[idx]


class Progress(object):
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


class Timer(object):
    def __init__(self):
        pass

    def __enter__(self):
        self.start = time.time()
        return self

    def __exit__(self, type, value, traceback):
        print(time.time() - self.start)

    def elapsed(self):
        return time.time() - self.start


class TimeOut(object):
    def __init__(self, wait):
        self.WaitTime = wait
        self.ExpireTime = time.time() + wait

    def is_timed_out(self):
        return time.time() > self.ExpireTime

    def __call__(self, *args, **kwargs):
        return time.time() > self.ExpireTime


def find_or_create_test_key(key_base_name, key_dir=None, quiet=True):
    '''
    Interface to sawtooth cli: creates .wif key file if it does not exist, and
    returns a tupple containing all pertinent information.  Useful for testing.
    Args:
        key_base_name: (str)
        key_dir: (str)
    Returns: (tupple)
        key_file: (str)
        private_key: (str)
        public_key: (str)
    '''
    use_key_dir = key_dir is not None and not os.path.isabs(key_base_name)
    key_file = key_base_name
    if not key_file.endswith('.wif'):
        key_file += '.wif'
    if use_key_dir:
        key_file = os.path.join(key_dir, key_file)
    if not os.path.isfile(key_file):
        if key_base_name.endswith('.wif'):
            key_base_name = ''.join(key_base_name.split('.')[:-1])
        cmd = 'keygen %s' % key_base_name
        if use_key_dir:
            cmd += ' --key-dir %s' % key_dir
        if quiet is True:
            cmd += ' -q'
        sawtooth_cli_intercept(cmd)
    assert os.path.exists(key_file)

    with open(key_file, 'r') as f:
        key_str = f.read()
    signing_key = key_str.split('\n')[0]
    identifier = signing.generate_identifier(
        signing.generate_pubkey(signing_key))

    addr_file = '.'.join(key_file.split('.')[:-1]) + '.addr'
    if not os.path.exists(addr_file):
        with open(addr_file, 'w') as f:
            f.write('{}\n'.format(identifier))

    return key_file, signing_key, identifier


def generate_private_key():
    return signing.encode_privkey(signing.generate_privkey(), 'wif')


def get_address_from_private_key_wif(key):
    return signing.generate_identifier(
        signing.generate_pubkey(signing.decode_privkey(key, 'wif')))


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


def find_executable(executable_name):
    ret_val = None
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
        if os.path.exists(os.path.join(directory, executable_name)):
            ret_val = os.path.join(directory, executable_name)
            return ret_val
    if ret_val is None:
        print("%s: %s" % (executable_name, ret_val))
        raise ExitError("Could not find %s in your $PATH" % executable_name)
    return ret_val


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


def load_log_config(log_config_file):
    log_dic = None
    if log_config_file.split(".")[-1] == "js":
        try:
            with open(log_config_file) as log_config_fd:
                log_dic = json.load(log_config_fd)
        except IOError, ex:
            raise ExitError("Could not read log config: {}"
                            .format(str(ex)))
    elif log_config_file.split(".")[-1] == "yaml":
        try:
            with open(log_config_file) as log_config_fd:
                log_dic = yaml.load(log_config_fd)
        except IOError, ex:
            raise ExitError("Could not read log config: {}"
                            .format(str(ex)))
    else:
        raise ExitError("LogConfigFile type not supported: {}"
                        .format(log_config_file))
    return log_dic

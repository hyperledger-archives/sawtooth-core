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
import psutil
import collections

import pybitcointools
from colorlog import ColoredFormatter
import yaml

from txnintegration.exceptions import ExitError
from sawtooth.client import LedgerWebClient


def get_blocklists(urls):
    ret = None
    try:
        ret = [(LedgerWebClient(url=u)).get_block_list() for u in urls]
    except Exception as e:
        print e.message
        raise
    for arr in ret:
        arr.reverse()
    return ret


def is_convergent(urls, tolerance=2, standard=5):
    # check for block id convergence across network:
    sample_size = max(1, tolerance) * standard
    print "testing block-level convergence with min sample size:",
    print " %s (after tolerance: %s)" % (sample_size, tolerance)
    # ...get all blockids from each server, newest last
    block_lists = get_blocklists(urls)
    # ...establish preconditions
    max_mag = len(max(block_lists, key=len))
    min_mag = len(min(block_lists, key=len))
    if max_mag - min_mag > tolerance:
        print 'block list magnitude differences (%s) ' \
              'exceed tolerance (%s)' % (max_mag - min_mag, tolerance)
        return False
    effective_sample_size = max_mag - tolerance
    print 'effective sample size: %s' % effective_sample_size
    if effective_sample_size < sample_size:
        print 'not enough target samples to determine convergence'
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
            print '%s is divergent:\n\t%s vs.\n\t%s' % (
                urls[i], block_lists[0], block_list)
            return False
    print 'network exhibits tolerable convergence'
    return True


def get_statuslist(urls):
    ret = None
    try:
        ret = [(LedgerWebClient(url=u)).get_status() for u in urls]
    except Exception as e:
        print e
        raise
    return ret


def sit_rep(urls, verbosity=1):
    def print_helper(data, tag, key):
        print tag
        for x in data:
            print '\t%s: %s' % (x['Status']['Name'], x['Status'][key])
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
                 base_http_port=8000, use_quorum=False):
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
        self.use_quorum = use_quorum

    def get_nodes(self):
        return self.nodes

    def get_quorum(self, tgt, dfl=None):
        '''
        This is a hack 'wrapping' function intended to ensure that all nodes
        enjoy quorum intersection.
        Args:
            tgt: node index for which we need a peer list
            dfl: Q override if not self.use_quorum
        Returns:
            peers: a list of q node NodeNames (including the requestor)
            gathered by modulating around the nodelist
        '''
        dfl = [] if dfl is None else dfl
        peers = dfl
        if self.use_quorum:
            peers = [x['NodeName'] for x in self.nodes]
            assert len(peers) == len(set(peers))
            return [peers[(tgt + i) % (self.n_mag)] for i in range(self.q_mag)]

    def get_node(self, idx):
        return self.nodes[idx]

    def get_key(self, idx):
        return self.keys[idx]

    def print_quorum_schema(self):
        '''
        A dev-only utility to assist in manually crafting hardcoded config
        files when manually testing/pogramming.  Includes the SigningKey as
        part of each node, as well as the list of its possible quorum members.
        Obviously, you'd never want to include the SigningKey in a shared
        configuation file.
        '''
        ret = []
        for (i, nd) in enumerate(self.nodes):
            x = nd.copy()
            x["SigningKey"] = self.keys[i]
            x["Quorum"] = self.get_quorum(i)
            ret.append(x)
        print json.dumps(ret, indent=4)


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
        print time.time() - self.start

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
        print "txnvalidator: {}".format(validator)
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


class StatsCollector(object):
    def __init__(self):
        self.statslist = []

    def get_names(self):
        """
        Returns: All data element names as list - for csv writer (header)
        """
        names = []

        for stat in self.statslist:
            statname = type(stat).__name__
            for name in stat._fields:
                names.append(statname + "_" + name)

        return names

    def get_data(self):
        """
        Returns: All data element values in list - for csv writer
        """
        values = []

        for stat in self.statslist:
            for value in stat:
                values.append(value)

        return values

    def get_data_as_dict(self):
        """
        Returns: returns platform stats as dictionary - for stats web interface
        """
        p_stats = collections.OrderedDict()

        for stat in self.statslist:
            statname = type(stat).__name__
            p_stats[statname] = stat._asdict()

        return p_stats

    def pprint_stats(self):
        p_stats = self.get_data_as_dict()
        print json.dumps(p_stats, indent=4)


CpuStats = collections.namedtuple("scpu",
                                  'percent '
                                  'user_time '
                                  'system_time '
                                  'idle_time')


class PlatformStats(StatsCollector):
    def __init__(self):
        super(PlatformStats, self).__init__()

        self.get_stats()

    def get_stats(self):
        cpct = psutil.cpu_percent(interval=0)
        ctimes = psutil.cpu_times_percent()
        self.cpu_stats = CpuStats(cpct, ctimes.user, ctimes.system,
                                  ctimes.idle)

        self.vmem_stats = psutil.virtual_memory()
        self.disk_stats = psutil.disk_io_counters()
        self.net_stats = psutil.net_io_counters()

        # must create new stats list each time stats are updated
        # because named tuples are immutable
        self.statslist = [self.cpu_stats, self.vmem_stats, self.disk_stats,
                          self.net_stats]

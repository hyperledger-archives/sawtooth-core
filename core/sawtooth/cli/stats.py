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

import signal
import traceback

from twisted.internet import reactor
from twisted.internet import task

from sawtooth.cli.stats_lib.stats_utils import SignalHandler

from sawtooth.cli.stats_lib.stats_print import StatsPrintManager

from sawtooth.cli.stats_lib.topology_stats import TopologyManager

from sawtooth.cli.stats_lib.stats_writers import StatsSnapshotWriter
from sawtooth.cli.stats_lib.stats_writers import CsvManager

from sawtooth.cli.stats_lib.platform_stats import PlatformStatsManager

from sawtooth.cli.stats_lib.validator_stats import ValidatorStatsManager
from sawtooth.cli.stats_lib.validator_stats import SystemStatsManager

from sawtooth.cli.stats_lib.endpoint_manager import EndpointManager

from sawtooth.cli.stats_lib.fork_detect import BranchManager

from sawtooth.cli.exceptions import CliException

CURSES_IMPORTED = True
try:
    import curses
except ImportError:
    CURSES_IMPORTED = False


class SawtoothStats(object):
    def __init__(self, endpoint_manager, config):
        self.epm = endpoint_manager
        self.config = config
        self.running = True

        self.stats_modules = []

        self.signal_handler = SignalHandler()
        self.stats_modules.append(self.signal_handler)

        sawtooth_stats_config = config['SawtoothStats']
        self.max_loop_count = sawtooth_stats_config.get('max_loop_count', 0)
        self.loop_count = 0

        modules = [
            ValidatorStatsManager,
            SystemStatsManager,
            PlatformStatsManager,
            TopologyManager,
            BranchManager,
            StatsPrintManager,
            CsvManager,
            StatsSnapshotWriter
        ]

        for module in modules:
            instance = module(self.epm, self.config)
            self.stats_modules.append(instance)

        for module in self.stats_modules:
            module.initialize(self.stats_modules)

    def stats_loop(self):
        # connect
        for module in self.stats_modules:
            module.connect()
        # collect
        for module in self.stats_modules:
            module.collect()
        # process
        for module in self.stats_modules:
            module.process()
        # analyze
        for module in self.stats_modules:
            module.analyze()
        # report
        for module in self.stats_modules:
            module.report()

        # loop_counter
        if self.max_loop_count > 0:
            self.loop_count += 1
            if self.loop_count > self.max_loop_count:
                reactor.stop()

    def signal_snapshot_write(self, signum, frame):
        self.signal_handler.sig_user1 = True

    def stop_modules(self):
        if self.running:
            for module in self.stats_modules:
                module.stop()
            self.running = False

    def stats_loop_stop(self, reason):
        self.stop_modules()
        return reason

    def stats_loop_error(self, reason):
        self.stop_modules()
        return reason

    def stats_stop(self):
        self.stop_modules()


def add_stats_parser(subparsers, parent_parser):
    parser = subparsers.add_parser('stats', parents=[parent_parser])

    parser.add_argument('--url',
                        metavar="",
                        help='Base validator url '
                             '(default: %(default)s)',
                        default="http://localhost:8800")
    parser.add_argument('--stats-time',
                        metavar="",
                        help='Interval between stats updates (s) '
                             '(default: %(default)s)',
                        default=3,
                        type=int)
    parser.add_argument('--endpoint-time',
                        metavar="",
                        help='Interval between endpoint updates (s) '
                             '(default: %(default)s)',
                        default=10,
                        type=int)
    parser.add_argument('--csv-enable-summary',
                        metavar="",
                        help='Enables summary CSV file generation'
                             '(default: %(default)s)',
                        default=False,
                        type=bool)
    parser.add_argument('--csv-enable-validator',
                        metavar="",
                        help='Enables per-validator CSV file generation'
                             '(default: %(default)s)',
                        default=False,
                        type=bool)


def reactor_startup(stats_interval, endpoint_interval, stats_man, ep_man):
    # set up loop to periodically collect and report stats
    stats_loop = task.LoopingCall(stats_man.stats_loop)
    stats_loop_deferred = stats_loop.start(stats_interval)
    # set up loop stop and error handlers
    stats_loop_deferred.addCallback(stats_man.stats_loop_stop)
    stats_loop_deferred.addErrback(stats_man.stats_loop_stop)
    stats_loop_deferred.addErrback(handle_loop_error, "stats loop")

    # set up loop to periodically update the list of validator endpoints
    ep_loop = task.LoopingCall(ep_man.endpoint_discovery_loop)
    ep_loop_deferred = ep_loop.start(endpoint_interval)
    # set up loop stop and error handlers
    ep_loop_deferred.addCallback(ep_man.endpoint_loop_stop)
    ep_loop_deferred.addErrback(ep_man.update_endpoint_loop_error)
    ep_loop_deferred.addErrback(handle_loop_error, "endpoint loop")


def handle_loop_error(reason, other_reason):
    print("stopping in main due to error in {}".format(other_reason))
    print(reason)
    print("stopping sawtooth stats")
    reactor.stop()


def default_config():
    config = {}
    config['CsvManager'] = {}
    config['CsvManager']['csv_enable_summary'] = False
    config['CsvManager']['csv_enable_validator'] = False
    config['EndpointManager'] = {}
    config['EndpointManager']['urls'] = ["http://localhost:8899"]
    config['EndpointManager']['interval'] = 10
    config['SawtoothStats'] = {}
    config['SawtoothStats']['interval'] = 3
    config['SawtoothStats']['max_loop_count'] = 0
    config['StatsPrint'] = {}
    config['StatsPrint']['print_all'] = False
    return config


def update_config(config, opts):
    config['CsvManager']['csv_enable_summary'] = opts.csv_enable_summary
    config['CsvManager']['csv_enable_validator'] = opts.csv_enable_validator
    config['EndpointManager']['urls'] = [opts.url]
    config['EndpointManager']['interval'] = opts.endpoint_time
    config['SawtoothStats']['interval'] = opts.stats_time
    return config


def update_config_dict(new_conf, default_conf):
    for key1 in set(new_conf) & set(default_conf):
        for key2 in set(new_conf[key1]) & set(default_conf[key1]):
            default_conf[key1][key2] = new_conf[key1][key2]


def run_stats(url, config_opts=None, config_dict=None):
    try:
        config = default_config()

        # update defaults with cli options if provided
        if config_opts is None:
            config['EndpointManager']['urls'] = [url]
        else:
            update_config(config, config_opts)

        if config_dict is not None:
            update_config_dict(config_dict, config)

        epm = EndpointManager(config['EndpointManager']['urls'])
        ss = SawtoothStats(epm, config)

        # set up SIGUSR1 handler for stats snapshots
        signal.signal(signal.SIGUSR1, ss.signal_snapshot_write)

        reactor_startup(config['SawtoothStats']['interval'],
                        config['EndpointManager']['interval'],
                        ss,
                        epm)

        reactor.run()

        ss.stats_stop()

    except Exception as e:
        if CURSES_IMPORTED:
            # its possible that exception occurred before curses.initscr()
            # was called; call in try block to avoid throwing additional error
            try:
                curses.endwin()
                print("curses window existed")
            except curses.error as ce:
                print("curses window did not exist")
                print(ce)
        raise e


def do_stats(opts):
    try:
        run_stats(opts.url, opts)
    except Exception as e:
        traceback.print_exc()
        raise CliException(e)

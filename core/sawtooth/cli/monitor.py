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

import traceback
import logging

from twisted.internet import reactor
from twisted.internet import task

from sawtooth.cli.exceptions import CliException

from sawtooth.cli.stats_lib.validator_stats import SystemStatsManager
from sawtooth.cli.stats_lib.endpoint_manager import EndpointManager
from sawtooth.cli.stats_lib.platform_stats import PlatformStatsManager
from sawtooth.cli.stats_lib.validator_stats import ValidatorStatsManager

from sawtooth.cli.monitor_lib.monitor_modules import PlatformCpu
from sawtooth.cli.monitor_lib.monitor_modules import EventScriptManager
from sawtooth.cli.monitor_lib.monitor_modules import LogManager
from sawtooth.cli.monitor_lib.monitor_modules import ValidatorFailure
from sawtooth.cli.monitor_lib.monitor_modules import SigUsr1
from sawtooth.cli.monitor_lib.monitor_modules import ConnectionStatus


def add_monitor_parser(subparsers, parent_parser):
    parser = subparsers.add_parser('monitor', parents=[parent_parser])

    parser.add_argument('--url',
                        metavar="",
                        help='base validator url '
                             '(default: %(default)s)',
                        default="http://localhost:8800")
    parser.add_argument('--log-config',
                        metavar="",
                        help='log config file')
    parser.add_argument('--event-script',
                        metavar="",
                        help='event script to run')

    parser.add_argument(
        '--module',
        metavar="",
        action='append',
        help='module to load for event detection. '
             'options: platform-cpu, validator-fail, sigusr1. '
             'add multiple modules by specifying one module '
             'per flag.')

    parser.add_argument('--endpoint-time',
                        metavar="",
                        help='interval between endpoint updates (s) '
                             '(default: %(default)s)',
                        default=5,
                        type=int)
    parser.add_argument('--quit',
                        action='store_true',
                        help='quit monitor after script execution')


def default_config():
    config = {}
    config['EndpointManager'] = {}
    config['EndpointManager']['urls'] = ["http://localhost:8899"]
    config['EndpointManager']['interval'] = 10
    config['Monitor'] = {}
    config['Monitor']['interval'] = 5
    config['EventScript'] = None
    config['Modules'] = []
    config['Verbose'] = 0
    config['LogConfigFile'] = ''
    config['QuitAfterScriptRun'] = False
    return config


def update_config(config, opts):
    config['EndpointManager']['urls'] = [opts.url]
    config['EndpointManager']['interval'] = opts.endpoint_time
    config['Monitor']['interval'] = opts.endpoint_time
    config['EventScript'] = opts.event_script
    if opts.module is not None:
        config['Modules'] = opts.module
    if opts.verbose is not None:
        config['Verbose'] = opts.verbose
    config['LogConfigFile'] = opts.log_config
    config['QuitAfterScriptRun'] = opts.quit
    return config


def reactor_startup(stats_interval, endpoint_interval, stats_man, ep_man):
    # set up loop to periodically collect and report stats
    stats_loop = task.LoopingCall(stats_man.monitor_loop)
    stats_loop_deferred = stats_loop.start(stats_interval)
    # set up loop stop and error handlers
    stats_loop_deferred.addCallback(stats_man.monitor_loop_stop)
    stats_loop_deferred.addErrback(stats_man.monitor_loop_stop)
    stats_loop_deferred.addErrback(handle_loop_error, "monitor loop")

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
    print("stopping monitor")
    reactor.stop()


class Monitor(object):
    ''' This class is based on the SawtoothStats class in stats.py
        A new Monitor class was created due to some major differences in
        functionality and purpose. It uses libraries from stats_lib
        to detect events and the state of validator networks.
    '''

    def __init__(self, endpoint_manager, config):
        self.epm = endpoint_manager
        self.config = config
        self.running = True
        self.logger = logging.getLogger(__name__)
        self.verbose = config['Verbose']
        self.monitor_modules = []

        modules = [
            SystemStatsManager,
            PlatformStatsManager,
            ValidatorStatsManager,
            EventScriptManager,
            LogManager,
            ConnectionStatus
        ]

        if self.verbose == 0:
            print("Monitor modules loading:")
        else:   # Don't output redundant messages about modules if verbse > 0
            self.logger.info("Monitor modules to load: %s", str(self.verbose))

        while len(config['Modules']) > 0:
            already_appended = []
            m = config['Modules'].pop()
            print(m)     # display each loading module
            if m == 'platform-cpu' and m not in already_appended:
                modules.append(PlatformCpu)
                already_appended.append(m)
            elif m == 'validator-fail' and m not in already_appended:
                modules.append(ValidatorFailure)
                already_appended.append(m)
            elif m == 'sigusr1' and m not in already_appended:
                modules.append(SigUsr1)
                already_appended.append(m)
            else:
                if self.verbose == 0:
                    print("Module not known: {}".format(m))
                else:
                    self.logger.info("Module not known: %s", str(m))
                already_appended.append(m)

        for module in modules:
            instance = module(self.epm, self.config)
            self.monitor_modules.append(instance)

        for module in self.monitor_modules:
            if module.__class__.__name__ == 'EventScriptManager':
                module.pass_mon(self)

            module.initialize(self.monitor_modules)

    def monitor_loop(self):
        # connect
        for module in self.monitor_modules:
            module.connect()
        # collect
        for module in self.monitor_modules:
            module.collect()
        # process
        for module in self.monitor_modules:
            module.process()
        # analyze
        for module in self.monitor_modules:
            module.analyze()
        # report
        for module in self.monitor_modules:
            module.report()

    def stop_modules(self):
        if self.running:
            for module in self.monitor_modules:
                module.stop()
            self.running = False

    def monitor_loop_stop(self, reason):
        self.stop_modules()
        return reason

    def monitor_loop_error(self, reason):
        self.stop_modules()
        return reason

    def monitor_stop(self):
        self.stop_modules()


def run_monitor(url, config_opts=None):
    logger = logging.getLogger(__name__)

    if config_opts.verbose is None or config_opts.verbose == 0:
        print("Running sawtooth monitor")
        print("URl = {}".format(url))
    else:
        logger.info("Running sawtooth monitor")

    try:
        config = default_config()
        # update defaults with cli options if provided
        if config_opts is None:
            config['EndpointManager']['urls'] = [url]
        else:
            update_config(config, config_opts)

        epm = EndpointManager(config['EndpointManager']['urls'])
        mm = Monitor(epm, config)

        reactor_startup(config['Monitor']['interval'],
                        config['EndpointManager']['interval'],
                        mm,
                        epm)

        reactor.run()

        mm.monitor_stop()
        logger.info("Monitor stop")

    except Exception as e:
        raise e


def do_monitor(opts):
    try:
        run_monitor(opts.url, opts)
    except Exception as e:
        traceback.print_exc()
        raise CliException(e)

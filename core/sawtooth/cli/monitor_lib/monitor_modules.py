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
import logging.config
import signal
import subprocess
import sys
from collections import namedtuple
import yaml

from sawtooth.cli.stats_lib.stats_utils import StatsModule
from sawtooth.cli.stats_lib.platform_stats import PlatformStatsManager
from sawtooth.cli.stats_lib.validator_stats import ValidatorStatsManager
from sawtooth.cli.stats_lib.validator_stats import SystemStatsManager
from txnserver import log_setup


class EventScriptManager(StatsModule):
    '''
    Executes scripts based on events added to the event queue by
    monitor modules. Always loaded by monitor.
    '''

    def __init__(self, epm, config):
        super(EventScriptManager, self).__init__()
        self.event_queue = []
        self.script = config['EventScript']
        self.logger = logging.getLogger(__name__)
        self.quit_after_exec = config['QuitAfterScriptRun']
        self.mon = None
        self.event = namedtuple('event', ['sev', 'event_desc'])

    def initialize(self, module_list):
        self.module_list = module_list
        # self.mon = mon
        self.logger.info("Monitor: finished initialization of EventScript")

    def pass_mon(self, mon):
        self.mon = mon

    def run_script(self, sev):
        # Run script with event type as argument
        print("Running script {}".format(self.script))
        self.logger.info("Running script %s", self.script)
        args = [self.script, sev]
        output = subprocess.check_output(args)
        print("Script output: {}".format(output))
        self.logger.info("Script output %s", str(output))
        if self.quit_after_exec is True:
            print("Monitor quitting")
            self.logger.info("Monitor quitting")
            self.mon.monitor_stop()
            quit()

    def examine_queue(self):
        self.logger.debug(
            "Monitor: examine queue with length %s",
            str(len(self.event_queue)))
        while len(self.event_queue) > 0:
            event = self.event_queue.pop()
            self.logger.info("Monitor: processing %s", str(event))
            self.run_script(event.sev)

    def report(self):
        self.examine_queue()


class LogManager(StatsModule):
    '''
    Handles logging for monitor. Loads config file, sets up logger config
    '''

    def __init__(self, epm, config):
        super(LogManager, self).__init__()
        # self.config = config
        self.event_queue = []
        self.log_configuration(config)
        self.logger = logging.getLogger(__name__)
        log_setup.setup_loggers(
            verbose_level=config['Verbose'],
            capture_std_output=False)

    def initialize(self, module_list):
        self.module_list = module_list
        self.logger.debug("Monitor: initialize method of LogManager complete")

    def report(self):
        self.logger.debug("Monitor: log manager report method running")

    def log_configuration(self, cfg):
        if 'LogConfigFile' in cfg and \
                isinstance(cfg['LogConfigFile'], basestring) and \
                len(cfg['LogConfigFile']) > 0:
            log_config_file = cfg['LogConfigFile']
            if log_config_file.split(".")[-1] == "js":
                try:
                    with open(log_config_file) as log_config_fd:
                        log_dic = json.load(log_config_fd)
                        logging.config.dictConfig(log_dic)
                except IOError, ex:
                    print("Could not read log config: {}"
                          .format(str(ex)), file=sys.stderr)
                    sys.exit(1)
            elif log_config_file.split(".")[-1] == "yaml":
                try:
                    with open(log_config_file) as log_config_fd:
                        log_dic = yaml.load(log_config_fd)
                        logging.config.dictConfig(log_dic)
                except IOError, ex:
                    print("Could not read log config: {}"
                          .format(str(ex)), file=sys.stderr)
                    sys.exit(1)
            else:
                print("LogConfigFile type not supported: {}"
                      .format(cfg['LogConfigFile']), file=sys.stderr)
                sys.exit(1)

        else:
            if cfg['Verbose'] == 0:
                print("No log config file specified")
                print("Use -v option to send logging to console")


class ConnectionStatus(StatsModule):
    '''
    Obtains and displays connection status of monitor to validator network
    '''

    def __init__(self, epm, config):
        super(ConnectionStatus, self).__init__()
        self.connection_status = False
        self.system_stats = None
        self.logger = logging.getLogger(__name__)

    def initialize(self, module_list):
        self.module_list = module_list
        system_stats_manager = self.get_module(SystemStatsManager)
        self.system_stats = system_stats_manager.system_stats
        self.logger.info(
            "Monitor: finished initialization of ConnectionStatus module")
        print("Waiting to connect...")

    def get_connection_status(self):
        active_validators = self.system_stats.sys_client.active_validators
        self.logger.debug("Monitor: Active validators: %i", active_validators)
        return (active_validators > 0), active_validators

    def report(self):
        self.logger.debug("Monitor: connection status module running")
        connection_status, active_validators = self.get_connection_status()
        if connection_status != self.connection_status:
            self.connection_status = connection_status
            print("Connection status: {}".format(connection_status))
            self.logger.info("Monitor connection status: %s",
                             connection_status)
        self.logger.debug("Number of active validators known: %s",
                          str(active_validators))


class PlatformCpu(StatsModule):
    '''
    Monitors the platform running the monitor command.
    Triggers if CPU usage is above 2 percent.
    Useful for testing.
    '''

    def __init__(self, epm, config):
        super(PlatformCpu, self).__init__()
        self.config = config
        self.platform_stats_manager = None
        self.event_script_mgr = None
        self.event_queue = None
        self.event = None
        self.logger = logging.getLogger(__name__)
        self.cpu_threshold = 2.0

    def initialize(self, module_list):
        self.module_list = module_list
        self.platform_stats_manager = self.get_module(PlatformStatsManager)
        self.event_script_mgr = self.get_module(EventScriptManager)
        self.event_queue = self.event_script_mgr.event_queue
        self.event = self.event_script_mgr.event
        self.logger.info(
            "Monitor: finished initialization of PlatformCpu module")

    def cpu_usage_trigger(self):
        p_stats = self.platform_stats_manager.get_data_as_dict()
        cpu_percent = p_stats["scpu"]["percent"]

        if int(cpu_percent) > self.cpu_threshold:
            print("Event detected: CPU threshold on platform")
            self.logger.info(
                "Monitor event detected: CPU threshold on platform")
            event = self.event(
                sev='FAIL', event_desc='CPU usage high on monitor platform')
            self.event_queue.append(event)

    def report(self):
        self.logger.debug("Monitor: platform stats module running")
        self.cpu_usage_trigger()


class ValidatorFailure(StatsModule):
    '''
    Monitors the validator network for a node failure.
    FAIL event added to event queue if a node does not
    respond.
    '''

    def __init__(self, epm, config):
        super(ValidatorFailure, self).__init__()
        self.config = config
        self.validator_stats_manager = None
        self.event_script_mgr = None
        self.event_queue = None
        self.event = None
        self.logger = logging.getLogger(__name__)

    def initialize(self, module_list):
        self.module_list = module_list
        self.validator_stats_manager = self.get_module(ValidatorStatsManager)
        self.event_script_mgr = self.get_module(EventScriptManager)
        self.event_queue = self.event_script_mgr.event_queue
        self.event = self.event_script_mgr.event
        self.logger.info(
            "Monitor: finished initialization of ValidatorFailure module")

    def no_response_trigger(self):
        stats_clients = self.validator_stats_manager.clients

        for client in stats_clients:
            if client.state == "NO_RESP":
                flagged_validator = client.name
                print("Event detected: no response from {}"
                      .format(flagged_validator))
                self.logger.info(
                    "Monitor event detected: no response from %s",
                    str(flagged_validator))
                event = self.event(
                    sev='FAIL', event_desc='No response from validator')
                self.event_queue.append(event)

    def report(self):
        self.logger.debug("Monitor: ValidatorFailure module running")
        self.no_response_trigger()


class SigUsr1(StatsModule):
    '''
    Receives SIGUSR1 signal and adds event with severity SIGUSR1 to the
    event queue.
    '''

    def __init__(self, epm, config):
        super(SigUsr1, self).__init__()
        self.config = config
        self.event_script_mgr = None
        self.event_queue = None
        self.event = None
        self.logger = logging.getLogger(__name__)

    def initialize(self, module_list):
        self.module_list = module_list
        self.event_script_mgr = self.get_module(EventScriptManager)
        self.event_queue = self.event_script_mgr.event_queue
        self.event = self.event_script_mgr.event
        signal.signal(signal.SIGUSR1, self.sigusr1_trigger)
        self.logger.info(
            "Monitor: finished initialization of SigUsr1 module")

    def report(self):
        self.logger.debug("Monitor: SigUsr1 module running")
        # self.no_response_trigger()

    def sigusr1_trigger(self, signum, stack):
        print("SIGUSR1 received")
        self.logger.info("Monitor: SIGUSR1 received")
        event = self.event(sev='SIGUSR1', event_desc='SIGUSR1 received')
        self.event_queue.append(event)

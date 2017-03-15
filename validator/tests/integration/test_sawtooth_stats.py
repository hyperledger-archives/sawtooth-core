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
import time

import unittest
import logging

from sawtooth.exceptions import MessageException

from sawtooth.cli.stats_lib.stats_utils import StatsModule
from sawtooth.cli.stats_lib.validator_stats import SystemStatsManager
from sawtooth.cli.stats_lib.endpoint_manager import EndpointManager
from sawtooth.cli.stats_lib.topology_stats import TopologyManager
from sawtooth.cli.stats import SawtoothStats

from twisted.internet import reactor

LOGGER = logging.getLogger(__name__)


RUN_TEST_SUITES = True \
    if os.environ.get("RUN_TEST_SUITES", False) == "1" else False

class SawtoothStatsTestHarness():
    '''
    test_run()
    - initializes stats config options
    - creates instances of endpoint_manager, sawtooth stats,
      sawtooth stats test module, sawtooth stats test harness,
      and int key workload
    - initializes test_run_in_thread() in reactor thread
    - starts reactor
    test_run_in_thread()
    - sequences the stats test operations
    - collects stats on initial network state; verifies they are correct
    - runs int key workload to increment txn and block count
    - collects stats on new network state; verifies they are correct
    - note: sleeps after calls to endpoint_discovery_loop() and stats_loop()
      to allow time for associated http requests to validators can complete
    - Note: runs in reactor thread so that blocking calls to time.sleep()
      do not suspend main reactor thread required to complete http calls
    '''
    def __init__(self):
        self.epm = None
        self.ss = None
        self.sst = None
        self.int_key_load_test = None
        self.urls = None

        self.keys = 10
        self.rounds = 2

    def test_run(self, urls, config_opts=None, config_dict=None):

        self.urls = urls
        self.url = urls[0]

        config = self.default_config()

        # update defaults with cli options if provided
        if config_opts is None:
            config['EndpointManager']['urls'] = self.urls
        else:
            self.update_config(config, config_opts)

        if config_dict is not None:
            self.update_config_dict(config_dict, config)

        self.epm = EndpointManager(config['EndpointManager']['urls'])
        self.ss = SawtoothStats(self.epm, config)
        self.sst = SawtoothStatsTest(None, None)
        self.sst.initialize(self.ss.stats_modules)

        reactor.callInThread(self.test_run_in_thread)

        print "test complete with no errors"

    def _are_registered(self, timeout=256, validators=5):
        registered = False
        wait_time = 0
        while not registered:
            reactor.callFromThread(self.epm.endpoint_discovery_loop)
            time.sleep(1)
            if len(self.epm.endpoint_urls) is validators:
                registered = True
            if wait_time > timeout:
                break
            wait_time += 1
        return registered

    def test_run_in_thread(self):
        # get list of validators in network
        # sleep to wait for requests to complete

        assert self._are_registered(), "max registration time exceeded"

        assert len(self.epm.endpoint_urls) == 5

        reactor.callFromThread(self.ss.stats_loop)
        time.sleep(1)

        reactor.callFromThread(self.ss.stats_loop)
        time.sleep(1)
        # compare stats values to expected values before executing
        self.sst.get_stats()
        self.sst.test_stats_values(self._stats_values_before_new_txns())

        # end test
        reactor.callFromThread(self.ss.stats_stop)

    def _stats_values_before_new_txns(self):

        validator_count = 1
        expected_params = {
            'clients': {
                'known_validators': validator_count,
                'active_validators': validator_count
            },
            'transactions': {
                'txns_max_committed': 1,
                'txns_max_pending': 0
            },
            'blocks': {
                'blocks_max_committed': 1,
                'blocks_min_pending': 0
            },
            'messages': {
                'msgs_max_acked': 1,
                'msgs_max_handled': 1
            },
            'packets': {
                'packets_max_acks_received': 1
            },
            'poet': {
                'avg_local_mean': 1
            },
            'topology': {
                'maximum_shortest_path_length': 1,
                'maximum_degree': validator_count - 1,
                'node_count': validator_count
            }
        }
        return expected_params

    def default_config(self):
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

    def update_config_dict(self, new_conf, default_conf):
        for key1 in set(new_conf) & set(default_conf):
            for key2 in set(new_conf[key1]) & set(default_conf[key1]):
                default_conf[key1][key2] = new_conf[key1][key2]

    def update_config(self, config, opts):
        config['CsvManager']['csv_enable_summary'] = opts.csv_enable_summary
        config['CsvManager']['csv_enable_validator'] = opts.csv_enable_validator
        config['EndpointManager']['urls'] = [opts.url]
        config['EndpointManager']['interval'] = opts.endpoint_time
        config['SawtoothStats']['interval'] = opts.stats_time
        return config


@unittest.skipUnless(RUN_TEST_SUITES, "Must be run in a test suites")
class TestSawtoothStatsTwistedThread(unittest.TestCase):
    def __init__(self, test_name, urls=None):
        super(TestSawtoothStatsTwistedThread, self).__init__(test_name)
        self.urls = urls
        self.ssth = SawtoothStatsTestHarness()

    def test_sawtooth_stats_twisted_thread(self):
        try:
            self.ssth.test_run(self.urls, config_opts=None, config_dict=None)
        except MessageException as e:
            raise MessageException('stats error: {0}'.format(e))

        finally:
            print "No Validators need to be stopped"

    def stats_config_dict(self):
        config = {}
        config['SawtoothStats'] = {}
        config['SawtoothStats']['max_loop_count'] = 4
        config['StatsPrint'] = {}
        config['StatsPrint']['print_all'] = True
        return config


class SawtoothStatsTest(StatsModule):
    '''
    initialize()
    - gets an instance of system stats manager, topology_stats_manager
      from stats module list
    - gets instance of system_stats, topology_stats from system stats manager,
      topology_stats_manager respectively
    get_stats()
    - builds a dict of system and topology stats
    test_stats()
    - asserts some stats values against reference list
    '''

    def __init__(self, epm, config):
        super(SawtoothStatsTest, self).__init__()
        self.stats = {}

        self.system_stats = None
        self.topology_stats = None

    def initialize(self, module_list):
        self.module_list = module_list
        system_stats_manager = self.get_module(SystemStatsManager)
        self.system_stats = system_stats_manager.system_stats
        topology_stats_manager = self.get_module(TopologyManager)
        self.topology_stats = topology_stats_manager.topology_stats

    def test_stats_values(self, expected_params):

        assert self.stats["summary_stats"]["clients"]["known_validators"] >= \
               expected_params["clients"]["known_validators"]

        assert self.stats["summary_stats"]["clients"]["active_validators"] == \
               expected_params["clients"]["active_validators"]

        assert self.stats
        ["summary_stats"]["topology"]["maximum_shortest_path_length"] >=\
               expected_params["topology"]["maximum_shortest_path_length"]

        assert self.stats["summary_stats"]["topology"]["maximum_degree"] >= \
               expected_params["topology"]["maximum_degree"]

        assert self.stats["summary_stats"]["topology"]["node_count"] >= \
               expected_params["topology"]["node_count"]

        assert self.stats
        ['summary_stats']["blocks"]["blocks_max_committed"] > \
               expected_params["blocks"]["blocks_max_committed"]

        assert self.stats['summary_stats']['blocks']["blocks_min_pending"] >= \
               expected_params["blocks"]["blocks_min_pending"]

        assert self.stats["summary_stats"]["messages"]["msgs_max_acked"] > \
               expected_params["messages"]["msgs_max_acked"]

        assert self.stats["summary_stats"]["messages"]["msgs_max_handled"] > \
               expected_params["messages"]["msgs_max_handled"]

        assert self.stats
        ["summary_stats"]["packets"]["packets_max_acks_received"] > \
            expected_params["packets"]["packets_max_acks_received"]

        assert self.stats["summary_stats"]["poet"]["avg_local_mean"] > \
               expected_params["poet"]["avg_local_mean"]

    def get_stats(self):
        self._get_summary_stats()

    def _get_summary_stats(self):
        stats = {'clients': self.system_stats.sys_client._asdict(),
                 'blocks': self.system_stats.sys_blocks._asdict(),
                 'transactions': self.system_stats.sys_txns._asdict(),
                 'packets': self.system_stats.sys_packets._asdict(),
                 'messages': self.system_stats.sys_msgs._asdict(),
                 'poet': self.system_stats.poet_stats._asdict(),
                 'topology': self.topology_stats.get_stats_as_dict(),
                 }

        self.stats['summary_stats'] = stats


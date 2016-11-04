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

import time
import json
import csv

from sawtooth.cli.stats_lib.stats_utils import StatsModule
from sawtooth.cli.stats_lib.stats_utils import DictWalker
from sawtooth.cli.stats_lib.stats_utils import SignalHandler

from sawtooth.cli.stats_lib.validator_stats import ValidatorStatsManager
from sawtooth.cli.stats_lib.validator_stats import SystemStatsManager

from sawtooth.cli.stats_lib.platform_stats import PlatformStatsManager
from sawtooth.cli.stats_lib.fork_detect import BranchManager
from sawtooth.cli.stats_lib.topology_stats import TopologyManager


class CsvWriter(object):
    def __init__(self):
        self.csvdata = []
        self.file = None
        self.writer = None

    def open_csv_file(self, filename, filepath=""):
        self.file = open(filename, 'wt')
        self.writer = csv.writer(self.file)

    def close_csv_file(self):
        self.file.close()

    def csv_newline(self):
        self.csvdata = []

    def csv_append(self, datalist):
        self.csvdata.extend(datalist)

    def csv_write_header(self, headerlist=None, add_time=True):
        if headerlist is not None:
            self.csvdata.extend(headerlist)
        if add_time:
            self.csvdata.insert(0, "time")
        self._csv_write()

    def csv_write_data(self, datalist=None, add_time=True):
        if datalist is not None:
            self.csvdata.extend(datalist)
        if add_time:
            self.csvdata.insert(0, time.time())
        self._csv_write()

    def _csv_write(self):
        self.writer.writerow(self.csvdata)
        self.csvdata = []


class CsvSummaryStats(object):
    def __init__(self, system_stats, platform_stats):
        self.enabled = False
        self.csv_writer = CsvWriter()

        self.system_stats = system_stats
        self.platform_stats = platform_stats

    def initialize(self):
        self.enabled = True

        filename = "summary_stats_" + str(int(time.time())) + ".csv"
        self.csv_writer.open_csv_file(filename)

        header = self.system_stats.get_names()
        self.csv_writer.csv_append(header)
        header = self.platform_stats.get_names()
        self.csv_writer.csv_write_header(header)

    def write_stats(self):
        if self.enabled:
            data = self.system_stats.get_data()
            self.csv_writer.csv_append(data)
            data = self.platform_stats.get_data()
            self.csv_writer.csv_write_data(data)

    def stop(self):
        if self.enabled:
            self.csv_writer.close_csv_file()


class CsvValidatorStats(object):
    def __init__(self, client_list):
        self.enabled = False
        self.csv_writer = CsvWriter()

        self.get_header = False
        self.csv_stats = CsvWriter()
        self.clients = client_list
        self.stat_names = []

        self.dict_walker = DictWalker()

    def initialize(self):
        self.enabled = True

        filename = "validator_stats_" + str(int(time.time())) + ".csv"
        self.csv_writer.open_csv_file(filename)

        # defer writing header until first instance of data dictionary
        # is available
        self.get_header = True

    def write_stats(self):
        current_time = time.time()
        if self.enabled:
            for client in self.clients:
                if client.responding:
                    self.dict_walker.walk(client.validator_stats.val_stats)
                    if self.get_header:
                        names = self.dict_walker.get_names()
                        names.insert(0, "validator_name")
                        names.insert(0, "time")
                        self.csv_writer.csv_write_header(names, add_time=False)
                        self.get_header = False
                    data = self.dict_walker.get_data()
                    data.insert(0, client.name)
                    data.insert(0, current_time)
                    self.csv_writer.csv_write_data(data, add_time=False)

    def stop(self):
        if self.enabled:
            self.csv_writer.close_csv_file()


class CsvManager(StatsModule):
    def __init__(self, epm, config):
        super(CsvManager, self).__init__()
        self.config = config

        self.css = None
        self.cvs = None

    def initialize(self, module_list):
        self.module_list = module_list
        system_stats = self.get_module(SystemStatsManager)
        platform_stats = self.get_module(PlatformStatsManager)
        validator_stats = self.get_module(ValidatorStatsManager)
        validator_clients = validator_stats.clients

        self.css = CsvSummaryStats(
            system_stats,
            platform_stats
        )
        self.cvs = CsvValidatorStats(validator_clients)
        self.update_config(self.config)

    def csv_init(self, enable_summary, enable_validator):
        if enable_summary is True:
            self.css.initialize()
        if enable_validator is True:
            self.cvs.initialize()

    def report(self):
        self.csv_write()

    def csv_write(self):
        self.css.write_stats()
        self.cvs.write_stats()

    def default_config(self):
        self.config = {}

    def update_config(self, config):
        csv_config = config.get('CsvManager', None)
        if csv_config is None:
            return
        else:
            if csv_config.get('csv_enable_summary', False):
                self.css.initialize()
            if csv_config.get('csv_enable_validator', False):
                self.cvs.initialize()

    def csv_stop(self):
        self.css.stop()
        self.cvs.stop()


class StatsSnapshotWriter(StatsModule):
    '''
    Writes json-formatted snapshot of stats client statistics to file.
    Writes file to where stats client is running.
    Filename includes searchable file name + timestamp
    Captures the following:
    - Summary: each of the summary lines displayed by stats client
    - Per-Validator: Each of the selectable views displayed by stats client
    '''

    def __init__(self, epm, config):
        super(StatsSnapshotWriter, self).__init__()
        self.stats = {}
        self.filename = None
        self.file = None
        self.do_snapshot = False

        self.platform_stats_manager = None
        self.branch_manager = None
        self.signal_handler = None
        self.system_stats = None
        self.topology_stats = None
        self.stats_clients = None

    def initialize(self, module_list):
        self.module_list = module_list
        system_stats_manager = self.get_module(SystemStatsManager)
        topology_stats_manager = self.get_module(TopologyManager)
        validator_stats_manager = self.get_module(ValidatorStatsManager)
        self.platform_stats_manager = self.get_module(PlatformStatsManager)
        self.branch_manager = self.get_module(BranchManager)
        self.signal_handler = self.get_module(SignalHandler)

        self.system_stats = system_stats_manager.system_stats
        self.topology_stats = topology_stats_manager.topology_stats
        self.stats_clients = validator_stats_manager.clients

    def report(self):
        self.write_snapshot()

    def write_snapshot(self):
        if self.signal_handler.sig_user1:
            self.signal_handler.sig_user1 = False  # acts as one-shot
            self._initialize()

            self._summary_stats()
            self._per_validator_stats()
            self._branch_stats()
            self._fork_stats()
            self._collector_stats()

            sawtooth_stats = {'sawtooth_stats': self.stats}
            self._write_snapshot(sawtooth_stats, pretty=True)
            self._close()

    def _initialize(self):
        self.filename = "sawtooth_stats_snap_" + str(int(time.time())) + ".js"
        self.file = open(self.filename, 'wt')

    def _close(self):
        self.file.close()

    def _write_snapshot(self, data, pretty=False, line_feed=True):
        if pretty:
            json.dump(data, self.file, indent=4, sort_keys=True)
        else:
            json.dump(data, self.file)
        if line_feed:
            self.file.write("\n")

    def _summary_stats(self):
        stats = {'clients': self.system_stats.sys_client._asdict(),
                 'blocks': self.system_stats.sys_blocks._asdict(),
                 'transactions': self.system_stats.sys_txns._asdict(),
                 'packets': self.system_stats.sys_packets._asdict(),
                 'messages': self.system_stats.sys_msgs._asdict(),
                 'poet': self.system_stats.poet_stats._asdict(),
                 'topology': self.topology_stats.get_stats_as_dict(),
                 'branches': self.branch_manager.bm_stats.get_stats_as_dict(),
                 'forks': self.branch_manager.f_stats.get_stats_as_dict()}

        self.stats['summary_stats'] = stats

    def _per_validator_stats(self):
        stats = {}
        for client in self.stats_clients:
            client_stats = self.val_stats_fixup(
                client.validator_stats.val_stats.copy())
            stats[client.name] = client_stats
            info = {'id': client.val_id,
                    'name': client.name,
                    'url': client.url,
                    'state': client.state,
                    'responding': client.responding,
                    'no_response_reason': client.no_response_reason,
                    'response_time': client.response_time}
            stats[client.name]['info'] = info
        self.stats['per-validator_stats'] = stats

    def _branch_stats(self):
        stats = {}
        for branch in self.branch_manager.branches:
            stats[branch.bcb_id] = branch.get_stats_as_dict()
        self.stats['branch_stats'] = stats

    def _fork_stats(self):
        stats = {}
        for fork in self.branch_manager.forks:
            stats[fork.bcf_id] = fork.get_stats_as_dict()
        self.stats['fork_stats'] = stats

    def _collector_stats(self):
        stats = {
            'gmt_time':
                time.strftime("GMT:%Y:%m:%d:%H:%M:%S", time.gmtime()),
            'local_time':
                time.strftime("LOCAL:%Y:%m:%d:%H:%M:%S", time.localtime()),
            'platform': self.platform_stats_manager.get_data_as_dict()}

        self.stats['stats_collector'] = stats

    def val_stats_fixup(self, val_stats_copy):
        # this will become a noop when validator stats is fixed so that
        # it reports nodes under the 'peer_nodes' key
        val_stats_copy['peer_nodes'] = {}
        keys_to_remove = []
        for key, root in val_stats_copy.iteritems():
            if 'IsPeer' in root:
                val_stats_copy['peer_nodes'][key] = root
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del val_stats_copy[key]

        return val_stats_copy

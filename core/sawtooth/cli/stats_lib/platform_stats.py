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

import collections
import psutil

from sawtooth.cli.stats_lib.stats_utils import StatsCollector
from sawtooth.cli.stats_lib.stats_utils import StatsModule

CpuStats = collections.namedtuple("scpu",
                                  'percent '
                                  'user_time '
                                  'system_time '
                                  'idle_time')


class PlatformStats(StatsCollector):
    def __init__(self):
        super(PlatformStats, self).__init__()

        self.get_stats()

        self.cpu_stats = None
        self.vmem_stats = None
        self.disk_stats = None
        self.net_stats = None
        self.statslist = []

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


class PlatformIntervalStats(object):
    def __init__(self):
        self.intv_net_bytes_sent = 0
        self.intv_net_bytes_recv = 0
        self.last_net_bytes_sent = 0
        self.last_net_bytes_recv = 0

        self.intv_disk_bytes_read = 0
        self.intv_disk_bytes_write = 0
        self.last_disk_bytes_read = 0
        self.last_disk_bytes_write = 0

        self.intv_disk_count_read = 0
        self.intv_disk_count_write = 0
        self.last_disk_count_read = 0
        self.last_disk_count_write = 0

    def calculate_interval_stats(self, val_stats):
        net_stats = val_stats["platform"]["snetio"]

        self.intv_net_bytes_sent = \
            net_stats["bytes_sent"] - self.last_net_bytes_sent
        self.intv_net_bytes_recv = \
            net_stats["bytes_recv"] - self.last_net_bytes_recv
        self.last_net_bytes_sent = net_stats["bytes_sent"]
        self.last_net_bytes_recv = net_stats["bytes_recv"]

        disk_stats = val_stats["platform"]["sdiskio"]

        self.intv_disk_bytes_write = \
            disk_stats["write_bytes"] - self.last_disk_bytes_write
        self.intv_disk_bytes_read = \
            disk_stats["read_bytes"] - self.last_disk_bytes_read
        self.last_disk_bytes_write = disk_stats["write_bytes"]
        self.last_disk_bytes_read = disk_stats["read_bytes"]

        self.intv_disk_count_write = \
            disk_stats["write_count"] - self.last_disk_count_write
        self.intv_disk_count_read = \
            disk_stats["read_count"] - self.last_disk_count_read
        self.last_disk_count_write = disk_stats["write_count"]
        self.last_disk_count_read = disk_stats["read_count"]


class PlatformStatsManager(StatsModule):
    def __init__(self, endpoint_manager, config):
        super(PlatformStatsManager, self).__init__()
        self.platform_stats = PlatformStats()
        self.platform_interval_stats = PlatformIntervalStats()

    def collect(self):
        self.platform_stats.get_stats()
        psr = {"platform": self.platform_stats.get_data_as_dict()}
        self.platform_interval_stats.calculate_interval_stats(psr)

    def get_data_as_dict(self):
        return self.platform_stats.get_data_as_dict()

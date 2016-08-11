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
import csv
import collections


class CsvManager(object):
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


class SummaryStatsCsvManager(object):
    def __init__(self, system_stats, platform_stats):
        self.csv_enabled = False
        self.csv_mgr = CsvManager()

        self.ss = system_stats
        self.ps = platform_stats

    def initialize(self):
        self.csv_enabled = True

        filename = "summary_stats_" + str(int(time.time())) + ".csv"
        self.csv_mgr.open_csv_file(filename)

        header = self.ss.get_names()
        self.csv_mgr.csv_append(header)
        header = self.ps.get_names()
        self.csv_mgr.csv_write_header(header)

    def write_stats(self):
        if self.csv_enabled:
            data = self.ss.get_data()
            self.csv_mgr.csv_append(data)
            data = self.ps.get_data()
            self.csv_mgr.csv_write_data(data)

    def stop(self):
        if self.csv_enabled:
            self.csv_mgr.close_csv_file()


class ValidatorStatsCsvManager(object):
    def __init__(self, client_list):
        self.csv_enabled = False
        self.csv_mgr = CsvManager()

        self.get_header = False
        self.csv_stats = CsvManager()
        self.clients = client_list
        self.stat_names = []

        self.dw = DictWalker()

    def initialize(self):
        self.csv_enabled = True

        filename = "validator_stats_" + str(int(time.time())) + ".csv"
        self.csv_mgr.open_csv_file(filename)

        # defer writing header until first instance of data dictionary
        # is available
        self.get_header = True

    def write_stats(self):
        current_time = time.time()
        if self.csv_enabled:
            for client in self.clients:
                if client.responding:
                    self.dw.walk(client.vsm.val_stats)
                    if self.get_header:
                        names = self.dw.get_names()
                        names.insert(0, "validator_name")
                        names.insert(0, "time")
                        self.csv_mgr.csv_write_header(names, add_time=False)
                        self.get_header = False
                    data = self.dw.get_data()
                    data.insert(0, client.name)
                    data.insert(0, current_time)
                    self.csv_mgr.csv_write_data(data, add_time=False)

    def stop(self):
        if self.csv_enabled:
            self.csv_mgr.close_csv_file()


class DictWalker(object):
    def __init__(self):
        self.name_list = []
        self.unique_name_list = []
        self.unique_name_with_comma_list = []

        # generates a new set of key/value pairs
        # each time walk() is called
        self.data = dict()
        # contains a set of keys ordered by entry order
        # that persists across calls to walk() - this lets you discover
        # (and remember) new keys as the appear in the data stream
        self.names = collections.OrderedDict()

        self.value_type_error_count = 0
        self.name_has_comma_error_count = 0

    def walk(self, data_dict):
        self.data = dict()
        return self._traverse_dict(data_dict)

    def _traverse_dict(self, data_dict):
        for key, value in data_dict.iteritems():
            self.name_list.append(key)
            if isinstance(value, dict):
                self._traverse_dict(value)
            else:
                if isinstance(value, (list, tuple)):
                    self.value_type_error_count += 1
                    value = "value_type_error"
                if isinstance(value, str):
                    if value.find(",") is not -1:
                        self.value_has_comma_error += 1
                        value = "value_comma_error"

                unique_name = self._unique_name(self.name_list)
                if unique_name.find(",") is not -1:
                    self.name_has_comma_error_count += 1
                    self.unique_name_with_comma_list.append(unique_name)
                else:
                    self.unique_name_list.append(unique_name)
                    self.data[unique_name] = value
                    self.names[unique_name] = None

                self.name_list.pop()
        if len(self.name_list) > 0:
            self.name_list.pop()

    def get_data(self):
        # retrieve data using names so it is always reported in the same order
        # this is important when using get_data() and get_names()
        # to write header and data to csv file to ensure headers and data
        # are written in the same order even if the source dictionary changes
        # size (which it will - at minimum validators do not all process
        # the same messages
        data_list = []
        for name, value in self.names.items():
            value = self.data.get(name, "no_val")
            data_list.append(value)
        return data_list

    def get_names(self):
        name_list = []
        for name in self.names:
            name_list.append(name)
        return name_list

    def _unique_name(self, name_list):
        s = ""
        for name in name_list:
            if len(s) == 0:
                s = name
            else:
                s = "{}-{}".format(s, name)
        return s


class TransactionRate(object):
    def __init__(self):
        self.txn_history = collections.deque()
        self.previous_block_count = 0
        self.avg_txn_rate = 0.0
        self.avg_block_time = 0.0
        self.window_time = 0.0
        self.window_txn_count = 0

    def calculate_txn_rate(self, current_block_count, current_txn_count,
                           window_size=10):
        """

        Args:
            current_block_count: current number of committed blocks
            current_txn_count: current number of committed transactions
            window_size: number of blocks to average over

        Synopsis:
            Each time the block count changes, a snapshot of the
            current number of committed txns and current time is placed in
            the queue.  If there are two or more entries in the queue, the
            average txn rate and average block commit time is calculated.
            If there are more than window_size transactions in the queue,
            the oldest entry is popped from the queue.

        Returns:
            avg_txn_rate: average number of transactions per second
            avg_block_time: average block commit time

        """
        if not current_block_count == self.previous_block_count:
            self.previous_block_count = current_block_count
            current_block_time = time.time()
            self.txn_history.append([current_txn_count, current_block_time])
            # if less than 2 samples, can't do anything
            if len(self.txn_history) < 2:
                self.avg_txn_rate = 0.0
                self.avg_block_time = 0.0
                return self.avg_txn_rate, self.avg_block_time
            # otherwise calculate from tip to tail; current is tip, [0] is tail
            past_txn_count, past_block_time = self.txn_history[0]
            self.window_time = current_block_time - past_block_time
            self.window_txn_count = current_txn_count - past_txn_count
            self.avg_txn_rate = \
                float(self.window_txn_count) / self.window_time
            self.avg_block_time = \
                (self.window_time) / (len(self.txn_history) - 1)
            # if more than "window_size" samples, discard oldest
            if len(self.txn_history) > window_size:
                self.txn_history.popleft()

            return self.avg_txn_rate, self.avg_block_time


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

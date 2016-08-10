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

    def csv_write_header(self, headerlist=None):
        if headerlist is not None:
            self.csvdata.extend(headerlist)
        self.csvdata.insert(0, "time")
        self._csv_write()

    def csv_write_data(self, datalist=None):
        if datalist is not None:
            self.csvdata.extend(datalist)
        self.csvdata.insert(0, time.time())
        self._csv_write()

    def _csv_write(self):
        self.writer.writerow(self.csvdata)
        self.csvdata = []


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

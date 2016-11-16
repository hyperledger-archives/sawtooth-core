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
import time
import threading

from sawtooth.cli.stats_lib.platform_stats import PlatformIntervalStats

from sawtooth.cli.stats_lib.stats_utils import TransactionRate
from sawtooth.cli.stats_lib.stats_utils import ValidatorCommunications
from sawtooth.cli.stats_lib.stats_utils import named_tuple_init
from sawtooth.cli.stats_lib.stats_utils import StatsCollector
from sawtooth.cli.stats_lib.stats_utils import StatsModule


class StatsClient(object):
    def __init__(self, val_id, fullurl):
        self.val_id = val_id
        self.url = fullurl
        self.name = "validator_{0}".format(val_id)

        self.state = "UNKNWN"

        self.ledgerstats = {}
        self.nodestats = {}

        self.validator_stats = ValidatorStats()

        self.responding = False
        self.no_response_reason = ""

        self.request_start = 0.0
        self.request_complete = 0.0
        self.response_time = 0.0

        self.validator_comm = ValidatorCommunications()

        self.path = None

    def stats_request(self):
        # request stats from specified validator url
        self.request_start = time.clock()
        self.path = self.url + "/statistics/all"
        self.validator_comm.get_request(
            self.path,
            self._stats_completion,
            self._stats_error)

    def _stats_completion(self, json_stats, response_code):
        self.request_complete = time.clock()
        self.response_time = self.request_complete - self.request_start
        self.state = "RESP_{}".format(response_code)
        if response_code is 200:
            self.validator_stats.update_stats(json_stats, self.request_start,
                                              self.request_complete)
            self.responding = True
        else:
            self.responding = False
            self.no_response_reason = ""

    def _stats_error(self, failure):
        self.validator_stats.update_stats(self.ledgerstats, 0, 0)
        self.responding = False
        self.state = "NO_RESP"
        self.no_response_reason = failure.type.__name__
        return


ValStatsEx = collections.namedtuple('calculated_validator_stats',
                                    'packet_bytes_received_total '
                                    'packet_bytes_received_average '
                                    'packet_bytes_sent_total '
                                    'packet_bytes_sent_average '
                                    'average_transaction_rate '
                                    'average_block_time')


class ValidatorStats(object):
    def __init__(self):

        self.val_stats = None
        self.val_stats_ex = named_tuple_init(ValStatsEx, 0)

        self.update_lock = threading.Lock()
        self._new_data = False

        self._stats = None

        self._request_time = 0.0
        self.response_time = 0.0
        self._end_time = 0.0

        self.txn_rate = TransactionRate()
        self.psis = PlatformIntervalStats()

    def update_stats(self, json_stats, start_time, end_time):
        self._new_data = True
        self.update_lock.acquire()
        self._stats = json_stats.copy()
        self._request_time = start_time
        self._end_time = end_time
        self.update_lock.release()

    def collect(self):
        if self._new_data:
            self.update_lock.acquire()
            self.val_stats = self._stats.copy()
            self.response_time = self._end_time - self._request_time
            self.update_lock.release()
            self._new_data = False

            # unpack stats that are delivered as lists of unnamed values
            bytes_received_total, bytes_received_average = \
                self.val_stats["packet"]["BytesReceived"]
            bytes_sent_total, bytes_sent_average = \
                self.val_stats["packet"]["BytesSent"]

            self.txn_rate.calculate_txn_rate(
                self.val_stats["journal"]["CommittedBlockCount"],
                self.val_stats["journal"].get("CommittedTxnCount", 0)
            )

            self.val_stats_ex = ValStatsEx(
                bytes_received_total,
                bytes_received_average,
                bytes_sent_total,
                bytes_sent_average,
                self.txn_rate.avg_txn_rate,
                self.txn_rate.avg_block_time
            )

            self.psis.calculate_interval_stats(self.val_stats)


class ValidatorStatsManager(StatsModule):

    def __init__(self, endpoint_manager, config):
        super(ValidatorStatsManager, self).__init__()
        self.epm = endpoint_manager
        self.config = config

        self.clients = []
        self.known_endpoint_names = []
        self.endpoints = {}

    def connect(self):
        self.update_client_list()

    def collect(self):
        self.collect_stats()

    def update_client_list(self):
        self.endpoints = self.epm.endpoints
        # add validator stats client for each endpoint name
        for val_num, endpoint in enumerate(self.endpoints.values()):
            if endpoint["Name"] not in self.known_endpoint_names:
                val_num = len(self.known_endpoint_names)
                url = 'http://{0}:{1}'.format(
                    endpoint["Host"], endpoint["HttpPort"])
                c = StatsClient(val_num, url)
                c.name = endpoint["Name"]
                self.clients.append(c)
                self.known_endpoint_names.append(endpoint["Name"])

    def collect_stats(self):
        # update client stats objects
        for c in self.clients:
            c.validator_stats.collect()

        # start a new round of stats collection
        for c in self.clients:
            c.stats_request()

SysClient = collections.namedtuple('sys_client',
                                   'starttime '
                                   'runtime '
                                   'known_validators '
                                   'active_validators '
                                   'avg_client_time '
                                   'max_client_time')
SysBlocks = collections.namedtuple('sys_blocks',
                                   'blocks_max_committed '
                                   'blocks_max_committed_count '
                                   'blocks_min_committed '
                                   'blocks_max_pending '
                                   'blocks_max_pending_count '
                                   'blocks_min_pending '
                                   'blocks_max_claimed '
                                   'blocks_min_claimed')
SysTxns = collections.namedtuple('sys_txns',
                                 'txns_max_committed '
                                 'txns_max_committed_count '
                                 'txns_min_committed '
                                 'txns_max_pending '
                                 'txns_max_pending_count '
                                 'txns_min_pending '
                                 'txn_rate')
SysPackets = collections.namedtuple('sys_packets',
                                    'packets_max_dropped '
                                    'packets_min_dropped '
                                    'packets_max_duplicates '
                                    'packets_min_duplicates '
                                    'packets_max_acks_received '
                                    'packets_min_acks_received')
SysMsgs = collections.namedtuple('sys_messages',
                                 'msgs_max_handled '
                                 'msgs_min_handled '
                                 'msgs_max_acked '
                                 'msgs_min_acked')
PoetStats = collections.namedtuple('poet_stats',
                                   'avg_local_mean '
                                   'max_local_mean '
                                   'min_local_mean '
                                   'last_unique_blockID')


class SystemStats(StatsCollector):
    def __init__(self):
        super(SystemStats, self).__init__()

        self.starttime = int(time.time())
        self.runtime = 0
        self.known_validators = 0
        self.active_validators = 0
        self.avg_client_time = 0
        self.max_client_time = 0
        self.txn_rate = 0

        self.sys_client = named_tuple_init(
            SysClient, 0, {'starttime': self.starttime})
        self.sys_blocks = named_tuple_init(SysBlocks, 0)
        self.sys_txns = named_tuple_init(SysTxns, 0)
        self.sys_packets = named_tuple_init(SysPackets, 0)
        self.sys_msgs = named_tuple_init(SysMsgs, 0)
        self.poet_stats = named_tuple_init(
            PoetStats, 0.0, {'last_unique_blockID': ''})

        self.statslist = [self.sys_client, self.sys_blocks, self.sys_txns,
                          self.sys_packets, self.sys_msgs, self.poet_stats]
        self.last_unique_block_id = None

        # accumulators
        self.response_times = []

        self.blocks_claimed = []
        self.blocks_committed = []
        self.blocks_pending = []
        self.txns_committed = []
        self.txns_pending = []
        self.packets_dropped = []
        self.packets_duplicates = []
        self.packets_acks_received = []
        self.msgs_handled = []
        self.msgs_acked = []

        self.local_mean = []
        self.previous_blockid = []
        self.avg_local_mean = None

    def collect_stats(self, stats_clients):
        # must clear the accumulators at start of each sample interval
        self.clear_accumulators()

        for client in stats_clients:
            if client.responding:
                self._append_stats(client)

    def _append_stats(self, client):
        stats = client.validator_stats.val_stats

        self.active_validators += 1

        self.response_times.append(client.validator_stats.response_time)

        self.blocks_claimed.append(
            stats["journal"]["BlocksClaimed"])
        self.blocks_committed.append(
            stats["journal"]["CommittedBlockCount"])
        self.blocks_pending.append(
            stats["journal"]["PendingBlockCount"])
        self.txns_committed.append(
            stats["journal"].get("CommittedTxnCount", 0))
        self.txns_pending.append(
            stats["journal"].get("PendingTxnCount", 0))
        self.packets_dropped.append(
            stats["packet"]["DroppedPackets"])
        self.packets_duplicates.append(
            stats["packet"]["DuplicatePackets"])
        self.packets_acks_received.append(
            stats["packet"]["AcksReceived"])
        self.msgs_handled.append(
            stats["packet"]["MessagesHandled"])
        self.msgs_acked.append(
            stats["packet"]["MessagesAcked"])

        self.local_mean.append(
            stats["journal"].get(
                "LocalMeanTime", 0.0))
        self.previous_blockid.append(
            stats["journal"].get(
                "PreviousBlockID", 'broken'))

    def calculate_stats(self):
        self.runtime = int(time.time()) - self.starttime
        if self.active_validators > 0:
            self.avg_client_time = sum(self.response_times)\
                / len(self.response_times)
            self.max_client_time = max(self.response_times)

            self.sys_client = SysClient(
                self.starttime,
                self.runtime,
                self.known_validators,
                self.active_validators,
                self.avg_client_time,
                self.max_client_time
            )

            blocks_max_committed = max(self.blocks_committed)
            blocks_max_pending = max(self.blocks_pending)

            self.sys_blocks = SysBlocks(
                blocks_max_committed,
                self.blocks_committed.count(blocks_max_committed),
                min(self.blocks_committed),
                blocks_max_pending,
                self.blocks_pending.count(blocks_max_pending),
                min(self.blocks_pending),
                max(self.blocks_claimed),
                min(self.blocks_claimed)
            )

            txns_max_committed = max(self.txns_committed)
            txns_max_pending = max(self.txns_pending)

            self.sys_txns = SysTxns(
                txns_max_committed,
                self.txns_committed.count(txns_max_committed),
                min(self.txns_committed),
                txns_max_pending,
                self.txns_pending.count(txns_max_pending),
                min(self.txns_pending),
                0
            )

            self.sys_packets = SysPackets(
                max(self.packets_dropped),
                min(self.packets_dropped),
                max(self.packets_duplicates),
                min(self.packets_duplicates),
                max(self.packets_acks_received),
                min(self.packets_acks_received)
            )

            self.sys_msgs = SysMsgs(
                max(self.msgs_handled),
                min(self.msgs_handled),
                max(self.msgs_acked),
                min(self.msgs_acked)
            )

            self.avg_local_mean = sum(self.local_mean) \
                / len(self.local_mean)

            unique_blockid_list = list(set(self.previous_blockid))
            self.last_unique_block_id = \
                unique_blockid_list[len(unique_blockid_list) - 1]
            self.poet_stats = PoetStats(
                self.avg_local_mean,
                max(self.local_mean),
                min(self.local_mean),
                self.last_unique_block_id
            )

            # because named tuples are immutable,
            #  must create new stats list each time stats are updated
            self.statslist = [self.sys_client, self.sys_blocks,
                              self.sys_txns, self.sys_packets, self.sys_msgs]

    def clear_accumulators(self):
        self.blocks_claimed = []
        self.blocks_committed = []
        self.blocks_pending = []
        self.txns_committed = []
        self.txns_pending = []
        self.packets_dropped = []
        self.packets_duplicates = []
        self.packets_acks_received = []
        self.msgs_handled = []
        self.msgs_acked = []

        self.local_mean = []
        self.previous_blockid = []

    def get_stats_as_dict(self):
        pass


class SystemStatsManager(StatsModule):
    def __init__(self, endpoint_manager, config):
        super(SystemStatsManager, self).__init__()
        self.vsm = None
        self.system_stats = SystemStats()

    def initialize(self, module_list):
        self.module_list = module_list
        self.vsm = self.get_module(ValidatorStatsManager)

    def process(self):

        self.system_stats.known_validators = len(self.vsm.clients)
        self.system_stats.active_validators = 0

        self.system_stats.collect_stats(self.vsm.clients)
        self.system_stats.calculate_stats()

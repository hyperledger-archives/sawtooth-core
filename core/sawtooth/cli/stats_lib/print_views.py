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


class SummaryView(object):
    def __init__(self, console_print, print_manager):
        self._console_print = console_print
        self.system_stats = print_manager.system_stats
        self.platform_stats = print_manager.platform_stats
        self.topology_stats = print_manager.topology_stats
        self.branch_manager = print_manager.branch_manager
        self._view_mode = None

    def print_summary(self, view_mode):
        self._view_mode = view_mode
        validator_formatter = \
            '{0:>16} ' \
            '{1:9d} {2:16.16} {3:9d} {4:16.16} {5:9.3f} {6:16.16} ' \
            '{7:9.3f} {8:16.16} {9:9d} {10:19.19}'
        self._console_print.cpprint(validator_formatter.format(
            "Validators:",
            self.system_stats.sys_client.known_validators, "known",
            self.system_stats.sys_client.active_validators, "responding",
            self.system_stats.sys_client.avg_client_time, "avg time(s)",
            self.system_stats.sys_client.max_client_time, "max time(s)",
            self.system_stats.sys_client.runtime, "run time(s)"))

        blocks_formatter = \
            '{0:>16} ' \
            '{1:9d} {2:16.16} {3:9d} {4:16.16} {5:9d} {6:16.16} ' \
            '{7:9d} {8:16.16} {9:9d} {10:19.19}'
        self._console_print.cpprint(blocks_formatter.format(
            "Blocks:",
            self.system_stats.sys_blocks.blocks_max_committed, "max committed",
            self.system_stats.sys_blocks.blocks_min_committed, "min committed",
            self.system_stats.sys_blocks.blocks_max_pending, "max pending",
            self.system_stats.sys_blocks.blocks_min_pending, "min pending",
            self.system_stats.sys_blocks.blocks_max_claimed, "max claimed",
            self.system_stats.sys_blocks.blocks_min_claimed, "min claimed"))

        txns_formatter = \
            '{0:>16} ' \
            '{1:9d} {2:16.16} {3:9d} {4:16.16} {5:9d} {6:16.16} ' \
            '{7:9d} {8:16.16} {9:9d} {10:19.19}'
        self._console_print.cpprint(txns_formatter.format(
            "Transactions:",
            self.system_stats.sys_txns.txns_max_committed, "max committed",
            self.system_stats.sys_txns.txns_min_committed, "min committed",
            self.system_stats.sys_txns.txns_max_pending, "max pending",
            self.system_stats.sys_txns.txns_min_pending, "min pending",
            0, "rate (t/s)"))

        pkt_formatter = \
            '{0:>16} ' \
            '{1:9d} {2:16.16} {3:9d} {4:16.16} {5:9d} {6:16.16} ' \
            '{7:9d} {8:16.16} {9:9d} {10:19.19} {11:9d} {12:17.17}'
        self._console_print.cpprint(pkt_formatter.format(
            "Packet totals:",
            self.system_stats.sys_packets.packets_max_dropped, "max dropped",
            self.system_stats.sys_packets.packets_min_dropped, "min dropped",
            self.system_stats.sys_packets.packets_max_duplicates,
            "max duplicated",
            self.system_stats.sys_packets.packets_min_duplicates,
            "min duplicated",
            self.system_stats.sys_packets.packets_max_acks_received,
            "max acks rcvd",
            self.system_stats.sys_packets.packets_min_acks_received,
            "min acks rcvd"))

        msg_formatter = \
            '{0:>16} ' \
            '{1:9d} {2:16.16} {3:9d} {4:16.16} {5:9d} {6:16.16} ' \
            '{7:9d} {8:16.16}'
        self._console_print.cpprint(msg_formatter.format(
            "Message totals:",
            self.system_stats.sys_msgs.msgs_max_handled, "max handled",
            self.system_stats.sys_msgs.msgs_min_handled, "min handled",
            self.system_stats.sys_msgs.msgs_max_acked, "max acked",
            self.system_stats.sys_msgs.msgs_min_acked, "min acked"))

        platform_formatter = \
            '{0:>16} ' \
            '{1:9.2f} {2:16.16} {3:9.2f} {4:16.16} {5:9d} {6:16.16} ' \
            '{7:9d} {8:16.16}'
        self._console_print.cpprint(platform_formatter.format(
            "Platform:",
            self.platform_stats.platform_stats.cpu_stats.percent,
            "cpu pct",
            self.platform_stats.platform_stats.vmem_stats.percent,
            "vmem pct",
            self.platform_stats.platform_interval_stats.intv_net_bytes_sent,
            "ntwrk bytes tx",
            self.platform_stats.platform_interval_stats.intv_net_bytes_recv,
            "ntwrk bytes rx"))

        topo_1_formatter = \
            '{0:>16} ' \
            '{1:9d} {2:16.16} {3:9d} {4:16.16} {5:9d} {6:16.16} ' \
            '{7:9d} {8:16.16} {9:9.2f} {10:19.19}'
        self._console_print.cpprint(topo_1_formatter.format(
            "Topology:",
            self.topology_stats.connected_component_count, "components",
            self.topology_stats.node_count, "nodes",
            self.topology_stats.edge_count, "edges",
            self.topology_stats.maximum_degree, "max peers",
            self.topology_stats.minimum_degree, "min peers"))

        topo_2_formatter = \
            '{0:>16} ' \
            '{1:9.2f} {2:16.16} {3:9d} {4:16.16} {5:9d} {6:16.16} ' \
            '{7:9.2f} {8:16.16} {9:9.2f} {10:19.19}'
        self._console_print.cpprint(topo_2_formatter.format(
            "Topology:",
            self.topology_stats.average_shortest_path_length,
            "avg shortest pth",
            self.topology_stats.maximum_shortest_path_length,
            "max shortest pth",
            self.topology_stats.minimum_connectivity,
            "min connectivity",
            self.topology_stats.maximum_degree_centrality,
            "max degree cent",
            self.topology_stats.maximum_between_centrality,
            "max between cent"))

        branch_formatter = \
            '{0:>16} ' \
            '{1:9d} {2:16.16} {3:9d} {4:16.16} {5:9d} {6:16.16} ' \
            '{7:9d} {8:16.16} {9:9d} {10:19.19} {11:9d} {12:17.17}'
        self._console_print.cpprint(branch_formatter.format(
            "Branch:",
            self.branch_manager.bm_stats.identified, "identified",
            self.branch_manager.bm_stats.active, "active",
            self.branch_manager.bm_stats.longest, "longest",
            self.branch_manager.bm_stats.longest_active, "longest active",
            self.branch_manager.bm_stats.next_longest_active,
            "next longest active",
            # self.bm.bm_stats.validators, "validator count"))
            self.branch_manager.bm_stats.blocks_processed, "blocks processed"))

        fork_formatter = \
            '{0:>16} ' \
            '{1:9} {2:16.16} {3:9d} {4:16.16} {5:9d} {6:16.16} ' \
            '{7:9d} {8:16.16} {9:9d} {10:19.19}'
        self._console_print.cpprint(fork_formatter.format(
            "Fork:",
            self.branch_manager.f_stats.status, "status",
            self.branch_manager.f_stats.fork_count, "fork count",
            self.branch_manager.f_stats.parent_count, "parent forks",
            self.branch_manager.f_stats.child_count, "child forks",
            self.branch_manager.f_stats.longest_child_fork_length,
            "longest child fork"))

        poet_formatter = \
            '{0:>16} ' \
            '{1:9.2f} {2:16.16} {3:9.2f} {4:16.16} {5:9.2f} {6:16.16} ' \
            '{7:>26.16} {8:22.22}'
        self._console_print.cpprint(poet_formatter.format(
            "Poet:",
            self.system_stats.poet_stats.avg_local_mean, "avg local mean",
            self.system_stats.poet_stats.max_local_mean, "max local mean",
            self.system_stats.poet_stats.min_local_mean, "min local mean",
            self.system_stats.poet_stats.last_unique_blockID,
            "last unique block ID"))

        view_formatter = \
            '{0:>16} ' \
            '{1:>9} {2:16.16} {3:>9} {4:16.16} {5:>9} {6:16.16} ' \
            '{7:>9} {8:16.16} {9:>9} {10:19.19}'
        self._console_print.cpprint(view_formatter.format(
            "View:",
            "(g)", "general",
            "(t)", "transaction",
            "(k)", "packet",
            "(c)", "consensus",
            "(o)", "topology"))

        view_formatter_2 = \
            '{0:>16} ' \
            '{1:>9} {2:16.16} {3:>9} {4:16.16} {5:>9} {6:16.16} ' \
            '{7:>9} {8:16.16}'
        self._console_print.cpprint(view_formatter_2.format(
            "({})".format(self._view_mode),
            "(p)", "platform",
            "(n)", "network",
            "(b)", "branch",
            "(f)", "fork"))


class ValidatorBaseView(object):
    def __init__(self, console_print, clients):
        self._console_print = console_print
        self.clients = clients

    def print_view(self):
        self._print_headers()
        for client in self.clients:
            self._print_body(client)

    def _print_headers(self):
        pass

    def _print_body(self, client):
        stats = client.validator_stats.val_stats
        stats_ex = client.validator_stats.val_stats_ex
        if client.responding:
            self._responding(client, stats, stats_ex)
        else:
            self._not_responding(client)

    def _responding(self, client, stats, stats_ex):
        pass

    def _not_responding(self, client):
        pass


class GeneralView(ValidatorBaseView):
    def __init__(self, console_print, clients):
        super(GeneralView, self).__init__(console_print, clients)
        self.header_formatter = \
            '{0:>5} {1:>8} ' \
            '{2:>8} {3:>7} {4:>9} {5:>7} ' \
            '{6:>11} {7:>7} {8:>9} {9:>7} {10:>8}  {11:>16} ' \
            '{12:>18.18} {13:>28.28}'
        self.resp_formatter = \
            '{0:5d} {1:>8} ' \
            '{2:8.3f} {3:7d} {4:9d} {5:7d} ' \
            '{6:11d} {7:7d} {8:9.2f} {9:7.2f} {10:8.2f}  {11:>16.16} ' \
            '{12:>18.18} {13:>28.28}'
        self.no_resp_formatter = \
            '{0:5d} {1:>8} ' \
            '{2:31} {3} {4} {5} ' \
            '{6:>11} {7:>7} {8:>9} {9:>7} {10:>8}  {11:>16} ' \
            '{12:>18.18} {13:>28.28}'

    def _print_headers(self):
        self._console_print.cpprint(self.header_formatter.format(
            'VAL', 'VAL',
            'RESPONSE', 'BLOCKS', 'BLOCKS', 'BLOCKS',
            'TXNS', 'TXNS', 'AVG TXN', 'AVG BLK', 'LOCAL', 'PREVIOUS',
            ' VALIDATOR', 'VALIDATOR'),
            reverse=True)

        self._console_print.cpprint(self.header_formatter.format(
            'ID', 'STATE',
            'TIME(S)', 'CLAIMED', 'COMMITTED', 'PENDING',
            'COMMITTED', 'PENDING', 'RATE(T/S)', 'TIME(S)', 'MEAN', 'BLOCKID',
            'NAME', 'URL'),
            reverse=True)

    def _responding(self, client, stats, stats_ex):
        self._console_print.cpprint(self.resp_formatter.format(
            client.val_id,
            client.state,
            client.response_time,
            stats["journal"]["BlocksClaimed"],
            stats["journal"]["CommittedBlockCount"],
            stats["journal"]["PendingBlockCount"],
            stats["journal"].get("CommittedTxnCount", 0),
            stats["journal"].get("PendingTxnCount", 0),
            stats_ex.average_transaction_rate,
            stats_ex.average_block_time,
            stats["journal"].get("LocalMeanTime", 0.0),
            stats["journal"].get("PreviousBlockID", 'not reported'),
            client.name[:16],
            client.url),
            False)

    def _not_responding(self, client):
        self._console_print.cpprint(self.no_resp_formatter.format(
            client.val_id,
            client.state,
            client.response_status, "", "", "",
            "", "", "", "", "", "",
            client.name[:16],
            client.url),
            False)


class PlatformView(ValidatorBaseView):
    def __init__(self, console_print, clients):
        super(PlatformView, self).__init__(console_print, clients)
        self.header_formatter = \
            '{0:>5} {1:>8} ' \
            '{2:>8} {3:>8} {4:>8} {5:>8} ' \
            '{6:>8} {7:>8} {8:>8} ' \
            '{9:>8} {10:>8} {11:>8} {12:>8} ' \
            '{13:>18.18} {14:>28.28}'
        self.resp_formatter = \
            '{0:5d} {1:>8} ' \
            '{2:8.2f} {3:8.2f} {4:8.2f} {5:8.2f} ' \
            '{6:8.2f} {7:8d} {8:8d} ' \
            '{9:8d} {10:8d} {11:8d} {12:8d} ' \
            '{13:>18.18} {14:>28.28}'
        self.no_resp_formatter = \
            '{0:5d} {1:>8} ' \
            '{2:>8} {3:>8} {4:>8} {5:>8} ' \
            '{6:>8} {7:>8} {8:>8} ' \
            '{9:>8} {10:>8} {11:>8} {12:>8}  ' \
            '{13:>18.18} {14:>28.28}'

    def _print_headers(self):
        self._console_print.cpprint(self.header_formatter.format(
            'VAL', 'VAL',
            'CPU', 'CPU', 'CPU', 'CPU',
            'MEM', 'MEM', 'MEM',
            'DISK', 'DISK', 'DISK', 'DISK',
            ' VALIDATOR', 'VALIDATOR'),
            reverse=True)

        self._console_print.cpprint(self.header_formatter.format(
            'ID', 'STATE',
            'PERCENT', 'USER PCT', 'SYS PCT', 'IDLE PCT',
            'PERCENT', 'TOTAL MB', 'AVAIL MB',
            'RD BYTES', 'WR BYTES', 'RD COUNT', 'WR COUNT',
            'NAME', 'URL'),
            reverse=True)

    def _responding(self, client, stats, stats_ex):
        self._console_print.cpprint(self.resp_formatter.format(
            client.val_id,
            client.state,
            stats["platform"]["scpu"]["percent"],
            stats["platform"]["scpu"]["user_time"],
            stats["platform"]["scpu"]["system_time"],
            stats["platform"]["scpu"]["idle_time"],
            stats["platform"]["svmem"]["percent"],
            stats["platform"]["svmem"]["total"] / 1000000,
            stats["platform"]["svmem"]["available"] / 1000000,
            client.validator_stats.psis.intv_disk_bytes_read,
            client.validator_stats.psis.intv_disk_bytes_write,
            client.validator_stats.psis.intv_disk_count_read,
            client.validator_stats.psis.intv_disk_count_write,
            client.name[:16],
            client.url),
            False)

    def _not_responding(self, client):
        self._console_print.cpprint(self.no_resp_formatter.format(
            client.val_id,
            client.state,
            "", "", "", "", "",
            "", "", "",
            "", "", "", "",
            client.name[:16],
            client.url),
            False)


class ConsensusView(ValidatorBaseView):
    def __init__(self, console_print, clients):
        super(ConsensusView, self).__init__(console_print, clients)
        self.header_formatter = \
            '{0:>5} {1:>8} ' \
            '{2:>8} {3:>10} {4:>12} {5:>16} ' \
            '{6:>18.18} {7:>28.28}'
        self.resp_formatter = \
            '{0:5d} {1:>8} ' \
            '{2:8.2f} {3:10.2f} {4:12.2f} {5:16.16} ' \
            '{6:>18.18} {7:>28.28}'
        self.no_resp_formatter = \
            '{0:5d} {1:>8} ' \
            '{2:>8} {3:>10} {4:>12} {5:>16} ' \
            '{6:>18.18} {7:>28.28}'

    def _print_headers(self):
        self._console_print.cpprint(self.header_formatter.format(
            'VAL', 'VAL',
            'LOCAL', 'POPULATION', 'AGGREGATE', 'LAST',
            ' VALIDATOR', 'VALIDATOR'),
            reverse=True)

        self._console_print.cpprint(self.header_formatter.format(
            'ID', 'STATE',
            'MEAN', 'ESTIMATE', 'LOCALMEAN', 'BLOCKID',
            'NAME', 'URL'),
            reverse=True)

    def _responding(self, client, stats, stats_ex):
        self._console_print.cpprint(self.resp_formatter.format(
            client.val_id,
            client.state,
            stats["journal"].get("LocalMeanTime", 0.0),
            stats["journal"].get("PopulationEstimate", 0.0),
            stats["journal"].get("AggregateLocalMean", 0.0),
            stats["journal"].get("PreviousBlockID", 'error'),
            client.name[:16],
            client.url),
            False)

    def _not_responding(self, client):
        self._console_print.cpprint(self.no_resp_formatter.format(
            client.val_id,
            client.state,
            "", "", "", "",
            client.name[:16],
            client.url),
            False)


class PacketView(ValidatorBaseView):
    def __init__(self, console_print, clients):
        super(PacketView, self).__init__(console_print, clients)
        self.header_formatter = \
            '{0:>5} {1:>8} ' \
            '{2:>10} {3:>10} {4:>10} {5:>10} ' \
            '{6:>12} {7:>12} {8:>12} {9:>12}' \
            '{10:>18.18} {11:>28.28}'
        self.resp_formatter = \
            '{0:5d} {1:>8} ' \
            '{2:10d} {3:10d} {4:10d} {5:10d} ' \
            '{6:12d} {7:12d} {8:12d} {9:12d}' \
            '{10:>18.18} {11:>28.28}'
        self.no_resp_formatter = \
            '{0:5d} {1:>8} ' \
            '{2:>10} {3:>10} {4:>10} {5:>10} ' \
            '{6:>12} {7:>12} {8:>12} {9:>12}' \
            '{10:>18.18} {11:>28.28}'

    def _print_headers(self):
        self._console_print.cpprint(self.header_formatter.format(
            'VAL', 'VAL',
            'ACKS', 'BYTES', 'BYTES', 'PACKETS',
            'PACKETS', 'UNACKED', 'MESSAGE', 'MESSAGE',
            ' VALIDATOR', 'VALIDATOR'),
            reverse=True)

        self._console_print.cpprint(self.header_formatter.format(
            'ID', 'STATE',
            'RECEIVED', 'RECEIVED', 'SENT', 'DROPPED',
            'DUPLICATED', 'PACKETCOUNT', 'ACKED', 'HANDLED',
            'NAME', 'URL'),
            reverse=True)

    def _responding(self, client, stats, stats_ex):
        self._console_print.cpprint(self.resp_formatter.format(
            client.val_id,
            client.state,
            stats["packet"]["AcksReceived"],
            stats["packet"]["BytesReceived"][0],
            stats["packet"]["BytesSent"][0],
            stats["packet"]["DroppedPackets"],
            stats["packet"]["DuplicatePackets"],
            stats["packet"]["UnackedPacketCount"],
            stats["packet"]["MessagesAcked"],
            stats["packet"]["MessagesHandled"],
            client.name[:16],
            client.url),
            False)

    def _not_responding(self, client):
        self._console_print.cpprint(self.no_resp_formatter.format(
            client.val_id,
            client.state,
            "", "", "", "",
            "", "", "", "",
            client.name[:16],
            client.url),
            False)


class NetworkView(ValidatorBaseView):
    def __init__(self, console_print, clients):
        super(NetworkView, self).__init__(console_print, clients)
        self.header_formatter = \
            '{0:>5} {1:>8} ' \
            '{2:>10} {3:>10} {4:>12} {5:>12} ' \
            '{6:>12} {7:>12} {8:>14} {9:>14}' \
            '{10:>18.18} {11:>28.28}'
        self.resp_formatter = \
            '{0:5d} {1:>8} ' \
            '{2:10d} {3:10d} {4:12d} {5:12d} ' \
            '{6:12d} {7:12d} {8:14d} {9:14d}' \
            '{10:>18.18} {11:>28.28}'
        self.no_resp_formatter = \
            '{0:5d} {1:>8} ' \
            '{2:>10} {3:>10} {4:>12} {5:>12} ' \
            '{6:>12} {7:>12} {8:>14} {9:>14}' \
            '{10:>18.18} {11:>28.28}'

    def _print_headers(self):
        self._console_print.cpprint(self.header_formatter.format(
            'VAL', 'VAL',
            'SEND', 'RECEIVE', 'SEND', 'RECEIVE',
            'SEND', 'RECEIVE', 'SEND', 'RECEIVE',
            ' VALIDATOR', 'VALIDATOR'),
            reverse=True)

        self._console_print.cpprint(self.header_formatter.format(
            'ID', 'STATE',
            'BYTES', 'BYTES', 'PCKT BYTES', 'PCKT BYTES',
            'BYTES ERR', 'BYTES ERR', 'DROPPED PCKTS', 'DROPPED PCKTS',
            'NAME', 'URL'),
            reverse=True)

    def _responding(self, client, stats, stats_ex):
        self._console_print.cpprint(self.resp_formatter.format(
            client.val_id,
            client.state,
            stats["platform"]["snetio"]["bytes_recv"],
            stats["platform"]["snetio"]["bytes_sent"],
            stats["platform"]["snetio"]["packets_recv"],
            stats["platform"]["snetio"]["packets_sent"],
            stats["platform"]["snetio"]["errout"],
            stats["platform"]["snetio"]["errin"],
            stats["platform"]["snetio"]["dropout"],
            stats["platform"]["snetio"]["dropin"],

            client.name[:16],
            client.url),
            False)

    def _not_responding(self, client):
        self._console_print.cpprint(self.no_resp_formatter.format(
            client.val_id,
            client.state,
            "", "", "", "",
            "", "", "", "",
            client.name[:16],
            client.url),
            False)


class TransactionView(ValidatorBaseView):
    def __init__(self, console_print, clients):
        super(TransactionView, self).__init__(console_print, clients)
        self.header_formatter = \
            '{0:>5} {1:>8} ' \
            '{2:>10} {3:>10} {4:>12} {5:>12} ' \
            '{6:>16} {7:>14} {8:>14}' \
            '{9:>18.18} {10:>28.28}'
        self.resp_formatter = \
            '{0:5d} {1:>8} ' \
            '{2:10d} {3:10d} {4:12d} {5:12d} ' \
            '{6:16d} {7:14d} {8:14d}' \
            '{9:>18.18} {10:>28.28}'
        self.no_resp_formatter = \
            '{0:5d} {1:>8} ' \
            '{2:>10} {3:>10} {4:>12} {5:>12} ' \
            '{6:>16} {7:>14} {8:>14}' \
            '{9:>18.18} {10:>28.28}'

    def _print_headers(self):
        self._console_print.cpprint(self.header_formatter.format(
            'VAL', 'VAL',
            'BLOCK', 'BLOCK', 'TXN', 'TXN',
            'MISSING TXN', 'MISSING TXN', 'INVALID',
            ' VALIDATOR', 'VALIDATOR'),
            reverse=True)

        self._console_print.cpprint(self.header_formatter.format(
            'ID', 'STATE',
            'COMMITTED', 'PENDING', 'COMMITTED', 'PENDING',
            'DEPENDENCY CNT', 'BLOCK CNT', 'TXN CNT',
            'NAME', 'URL'),
            reverse=True)

    def _responding(self, client, stats, stats_ex):
        self._console_print.cpprint(self.resp_formatter.format(
            client.val_id,
            client.state,
            stats["journal"]["CommittedBlockCount"],
            stats["journal"]["PendingBlockCount"],
            stats["journal"]["CommittedTxnCount"],
            stats["journal"]["PendingTxnCount"],
            stats["journal"]["MissingTxnDepCount"],
            stats["journal"]["MissingTxnFromBlockCount"],
            stats["journal"]["InvalidTxnCount"],

            client.name[:16],
            client.url),
            False)

    def _not_responding(self, client):
        self._console_print.cpprint(self.no_resp_formatter.format(
            client.val_id,
            client.state,
            "", "", "", "",
            "", "", "",
            client.name[:16],
            client.url),
            False)


class BranchView(object):
    def __init__(self, console_print, branch_manager):
        self._console_print = console_print
        self._branch_manager = branch_manager
        # determine which branch has the longest active list
        # and active history list; size columns to match
        max_active = 0
        max_active_history = 0
        for branch in self._branch_manager.branches:
            als = str(branch.is_active_list).replace(" ", "")
            ahls = str(branch.is_active_history).replace(" ", "")
            if len(als) > max_active:
                max_active = len(als)
            if len(ahls) > max_active_history:
                max_active_history = len(ahls)
        mastr = str(max_active) + '}'
        mahstr = str(max_active_history) + '}'

        self.header_formatter = \
            '{0:>12} {1:>10} {2:>6} ' \
            '{3:>16} {4:>10} ' \
            '{5:>16} {6:>10} ' \
            '{7:>12} {8:>16} {9:>10} ' \
            '{10:>14} {11:>14} ' \
            '{12:>8} ' \
            '{13:>' + mastr + ' {14:>' + mahstr
        self.resp_formatter = \
            '{0:>12} {1:>10d} {2:>6} ' \
            '{3:>16} {4:>10} ' \
            '{5:>16} {6:>10} ' \
            '{7:>12} {8:>16} {9:>10} ' \
            '{10:>14} {11:>14} ' \
            '{12:>8d} ' \
            '{13:>' + mastr + ' {14:>' + mahstr

    def print_view(self):
        self._print_headers()
        self._print_branches()

    def _print_headers(self):
        self._console_print.cpprint(self.header_formatter.format(
            'BRANCH', 'BRANCH', 'ACTIVE',
            'TAIL', 'TAIL',
            'HEAD', 'HEAD',
            'ANCESTOR', 'ANCESTOR', 'ANCESTOR',
            'CREATE TIME', 'LAST ACTIVE',
            'ACTIVE',
            'ACTIVE', 'ACTIVE'),
            reverse=True)

        self._console_print.cpprint(self.header_formatter.format(
            'ID', 'LENGTH', 'STATUS',
            'BLOCK ID', 'BLOCK NUM',
            'BLOCK ID', 'BLOCK NUM',
            'BRANCH ID', 'BLOCK ID', 'BLOCK NUM',
            'MM:DD:HH:MM:SS', 'MM:DD:HH:MM:SS',
            'COUNT',
            'LIST', 'HISTORY'),
            reverse=True)

    def _print_branches(self):
        for branch in self._branch_manager.branches:
            self._print_branch(branch)

    def _print_branch(self, branch):
        branch_create_time = time.strftime(
            "%m:%d:%H:%M:%S", time.localtime(branch.create_time))
        branch_last_active_time = time.strftime(
            "%m:%d:%H:%M:%S", time.localtime(branch.last_active_time))
        ancestor_branch_id = "None" if branch.ancestor_branch is None \
            else branch.ancestor_branch.bcb_id
        ancestor_block_id = "None" if branch.ancestor_branch is None \
            else branch.ancestor_block_id
        ancestor_block_num = "None" if branch.ancestor_branch is None \
            else str(branch.ancestor_block_num)

        self._console_print.cpprint(self.resp_formatter.format(
            branch.bcb_id,
            branch.block_count,
            "Active" if branch.is_active else "Idle",
            branch.tail_block_id,
            str(branch.tail_block_num),
            branch.head_block_id,
            str(branch.head_block_num),
            ancestor_branch_id,
            ancestor_block_id,
            ancestor_block_num,
            branch_create_time,
            branch_last_active_time,
            branch.is_active_count,
            str(branch.is_active_list).replace(" ", ""),
            str(branch.is_active_history).replace(" ", "")),
            False)


class ForkView(object):
    def __init__(self, console_print, branch_manager):
        self._console_print = console_print
        self._branch_manager = branch_manager

        self.header_formatter = \
            '{0:>12} {1:>10} {2:>10} ' \
            '{3:>16} {4:>10} ' \
            '{5:>16} {6:>10} ' \
            '{7:>9} {8:>6} ' \
            '{9:>10} ' \
            '{10:>16} {11:>10} '
        self.resp_formatter = \
            '{0:>12} {1:>10d} {2:>10d} ' \
            '{3:>16} {4:>10} ' \
            '{5:>16} {6:>10} ' \
            '{7:>9d} {8:>6} ' \
            '{9:>10} ' \
            '{10:>16} {11:>10} '

    def print_view(self):
        self._print_headers()
        self._print_forks()

    def _print_headers(self):
        self._console_print.cpprint(self.header_formatter.format(
            'FORK', 'TOTAL', 'BRANCH',
            'TAIL', 'TAIL',
            'HEAD', 'HEAD',
            'VALIDATOR', 'FORK',
            'FORK',
            'INTERCEPT', 'INTERCEPT'),
            reverse=True)

        self._console_print.cpprint(self.header_formatter.format(
            'ID', 'LENGTH', 'COUNT',
            'BLOCK ID', 'BLOCK NUM',
            'BLOCK ID', 'BLOCK NUM',
            'COUNT', 'STATUS',
            'LENGTH',
            'BLOCK ID', 'BLOCK NUM'),
            reverse=True)

    def _print_forks(self):
        for fork in self._branch_manager.forks:
            self._print_fork(fork)

    def _print_fork(self, fork):
        status = "parent" if fork.is_parent is True else "child"
        fork_intercept_length = "" if \
            fork.fork_intercept_length is None else \
            str(fork.fork_intercept_length)
        intercept_block_id = "" if \
            fork.intercept_block_id is None else str(fork.intercept_block_id)
        intercept_block_num = "" if \
            fork.intercept_block_num is None else str(fork.intercept_block_num)
        self._console_print.cpprint(self.resp_formatter.format(
            fork.bcf_id,
            fork.block_count,
            fork.branch_count,
            fork.tail_block_id,
            fork.tail_block_num,
            fork.head_block_id,
            fork.tail_block_num,
            fork.validator_count,
            status,
            fork_intercept_length,
            intercept_block_id,
            intercept_block_num),
            False)

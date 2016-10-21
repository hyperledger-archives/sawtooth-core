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

curses_imported = True
try:
    import curses
except ImportError:
    curses_imported = False


class ConsolePrint(object):

    def __init__(self):
        self.use_curses = True if curses_imported else False
        self.start = True
        self.scrn = None

        if self.use_curses:
            self.scrn = curses.initscr()

            curses.noecho()
            curses.cbreak()

            self.scrn.nodelay(1)

    def cpprint(self, print_string, finish=False, reverse=False):
        if self.use_curses:
            try:
                attr = curses.A_NORMAL
                if reverse:
                    attr = curses.A_REVERSE
                if self.start:
                    self.scrn.erase()
                    self.start = False
                hw = self.scrn.getmaxyx()
                pos = self.scrn.getyx()
                if pos[0] < hw[0] and pos[1] == 0:
                    print_string = print_string[:hw[1] - 1]
                    self.scrn.addstr(print_string, attr)
                    if pos[0] + 1 < hw[0]:
                        self.scrn.move(pos[0] + 1, 0)
                if finish:
                    self.scrn.refresh()
                    self.start = True
            except curses.CursesError as e:
                # show curses errors at top of screen for easier debugging
                self.scrn.move(0, 0)
                self.scrn.addstr("{} {} {} {}\n".format(type(e), e, pos, hw),
                                 attr)
                self.scrn.addstr(print_string + "\n", attr)
        else:
            print print_string

    def cpstop(self):
        if self.use_curses:
            curses.nocbreak()
            self.scrn.keypad(0)
            curses.echo()
            curses.endwin()


class StatsPrintManager(object):
    def __init__(self,
                 system_stats,
                 platform_stats,
                 topology_stats,
                 branch_manager,
                 stats_clients):

        self.cp = ConsolePrint()
        self.ss = system_stats
        self.ps = platform_stats
        self.ts = topology_stats
        self.bm = branch_manager
        self.stats_clients = stats_clients

        self.view_mode = "general"
        self.print_view = self.print_general_view

    def print_stats(self):
        self.check_view()
        self.print_summary()
        self.print_view()
        self.cp.cpprint("", True)

    def check_view(self):
        if self.cp.scrn:
            char_buffer = self.cp.scrn.getch()

            view_options = {
                ord('g'): ["general", self.print_general_view],
                ord('p'): ["platform", self.print_platform_view],
                ord('c'): ["consensus", self.print_consensus_view],
                ord('n'): ["network", self.print_network_view],
                ord('t'): ["transaction", self.print_transaction_view],
                ord('k'): ["packet", self.print_packet_view],
                ord('b'): ["branch", self.print_branch_view],
                ord('f'): ["fork", self.print_fork_view]
            }

            vo = view_options.get(char_buffer)

            if vo is not None:
                self.view_mode = vo[0]
                self.print_view = vo[1]

    def print_summary(self):
        validator_formatter = \
            '{0:>16} ' \
            '{1:9d} {2:16.16} {3:9d} {4:16.16} {5:9.3f} {6:16.16} ' \
            '{7:9.3f} {8:16.16} {9:9d} {10:19.19}'
        self.cp.cpprint(validator_formatter.format(
            "Validators:",
            self.ss.sys_client.known_validators, "known",
            self.ss.sys_client.active_validators, "responding",
            self.ss.sys_client.avg_client_time, "avg time(s)",
            self.ss.sys_client.max_client_time, "max time(s)",
            self.ss.sys_client.runtime, "run time(s)"))

        blocks_formatter = \
            '{0:>16} ' \
            '{1:9d} {2:16.16} {3:9d} {4:16.16} {5:9d} {6:16.16} ' \
            '{7:9d} {8:16.16} {9:9d} {10:19.19}'
        self.cp.cpprint(blocks_formatter.format(
            "Blocks:",
            self.ss.sys_blocks.blocks_max_committed, "max committed",
            self.ss.sys_blocks.blocks_min_committed, "min committed",
            self.ss.sys_blocks.blocks_max_pending, "max pending",
            self.ss.sys_blocks.blocks_min_pending, "min pending",
            self.ss.sys_blocks.blocks_max_claimed, "max claimed",
            self.ss.sys_blocks.blocks_min_claimed, "min claimed"))

        txns_formatter = \
            '{0:>16} ' \
            '{1:9d} {2:16.16} {3:9d} {4:16.16} {5:9d} {6:16.16} ' \
            '{7:9d} {8:16.16} {9:9d} {10:19.19}'
        self.cp.cpprint(txns_formatter.format(
            "Transactions:",
            self.ss.sys_txns.txns_max_committed, "max committed",
            self.ss.sys_txns.txns_min_committed, "min committed",
            self.ss.sys_txns.txns_max_pending, "max pending",
            self.ss.sys_txns.txns_min_pending, "min pending",
            0, "rate (t/s)"))

        pkt_formatter = \
            '{0:>16} ' \
            '{1:9d} {2:16.16} {3:9d} {4:16.16} {5:9d} {6:16.16} ' \
            '{7:9d} {8:16.16} {9:9d} {10:19.19} {11:9d} {12:17.17}'
        self.cp.cpprint(pkt_formatter.format(
            "Packet totals:",
            self.ss.sys_packets.packets_max_dropped, "max dropped",
            self.ss.sys_packets.packets_min_dropped, "min dropped",
            self.ss.sys_packets.packets_max_duplicates, "max duplicated",
            self.ss.sys_packets.packets_min_duplicates, "min duplicated",
            self.ss.sys_packets.packets_max_acks_received, "max acks rcvd",
            self.ss.sys_packets.packets_min_acks_received, "min acks rcvd"))

        msg_formatter = \
            '{0:>16} ' \
            '{1:9d} {2:16.16} {3:9d} {4:16.16} {5:9d} {6:16.16} ' \
            '{7:9d} {8:16.16}'
        self.cp.cpprint(msg_formatter.format(
            "Message totals:",
            self.ss.sys_msgs.msgs_max_handled, "max handled",
            self.ss.sys_msgs.msgs_min_handled, "min handled",
            self.ss.sys_msgs.msgs_max_acked, "max acked",
            self.ss.sys_msgs.msgs_min_acked, "min acked"))

        platform_formatter = \
            '{0:>16} ' \
            '{1:9.2f} {2:16.16} {3:9.2f} {4:16.16} {5:9d} {6:16.16} ' \
            '{7:9d} {8:16.16}'
        self.cp.cpprint(platform_formatter.format(
            "Platform:",
            self.ps.cpu_stats.percent, "cpu pct",
            self.ps.vmem_stats.percent, "vmem pct",
            self.ps.psis.intv_net_bytes_sent, "ntwrk bytes tx",
            self.ps.psis.intv_net_bytes_recv, "ntwrk bytes rx"))

        topo_1_formatter = \
            '{0:>16} ' \
            '{1:9d} {2:16.16} {3:9d} {4:16.16} {5:9d} {6:16.16} ' \
            '{7:9d} {8:16.16} {9:9.2f} {10:19.19}'
        self.cp.cpprint(topo_1_formatter.format(
            "Topology:",
            self.ts.connected_component_count, "components",
            self.ts.node_count, "nodes",
            self.ts.edge_count, "edges",
            self.ts.maximum_degree, "max peers",
            self.ts.minimum_degree, "min peers"))

        topo_2_formatter = \
            '{0:>16} ' \
            '{1:9.2f} {2:16.16} {3:9d} {4:16.16} {5:9d} {6:16.16} ' \
            '{7:9.2f} {8:16.16} {9:9.2f} {10:19.19}'
        self.cp.cpprint(topo_2_formatter.format(
            "Topology:",
            self.ts.average_shortest_path_length, "avg shortest pth",
            self.ts.maximum_shortest_path_length, "max shortest pth",
            self.ts.minimum_connectivity, "min connectivity",
            self.ts.maximum_degree_centrality, "max degree cent",
            self.ts.maximum_between_centrality, "max between cent"))

        branch_formatter = \
            '{0:>16} ' \
            '{1:9d} {2:16.16} {3:9d} {4:16.16} {5:9d} {6:16.16} ' \
            '{7:9d} {8:16.16} {9:9d} {10:19.19} {11:9d} {12:17.17}'
        self.cp.cpprint(branch_formatter.format(
            "Branch:",
            self.bm.bm_stats.identified, "identified",
            self.bm.bm_stats.active, "active",
            self.bm.bm_stats.longest, "longest",
            self.bm.bm_stats.longest_active, "longest active",
            self.bm.bm_stats.next_longest_active, "next longest active",
            # self.bm.bm_stats.validators, "validator count"))
            self.bm.bm_stats.blocks_processed, "blocks processed"))

        fork_formatter = \
            '{0:>16} ' \
            '{1:9} {2:16.16} {3:9d} {4:16.16} {5:9d} {6:16.16} ' \
            '{7:9d} {8:16.16} {9:9d} {10:19.19}'
        self.cp.cpprint(fork_formatter.format(
            "Fork:",
            self.bm.f_stats.status, "status",
            self.bm.f_stats.fork_count, "fork count",
            self.bm.f_stats.parent_count, "parent forks",
            self.bm.f_stats.child_count, "child forks",
            self.bm.f_stats.longest_child_fork_length, "longest child fork"))

        poet_formatter = \
            '{0:>16} ' \
            '{1:9.2f} {2:16.16} {3:9.2f} {4:16.16} {5:9.2f} {6:16.16} ' \
            '{7:>26.16} {8:22.22}'
        self.cp.cpprint(poet_formatter.format(
            "Poet:",
            self.ss.poet_stats.avg_local_mean, "avg local mean",
            self.ss.poet_stats.max_local_mean, "max local mean",
            self.ss.poet_stats.min_local_mean, "min local mean",
            self.ss.poet_stats.last_unique_blockID, "last unique block ID"))

        view_formatter = \
            '{0:>16} ' \
            '{1:>9} {2:16.16} {3:>9} {4:16.16} {5:>9} {6:16.16} ' \
            '{7:>9} {8:16.16} {9:>9} {10:19.19}'
        self.cp.cpprint(view_formatter.format(
            "View ({0:1.8}):".format(self.view_mode),
            "(g)", "general",
            "(t)", "transaction",
            "(k)", "packet",
            "(c)", "consensus",
            "(o)", "topology"))

        view_formatter_2 = \
            '{0:>16} ' \
            '{1:>9} {2:16.16} {3:>9} {4:16.16} {5:>9} {6:16.16} ' \
            '{7:>9} {8:16.16}'
        self.cp.cpprint(view_formatter_2.format(
            "View ({0:1.8}):".format(self.view_mode),
            "(p)", "platform",
            "(n)", "network",
            "(b)", "branch",
            "(f)", "fork"))

    def print_general_view(self):
        header_formatter = \
            '{0:>5} {1:>8} ' \
            '{2:>8} {3:>7} {4:>9} {5:>7} ' \
            '{6:>11} {7:>7} {8:>9} {9:>7} {10:>8}  {11:>16} ' \
            '{12:>18.18} {13:>28.28}'
        resp_formatter = \
            '{0:5d} {1:>8} ' \
            '{2:8.3f} {3:7d} {4:9d} {5:7d} ' \
            '{6:11d} {7:7d} {8:9.2f} {9:7.2f} {10:8.2f}  {11:>16.16} ' \
            '{12:>18.18} {13:>28.28}'
        no_resp_formatter = \
            '{0:5d} {1:>8} ' \
            '{2:31} {3} {4} {5} ' \
            '{6:>11} {7:>7} {8:>9} {9:>7} {10:>8}  {11:>16} ' \
            '{12:>18.18} {13:>28.28}'

        self.cp.cpprint(header_formatter.format(
            'VAL', 'VAL',
            'RESPONSE', 'BLOCKS', 'BLOCKS', 'BLOCKS',
            'TXNS', 'TXNS', 'AVG TXN', 'AVG BLK', 'LOCAL', 'PREVIOUS',
            ' VALIDATOR', 'VALIDATOR'),
            reverse=True)

        self.cp.cpprint(header_formatter.format(
            'ID', 'STATE',
            'TIME(S)', 'CLAIMED', 'COMMITTED', 'PENDING',
            'COMMITTED', 'PENDING', 'RATE(T/S)', 'TIME(S)', 'MEAN', 'BLOCKID',
            'NAME', 'URL'),
            reverse=True)

        for c in self.stats_clients:
            if c.responding:
                self.cp.cpprint(resp_formatter.format(
                    c.id,
                    c.validator_state,
                    c.response_time,
                    c.vsm.val_stats["journal"]["BlocksClaimed"],
                    c.vsm.val_stats["journal"]["CommittedBlockCount"],
                    c.vsm.val_stats["journal"]["PendingBlockCount"],
                    c.vsm.val_stats["journal"].get("CommittedTxnCount", 0),
                    c.vsm.val_stats["journal"].get("PendingTxnCount", 0),
                    c.vsm.txn_rate.avg_txn_rate,
                    c.vsm.txn_rate.avg_block_time,
                    c.vsm.val_stats["journal"].get("LocalMeanTime", 0.0),
                    c.vsm.val_stats["journal"].get("PreviousBlockID",
                                                   'not reported'),
                    c.name[:16],
                    c.url),
                    False)
            else:
                self.cp.cpprint(no_resp_formatter.format(
                    c.id,
                    c.validator_state,
                    c.no_response_reason, "", "", "",
                    "", "", "", "", "", "",
                    c.name[:16],
                    c.url),
                    False)

    def print_platform_view(self):
        header_formatter = \
            '{0:>5} {1:>8} ' \
            '{2:>8} {3:>8} {4:>8} {5:>8} ' \
            '{6:>8} {7:>8} {8:>8} ' \
            '{9:>8} {10:>8} {11:>8} {12:>8} ' \
            '{13:>18.18} {14:>28.28}'
        resp_formatter = \
            '{0:5d} {1:>8} ' \
            '{2:8.2f} {3:8.2f} {4:8.2f} {5:8.2f} ' \
            '{6:8.2f} {7:8d} {8:8d} ' \
            '{9:8d} {10:8d} {11:8d} {12:8d} ' \
            '{13:>18.18} {14:>28.28}'
        no_resp_formatter = \
            '{0:5d} {1:>8} ' \
            '{2:>8} {3:>8} {4:>8} {5:>8} ' \
            '{6:>8} {7:>8} {8:>8} ' \
            '{9:>8} {10:>8} {11:>8} {12:>8}  ' \
            '{13:>18.18} {14:>28.28}'

        self.cp.cpprint(header_formatter.format(
            'VAL', 'VAL',
            'CPU', 'CPU', 'CPU', 'CPU',
            'MEM', 'MEM', 'MEM',
            'DISK', 'DISK', 'DISK', 'DISK',
            ' VALIDATOR', 'VALIDATOR'),
            reverse=True)

        self.cp.cpprint(header_formatter.format(
            'ID', 'STATE',
            'PERCENT', 'USER PCT', 'SYS PCT', 'IDLE PCT',
            'PERCENT', 'TOTAL MB', 'AVAIL MB',
            'RD BYTES', 'WR BYTES', 'RD COUNT', 'WR COUNT',
            'NAME', 'URL'),
            reverse=True)

        for c in self.stats_clients:
            if c.responding:
                self.cp.cpprint(resp_formatter.format(
                    c.id,
                    c.validator_state,
                    c.vsm.val_stats["platform"]["scpu"]["percent"],
                    c.vsm.val_stats["platform"]["scpu"]["user_time"],
                    c.vsm.val_stats["platform"]["scpu"]["system_time"],
                    c.vsm.val_stats["platform"]["scpu"]["idle_time"],
                    c.vsm.val_stats["platform"]["svmem"]["percent"],
                    c.vsm.val_stats["platform"]["svmem"]["total"] / 1000000,
                    c.vsm.val_stats["platform"]["svmem"]["available"] /
                    1000000,
                    c.vsm.psis.intv_disk_bytes_read,
                    c.vsm.psis.intv_disk_bytes_write,
                    c.vsm.psis.intv_disk_count_read,
                    c.vsm.psis.intv_disk_count_write,
                    c.name[:16],
                    c.url),
                    False)
            else:
                self.cp.cpprint(no_resp_formatter.format(
                    c.id,
                    c.validator_state,
                    "", "", "", "", "",
                    "", "", "",
                    "", "", "", "",
                    c.name[:16],
                    c.url),
                    False)

    def print_consensus_view(self):
        header_formatter = \
            '{0:>5} {1:>8} ' \
            '{2:>8} {3:>10} {4:>12} {5:>16} ' \
            '{6:>18.18} {7:>28.28}'
        resp_formatter = \
            '{0:5d} {1:>8} ' \
            '{2:8.2f} {3:10.2f} {4:12.2f} {5:16.16} ' \
            '{6:>18.18} {7:>28.28}'
        no_resp_formatter = \
            '{0:5d} {1:>8} ' \
            '{2:>8} {3:>10} {4:>12} {5:>16} ' \
            '{6:>18.18} {7:>28.28}'

        self.cp.cpprint(header_formatter.format(
            'VAL', 'VAL',
            'LOCAL', 'POPULATION', 'AGGREGATE', 'LAST',
            ' VALIDATOR', 'VALIDATOR'),
            reverse=True)

        self.cp.cpprint(header_formatter.format(
            'ID', 'STATE',
            'MEAN', 'ESTIMATE', 'LOCALMEAN', 'BLOCKID',
            'NAME', 'URL'),
            reverse=True)

        for c in self.stats_clients:
            if c.responding:
                self.cp.cpprint(resp_formatter.format(
                    c.id,
                    c.validator_state,
                    c.vsm.val_stats["journal"].get("LocalMeanTime", 0.0),
                    c.vsm.val_stats["journal"].get("PopulationEstimate", 0.0),
                    c.vsm.val_stats["journal"].get("AggregateLocalMean", 0.0),
                    c.vsm.val_stats["journal"].get("PreviousBlockID", 'error'),

                    c.name[:16],
                    c.url),
                    False)
            else:
                self.cp.cpprint(no_resp_formatter.format(
                    c.id,
                    c.validator_state,
                    "", "", "", "",
                    c.name[:16],
                    c.url),
                    False)

    def print_packet_view(self):
        header_formatter = \
            '{0:>5} {1:>8} ' \
            '{2:>10} {3:>10} {4:>10} {5:>10} ' \
            '{6:>12} {7:>12} {8:>12} {9:>12}' \
            '{10:>18.18} {11:>28.28}'
        resp_formatter = \
            '{0:5d} {1:>8} ' \
            '{2:10d} {3:10d} {4:10d} {5:10d} ' \
            '{6:12d} {7:12d} {8:12d} {9:12d}' \
            '{10:>18.18} {11:>28.28}'
        no_resp_formatter = \
            '{0:5d} {1:>8} ' \
            '{2:>10} {3:>10} {4:>10} {5:>10} ' \
            '{6:>12} {7:>12} {8:>12} {9:>12}' \
            '{10:>18.18} {11:>28.28}'

        self.cp.cpprint(header_formatter.format(
            'VAL', 'VAL',
            'ACKS', 'BYTES', 'BYTES', 'PACKETS',
            'PACKETS', 'UNACKED', 'MESSAGE', 'MESSAGE',
            ' VALIDATOR', 'VALIDATOR'),
            reverse=True)

        self.cp.cpprint(header_formatter.format(
            'ID', 'STATE',
            'RECEIVED', 'RECEIVED', 'SENT', 'DROPPED',
            'DUPLICATED', 'PACKETCOUNT', 'ACKED', 'HANDLED',
            'NAME', 'URL'),
            reverse=True)

        for c in self.stats_clients:
            if c.responding:
                self.cp.cpprint(resp_formatter.format(
                    c.id,
                    c.validator_state,
                    c.vsm.val_stats["packet"]["AcksReceived"],
                    c.vsm.val_stats["packet"]["BytesReceived"][0],
                    c.vsm.val_stats["packet"]["BytesSent"][0],
                    c.vsm.val_stats["packet"]["DroppedPackets"],
                    c.vsm.val_stats["packet"]["DuplicatePackets"],
                    c.vsm.val_stats["packet"]["UnackedPacketCount"],
                    c.vsm.val_stats["packet"]["MessagesAcked"],
                    c.vsm.val_stats["packet"]["MessagesHandled"],

                    c.name[:16],
                    c.url),
                    False)
            else:
                self.cp.cpprint(no_resp_formatter.format(
                    c.id,
                    c.validator_state,
                    "", "", "", "",
                    "", "", "", "",
                    c.name[:16],
                    c.url),
                    False)

    def print_network_view(self):
        header_formatter = \
            '{0:>5} {1:>8} ' \
            '{2:>10} {3:>10} {4:>12} {5:>12} ' \
            '{6:>12} {7:>12} {8:>14} {9:>14}' \
            '{10:>18.18} {11:>28.28}'
        resp_formatter = \
            '{0:5d} {1:>8} ' \
            '{2:10d} {3:10d} {4:12d} {5:12d} ' \
            '{6:12d} {7:12d} {8:14d} {9:14d}' \
            '{10:>18.18} {11:>28.28}'
        no_resp_formatter = \
            '{0:5d} {1:>8} ' \
            '{2:>10} {3:>10} {4:>12} {5:>12} ' \
            '{6:>12} {7:>12} {8:>14} {9:>14}' \
            '{10:>18.18} {11:>28.28}'

        self.cp.cpprint(header_formatter.format(
            'VAL', 'VAL',
            'SEND', 'RECEIVE', 'SEND', 'RECEIVE',
            'SEND', 'RECEIVE', 'SEND', 'RECEIVE',
            ' VALIDATOR', 'VALIDATOR'),
            reverse=True)

        self.cp.cpprint(header_formatter.format(
            'ID', 'STATE',
            'BYTES', 'BYTES', 'PCKT BYTES', 'PCKT BYTES',
            'BYTES ERR', 'BYTES ERR', 'DROPPED PCKTS', 'DROPPED PCKTS',
            'NAME', 'URL'),
            reverse=True)

        for c in self.stats_clients:
            if c.responding:
                self.cp.cpprint(resp_formatter.format(
                    c.id,
                    c.validator_state,
                    c.vsm.val_stats["platform"]["snetio"]["bytes_recv"],
                    c.vsm.val_stats["platform"]["snetio"]["bytes_sent"],
                    c.vsm.val_stats["platform"]["snetio"]["packets_recv"],
                    c.vsm.val_stats["platform"]["snetio"]["packets_sent"],
                    c.vsm.val_stats["platform"]["snetio"]["errout"],
                    c.vsm.val_stats["platform"]["snetio"]["errin"],
                    c.vsm.val_stats["platform"]["snetio"]["dropout"],
                    c.vsm.val_stats["platform"]["snetio"]["dropin"],

                    c.name[:16],
                    c.url),
                    False)
            else:
                self.cp.cpprint(no_resp_formatter.format(
                    c.id,
                    c.validator_state,
                    "", "", "", "",
                    "", "", "", "",
                    c.name[:16],
                    c.url),
                    False)

    def print_transaction_view(self):
        header_formatter = \
            '{0:>5} {1:>8} ' \
            '{2:>10} {3:>10} {4:>12} {5:>12} ' \
            '{6:>16} {7:>14} {8:>14}' \
            '{9:>18.18} {10:>28.28}'
        resp_formatter = \
            '{0:5d} {1:>8} ' \
            '{2:10d} {3:10d} {4:12d} {5:12d} ' \
            '{6:16d} {7:14d} {8:14d}' \
            '{9:>18.18} {10:>28.28}'
        no_resp_formatter = \
            '{0:5d} {1:>8} ' \
            '{2:>10} {3:>10} {4:>12} {5:>12} ' \
            '{6:>16} {7:>14} {8:>14}' \
            '{9:>18.18} {10:>28.28}'

        self.cp.cpprint(header_formatter.format(
            'VAL', 'VAL',
            'BLOCK', 'BLOCK', 'TXN', 'TXN',
            'MISSING TXN', 'MISSING TXN', 'INVALID',
            ' VALIDATOR', 'VALIDATOR'),
            reverse=True)

        self.cp.cpprint(header_formatter.format(
            'ID', 'STATE',
            'COMMITTED', 'PENDING', 'COMMITTED', 'PENDING',
            'DEPENDENCY CNT', 'BLOCK CNT', 'TXN CNT',
            'NAME', 'URL'),
            reverse=True)

        for c in self.stats_clients:
            if c.responding:
                self.cp.cpprint(resp_formatter.format(
                    c.id,
                    c.validator_state,
                    c.vsm.val_stats["journal"]["CommittedBlockCount"],
                    c.vsm.val_stats["journal"]["PendingBlockCount"],
                    c.vsm.val_stats["journal"]["CommittedTxnCount"],
                    c.vsm.val_stats["journal"]["PendingTxnCount"],
                    c.vsm.val_stats["journal"]["MissingTxnDepCount"],
                    c.vsm.val_stats["journal"]["MissingTxnFromBlockCount"],
                    c.vsm.val_stats["journal"]["InvalidTxnCount"],

                    c.name[:16],
                    c.url),
                    False)
            else:
                self.cp.cpprint(no_resp_formatter.format(
                    c.id,
                    c.validator_state,
                    "", "", "", "",
                    "", "", "",
                    c.name[:16],
                    c.url),
                    False)

    def print_branch_view(self):
        # determine which branch has the longest active list
        # and active history list; size columns to match
        max_active = 0
        max_active_history = 0
        for b in self.bm.branches:
            als = str(b.is_active_list).replace(" ", "")
            ahls = str(b.is_active_history).replace(" ", "")
            if len(als) > max_active:
                max_active = len(als)
            if len(ahls) > max_active_history:
                max_active_history = len(ahls)
        mastr = str(max_active) + '}'
        mahstr = str(max_active_history) + '}'

        header_formatter = \
            '{0:>12} {1:>10} {2:>6} ' \
            '{3:>16} {4:>10} ' \
            '{5:>16} {6:>10} ' \
            '{7:>12} {8:>16} {9:>10} ' \
            '{10:>14} {11:>14} ' \
            '{12:>8} ' \
            '{13:>' + mastr + ' {14:>' + mahstr
        resp_formatter = \
            '{0:>12} {1:>10d} {2:>6} ' \
            '{3:>16} {4:>10} ' \
            '{5:>16} {6:>10} ' \
            '{7:>12} {8:>16} {9:>10} ' \
            '{10:>14} {11:>14} ' \
            '{12:>8d} ' \
            '{13:>' + mastr + ' {14:>' + mahstr

        self.cp.cpprint(header_formatter.format(
            'BRANCH', 'BRANCH', 'ACTIVE',
            'TAIL', 'TAIL',
            'HEAD', 'HEAD',
            'ANCESTOR', 'ANCESTOR', 'ANCESTOR',
            'CREATE TIME', 'LAST ACTIVE',
            'ACTIVE',
            'ACTIVE', 'ACTIVE'),
            reverse=True)

        self.cp.cpprint(header_formatter.format(
            'ID', 'LENGTH', 'STATUS',
            'BLOCK ID', 'BLOCK NUM',
            'BLOCK ID', 'BLOCK NUM',
            'BRANCH ID', 'BLOCK ID', 'BLOCK NUM',
            'MM:DD:HH:MM:SS', 'MM:DD:HH:MM:SS',
            'COUNT',
            'LIST', 'HISTORY'),
            reverse=True)

        for b in self.bm.branches:
            branch_create_time = time.strftime(
                "%m:%d:%H:%M:%S", time.localtime(b.create_time))
            branch_last_active_time = time.strftime(
                "%m:%d:%H:%M:%S", time.localtime(b.last_active_time))
            ancestor_branch_id = \
                "None" if b.ancestor_branch is None else b.ancestor_branch.id
            ancestor_block_id = \
                "None" if b.ancestor_branch is None else b.ancestor_block_id
            ancestor_block_num = \
                "None" if \
                b.ancestor_branch is None else str(b.ancestor_block_num)

            self.cp.cpprint(resp_formatter.format(
                b.id,
                len(b.blocks),
                "Active" if b.is_active else "Idle",
                b.tail_block_id,
                str(b.tail_block_num),
                b.head_block_id,
                str(b.head_block_num),
                ancestor_branch_id,
                ancestor_block_id,
                ancestor_block_num,
                branch_create_time,
                branch_last_active_time,
                len(b.is_active_list),
                str(b.is_active_list).replace(" ", ""),
                str(b.is_active_history).replace(" ", "")),
                False)

    def print_fork_view(self):

        header_formatter = \
            '{0:>12} {1:>10} {2:>10} ' \
            '{3:>16} {4:>10} ' \
            '{5:>16} {6:>10} ' \
            '{7:>9} {8:>6} ' \
            '{9:>10} ' \
            '{10:>16} {11:>10} '

        resp_formatter = \
            '{0:>12} {1:>10d} {2:>10d} ' \
            '{3:>16} {4:>10} ' \
            '{5:>16} {6:>10} ' \
            '{7:>9d} {8:>6} ' \
            '{9:>10} ' \
            '{10:>16} {11:>10} '

        self.cp.cpprint(header_formatter.format(
            'FORK', 'TOTAL', 'BRANCH',
            'TAIL', 'TAIL',
            'HEAD', 'HEAD',
            'VALIDATOR', 'FORK',
            'FORK',
            'INTERCEPT', 'INTERCEPT'),
            reverse=True)

        self.cp.cpprint(header_formatter.format(
            'ID', 'LENGTH', 'COUNT',
            'BLOCK ID', 'BLOCK NUM',
            'BLOCK ID', 'BLOCK NUM',
            'COUNT', 'STATUS',
            'LENGTH',
            'BLOCK ID', 'BLOCK NUM'),
            reverse=True)

        for f in self.bm.forks:
            status = "parent" if f.is_parent is True else "child"
            fork_intercept_length = "" if \
                f.fork_intercept_length is None else \
                str(f.fork_intercept_length)
            intercept_block_id = "" if \
                f.intercept_block_id is None else str(f.intercept_block_id)
            intercept_block_num = "" if \
                f.intercept_block_num is None else str(f.intercept_block_num)
            self.cp.cpprint(resp_formatter.format(
                f.id,
                f.block_count,
                f.branch_count,
                f.tail_block_id,
                f.tail_block_num,
                f.head_block_id,
                f.tail_block_num,
                f.validator_count,
                status,
                fork_intercept_length,
                intercept_block_id,
                intercept_block_num),
                False)

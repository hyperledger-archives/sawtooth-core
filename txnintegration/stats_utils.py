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


class StatsPrintManager(object):
    def __init__(self, system_stats, platform_stats, clients):
        self.cp = ConsolePrint()
        self.ss = system_stats
        self.ps = platform_stats
        self.clients = clients

    def print_stats(self):

        validator_formatter = \
            '{0:>15} ' \
            '{1:9d} {2:14.14} {3:9d} {4:14.14} {5:9.3f} {6:14.14} ' \
            '{7:9.3f} {8:14.14} {9:9d} {10:14.14}'
        self.cp.cpprint(validator_formatter.format(
            "Validators:",
            self.ss.sys_client.known_validators, "known",
            self.ss.sys_client.active_validators, "responding",
            self.ss.sys_client.avg_client_time, "avg time(s)",
            self.ss.sys_client.max_client_time, "max time(s)",
            self.ss.sys_client.runtime, "run time(s)"))

        blocks_formatter = \
            '{0:>15} ' \
            '{1:9d} {2:14.14} {3:9d} {4:14.14} {5:9d} {6:14.14} ' \
            '{7:9d} {8:14.14} {9:9d} {10:14.14}'
        self.cp.cpprint(blocks_formatter.format(
            "Blocks:",
            self.ss.sys_blocks.blocks_max_committed, "max committed",
            self.ss.sys_blocks.blocks_min_committed, "min committed",
            self.ss.sys_blocks.blocks_max_pending, "max pending",
            self.ss.sys_blocks.blocks_min_pending, "min pending",
            self.ss.sys_blocks.blocks_max_claimed, "max claimed",
            self.ss.sys_blocks.blocks_min_claimed, "min claimed"))

        txns_formatter = \
            '{0:>15} ' \
            '{1:9d} {2:14.14} {3:9d} {4:14.14} {5:9d} {6:14.14} ' \
            '{7:9d} {8:14.14} {9:9d} {10:14.14}'
        self.cp.cpprint(txns_formatter.format(
            "Transactions:",
            self.ss.sys_txns.txns_max_committed, "max committed",
            self.ss.sys_txns.txns_min_committed, "min committed",
            self.ss.sys_txns.txns_max_pending, "max pending",
            self.ss.sys_txns.txns_min_pending, "min pending",
            0, "rate (t/s)"))

        pkt_formatter = \
            '{0:>15} ' \
            '{1:9d} {2:14.14} {3:9d} {4:14.14} {5:9d} {6:14.14} ' \
            '{7:9d} {8:14.14} {9:9d} {10:14.14} {11:9d} {12:14.14}'
        self.cp.cpprint(pkt_formatter.format(
            "Packet totals:",
            self.ss.sys_packets.packets_max_dropped, "max dropped",
            self.ss.sys_packets.packets_min_dropped, "min dropped",
            self.ss.sys_packets.packets_max_duplicates, "max duplicated",
            self.ss.sys_packets.packets_min_duplicates, "min duplicated",
            self.ss.sys_packets.packets_max_acks_received, "max acks rcvd",
            self.ss.sys_packets.packets_min_acks_received, "min acks rcvd"))

        msg_formatter = \
            '{0:>15} ' \
            '{1:9d} {2:14.14} {3:9d} {4:14.14} {5:9d} {6:14.14} ' \
            '{7:9d} {8:14.14}'
        self.cp.cpprint(msg_formatter.format(
            "Message totals:",
            self.ss.sys_msgs.msgs_max_handled, "max handled",
            self.ss.sys_msgs.msgs_min_handled, "min handled",
            self.ss.sys_msgs.msgs_max_acked, "max acked",
            self.ss.sys_msgs.msgs_min_acked, "min acked"))

        platform_formatter = \
            '{0:>15} ' \
            '{1:9.2f} {2:14.14} {3:9.2f} {4:14.14} {5:9d} {6:14.14} ' \
            '{7:9d} {8:14.14}'
        self.cp.cpprint(platform_formatter.format(
            "Platform stats:",
            self.ps.cpu_stats.percent, "cpu pct",
            self.ps.vmem_stats.percent, "vmem pct",
            self.ps.interval_net_bytes_sent, "ntwrk bytes tx",
            self.ps.interval_net_bytes_recv, "ntwrk bytes rx"))

        poet_formatter = \
            '{0:>15} ' \
            '{1:9.2f} {2:14.14} {3:9.2f} {4:14.14} {5:9.2f} {6:14.14} ' \
            '{7:>26.16} {8:22.22}'
        self.cp.cpprint(poet_formatter.format(
            "Poet stats:",
            self.ss.poet_stats.avg_local_mean, "avg local mean",
            self.ss.poet_stats.max_local_mean, "max local mean",
            self.ss.poet_stats.min_local_mean, "min local mean",
            self.ss.poet_stats.last_unique_blockID, "last unique block ID"))

        header_formatter = \
            '{0:>6} {1:>7} {2:>9} {3:>9} {4:>9} {5:>9} ' \
            '{6:>7}  {7:>16} {8:>9} {9:>9} {10:>18.18} {11:>28.28}'
        resp_formatter = \
            '{0:6d} {1:>7} {2:9.3f} {3:9d} {4:9d} {5:9d} ' \
            '{6:7.2f}  {7:>16.16} {8:9d} {9:9d} {10:>18.18} {11:>28.28}'
        no_resp_formatter = \
            '{0:6d} {1:>7} {2:>9} {3:>9} {4:>9} {5:>9} ' \
            '{6:>7}  {7:>16} {8:>9} {9:>9} {10:>18.18} {11:>28.28}'

        self.cp.cpprint(header_formatter.format(
            'VAL', 'VAL', 'RESPONSE', 'BLOCKS', 'BLOCKS', 'BLOCKS',
            'LOCAL', 'PREVIOUS', 'TXNS', 'TXNS', ' VAL', 'VAL'),
            reverse=True)

        self.cp.cpprint(header_formatter.format(
            'ID', 'STATE', 'TIME(S)', 'CLAIMED', 'COMMITTED', 'PENDING',
            'MEAN', 'BLOCKID', 'COMMITTED', 'PENDING', 'NAME', 'URL'),
            reverse=True)

        for c in self.clients:
            if c.responding:
                self.cp.cpprint(resp_formatter.format(
                    c.id,
                    c.validator_state,
                    c.response_time,
                    c.vsm.vstats.blocks_claimed,
                    c.vsm.vstats.blocks_committed,
                    c.vsm.vstats.blocks_pending,
                    c.vsm.vstats.local_mean,
                    c.vsm.vstats.previous_blockid,
                    c.vsm.vstats.txns_committed,
                    c.vsm.vstats.txns_pending,
                    c.name[:16],
                    c.url),
                    False)
            else:
                self.cp.cpprint(no_resp_formatter.format(
                    c.id,
                    c.validator_state,
                    "", "", "", "", "", "", "", "", "",
                    c.name[:16],
                    c.url),
                    False)
        self.cp.cpprint("", True)

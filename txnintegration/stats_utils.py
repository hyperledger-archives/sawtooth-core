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
        self.cp.cpprint('    Validators: {0:8d} known,'
                        '         {1:8d} responding,'
                        '      {2:8f} avg time(s),'
                        '    {3:8f} max time(s),'
                        '    {4:8d} run time(s)'
                        .format(self.ss.sys_client.known_validators,
                                self.ss.sys_client.active_validators,
                                self.ss.sys_client.avg_client_time,
                                self.ss.sys_client.max_client_time,
                                self.ss.sys_client.runtime))

        self.cp.cpprint('        Blocks: {0:8d} max committed,'
                        ' {1:8d} min committed,'
                        '   {2:8d} max pending,'
                        '    {3:8d} min pending,'
                        '    {4:8d} max claimed,'
                        '      {5:8d} min claimed'
                        .format(self.ss.sys_blocks.blocks_max_committed,
                                self.ss.sys_blocks.blocks_min_committed,
                                self.ss.sys_blocks.blocks_max_pending,
                                self.ss.sys_blocks.blocks_min_pending,
                                self.ss.sys_blocks.blocks_max_claimed,
                                self.ss.sys_blocks.blocks_min_claimed))
        self.cp.cpprint('  Transactions: {0:8d} max committed,'
                        ' {1:8d} min committed,'
                        '   {2:8d} max pending,'
                        '    {3:8d} min pending,'
                        '    {4:8d} rate (t/s)'
                        .format(self.ss.sys_txns.txns_max_committed,
                                self.ss.sys_txns.txns_min_committed,
                                self.ss.sys_txns.txns_max_pending,
                                self.ss.sys_txns.txns_min_pending,
                                0))
        self.cp.cpprint(' Packet totals: {0:8d} max dropped,'
                        '   {1:8d} min dropped,'
                        '     {2:8d} max duplicated,'
                        ' {3:8d} min duplicated,'
                        ' {4:8d} max aks received,'
                        ' {5:8d} min aks received'
                        .format(self.ss.sys_packets.packets_max_dropped,
                                self.ss.sys_packets.packets_min_dropped,
                                self.ss.sys_packets.packets_max_duplicates,
                                self.ss.sys_packets.packets_min_duplicates,
                                self.ss.sys_packets.packets_max_acks_received,
                                self.ss.sys_packets.packets_min_acks_received))
        self.cp.cpprint('Message totals: {0:8d} max handled,'
                        '   {1:8d} min handled,'
                        '     {2:8d} max acked,'
                        '      {3:8d} min acked'
                        .format(self.ss.sys_msgs.msgs_max_handled,
                                self.ss.sys_msgs.msgs_min_handled,
                                self.ss.sys_msgs.msgs_max_acked,
                                self.ss.sys_msgs.msgs_min_acked))
        self.cp.cpprint('Platform stats: {0:8f} cpu pct,'
                        '       {1:8f} vmem pct,'
                        '       {2:8d} net bytes tx,'
                        '  {3:8d} net bytes rx'
                        .format(self.ps.cpu_stats.percent,
                                self.ps.vmem_stats.percent,
                                self.ps.net_stats.bytes_sent,
                                self.ps.net_stats.bytes_recv))

        self.cp.cpprint('Poet Stats: {0:.2f} avg local mean,'
                        '       {1:.2f} max local mean,'
                        '       {2:.2f} min local mean,'
                        '       {3:8s} last unique blockID'
                        .format(self.ss.poet_stats.avg_local_mean,
                                self.ss.poet_stats.max_local_mean,
                                self.ss.poet_stats.min_local_mean,
                                self.ss.poet_stats.last_unique_blockID))

        self.cp.cpprint('   VAL     VAL  RESPONSE    BLOCKS    BLOCKS   BLOCKS'
                        '  LOCAL       PREVIOUS        TXNS     TXNS       '
                        '  VAL              VAL',
                        reverse=True)
        self.cp.cpprint('    ID   STATE      TIME   CLAIMED COMMITTED  PENDING'
                        '  MEAN        BLOCKID       COMMITTED  PENDING    '
                        '  NAME             URL',
                        reverse=True)

        for c in self.clients:
            if c.responding:
                self.cp.cpprint('{0:6d}  {1:6}  {2:8f}  {3:8d}  {4:8d} '
                                '{5:8d}  {6:.2f}  {7:8s}  {8:8d} {9:8d}  '
                                '{10:16}  {11:16}'
                                .format(c.id, c.validator_state,
                                        c.response_time,
                                        c.vsm.vstats.blocks_claimed,
                                        c.vsm.vstats.blocks_committed,
                                        c.vsm.vstats.blocks_pending,
                                        c.vsm.vstats.local_mean,
                                        c.vsm.vstats.previous_blockid,
                                        c.vsm.vstats.txns_committed,
                                        c.vsm.vstats.txns_pending,
                                        c.name[:16], c.url))
            else:
                self.cp.cpprint('{0:6d}  {1:6}                               '
                                '                             {2:16}   {3:16}'
                                .format(c.id, c.validator_state,
                                        c.name[:16], c.url))

        self.cp.cpprint("", True)

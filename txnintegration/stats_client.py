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

import json

from twisted.internet import task
from twisted.internet import reactor
from twisted.web.client import Agent
from twisted.web.client import readBody
from twisted.web.http_headers import Headers

from txnintegration.utils import StatsCollector
from txnintegration.utils import PlatformStats

import time
import csv
import collections

import argparse
import sys

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

    def cpprint(self, printstring, finish=False, reverse=False):
        if self.use_curses:
            attr = curses.A_NORMAL
            if reverse:
                attr = curses.A_REVERSE
            if self.start:
                self.scrn.erase()
                self.start = False
            hw = self.scrn.getmaxyx()
            self.scrn.addstr(printstring[:hw[1] - 1] + "\n", attr)
            if finish:
                self.scrn.refresh()
                self.start = True
        else:
            print printstring

    def cpstop(self):
        if self.use_curses:
            curses.nocbreak()
            self.scrn.keypad(0)
            curses.echo()
            curses.endwin()


class CsvManager(object):
    def __init__(self):
        self.csvdata = []

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


class StatsClient(object):
    def __init__(self, val_id, baseurl, portnum):
        self.id = val_id
        self.url = baseurl + ":" + str(portnum)
        self.name = ""

        self.validator_state = "UNKNWN"

        self.ledgerstats = {}
        self.nodestats = {}

        self.responding = False
        self.response_time = 0.0

        self.vsm = ValidatorStatsManager()

        self.request_start = 0.0
        self.request_complete = 0.0

    def request(self):
        self.request_start = time.clock()
        d = agent.request(
            'GET',
            self.url + '/stat/ledger',
            Headers({'User-Agent': ['sawtooth stats collector']}),
            None)

        d.addCallback(self.handlerequest)
        d.addErrback(self.handleerror)

        return d

    def handlerequest(self, response):
        self.request_complete = time.clock()
        self.response_time = self.request_complete - self.request_start
        self.responding = True
        self.validator_state = "RESPND"
        d = readBody(response)
        d.addCallback(self.handlebody)
        return d

    def handlebody(self, body):
        self.ledgerstats = json.loads(body)
        self.vsm.update_stats(self.ledgerstats, True, self.request_start,
                              self.request_complete)

    def handleerror(self, failed):
        self.vsm.update_stats(self.ledgerstats, False, 0, 0)
        self.responding = False
        self.validator_state = "NORESP"
        return

    def shutdown(self, ignored):
        reactor.stop()


ValStats = collections.namedtuple('validatorstats',
                                  'blocks_claimed '
                                  'blocks_committed '
                                  'blocks_pending '
                                  'txns_committed '
                                  'txns_pending '
                                  'packets_dropped '
                                  'packets_duplicates '
                                  'packets_acks_received '
                                  'msgs_handled '
                                  'msgs_acked '
                                  'packet_bytes_received_total '
                                  'pacet_bytes_received_average '
                                  'packet_bytes_sent_total '
                                  'packet_bytes_sent_average')


class ValidatorStats(ValStats, StatsCollector):
    def __init__(self, *args):
        super(ValidatorStats, self).__init__()
        self.statslist = [self]


class ValidatorStatsManager(object):
    def __init__(self):
        self.vstats = ValidatorStats(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)

        self.val_name = None
        self.val_url = None
        self.active = False
        self.request_time = 0.0
        self.response_time = 0.0

    def update_stats(self, jsonstats, active, starttime, endtime):

        if active:

            try:
                bytes_received_total, bytes_received_average = \
                    jsonstats["packet"]["BytesReceived"]
                bytes_sent_total, bytes_sent_average = \
                    jsonstats["packet"]["BytesSent"]

                self.vstats = ValStats(
                    jsonstats["ledger"]["BlocksClaimed"],
                    jsonstats["ledger"]["CommittedBlockCount"],
                    jsonstats["ledger"]["PendingBlockCount"],
                    jsonstats["ledger"]["CommittedTxnCount"],
                    jsonstats["ledger"]["PendingTxnCount"],
                    jsonstats["packet"]["DroppedPackets"],
                    jsonstats["packet"]["DuplicatePackets"],
                    jsonstats["packet"]["AcksReceived"],
                    jsonstats["packet"]["MessagesHandled"],
                    jsonstats["packet"]["MessagesAcked"],
                    bytes_received_total,
                    bytes_received_average,
                    bytes_sent_total,
                    bytes_sent_average
                )
            except KeyError as ke:
                print "invalid key in vsm.update_stats()", ke

            self.active = True
            self.request_time = starttime
            self.response_time = endtime - starttime
        else:
            self.active = False
            self.request_time = starttime
            self.response_time = endtime - starttime


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

        self.sys_client = SysClient(self.starttime, 0, 0, 0, 0, 0)
        self.sys_blocks = SysBlocks(0, 0, 0, 0, 0, 0, 0, 0)
        self.sys_txns = SysTxns(0, 0, 0, 0, 0, 0, 0)
        self.sys_packets = SysPackets(0, 0, 0, 0, 0, 0)
        self.sys_msgs = SysMsgs(0, 0, 0, 0)

        self.statslist = [self.sys_client, self.sys_blocks, self.sys_txns,
                          self.sys_packets, self.sys_msgs]

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

    def collect_stats(self, statsclients):
        # must clear the accumulators at start of each sample interval
        self.clear_accumulators()

        for c in statsclients:
            if c.responding:
                self.active_validators += 1

                self.response_times.append(c.vsm.response_time)

                self.blocks_claimed.append(c.vsm.vstats.blocks_claimed)
                self.blocks_committed.append(c.vsm.vstats.blocks_committed)
                self.blocks_pending.append(c.vsm.vstats.blocks_pending)
                self.txns_committed.append(c.vsm.vstats.txns_committed)
                self.txns_pending.append(c.vsm.vstats.txns_pending)
                self.packets_dropped.append(c.vsm.vstats.packets_dropped)
                self.packets_duplicates.append(c.vsm.vstats.packets_duplicates)
                self.packets_acks_received \
                    .append(c.vsm.vstats.packets_acks_received)
                self.msgs_handled.append(c.vsm.vstats.msgs_handled)
                self.msgs_acked.append(c.vsm.vstats.msgs_acked)

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

            blocksmaxcommited = max(self.blocks_committed)
            blocksmaxpending = max(self.blocks_pending)

            self.sys_blocks = SysBlocks(
                blocksmaxcommited,
                self.blocks_committed.count(blocksmaxcommited),
                min(self.blocks_committed),
                blocksmaxpending,
                self.blocks_pending.count(blocksmaxpending),
                min(self.blocks_pending),
                max(self.blocks_claimed),
                min(self.blocks_claimed)
            )

            txnsmaxcommited = max(self.txns_committed)
            txnsmaxpending = max(self.txns_pending)

            self.sys_txns = SysTxns(
                txnsmaxcommited,
                self.txns_committed.count(txnsmaxcommited),
                min(self.txns_committed),
                txnsmaxpending,
                self.txns_pending.count(txnsmaxpending),
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


class SystemStatsManager(object):
    def __init__(self):
        self.cp = ConsolePrint()

        self.ss = SystemStats()
        self.ps = PlatformStats()

        self.last_net_bytes_recv = 0
        self.last_net_bytes_sent = 0

        self.csv_enabled = False

    def process_stats(self, statsclients):
        self.ss.known_validators = len(statsclients)
        self.ss.active_validators = 0

        self.ss.collect_stats(statsclients)
        self.ss.calculate_stats()

        self.ps.get_stats()

        self.this_net_bytes_recv = self.ps.net_stats.bytes_recv - \
            self.last_net_bytes_recv
        self.last_net_bytes_recv = self.ps.net_stats.bytes_recv

        self.this_net_bytes_sent = self.ps.net_stats.bytes_sent - \
            self.last_net_bytes_sent
        self.last_net_bytes_sent = self.ps.net_stats.bytes_sent

    def print_stats(self):
        self.cp.cpprint('    Validators: {0:8d} known'
                        '          {1:8d} responding'
                        '      {2:8f} avg time(s)'
                        '     {3:8f} max time(s)'
                        '    {4:8d} run time(s)'
                        .format(self.ss.sys_client.known_validators,
                                self.ss.sys_client.active_validators,
                                self.ss.sys_client.avg_client_time,
                                self.ss.sys_client.max_client_time,
                                self.ss.sys_client.runtime),
                        False)
        self.cp.cpprint('        Blocks: {0:8d} max committed'
                        '    {1:6d} max committed cnt'
                        ' {2:6d} max pending'
                        '       {3:6d} max pending cnt'
                        '{4:8d} max claimed'
                        '      {5:8d} min claimed'
                        .format(self.ss.sys_blocks.blocks_max_committed,
                                self.ss.sys_blocks.blocks_max_committed_count,
                                self.ss.sys_blocks.blocks_max_pending,
                                self.ss.sys_blocks.blocks_max_pending_count,
                                self.ss.sys_blocks.blocks_max_claimed,
                                self.ss.sys_blocks.blocks_min_claimed),
                        False)
        self.cp.cpprint('  Transactions: {0:8d} max committed'
                        '    {1:6d} max committed cnt'
                        ' {2:6d} max pending'
                        '       {3:6d} max pending cnt'
                        '{4:8d} rate (t/s)'
                        .format(self.ss.sys_txns.txns_max_committed,
                                self.ss.sys_txns.txns_max_committed_count,
                                self.ss.sys_txns.txns_max_pending,
                                self.ss.sys_txns.txns_max_pending_count,
                                0),
                        False)
        self.cp.cpprint(' Packet totals: {0:8d} max dropped'
                        '    {1:8d} min dropped'
                        '     {2:8d} max duplicated'
                        '  {3:8d} min duplicated'
                        ' {4:8d} max aks received'
                        ' {5:8d} min aks received'
                        .format(self.ss.sys_packets.packets_max_dropped,
                                self.ss.sys_packets.packets_min_dropped,
                                self.ss.sys_packets.packets_max_duplicates,
                                self.ss.sys_packets.packets_min_duplicates,
                                self.ss.sys_packets.packets_max_acks_received,
                                self.ss.sys_packets.packets_min_acks_received),
                        False)
        self.cp.cpprint('Message totals: {0:8d} max handled'
                        '    {1:8d} min handled'
                        '     {2:8d} max acked'
                        '       {3:8d} min acked'
                        .format(self.ss.sys_msgs.msgs_max_handled,
                                self.ss.sys_msgs.msgs_min_handled,
                                self.ss.sys_msgs.msgs_max_acked,
                                self.ss.sys_msgs.msgs_min_acked),
                        False)
        self.cp.cpprint('Platform stats: {0:8f} cpu pct'
                        '       {1:8f} vmem pct'
                        '      {2:8d} net bytes tx'
                        '  {3:8d} net bytes rx'
                        .format(self.ps.cpu_stats.percent,
                                self.ps.vmem_stats.percent,
                                self.this_net_bytes_sent,
                                self.this_net_bytes_recv),
                        False)

        self.cp.cpprint('   VAL     VAL  RESPONSE    BLOCKS    BLOCKS   BLOCKS'
                        '      TXNS     TXNS  VAL                VAL',
                        reverse=True)
        self.cp.cpprint('    ID   STATE      TIME   CLAIMED COMMITTED  PENDING'
                        ' COMMITTED  PENDING  NAME               URL',
                        reverse=True)

        for c in clients:
            if c.responding:
                self.cp.cpprint('{0:6d}  {1:6}  {2:8f}  {3:8d}  {4:8d} '
                                '{5:8d}  {6:8d} {7:8d}  {8:16}   {9:16}'
                                .format(c.id, c.validator_state,
                                        c.response_time,
                                        c.vsm.vstats.blocks_claimed,
                                        c.vsm.vstats.blocks_committed,
                                        c.vsm.vstats.blocks_pending,
                                        c.vsm.vstats.txns_committed,
                                        c.vsm.vstats.txns_pending,
                                        c.name[:16], c.url), False)
            else:
                self.cp.cpprint('{0:6d}  {1:6}                               '
                                '                             {2:16}   {3:16}'
                                .format(c.id, c.validator_state,
                                        c.name[:16], c.url), False)

        self.cp.cpprint("", True)

    def csv_init(self):
        self.csv_enabled = True
        self.csvmgr = CsvManager()
        filename = "stats_client_" + str(int(time.time())) + ".csv"

        self.csvmgr.open_csv_file(filename)
        header = self.ss.get_names()
        self.csvmgr.csv_append(header)
        header = self.ps.get_names()
        self.csvmgr.csv_write_header(header)

    def write_stats(self):
        if self.csv_enabled:
            data = self.ss.get_data()
            self.csvmgr.csv_append(data)
            data = self.ps.get_data()
            self.csvmgr.csv_write_data(data)

    def ssmstop(self):
        print "ssm is stopping"
        self.cp.cpstop()

        if self.csv_enabled:
            self.csvmgr.close_csv_file()


def workloop():

    ssm.process_stats(clients)
    ssm.print_stats()
    ssm.write_stats()

    for c in clients:
        c.request()

    return


def handleshutdown(ignored):
    reactor.stop()


def handleloopdone(result):
    print "Loop done."
    reactor.stop()


def handleloopfailed(failure):
    print failure.getBriefTraceback()
    reactor.stop()


def parse_args(args):
    parser = argparse.ArgumentParser()

    parser.add_argument('--count',
                        metavar="",
                        help='number of validators to monitor '
                             '(default: %(default)s)',
                        default=3,
                        type=int)
    parser.add_argument('--url',
                        metavar="",
                        help='Base validator url '
                             '(default: %(default)s)',
                        default="http://localhost")
    parser.add_argument('--port',
                        metavar="",
                        help='Base validator http port '
                             '(default: %(default)s)',
                        default=8800,
                        type=int)
    parser.add_argument('--update-time',
                        metavar="",
                        help='Interval between stats updates (s) '
                             '(default: %(default)s)',
                        default=3,
                        type=int)
    parser.add_argument('--csv-enable',
                        metavar="",
                        help='Enables csv file generation '
                             '(default: %(default)s)',
                        default=False,
                        type=bool)

    return parser.parse_args(args)


def configure(opts):

    print "    validator count: ", opts.count
    print " validator base url: ", opts.url
    print "validator base port: ", opts.port

clients = []
agent = Agent(reactor)
ssm = SystemStatsManager()


def main():
    """
    Synopsis:
    1) Creates a twisted instance of twisted http Agent
    2) Creates a instance of SystemStatsManager.  This implement logic for:
        a) Collecting stats from each stats client
        b) processing stats to generate system stats
        c) printing stats to console
    3) Creates an instance of StatsClient for each validator
    4) StatsClient implements the following key functions:
        a) request: creates an agent.request() to send stats request to its
            corresponding validator, and sets the handle_request() and
            handle_error() functions as callbacks. Using twisted agent to
            separate request and response this way allows requests by all
            clients to be issued "simultaneously" without having to wait
            for responses.
        b) handle_request: handles the stats response
        c) handle_error: handles any errors, including unresponsive validator
    4) Creates twisted LoopingCall workloop.  Each time it executes it:
        a) calls SystemStatsManager.process_stats()
        b) calls SystemStatsManager.print_stats()
        c) calls the request function of each StatsClient,
            starting another round of stats collection
    5) ConsolePrint() manages printing to console.  When printing to posix
    (linux)console, curses allows a "top"-like non-scrolling display to be
        implemented.  When printing to a non-posix non-posix console,
        results simply scroll.
     """

    # prevents curses import from modifying normal terminal operation
    # (suppression of cr-lf) during display of help screen, config settings
    if curses_imported:
        curses.endwin()

    try:
        opts = parse_args(sys.argv[1:])
    except:
        # argparse reports details on the parameter error.
        sys.exit(1)

    configure(opts)

    validators = opts.count
    portnum = opts.port
    baseurl = opts.url

    if opts.csv_enable:
        ssm.csv_init()

    for i in range(0, validators):
        c = StatsClient(i, baseurl, portnum)
        c.name = "validator_{0}".format(i)
        clients.append(c)
        portnum += 1

    loop = task.LoopingCall(workloop)

    loopdeferred = loop.start(3.0)

    loopdeferred.addCallback(handleloopdone)
    loopdeferred.addErrback(handleloopfailed)

    reactor.run()

    ssm.ssmstop()


if __name__ == "__main__":
    main()

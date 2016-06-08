import json

from twisted.internet import task
from twisted.internet import reactor
from twisted.web.client import Agent
from twisted.web.client import readBody
from twisted.web.http_headers import Headers

import time

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


class ValidatorStats(object):
    def __init__(self):
        self.blocks_claimed = 0
        self.blocks_committed = 0
        self.blocks_pending = 0
        self.txns_committed = 0
        self.txns_pending = 0
        self.packets_dropped = 0
        self.packets_duplicates = 0
        self.packets_acks_received = 0
        self.msgs_handled = 0
        self.msgs_acked = 0


class ValidatorStatsManager(object):
    def __init__(self):
        self.vstats = ValidatorStats()
        self.vstatslast = ValidatorStats()

        self.val_name = None
        self.val_url = None
        self.active = False
        self.request_time = 0.0
        self.response_time = 0.0

    def update_stats(self, jsonstats, active, starttime, endtime):

        if active:

            try:
                self.vstats.blocks_claimed = \
                    jsonstats["ledger"]["BlocksClaimed"]
                self.vstats.blocks_committed = \
                    jsonstats["ledger"]["CommittedBlockCount"]
                self.vstats.blocks_pending = \
                    jsonstats["ledger"]["PendingBlockCount"]
                self.vstats.txns_committed = \
                    jsonstats["ledger"]["CommittedTxnCount"]
                self.vstats.txns_pending = \
                    jsonstats["ledger"]["PendingTxnCount"]
                self.vstats.packets_dropped = \
                    jsonstats["packet"]["DroppedPackets"]
                self.vstats.packets_duplicates = \
                    jsonstats["packet"]["DuplicatePackets"]
                self.vstats.packets_acks_received = \
                    jsonstats["packet"]["AcksReceived"]
                self.vstats.msgs_handled = \
                    jsonstats["packet"]["MessagesHandled"]
                self.vstats.msgs_acked = \
                    jsonstats["packet"]["MessagesAcked"]
            except KeyError as ke:
                print "invalid key in vsm.update_stats()", ke

            self.active = True
            self.request_time = starttime
            self.response_time = endtime - starttime
        else:
            self.active = False
            self.request_time = starttime
            self.response_time = endtime - starttime


class SystemStats(object):
    def __init__(self):
        self.starttime = int(time.time())
        self.runtime = 0

        self.known_validators = 0
        self.active_validators = 0

        self.avg_client_time = 0
        self.max_client_time = 0

        self.blocks_max_committed = 0
        self.blocks_min_committed = 0
        self.blocks_max_pending = 0
        self.blocks_min_pending = 0
        self.blocks_max_claimed = 0
        self.blocks_min_claimed = 0

        self.txns_max_committed = 0
        self.txns_min_committed = 0
        self.txns_max_pending = 0
        self.txns_min_pending = 0

        self.txn_rate = 0

        self.packets_max_dropped = 0
        self.packets_min_dropped = 0
        self.packets_max_duplicates = 0
        self.packets_min_duplicates = 0
        self.packets_max_acks_received = 0
        self.packets_min_acks_received = 0

        self.msgs_max_handled = 0
        self.msgs_min_handled = 0
        self.msgs_max_acked = 0
        self.msgs_min_acked = 0

        # collectors

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
        if self.active_validators > 0:
            self.avg_client_time = sum(self.response_times)\
                / len(self.response_times)
            self.max_client_time = max(self.response_times)

            self.blocks_max_committed = max(self.blocks_committed)
            self.blocks_min_committed = min(self.blocks_committed)
            self.blocks_max_pending = max(self.blocks_pending)
            self.blocks_min_pending = min(self.blocks_pending)
            self.blocks_max_claimed = max(self.blocks_claimed)
            self.blocks_min_claimed = min(self.blocks_claimed)

            self.txns_max_committed = max(self.txns_committed)
            self.txns_min_committed = min(self.txns_committed)
            self.txns_max_pending = max(self.txns_pending)
            self.txns_min_pending = min(self.txns_pending)

            self.packets_max_dropped = max(self.packets_dropped)
            self.packets_min_dropped = min(self.packets_dropped)
            self.packets_max_duplicates = max(self.packets_duplicates)
            self.packets_min_duplicates = min(self.packets_duplicates)
            self.packets_max_acks_received = max(self.packets_acks_received)
            self.packets_min_acks_received = min(self.packets_acks_received)

            self.msgs_max_handled = max(self.msgs_handled)
            self.msgs_min_handled = min(self.msgs_handled)
            self.msgs_max_acked = max(self.msgs_acked)
            self.msgs_min_acked = min(self.msgs_acked)


class SystemStatsManager(object):
    def __init__(self):
        self.cp = ConsolePrint()
        self.ss = SystemStats()

    def process_stats(self, statsclients):
        self.ss.known_validators = len(statsclients)
        self.ss.active_validators = 0

        self.ss.collect_stats(statsclients)
        self.ss.calculate_stats()

        self.ss.runtime = int(time.time()) - self.ss.starttime

    def print_stats(self):
        self.cp.cpprint('    Validators: {0:8d} known,'
                        '         {1:8d} responding,'
                        '      {2:8f} avg time(s),'
                        '    {3:8f} max time(s),'
                        '    {4:8d} run time(s)'
                        .format(self.ss.known_validators,
                                self.ss.active_validators,
                                self.ss.avg_client_time,
                                self.ss.max_client_time,
                                self.ss.runtime), False)
        self.cp.cpprint('        Blocks: {0:8d} max committed,'
                        ' {1:8d} min committed,'
                        '   {2:8d} max pending,'
                        '    {3:8d} min pending,'
                        '    {4:8d} max claimed,'
                        '      {5:8d} min claimed'
                        .format(self.ss.blocks_max_committed,
                                self.ss.blocks_min_committed,
                                self.ss.blocks_max_pending,
                                self.ss.blocks_min_pending,
                                self.ss.blocks_max_claimed,
                                self.ss.blocks_min_claimed), False)
        self.cp.cpprint('  Transactions: {0:8d} max committed,'
                        ' {1:8d} min committed,'
                        '   {2:8d} max pending,'
                        '    {3:8d} min pending,'
                        '    {4:8d} rate (t/s)'
                        .format(self.ss.txns_max_committed,
                                self.ss.txns_min_committed,
                                self.ss.txns_max_pending,
                                self.ss.txns_min_pending,
                                0), False)
        self.cp.cpprint(' Packet totals: {0:8d} max dropped,'
                        '   {1:8d} min dropped,'
                        '     {2:8d} max duplicated,'
                        ' {3:8d} min duplicated,'
                        ' {4:8d} max aks received,'
                        ' {5:8d} min aks received'
                        .format(self.ss.packets_max_dropped,
                                self.ss.packets_min_dropped,
                                self.ss.packets_max_duplicates,
                                self.ss.packets_min_duplicates,
                                self.ss.packets_max_acks_received,
                                self.ss.packets_min_acks_received), False)
        self.cp.cpprint('Message totals: {0:8d} max handled,'
                        '   {1:8d} min handled,'
                        '     {2:8d} max acked,'
                        '      {3:8d} min acked'
                        .format(self.ss.msgs_max_handled,
                                self.ss.msgs_min_handled,
                                self.ss.msgs_max_acked,
                                self.ss.msgs_min_acked), False)

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

    def ssmstop(self):
        self.cp.cpstop()


def handleshutdown(ignored):
    reactor.stop()


def workloop():

    loopcounter = 0

    while True:
        loopcounter += 1

        ssm.process_stats(clients)
        ssm.print_stats()

        for c in clients:
            c.request()

        return


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

from pprint import pformat
import json

from twisted.internet import task
from twisted.internet import reactor
from twisted.internet.defer import Deferred
from twisted.internet.protocol import Protocol
from twisted.web.client import Agent
from twisted.web.http_headers import Headers
from twisted.web.client import Agent, readBody

import time

import argparse
import sys

import os

if os.name == "posix":
    import curses


class ConsolePrint:
    def __init__(self):
        self.use_curses = True if os.name == "posix" else False
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
            he, wi = self.scrn.getmaxyx()
            self.scrn.addstr(printstring[:wi - 1] + "\n", attr)
            if finish:
                self.scrn.refresh()
                self.start = True
        # todo: limit number of lines printed to screen height
        else:
            print(printstring)

    def cpstop(self):
        if self.use_curses:
            # todo: dont clear screen
            # todo: stop curses on exception
            curses.nocbreak()
            self.scrn.keypad(0)
            curses.echo()
            curses.endwin()


class DataReader(Protocol):
    def __init__(self, finished):
        self.finished = finished
        self.remaining = 1024 * 10

    def dataReceived(self, somebytes):
        if self.remaining:
            display = somebytes[:self.remaining]
            print 'Some data received:'
            print display
            self.remaining -= len(display)

    def connectionLost(self, reason):
        print 'Finished receiving body:', reason.getErrorMessage()
        self.finished.callback(None)


class StatsClient():
    def __init__(self, val_id, baseurl, portnum):
        # self.delay=delay
        self.id = val_id
        # self.portindex=portindex
        # self.url = 'http://localhost:880{0}'.format(self.portindex)
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
        # d.addBoth(self.handleshutdown)

        return d

    def handlerequest(self, response):
        self.request_complete = time.clock()
        self.response_time = self.request_complete - self.request_start
        # print 'delay:', self.delay
        # print 'Response version:', response.version, 'code:', response.code,
        # 'phrase:', response.phrase
        # print 'Response headers:'
        # print pformat(list(response.headers.getAllRawHeaders()))
        # if response to be read in entirety
        self.responding = True
        self.validator_state = "ACTIVE"
        d = readBody(response)
        d.addCallback(self.handlebody)
        return d
        # if response to be read incrementally
        # finished = Deferred()
        # response.deliverBody(datareader(finished))
        # return finished

    def handlebody(self, body):
        # print 'Response body for {0}:'.format(self.url)
        # print body [:80]
        self.ledgerstats = json.loads(body)
        # print "Blocks claimed: ", self.ledgerstats["ledger"]["BlocksClaimed"]
        self.vsm.update_stats(self.ledgerstats, True, self.request_start,
                              self.request_complete)

    def handleerror(self, f):
        # print "validator_client errback exception: %s" % (f.getTraceback(),)
        # todo: better handle unresponsive validator node
        self.vsm.update_stats(self.ledgerstats, False, 0, 0)
        self.responding = False
        self.validator_state = "NORESP"
        return

    # todo: add callbacks to request additional stats or modify stats provider

    def shutdown(self, ignored):
        reactor.stop()


class ValidatorStats:
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


class ValidatorStatsManager():
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
            # self.vstatslast = deepcopy(self.vstats)

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
                "todo: figure out how to pass this to proper deferred errback"

            self.active = True
            self.request_time = starttime
            self.response_time = endtime - starttime
        else:
            self.active = False
            self.request_time = starttime
            self.response_time = endtime - starttime


class SystemStats:
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


class SystemStatsManager():
    def __init__(self):
        self.cp = ConsolePrint()
        self.ss = SystemStats()

    def process_stats(self, statsclients):
        self.ss.known_validators = len(statsclients)
        self.ss.active_validators = 0

        response_times = []

        blocks_claimed = []
        blocks_committed = []
        blocks_pending = []
        txns_committed = []
        txns_pending = []
        packets_dropped = []
        packets_duplicates = []
        packets_acks_received = []
        msgs_handled = []
        msgs_acked = []

        for c in statsclients:
            if c.responding:
                self.ss.active_validators += 1

                response_times.append(c.vsm.response_time)

                blocks_claimed.append(c.vsm.vstats.blocks_claimed)
                blocks_committed.append(c.vsm.vstats.blocks_committed)
                blocks_pending.append(c.vsm.vstats.blocks_pending)
                txns_committed.append(c.vsm.vstats.txns_committed)
                txns_pending.append(c.vsm.vstats.txns_pending)
                packets_dropped.append(c.vsm.vstats.packets_dropped)
                packets_duplicates.append(c.vsm.vstats.packets_duplicates)
                packets_acks_received\
                    .append(c.vsm.vstats.packets_acks_received)
                msgs_handled.append(c.vsm.vstats.msgs_handled)
                msgs_acked.append(c.vsm.vstats.msgs_acked)

        if self.ss.active_validators > 0:
            self.ss.avg_client_time = sum(response_times) / len(response_times)
            self.ss.max_client_time = max(response_times)

            self.ss.blocks_max_committed = max(blocks_committed)
            self.ss.blocks_min_committed = min(blocks_committed)
            self.ss.blocks_max_pending = max(blocks_pending)
            self.ss.blocks_min_pending = min(blocks_pending)
            self.ss.blocks_max_claimed = max(blocks_claimed)
            self.ss.blocks_min_claimed = min(blocks_claimed)

            self.ss.txns_max_committed = max(txns_committed)
            self.ss.txns_min_committed = min(txns_committed)
            self.ss.txns_max_pending = max(txns_pending)
            self.ss.txns_min_pending = min(txns_pending)

            self.ss.packets_max_dropped = max(packets_dropped)
            self.ss.packets_min_dropped = min(packets_dropped)
            self.ss.packets_max_duplicates = max(packets_duplicates)
            self.ss.packets_min_duplicates = min(packets_duplicates)
            self.ss.packets_max_acks_received = max(packets_acks_received)
            self.ss.packets_min_acks_received = min(packets_acks_received)

            self.ss.msgs_max_handled = max(msgs_handled)
            self.ss.msgs_min_handled = min(msgs_handled)
            self.ss.msgs_max_acked = max(msgs_acked)
            self.ss.msgs_min_acked = min(msgs_acked)

        self.ss.runtime = int(time.time()) - self.ss.starttime

    def print_stats(self):
        self.cp.cpprint(
            '    Validators: {0:8d} known,         {1:8d} responding,      {2:8f} avg time(s),    {3:8f} max time(s),    {4:8d} run time(s)'  # noqa
                .format(self.ss.known_validators, self.ss.active_validators,
                        self.ss.avg_client_time, self.ss.max_client_time,
                        self.ss.runtime), False)
        self.cp.cpprint(
            '        Blocks: {0:8d} max committed, {1:8d} min commited,    {2:8d} max pending,    {3:8d} min pending,    {4:8d} max claimed,      {5:8d} min claimed'  # noqa
                .format(self.ss.blocks_max_committed,
                        self.ss.blocks_min_committed,
                        self.ss.blocks_max_pending,
                        self.ss.blocks_min_pending,
                        self.ss.blocks_max_claimed,
                        self.ss.blocks_min_claimed), False)
        self.cp.cpprint(
            '  Transactions: {0:8d} max committed, {1:8d} min committed,   {2:8d} max pending,    {2:8d} min pending,    {3:8d} rate (t/s)'  # noqa
                .format(self.ss.txns_max_committed, self.ss.txns_min_committed,
                        self.ss.txns_max_pending, self.ss.txns_min_pending,
                        0), False)
        self.cp.cpprint(
            ' Packet totals: {0:8d} max dropped,   {1:8d} min dropped      {2:8d} max duplicated, {3:8d} min duplicated, {4:8d} max aks received, {5:8d} min aks received'  # noqa
                .format(self.ss.packets_max_dropped,
                        self.ss.packets_min_dropped,
                        self.ss.packets_max_duplicates,
                        self.ss.packets_min_duplicates,
                        self.ss.packets_max_acks_received,
                        self.ss.packets_min_acks_received), False)
        self.cp.cpprint(
            'Message totals: {0:8d} max handled,   {1:8d} min handled,     {2:8d} max acked,      {3:8d} min acked'  # noqa
                .format(self.ss.msgs_max_handled, self.ss.msgs_min_handled,
                        self.ss.msgs_max_acked, self.ss.msgs_min_acked), False)

        self.cp.cpprint(
            '   VAL     VAL  RESPONSE    BLOCKS    BLOCKS   BLOCKS      TXNS     TXNS  VAL                VAL',  # noqa
            reverse=True)
        self.cp.cpprint(
            '    ID   STATE      TIME   CLAIMED COMMITTED  PENDING COMMITTED  PENDING  NAME               URL',  # noqa
            reverse=True)
        # self.cp.cpprint('{0:6d}  {1:6}  {1:8d}  {2:8d}  {3:8d} {4:8d}  {5:8d} {6:8d}  {7:16}   {8:16}'.format(0, 0, 0, 0, 0, 0, 0, "barney_83_exiter"[:16], "ragmuffin1234//roofuscalamzoo//3/4/5"), False)  # noqa

        for c in clients:
            if c.responding:
                self.cp.cpprint('{0:6d}  {1:6}  {2:8f}  {3:8d}  {4:8d} {5:8d}  {6:8d} {7:8d}  {8:16}   {9:16}'  # noqa
                                .format(c.id, c.validator_state,
                                        c.response_time,
                                        c.vsm.vstats.blocks_claimed,
                                        c.vsm.vstats.blocks_committed,
                                        c.vsm.vstats.blocks_pending,
                                        c.vsm.vstats.txns_committed,
                                        c.vsm.vstats.txns_pending,
                                        c.name[:16], c.url), False)
            else:
                self.cp.cpprint(
                    '{0:6d}  {1:6}                                                            {2:16}   {3:16}'  # noqa
                        .format(c.id, c.validator_state,
                                c.name[:16], c.url), False)

        self.cp.cpprint("", True)

        # todo: limit number of lines to screen height

    def ssmstop(self):
        self.cp.cpstop()


def handleshutdown(ignored):
    reactor.stop()


def dowork():
    # d = None
    for c in clients:
        d = c.request()
        # clients.append(c)


def workloop():
    global loopcounter

    if loopcounter < looptimes:
        loopcounter += 1

        ssm.process_stats(clients)
        ssm.print_stats()
        dowork()
        return

    if workloopfail:
        raise Exception('Failed during work loop')

    loop.stop()
    return


def handleloopdone(result):
    print "Loop done."
    reactor.stop()


def handleloopfailed(failure):
    print failure.getBriefTraceback()
    reactor.stop()


def parse_args(args):
    parser = argparse.ArgumentParser()

    # use system or dev paths...
    parser.add_argument('--validator-count',
                        metavar="",
                        help='number of validators to monitor '
                             '(default: %(default)s)',
                        default=3,
                        type=int)
    parser.add_argument('--validator-url',
                        metavar="",
                        help='Base validator url '
                             '(default: %(default)s)',
                        default="http://localhost")
    parser.add_argument('--validator-port',
                        metavar="",
                        help='Base validator http port '
                             '(default: %(default)s)',
                        default=8800,
                        type=int)
    parser.add_argument('--sample-time',
                        metavar="",
                        help='Number of validators to launch '
                             '(default: %(default)s)',
                        default=3,
                        type=int)

    return parser.parse_args(args)


def configure(opts):
    # scriptdir = os.path.dirname(os.path.realpath(__file__))

    print "    validator count: ", opts.validator_count
    print " validator base url: ", opts.validator_url
    print "validator base port: ", opts.validator_port
    # sys.exit(1)


def main():
    try:
        opts = parse_args(sys.argv[1:])
    except:
        # argparse reports details on the parameter error.
        sys.exit(1)

    configure(opts)

    global agent
    agent = Agent(reactor)

    global clients
    clients = []

    validators = opts.validator_count
    portnum = opts.validator_port
    baseurl = opts.validator_url

    for i in range(0, validators):
        c = StatsClient(i, baseurl, portnum)
        c.name = "validator_{0}".format(i)
        clients.append(c)
        portnum += 1

    global looptimes
    looptimes = 1000000  # run for a really long time

    global loopcounter
    loopcounter = 0

    workloopfail = False

    global ssm
    ssm = SystemStatsManager()

    loop = task.LoopingCall(workloop)

    loopdeferred = loop.start(3.0)

    loopdeferred.addCallback(handleloopdone)
    loopdeferred.addErrback(handleloopfailed)

    reactor.run()

    ssm.ssmstop()


if __name__ == "__main__":
    main()

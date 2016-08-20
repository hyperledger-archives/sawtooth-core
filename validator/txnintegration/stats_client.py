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

import argparse
import collections
import json
import sys
import time

from twisted.internet import task
from twisted.internet import reactor
from twisted.web.client import Agent
from twisted.web.client import readBody
from twisted.web.http_headers import Headers

from txnintegration.utils import StatsCollector
from txnintegration.utils import PlatformStats

from txnintegration.stats_print import ConsolePrint
from txnintegration.stats_print import StatsPrintManager

from txnintegration.stats_utils import TransactionRate
from txnintegration.stats_utils import PlatformIntervalStats

from txnintegration.stats_utils import SummaryStatsCsvManager
from txnintegration.stats_utils import ValidatorStatsCsvManager

curses_imported = True
try:
    import curses
except ImportError:
    curses_imported = False


class StatsClient(object):
    def __init__(self, val_id, fullurl):
        self.id = val_id
        self.url = fullurl
        self.name = "validator_{0}".format(val_id)

        self.validator_state = "UNKNWN"

        self.ledgerstats = {}
        self.nodestats = {}

        self.vsm = ValidatorStatsManager()

        self.responding = False

        self.request_start = 0.0
        self.request_complete = 0.0
        self.response_time = 0.0

        self.vc = ValidatorCommunications()

    def stats_request(self):
        # initialize endpoint urls from specified validator url
        self.request_start = time.clock()
        self.path = self.url + "/statistics/all"
        self.vc.get_request(self.path,
                            self._stats_completion,
                            self._stats_error)

    def _stats_completion(self, json_stats):
        self.request_complete = time.clock()
        self.response_time = self.request_complete - self.request_start
        self.vsm.update_stats(json_stats, True, self.request_start,
                              self.request_complete)
        self.responding = True
        self.validator_state = "RESPND"

    def _stats_error(self):
        self.vsm.update_stats(self.ledgerstats, False, 0, 0)
        self.responding = False
        self.validator_state = "NORESP"
        return


ValStats = collections.namedtuple('validatorstats',
                                  'blocks_claimed '
                                  'blocks_committed '
                                  'blocks_pending '
                                  'local_mean '
                                  'expected_expiration '
                                  'previous_blockid '
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
        self.vstats = ValidatorStats(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                                     0, 0, 0, 0, 0)

        self.val_name = None
        self.val_url = None
        self.active = False
        self.request_time = 0.0
        self.response_time = 0.0

        self.val_stats = None

        self.txn_rate = TransactionRate()
        self.psis = PlatformIntervalStats()

    def update_stats(self, json_stats, active, starttime, endtime):

        if active:

            self.val_stats = json_stats

            try:
                bytes_received_total, bytes_received_average = \
                    json_stats["packet"]["BytesReceived"]
                bytes_sent_total, bytes_sent_average = \
                    json_stats["packet"]["BytesSent"]

                self.vstats = ValStats(
                    json_stats["ledger"]["BlocksClaimed"],
                    json_stats["ledger"]["CommittedBlockCount"],
                    json_stats["ledger"]["PendingBlockCount"],

                    json_stats["ledger"].get("LocalMeanTime", 0.0),
                    json_stats["ledger"].get("ExpectedExpirationTime", 0.0),
                    json_stats["ledger"].get("PreviousBlockID", 'broken'),
                    json_stats["ledger"].get("CommittedTxnCount", 0),
                    json_stats["ledger"].get("PendingTxnCount", 0),

                    json_stats["packet"]["DroppedPackets"],
                    json_stats["packet"]["DuplicatePackets"],
                    json_stats["packet"]["AcksReceived"],
                    json_stats["packet"]["MessagesHandled"],
                    json_stats["packet"]["MessagesAcked"],
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

            self.psis.calculate_interval_stats(self.val_stats)
        else:
            self.active = False
            self.request_time = starttime
            self.response_time = endtime - starttime

        self.txn_rate.calculate_txn_rate(
            self.vstats.blocks_committed,
            self.vstats.txns_committed
        )

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

        self.sys_client = SysClient(self.starttime, 0, 0, 0, 0, 0)
        self.sys_blocks = SysBlocks(0, 0, 0, 0, 0, 0, 0, 0)
        self.sys_txns = SysTxns(0, 0, 0, 0, 0, 0, 0)
        self.sys_packets = SysPackets(0, 0, 0, 0, 0, 0)
        self.sys_msgs = SysMsgs(0, 0, 0, 0)

        self.poet_stats = PoetStats(0.0, 0.0, 0.0, '')

        self.statslist = [self.sys_client, self.sys_blocks, self.sys_txns,
                          self.sys_packets, self.sys_msgs, self.poet_stats]

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

    def collect_stats(self, stats_clients):
        # must clear the accumulators at start of each sample interval
        self.clear_accumulators()

        for c in stats_clients:
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

                self.local_mean.append(c.vsm.vstats.local_mean)
                self.previous_blockid.append(c.vsm.vstats.previous_blockid)

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
            self.last_unique_blockID = \
                unique_blockid_list[len(unique_blockid_list) - 1]
            self.poet_stats = PoetStats(
                self.avg_local_mean,
                max(self.local_mean),
                min(self.local_mean),
                self.last_unique_blockID
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


class StatsManager(object):
    def __init__(self):
        self.cp = ConsolePrint()

        self.ss = SystemStats()

        self.ps = PlatformStats()
        self.psis = PlatformIntervalStats()
        self.ps.psis = self.psis

        self.previous_net_bytes_recv = 0
        self.previous_net_bytes_sent = 0

        self.clients = []
        self.known_endpoint_urls = []
        self.known_endpoint_names = []
        self.stats_loop_count = 0

        self.spm = StatsPrintManager(self.ss, self.ps, self.clients)

        self.sscm = SummaryStatsCsvManager(self.ss, self.ps)
        self.vscm = ValidatorStatsCsvManager(self.clients)

    def initialize_client_list(self, endpoints):
        # add validator stats client for each endpoint
        for val_num, endpoint in enumerate(endpoints.values()):
            url = 'http://{0}:{1}'.format(
                endpoint["Host"], endpoint["HttpPort"])
            try:
                c = StatsClient(val_num, url)
                c.name = endpoint["Name"]
                self.known_endpoint_names.append(endpoint["Name"])
            except:
                e = sys.exc_info()[0]
                print ("error creating stats clients: ", e)
            self.clients.append(c)

    def update_client_list(self, endpoints):
        # add validator stats client for each endpoint name
        for val_num, endpoint in enumerate(endpoints.values()):
            if endpoint["Name"] not in self.known_endpoint_names:
                val_num = len(self.known_endpoint_names)
                url = 'http://{0}:{1}'.format(
                    endpoint["Host"], endpoint["HttpPort"])
                c = StatsClient(val_num, url)
                c.name = endpoint["Name"]
                self.clients.append(c)
                self.known_endpoint_names.append(endpoint["Name"])

    def stats_loop(self):
        self.process_stats(self.clients)
        self.print_stats()
        self.csv_write()

        for c in self.clients:
            c.stats_request()

        self.stats_loop_count += 1

        return

    def stats_loop_done(self, result):
        reactor.stop()

    def stats_loop_failed(self, failure):
        print failure.getBriefTraceback()
        reactor.stop()

    def process_stats(self, statsclients):
        self.ss.known_validators = len(statsclients)
        self.ss.active_validators = 0

        self.ss.collect_stats(statsclients)
        self.ss.calculate_stats()

        self.ps.get_stats()
        psr = {"platform": self.ps.get_data_as_dict()}
        self.psis.calculate_interval_stats(psr)

    def print_stats(self):
        self.spm.print_stats()

    def csv_init(self, enable_summary, enable_validator):
        if enable_summary is True:
            self.sscm.initialize()
        if enable_validator is True:
            self.vscm.initialize()

    def csv_write(self):
        self.sscm.write_stats()
        self.vscm.write_stats()

    def csv_stop(self):
        self.sscm.stop()
        self.vscm.stop()

    def stats_stop(self):
        print "StatsManager is stopping"
        self.cp.cpstop()
        self.csv_stop()


class EndpointManager(object):
    def __init__(self):
        self.error_count = 0
        self.no_endpoint_responders = False
        self.endpoint_urls = []
        self.endpoints = None
        self.vc = ValidatorCommunications()

    def initialize_endpoint_discovery(self, url, init_cb, init_args=None):
        # initialize endpoint urls from specified validator url
        self.endpoint_completion_cb = init_cb
        self.endpoint_completion_cb_args = init_args or {}
        path = url + "/store/{0}/*".format('EndpointRegistryTransaction')
        self.init_path = path
        self.vc.get_request(path,
                            self.endpoint_discovery_completion,
                            self._init_terminate)

    def endpoint_discovery_completion(self, results):
        # response has been received
        # extract host url and port number for each validator identified
        self.endpoint_urls = []
        self.endpoints = results
        for endpoint in results.values():
            self.endpoint_urls.append(
                'http://{0}:{1}'.format(
                    endpoint["Host"], endpoint["HttpPort"]))
        self.endpoint_completion_cb(self.endpoints,
                                    **self.endpoint_completion_cb_args)

    def update_endpoint_discovery(self, update_cb):
        # initiates update of endpoint urls
        self.endpoint_completion_cb = update_cb
        self.endpoint_completion_cb_args = {}
        self.contact_list = list(self.endpoint_urls)
        url = self.contact_list.pop()
        path = url + "/store/{0}/*".format('EndpointRegistryTransaction')
        self.vc.get_request(path,
                            self.endpoint_discovery_completion,
                            self._update_endpoint_continue)

    def _update_endpoint_continue(self):
        # update response not received, try another url
        # if all urls have been tried, set "no update" flag and be done
        if len(self.contact_list) > 0:
            url = self.contact_list.pop()
            path = url + "/store/{0}/*".format('EndpointRegistryTransaction')
            self.vc.get_request(path,
                                self.endpoint_discovery_completion,
                                self._update_endpoint_continue)
        else:
            self.no_endpoint_responders = True

    def update_endpoint_done(self, result):
        reactor.stop()

    def update_endpoint_failed(self, failure):
        print failure.getBriefTraceback()
        reactor.stop()

    def _init_terminate(self):
        print "no response to endpoint request to {0}".format(self.init_path)
        print "terminating session"
        reactor.stop()
        return


class ValidatorCommunications(object):
    def __init__(self):
        self.request_count = 0
        self.error_count = 0
        self.agent = Agent(reactor)
        self.completion_callback = None
        self.error_callback = None
        self.request_path = None

    def get_request(self, path, ccb=None, ecb=None):
        self.completion_callback = self._completion_default if ccb is None \
            else ccb
        self.error_callback = self._error_default if ecb is None \
            else ecb

        self.request_path = path
        d = self.agent.request(
            'GET',
            path,
            Headers({'User-Agent': ['sawtooth stats collector']}),
            None)

        d.addCallback(self._handle_request)
        d.addErrback(self._handle_error)

        return d

    def _handle_request(self, response):
        self.responding = True
        d = readBody(response)
        d.addCallback(self._handle_body)
        return d

    def _handle_body(self, body):
        self.json_stats = json.loads(body)
        self.completion_callback(self.json_stats)

    def _handle_error(self, failed):
        print failed
        self.error_count += 1
        self.error_callback()

    def _completion_default(self, data):
        print "ValidatorCommunications.get_request() " \
              "default completion handler"
        print json.dumps(data, indent=4)

    def _error_default(self):
        print "ValidatorCommunications.get_request() " \
              "default error handler"


def parse_args(args):
    parser = argparse.ArgumentParser()

    parser.add_argument('--url',
                        metavar="",
                        help='Base validator url '
                             '(default: %(default)s)',
                        default="http://localhost:8800")
    parser.add_argument('--stats-time',
                        metavar="",
                        help='Interval between stats updates (s) '
                             '(default: %(default)s)',
                        default=3,
                        type=int)
    parser.add_argument('--endpoint-time',
                        metavar="",
                        help='Interval between endpoint updates (s) '
                             '(default: %(default)s)',
                        default=30,
                        type=int)
    parser.add_argument('--csv-enable-summary',
                        metavar="",
                        help='Enables summary CSV file generation'
                             '(default: %(default)s)',
                        default=False,
                        type=bool)
    parser.add_argument('--csv-enable-validator',
                        metavar="",
                        help='Enables per-validator CSV file generation'
                             '(default: %(default)s)',
                        default=False,
                        type=bool)

    return parser.parse_args(args)


def startup(urls, loop_times, stats_man, ep_man):
    stats_man.initialize_client_list(ep_man.endpoints)

    # start loop to periodically collect and report stats
    stats_loop = task.LoopingCall(stats_man.stats_loop)
    stats_loop_deferred = stats_loop.start(loop_times["stats"])
    stats_loop_deferred.addCallback(stats_man.stats_loop_done)
    stats_loop_deferred.addErrback(stats_man.stats_loop_failed)

    # start loop to periodically update the list of validator endpoints
    # and call WorkManager.update_client_list
    ep_loop = task.LoopingCall(ep_man.update_endpoint_discovery,
                               stats_man.update_client_list)
    ep_loop_deferred = ep_loop.start(loop_times["endpoint"], now=False)
    ep_loop_deferred.addCallback(ep_man.update_endpoint_done)
    ep_loop_deferred.addErrback(ep_man.update_endpoint_failed)


def run_stats(url,
              stats_update_frequency=3,
              endpoint_update_frequency=30,
              csv_enable_summary=False,
              csv_enable_validator=False
              ):
    try:
        # initialize globals when we are read for stats display. This keeps
        # curses from messing up the status prints prior to stats start up.
        epm = EndpointManager()
        sm = StatsManager()  # sm assumes epm is created!

        # initialize csv stats file generation
        print "initializing csv"
        sm.csv_init(csv_enable_summary, csv_enable_validator)

        # prevent curses import from modifying normal terminal operation
        # (suppression of cr-lf) during display of help screen, config settings
        if curses_imported:
            curses.endwin()

        # discover validator endpoints; if successful, continue with startup()
        epm.initialize_endpoint_discovery(
            url,
            startup,
            {
                'loop_times': {
                    "stats": stats_update_frequency,
                    'endpoint': endpoint_update_frequency},
                'stats_man': sm,
                'ep_man': epm
            })

        reactor.run()

        sm.stats_stop()
    except Exception as e:
        if curses_imported:
            curses.endwin()
        sys.stderr.write(e)
        raise


def main():
    """
    Synopsis:
    1) Twisted http Agent
        a) Handles http communications
    2) EndpointManager
        a) Maintains list of validator endpoints and their associated urls
        b) update_endpoint_urls is called periodically to update the list of
            registered urls
    3) StatsManager
        a) Creates instance of SystemStats and PlatformStats
        b) Maintains list of validator StatsClient instances
            using url list maintained by EndpointManager
        c) StatsManager.stats_loop is called periodically to...
            i) Call SystemStats.process() to generate summary statistics
            ii) Call StatsPrintManager.stats_print()
            iii) Call CsvManager.write() to write stats to CSV file
            iv) Call each StatsClient instance to initiate a stats request
    4) StatsClient
        a) Sends stats requests to its associated validator url
        b) Handles stats response
        c) Handles any errors, including unresponsive validator
    5) Global
        a) Creates instance of twisted http agent,
            StatsManager, and EndpointManager
    6) Main
        a) calls endpoint manager to initialize url list.
            i) Program continues at Setup() if request succeeds
            ii) Program terminates request fails
        b) sets up looping call for StatsManager.stats_loop
        c) sets up looping call for EndpointManager.update_validator_urls
    7) StatsPrintManager
        a) Handles formatting of console output
    8) ConsolePrint() manages low-level details of printing to console.
        When printing to posix (linux)console, curses allows a "top"-like
        non-scrolling display to be implemented.  When printing to a non-posix
        console, results simply scroll.
    9) CsvManager
        a) Handles file management and timestamped output
            for csv file generation
    10) ValidatorCommunications
        a) Handles low-level details of issuing an http request
            via twisted http agent async i/o
     """
    opts = parse_args(sys.argv[1:])

    run_stats(opts.url,
              csv_enable_summary=opts.csv_enable_summary,
              csv_enable_validator=opts.csv_enable_validator,
              stats_update_frequency=opts.stats_time,
              endpoint_update_frequency=opts.endpoint_time)

if __name__ == "__main__":
    main()

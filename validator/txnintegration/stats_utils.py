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
import json
import collections
import networkx as nx

from twisted.web.client import readBody
from twisted.web.http_headers import Headers


class ValidatorCommunications(object):

    def __init__(self, reactor_agent):
        self.request_count = 0
        self.error_count = 0
        self.agent = reactor_agent
        self.completion_callback = None
        self.error_callback = None
        self.request_path = None

        self.error_value = None
        self.error_type = None
        self.error_name = None
        self.error_message = None

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
        self.response_code = response.code
        d = readBody(response)
        d.addCallback(self._handle_body)
        return d

    def _handle_body(self, body):
        if self.response_code is 200:
            self.json_stats = json.loads(body)
        else:
            self.json_stats = None
        self.completion_callback(self.json_stats, self.response_code)

    def _handle_error(self, failure):
        self.error_value = failure.value
        self.error_type = failure.type
        self.error_name = failure.type.__name__
        self.error_message = failure.getErrorMessage()

        self.error_count += 1
        self.error_callback(failure)

    def _completion_default(self, data):
        print "ValidatorCommunications.get_request() " \
              "default completion handler"
        print json.dumps(data, indent=4)

    def _error_default(self):
        print "ValidatorCommunications.get_request() " \
              "default error handler"


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

    def csv_write_header(self, headerlist=None, add_time=True):
        if headerlist is not None:
            self.csvdata.extend(headerlist)
        if add_time:
            self.csvdata.insert(0, "time")
        self._csv_write()

    def csv_write_data(self, datalist=None, add_time=True):
        if datalist is not None:
            self.csvdata.extend(datalist)
        if add_time:
            self.csvdata.insert(0, time.time())
        self._csv_write()

    def _csv_write(self):
        self.writer.writerow(self.csvdata)
        self.csvdata = []


class SummaryStatsCsvManager(object):
    def __init__(self, system_stats, platform_stats):
        self.csv_enabled = False
        self.csv_mgr = CsvManager()

        self.ss = system_stats
        self.ps = platform_stats

    def initialize(self):
        self.csv_enabled = True

        filename = "summary_stats_" + str(int(time.time())) + ".csv"
        self.csv_mgr.open_csv_file(filename)

        header = self.ss.get_names()
        self.csv_mgr.csv_append(header)
        header = self.ps.get_names()
        self.csv_mgr.csv_write_header(header)

    def write_stats(self):
        if self.csv_enabled:
            data = self.ss.get_data()
            self.csv_mgr.csv_append(data)
            data = self.ps.get_data()
            self.csv_mgr.csv_write_data(data)

    def stop(self):
        if self.csv_enabled:
            self.csv_mgr.close_csv_file()


class ValidatorStatsCsvManager(object):
    def __init__(self, client_list):
        self.csv_enabled = False
        self.csv_mgr = CsvManager()

        self.get_header = False
        self.csv_stats = CsvManager()
        self.clients = client_list
        self.stat_names = []

        self.dw = DictWalker()

    def initialize(self):
        self.csv_enabled = True

        filename = "validator_stats_" + str(int(time.time())) + ".csv"
        self.csv_mgr.open_csv_file(filename)

        # defer writing header until first instance of data dictionary
        # is available
        self.get_header = True

    def write_stats(self):
        current_time = time.time()
        if self.csv_enabled:
            for client in self.clients:
                if client.responding:
                    self.dw.walk(client.vsm.val_stats)
                    if self.get_header:
                        names = self.dw.get_names()
                        names.insert(0, "validator_name")
                        names.insert(0, "time")
                        self.csv_mgr.csv_write_header(names, add_time=False)
                        self.get_header = False
                    data = self.dw.get_data()
                    data.insert(0, client.name)
                    data.insert(0, current_time)
                    self.csv_mgr.csv_write_data(data, add_time=False)

    def stop(self):
        if self.csv_enabled:
            self.csv_mgr.close_csv_file()


class StatsSnapshotWriter(object):
    '''
    Writes json-formatted snapshot of stats client statistics to file.
    Writes file to where stats client is running.
    Filename includes searchable file name + timestamp
    Captures the following:
    - Summary: each of the summary lines displayed by stats client
    - Per-Validator: Each of the selectable views displayed by stats client
    '''

    def __init__(self,
                 system_stats,
                 platform_stats,
                 topology_stats,
                 branch_manager,
                 stats_clients):

        self.ss = system_stats
        self.ps = platform_stats
        self.ts = topology_stats
        self.bm = branch_manager
        self.stats_clients = stats_clients

        self.stats = {}

        self.filename = None
        self.file = None

        self.do_snapshot = False

    def write_snapshot(self):
        if self.do_snapshot:
            self.do_snapshot = False  # acts as one-shot
            self._initialize()

            self._summary_stats()
            self._per_validator_stats()
            self._branch_stats()
            self._fork_stats()
            self._collector_stats()

            sawtooth_stats = {'sawtooth_stats': self.stats}
            self._write_snapshot(sawtooth_stats, pretty=True)
            self._close()

    def _initialize(self):
        self.filename = "sawtooth_stats_snap_" + str(int(time.time())) + ".js"
        self.file = open(self.filename, 'wt')

    def _close(self):
        self.file.close()

    def _write_snapshot(self, data, pretty=False, line_feed=True):
        if pretty:
            json.dump(data, self.file, indent=4, sort_keys=True)
        else:
            json.dump(data, self.file)
        if line_feed:
            self.file.write("\n")

    def _summary_stats(self):
        stats = {'clients': self.ss.sys_client._asdict(),
                 'blocks': self.ss.sys_blocks._asdict(),
                 'transactions': self.ss.sys_txns._asdict(),
                 'packets': self.ss.sys_packets._asdict(),
                 'messages': self.ss.sys_msgs._asdict(),
                 'poet': self.ss.poet_stats._asdict(),
                 'topology': self.ts.get_stats_as_dict(),
                 'branches': self.bm.bm_stats.get_stats_as_dict(),
                 'forks': self.bm.f_stats.get_stats_as_dict()}

        self.stats['summary_stats'] = stats

    def _per_validator_stats(self):
        stats = {}
        for client in self.stats_clients:
            client_stats = self.val_stats_fixup(client.vsm.val_stats.copy())
            stats[client.name] = client_stats
            info = {'id': client.id,
                    'name': client.name,
                    'url': client.url,
                    'state': client.state,
                    'responding': client.responding,
                    'no_response_reason': client.no_response_reason,
                    'response_time': client.response_time}
            stats[client.name]['info'] = info
        self.stats['per-validator_stats'] = stats

    def _branch_stats(self):
        stats = {}
        for branch in self.bm.branches:
            stats[branch.id] = branch.get_stats_as_dict()
        self.stats['branch_stats'] = stats

    def _fork_stats(self):
        stats = {}
        for fork in self.bm.forks:
            stats[fork.id] = fork.get_stats_as_dict()
        self.stats['fork_stats'] = stats

    def _collector_stats(self):
        stats = {
            'gmt_time':
                time.strftime("GMT:%Y:%m:%d:%H:%M:%S", time.gmtime()),
            'local_time':
                time.strftime("LOCAL:%Y:%m:%d:%H:%M:%S", time.localtime()),
            'platform': self.ps.get_data_as_dict()}

        self.stats['stats_collector'] = stats

    def val_stats_fixup(self, val_stats_copy):
        # this will become a noop when validator stats is fixed so that
        # it reports nodes under the 'peer_nodes' key
        val_stats_copy['peer_nodes'] = {}
        keys_to_remove = []
        for key, root in val_stats_copy.iteritems():
            if 'IsPeer' in root:
                val_stats_copy['peer_nodes'][key] = root
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del val_stats_copy[key]

        return val_stats_copy


class DictWalker(object):
    def __init__(self):
        self.name_list = []
        self.unique_name_list = []
        self.unique_name_with_comma_list = []

        # generates a new set of key/value pairs
        # each time walk() is called
        self.data = dict()
        # contains a set of keys ordered by entry order
        # that persists across calls to walk() - this lets you discover
        # (and remember) new keys as the appear in the data stream
        self.names = collections.OrderedDict()

        self.value_type_error_count = 0
        self.name_has_comma_error_count = 0

    def walk(self, data_dict):
        self.data = dict()
        return self._traverse_dict(data_dict)

    def _traverse_dict(self, data_dict):
        for key, value in data_dict.iteritems():
            self.name_list.append(key)
            if isinstance(value, dict):
                self._traverse_dict(value)
            else:
                if isinstance(value, (list, tuple)):
                    self.value_type_error_count += 1
                    value = "value_type_error"
                if isinstance(value, str):
                    if value.find(",") is not -1:
                        self.value_has_comma_error += 1
                        value = "value_comma_error"

                unique_name = self._unique_name(self.name_list)
                if unique_name.find(",") is not -1:
                    self.name_has_comma_error_count += 1
                    self.unique_name_with_comma_list.append(unique_name)
                else:
                    self.unique_name_list.append(unique_name)
                    self.data[unique_name] = value
                    self.names[unique_name] = None

                self.name_list.pop()
        if len(self.name_list) > 0:
            self.name_list.pop()

    def get_data(self):
        # retrieve data using names so it is always reported in the same order
        # this is important when using get_data() and get_names()
        # to write header and data to csv file to ensure headers and data
        # are written in the same order even if the source dictionary changes
        # size (which it will - at minimum validators do not all process
        # the same messages
        data_list = []
        for name, value in self.names.items():
            value = self.data.get(name, "no_val")
            data_list.append(value)
        return data_list

    def get_names(self):
        name_list = []
        for name in self.names:
            name_list.append(name)
        return name_list

    def _unique_name(self, name_list):
        s = ""
        for name in name_list:
            if len(s) == 0:
                s = name
            else:
                s = "{}-{}".format(s, name)
        return s


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
                self.window_time / (len(self.txn_history) - 1)
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


class TopologyManager(object):
    def __init__(self, client_list):
        self.clients = client_list
        self.node_peer_names = {}
        self.node_peer_info = {}
        self.graph = nx.Graph()

        self.topology_stats = TopologyStats()

    def update_topology(self):
        self.node_peer_names = {}
        self.node_peer_info = {}
        for client in self.clients:
            if client.responding:
                names, info = self.extract_peer_nodes(client.vsm.val_stats)
                self.node_peer_names[client.name] = names
                self.node_peer_info[client.name] = info

        self.build_map()
        self.analyze_graph()

    def extract_peer_nodes(self, stats):
        # this would be easy if node stats were returned under a common key,
        # but for now, we will look for "IsPeer" to identify node dicts
        peer_info = {}
        peer_names = []
        for key, root in stats.iteritems():
            if "IsPeer" in root:
                if root['IsPeer'] is True:
                    peer_info[key] = root
                    peer_names.append(key.encode('utf-8'))
        return peer_names, peer_info

    def build_map(self):
        for node, peers in self.node_peer_names.iteritems():
            self.graph.add_node(node)
            for peer in peers:
                self.graph.add_node(peer)
                self.graph.add_edge(node, peer)

    def analyze_graph(self):
        self.topology_stats.analyze_graph(self.graph)


class TopologyStats(object):
    """
    Edge Conditions:
        must handle empty graph (no nodes)
        must handle one node (and no edges)
        must handle graph with no edges (no connected nodes)
        must handle graph with multiple connected components
        (including nodes with no edges)
    Synopsis:
        identifies connected components
        does full analysis if there is only one connected component
    """
    def __init__(self):

        self.clear_stats()

    def clear_stats(self):
        # private attributes must have underscore
        self._graph = None
        self._connected_component_graphs = None
        self._largest_component_graph = None
        self._degree_histogram = None

        # public stats are attributes with no underscore - follow this
        # convention to automate stats dict generation below
        self.node_count = 0
        self.edge_count = 0
        self.connected_component_count = 0
        self.average_degree = 0
        self.shortest_path_count = 0
        self.maximum_shortest_path_length = 0
        self.maximum_degree = 0
        self.minimum_degree = 0
        self.maximum_shortest_path_length = 0
        self.average_shortest_path_length = 0
        self.maximum_degree_centrality = 0
        self.minimum_connectivity = 0
        self.diameter = 0
        self.maximum_between_centrality = 0
        self.elapsed_time = 0

    def analyze_graph(self, graph):
        start_time = time.time()
        self.clear_stats()
        self._graph = graph

        self.node_count = nx.number_of_nodes(graph)
        self.edge_count = nx.number_of_edges(graph)

        degree_list = nx.degree(graph).values()

        self.connected_component_count = \
            sum(1 for cx in nx.connected_components(graph))
        if self.connected_component_count is 0:
            return

        self._connected_component_graphs = \
            nx.connected_component_subgraphs(graph)
        self._largest_component_graph = \
            max(nx.connected_component_subgraphs(graph), key=len)

        self.average_degree = sum(degree_list) / float(len(degree_list))
        self._degree_histogram = nx.degree_histogram(graph)
        spc = self.shortest_paths(graph)
        self.shortest_path_count = len(spc)
        self.maximum_shortest_path_length = \
            self.max_shortest_path_length(graph)

        if self.connected_component_count is 1:

            self.diameter = nx.diameter(graph)

            if self.node_count > 1:
                self.average_shortest_path_length = \
                    nx.average_shortest_path_length(graph)
                self.minimum_connectivity = self.min_connectivity(graph)

        if self.node_count > 0:
            self.maximum_degree = max(degree_list)
            self.minimum_degree = min(degree_list)

        if self.node_count > 1:
            dg = nx.degree_centrality(graph)
            self.maximum_degree_centrality = max(list(dg.values()))

        bc = nx.betweenness_centrality(graph)
        self.maximum_between_centrality = max(list(bc.values()))

        self.elapsed_time = time.time() - start_time

    def min_connectivity(self, graph):
        apnc = nx.all_pairs_node_connectivity(graph)
        # start with graph diameter; minimum won't be larger than this
        mc = nx.diameter(graph)
        for targets in apnc.itervalues():
            mc = min(min(targets.itervalues()), mc)
        return mc

    def shortest_paths(self, graph):
        sp = nx.shortest_path(graph)
        paths = []
        for targets in sp.itervalues():
            for path in targets.itervalues():
                if len(path) > 1:
                    if path not in paths:
                        if path[::-1] not in paths:
                            paths.append(path)
        return paths

    def max_shortest_path_length(self, graph):
        max_spl = []
        for ni in graph:
            spl = nx.shortest_path_length(graph, ni)
            mspl = max(list(spl.values()))
            max_spl.append(mspl)
        return max(max_spl)

    def get_stats_as_dict(self):
        return get_public_attrs_as_dict(self)


def get_public_attrs_as_dict(class_instance):
    # walk dictionary of class instance objects
    # filter out built-in attributes, private attributes, functions
    # requires private attributes to start with underscore
    stats = {}
    for key, value in class_instance.__dict__.items():
        if not key.startswith('__') and \
                not key.startswith('_') and \
                not callable(key):
            stats[key] = value
    return stats


def named_tuple_init(named_tuple, default=0, defaults=None):
    '''
    Initialize the instance rather than the named tuple itself because
    some values have to be initialized at runtime
    Args:
        named_tuple: named tuple instance of which is to be returned
        default: default value to be applied to all fields
        defaults: dict of default values to be applied to specified fields

    Returns:
        an initialized instance of the named_tuple
    '''
    nt = named_tuple
    default_map = {}
    for field in nt._fields:
        default_map[field] = default

    if defaults is not None:
        for k, v in defaults.iteritems():
            default_map[k] = v

    nti = named_tuple(**default_map)
    return nti

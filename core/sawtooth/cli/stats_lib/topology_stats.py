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
import networkx as nx

from sawtooth.cli.stats_lib.validator_stats import ValidatorStatsManager

from sawtooth.cli.stats_lib.stats_utils import StatsModule
from sawtooth.cli.stats_lib.stats_utils import get_public_attrs_as_dict


class TopologyManager(StatsModule):
    def __init__(self, endpoint_manager, config):
        super(TopologyManager, self).__init__()
        self.clients = None
        self.node_peer_names = {}
        self.node_peer_info = {}
        self.graph = nx.Graph()

        self.topology_stats = TopologyStats()

        self.vsm = None

    def initialize(self, module_list):
        self.module_list = module_list
        self.vsm = self.get_module(ValidatorStatsManager)
        self.clients = self.vsm.clients

    def process(self):
        self.update_topology()

    def update_topology(self):
        self.node_peer_names = {}
        self.node_peer_info = {}
        for client in self.clients:
            if client.responding:
                names, info = self.extract_peer_nodes(
                    client.validator_stats.val_stats)
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
        self.diameter = None
        self.maximum_shortest_path_length = None
        self._graph = None
        self.edge_count = None
        self._connected_component_graphs = None
        self._largest_component_graph = None
        self.minimum_degree = None
        self.shortest_path_count = None
        self.maximum_degree_centrality = None
        self.minimum_connectivity = None
        self._degree_histogram = None
        self.connected_component_count = None
        self.average_degree = None
        self.maximum_between_centrality = None
        self.maximum_degree = None
        self.node_count = None
        self.average_shortest_path_length = None
        self.elapsed_time = None

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

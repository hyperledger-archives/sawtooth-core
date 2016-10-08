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
from collections import OrderedDict
import json

from txnintegration.matrices import AdjacencyMatrix
from txnintegration.matrices import AdjacencyMatrixAnimation
from txnintegration.utils import generate_private_key
from txnintegration.utils import get_address_from_private_key_wif


def gen_dfl_cfg_poet0():
    ret = OrderedDict()
    ret['CertificateSampleLength'] = 5
    return ret


def gen_dfl_cfg_quorum(q_mag):
    ret = OrderedDict()
    ret['LedgerType'] = 'quorum'
    ret['TopologyAlgorithm'] = "Quorum"
    ret["MinimumConnectivity"] = q_mag
    ret["TargetConnectivity"] = q_mag
    ret['VotingQuorumTargetSize'] = q_mag
    ret['Nodes'] = []
    ret['VoteTimeInterval'] = 48.0
    ret['BallotTimeInterval'] = 8.0
    return ret


class NetworkConfig(object):
    def __init__(self, cfg, n_mag,
                 use_genesis=True,
                 base_host=None,
                 base_name='validator',
                 base_port=9000,
                 base_http_port=8800,
                 ):
        self.n_mag = n_mag
        self.use_genesis = use_genesis
        self.nodes = []
        for idx in range(n_mag):
            key = generate_private_key()
            nd = OrderedDict()
            nd.update(cfg)
            nd["id"] = idx
            nd["NodeName"] = "{0}-{1}".format(base_name, idx)
            nd["SigningKey"] = key
            nd["Identifier"] = get_address_from_private_key_wif(key)
            nd['Host'] = "localhost"
            if base_host is not None:
                nd['Host'] = "%s-%s" % (base_host, idx)
            nd["Port"] = base_port + idx
            nd["HttpPort"] = base_http_port + idx
            nd["Nodes"] = []
            nd["Peers"] = []
            nd["Quorum"] = []
            nd['Listen'] = [
                '%s:%s/UDP gossip' % (nd['Host'], nd['Port']),
                '%s:%s/TCP http' % (nd['Host'], nd['HttpPort']),
            ]
            nd["LedgerURL"] = []
            nd["GenesisLedger"] = False
            if idx == 0 and use_genesis is True:
                nd["GenesisLedger"] = True
            self.nodes.append(nd)
        self.node_mat = None
        self.peer_mat = None
        self.quorum_mat = None
        self.blacklist_mat = None
        self.con_mat = AdjacencyMatrixAnimation(n_mag)

    def set_ledger_url(self, node_index, ledger_node_indexes):
        self.nodes[node_index]['LedgerURL'] = [
            'http://%s:%s' % (nd['Host'], nd['HttpPort'])
            for (idx, nd) in enumerate(self.nodes)
            if idx in ledger_node_indexes
        ]

    def _get_gossip_info(self, idx):
        nd = self.nodes[idx]
        return {
            "NodeName": nd["NodeName"],
            "Identifier": nd["Identifier"],
            "Host": nd["Host"],
            "Port": nd["Port"],
            "HttpPort": nd["HttpPort"],
        }

    def set_nodes(self, node_mat):
        if self.node_mat is not None:
            raise Exception('validator configuration is static')
        self.node_mat = AdjacencyMatrix(self.n_mag, node_mat)
        mat = self.node_mat.get_mat()
        for (this_idx, this) in enumerate(self.nodes):
            this['Nodes'] = []
            for (other_idx, add_other) in enumerate(mat[this_idx]):
                if add_other == 1:
                    this['Nodes'].append(self._get_gossip_info(other_idx))

    def set_peers(self, peer_mat):
        if self.peer_mat is not None:
            raise Exception('validator configuration is static')
        self.peer_mat = AdjacencyMatrix(self.n_mag, peer_mat)
        mat = self.peer_mat.get_mat()
        for (nd_idx, nd) in enumerate(self.nodes):
            nd['Peers'] = []
            for (peer_idx, is_peer) in enumerate(mat[nd_idx]):
                if is_peer == 1 and peer_idx != nd_idx:
                    nd['Peers'].append(self.nodes[peer_idx]['NodeName'])

    def set_quorum(self, quorum_mat):
        if self.quorum_mat is not None:
            raise Exception('validator configuration is static')
        self.quorum_mat = AdjacencyMatrix(self.n_mag, quorum_mat)
        mat = self.quorum_mat.get_mat()
        for (nd_idx, nd) in enumerate(self.nodes):
            nd['Quorum'] = []
            for (quorum_idx, in_quorum) in enumerate(mat[nd_idx]):
                if in_quorum == 1:
                    nd['Quorum'].append(self.nodes[quorum_idx]['NodeName'])

    def set_blacklist(self, blacklist_mat=None):
        if self.blacklist_mat is not None:
            raise Exception('validator configuration is static')
        if blacklist_mat is None:
            assert self.peer_mat is not None
            blacklist_mat = self.peer_mat.negate()
        self.blacklist_mat = AdjacencyMatrix(self.n_mag, blacklist_mat)
        mat = self.blacklist_mat.get_mat()
        for (nd_idx, nd) in enumerate(self.nodes):
            nd['Blacklist'] = []
            for (exclude_idx, is_exclude) in enumerate(mat[nd_idx]):
                if is_exclude == 1:
                    exclude = self._get_gossip_info(exclude_idx)
                    nd['Blacklist'].append(exclude['Identifier'])

    def get_node_cfg(self, idx):
        ret = self.nodes[idx].copy()
        return ret

    def get_config_list(self):
        return [self.get_node_cfg(i) for i in range(self.n_mag)]

    def print_config_list(self):
        val = self.get_config_list()
        print json.dumps(val, indent=4)

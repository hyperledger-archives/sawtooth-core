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

from __future__ import print_function

import json
import logging
import numpy
import os
import subprocess
import sys

from sawtooth.cli.admin_sub.genesis_common import genesis_info_file_name
from txnintegration.exceptions import ExitError
from txnintegration.matrices import NodeController
from txnintegration.matrices import EdgeController
from txnintegration.netconfig import NetworkConfig
from txnintegration.utils import find_executable

LOGGER = logging.getLogger(__name__)


class ValidatorNetworkManager(object):
    def __init__(self, n_mag, same_matrix=True):
        '''
        Args:
            n_mag (int): number of nodes for your node_controller, and,
                correspondingly, the number of rows and columns in the
                adjacency matrix for controlling point-to-point network
                connectivity in your edge_controller.
            same_matrix (bool): use the same matrix for nodes and edges.  In
                this case, the diagonal for the edge_matrix can be overloaded
                to also activate and deactivate nodes.  Quite convenient for
                testing scenarios, but harder to discuss mathematically.
                Overloading the diagonal of the edge matrix to 'be' the node
                matrix is tempting because it's generally uninteresting to
                prohibit a node from talking to itself on the network.
        '''
        self.n_mag = n_mag
        self.node_controller = None
        self.edge_controller = None
        self.overload_matrices = same_matrix
        self._initialized = False

    def initialize(self, net_config, node_controller, edge_controller):
        assert isinstance(net_config, NetworkConfig)
        assert isinstance(node_controller, NodeController)
        assert isinstance(edge_controller, EdgeController)
        assert node_controller.get_mag() == edge_controller.get_mag()
        self.net_config = net_config
        self.node_controller = node_controller
        self.edge_controller = edge_controller
        self._initialized = True

    def do_genesis(self, do_genesis_validator_idx=0, **kwargs):
        assert self._initialized

        cfg = self.get_configuration(do_genesis_validator_idx)
        overrides = {
            "InitialConnectivity": 0,
            "DevModePublisher": True,
        }
        cfg.update(overrides)
        self.set_configuration(do_genesis_validator_idx, cfg)
        config_file = self.write_configuration(do_genesis_validator_idx)
        cfg = self.get_configuration(do_genesis_validator_idx)
        ledger_type = cfg.get('LedgerType', 'poet0')
        # validate user input to Popen
        assert ledger_type in ['dev_mode', 'poet0', 'poet1']
        assert os.path.isfile(config_file)
        alg_name = ledger_type
        if ledger_type == 'dev_mode':
            alg_name = 'dev-mode'
        cli_args = 'admin %s-genesis --config %s' % (alg_name, config_file)
        try:
            executable = find_executable('sawtooth')
        except ExitError:
            path = os.path.dirname(self.node_controller.txnvalidator)
            executable = os.path.join(path, 'sawtooth')
        assert os.path.isfile(executable)
        cmd = '%s %s %s' % (sys.executable, executable, cli_args)
        proc = subprocess.Popen(cmd.split())
        proc.wait()
        if proc.returncode != 0:
            return
        # Get genesis block id
        gblock_file = genesis_info_file_name(cfg['DataDirectory'])
        assert os.path.exists(gblock_file) is True
        genesis_dat = None
        with open(gblock_file, 'r') as f:
            genesis_dat = json.load(f)
        assert 'GenesisId' in genesis_dat.keys()
        head = genesis_dat['GenesisId']
        print('created genesis block: %s' % head)

    def launch(self, **kwargs):
        assert self._initialized
        print('launching network')
        mat = numpy.ones(shape=(self.n_mag, self.n_mag))
        self.update(node_mat=mat, edge_mat=mat, **kwargs)

    def staged_launch(self, stage_chunk_size=8, **kwargs):
        '''
        Quick and dirty function to spread out initializations. Most re-draws
        are effectively NOPs due to the delta matrix. Each round, the ledger
        url becomes the zeroth index of the round.
        Args:
            stage_chunk_size (int): nax number of nodes to launch per round
        Returns:
            None
        '''
        assert self._initialized
        if stage_chunk_size < self.n_mag:
            print('launching network in segments of %s' % stage_chunk_size)
        mat = numpy.zeros(shape=(self.n_mag, self.n_mag))
        idx = 0
        while idx < self.n_mag:
            n = min(idx + stage_chunk_size, self.n_mag)
            for i in range(n):
                for j in range(n):
                    mat[i][j] = 1
            self.update(node_mat=mat, edge_mat=mat, **kwargs)
            idx += stage_chunk_size

    def update(self, node_mat=None, edge_mat=None, **kwargs):
        assert self._initialized
        if self.overload_matrices is True:
            if node_mat is None:
                node_mat = edge_mat
            if edge_mat is None:
                edge_mat = node_mat
        if edge_mat is not None:
            self.edge_controller.animate(edge_mat, **kwargs)
        if node_mat is not None:
            self.node_controller.animate(node_mat, **kwargs)
        if self.overload_matrices is True:
            nm = self.node_controller.get_mat()
            em = self.edge_controller.get_mat()
            try:
                assert nm.all() == em.all()
            except AssertionError:
                msg = "You've chose to overrload the edge matrix, but your"
                msg += " node and edge matrices differ..."
                print(msg)

    def get_configuration(self, idx):
        assert self._initialized
        return self.net_config.get_node_cfg(idx)

    def set_configuration(self, idx, cfg):
        assert self._initialized
        return self.net_config.set_node_cfg(idx, cfg)

    def write_configuration(self, idx, path=None):
        assert self._initialized
        return self.net_config.write_node_cfg(idx, path)

    def urls(self):
        assert self._initialized
        return self.node_controller.urls()

    def shutdown(self, **kwargs):
        if self._initialized:
            self.node_controller.shutdown(**kwargs)
            self.edge_controller.shutdown(**kwargs)
            if self.net_config.provider is not None:
                self.net_config.provider.shutdown()

    def activate_node(self, idx, **kwargs):
        mat = self.node_controller.get_mat()
        mat[idx][idx] = 1
        self.update(node_mat=mat, **kwargs)

    def deactivate_node(self, idx, **kwargs):
        mat = self.node_controller.get_mat()
        mat[idx][idx] = 0
        self.update(node_mat=mat, **kwargs)

    def connect_edge(self, src, dst, **kwargs):
        mat = self.edge_controller.get_mat()
        mat[src][dst] = 1
        self.update(edge_mat=mat, **kwargs)

    def sever_edge(self, src, dst, **kwargs):
        mat = self.edge_controller.get_mat()
        mat[src][dst] = 0
        self.update(edge_mat=mat, **kwargs)


def get_default_vnm(num_nodes,
                    txnvalidator=None,
                    overrides=None,
                    log_config=None,
                    data_dir=None,
                    block_chain_archive=None,
                    http_port=None,
                    udp_port=None,
                    host=None,
                    endpoint_host=None):
    from txnintegration.netconfig import get_default_network_config_obj
    from txnintegration.matrices import NopEdgeController
    from txnintegration.validator_collection_controller import \
        ValidatorCollectionController
    vnm = ValidatorNetworkManager(num_nodes)
    archive = block_chain_archive
    net_cfg = get_default_network_config_obj(num_nodes,
                                             overrides=overrides,
                                             data_dir=data_dir,
                                             block_chain_archive=archive,
                                             http_port=http_port,
                                             udp_port=udp_port,
                                             host=host,
                                             endpoint_host=endpoint_host)
    vcc = ValidatorCollectionController(net_cfg, txnvalidator=txnvalidator)
    nop = NopEdgeController(net_cfg)
    vnm.initialize(net_cfg, vcc, nop)
    return vnm

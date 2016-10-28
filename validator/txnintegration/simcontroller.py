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
import numpy

from txnintegration.matrices import NodeController
from txnintegration.matrices import EdgeController
from txnintegration.netconfig import NetworkConfig


class SimController(object):
    def __init__(self, n_mag):
        self.n_mag = n_mag
        self.node_controller = None
        self.edge_controller = None
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
        idx = do_genesis_validator_idx
        cfg = self.net_config.get_node_cfg(idx)
        special = {"GenesisLedger": True}
        cfg.update(special)
        self.net_config.set_node_cfg(idx, cfg)
        print 'launching genesis node:', cfg['NodeName']
        mat = numpy.zeros(shape=(self.n_mag, self.n_mag))
        mat[idx, idx] = 1
        self.node_controller.animate(mat, **kwargs)

    def launch(self, **kwargs):
        assert self._initialized
        print 'launching network'
        mat = numpy.ones(shape=(self.n_mag, self.n_mag))
        self.node_controller.animate(mat, **kwargs)

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
            print 'launching network in segments of %s' % stage_chunk_size
        mat = numpy.zeros(shape=(self.n_mag, self.n_mag))
        idx = 0
        while idx < self.n_mag:
            n = min(idx + stage_chunk_size, self.n_mag)
            for i in range(n):
                self.net_config.set_ledger_url(i, [idx])
                for j in range(n):
                    mat[i][j] = 1
            self.node_controller.animate(mat, **kwargs)
            idx += stage_chunk_size

    def update(self,
               node_mat=None,
               edge_mat=None,
               **kwargs
               ):
        assert self._initialized
        self.edge_controller.animate(edge_mat, **kwargs)
        self.node_controller.animate(node_mat, **kwargs)

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


def get_default_sim_controller(num_nodes,
                               txnvalidator=None,
                               overrides=None,
                               log_config=None,
                               data_dir=None,
                               block_chain_archive=None,
                               http_port=None,
                               udp_port=None,
                               host=None,
                               endpoint_host=None):
    from txnintegration.netconfig import gen_dfl_net_cfg
    from txnintegration.matrices import NopEdgeController
    from txnintegration.validator_collection_controller import \
        ValidatorCollectionController
    ret = SimController(num_nodes)
    net_cfg = gen_dfl_net_cfg(num_nodes,
                              overrides=overrides,
                              data_dir=data_dir,
                              block_chain_archive=block_chain_archive,
                              http_port=http_port,
                              udp_port=udp_port,
                              host=host,
                              endpoint_host=endpoint_host)
    vnm = ValidatorCollectionController(net_cfg, txnvalidator=txnvalidator)
    nop = NopEdgeController(net_cfg)
    ret.initialize(net_cfg, vnm, nop)
    return ret

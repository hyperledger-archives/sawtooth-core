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
    def __init__(self, n_mag, ledger_type='poet0'):
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

    def do_genesis(self, **kwargs):
        assert self._initialized
        print 'launching genesis'
        mat = numpy.zeros(shape=(self.n_mag, self.n_mag))
        mat[0, 0] = 1
        self.node_controller.animate(mat, **kwargs)

    def launch(self, **kwargs):
        assert self._initialized
        print 'launching network'
        mat = numpy.ones(shape=(self.n_mag, self.n_mag))
        self.node_controller.animate(mat, **kwargs)

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


def get_default_sim_controller(n, ledger_type=None):
    from txnintegration.netconfig import gen_dfl_net_cfg
    from txnintegration.matrices import NopEdgeController
    from txnintegration.validator_collection_controller import \
        ValidatorCollectionController
    ret = SimController(n)
    net_cfg = gen_dfl_net_cfg(n, ledger_type=ledger_type)
    vnm = ValidatorCollectionController(net_cfg)
    nop = NopEdgeController(net_cfg)
    ret.initialize(net_cfg, vnm, nop)
    return ret

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
from txnintegration.matrices import NopEdgeController
from txnintegration.netconfig import NetworkConfig
from txnintegration.netconfig import gen_dfl_cfg_poet0
from txnintegration.netconfig import gen_dfl_cfg_quorum
from txnintegration.validator_collection_controller import \
    ValidatorCollectionController


def set_default_topology(topology,
                         ledger_type,
                         cfg_overrides=None,
                         use_ledger_url=True,
                         use_mktplace=False,
                         q_mag=None
                         ):
    cfg = None
    if ledger_type in ['dev_mode', 'poet0']:
        cfg = gen_dfl_cfg_poet0()
    elif ledger_type in ['quorum']:
        q = q_mag
        if q is None:
            q = topology.n_mag
        cfg = gen_dfl_cfg_quorum(q)
    cfg['LedgerType'] = ledger_type
    if cfg_overrides is not None:
        cfg.update(cfg_overrides)
    if use_mktplace is True and 'mktplace.transactions.market_place' \
            not in cfg['TransactionFamilies']:
        cfg['TransactionFamilies'].append('mktplace.transactions.market_place')
    net = NetworkConfig(cfg, topology.n_mag)
    if use_ledger_url:
        for i in range(1, topology.n_mag):
            net.set_ledger_url(i, [0])
    vnm = ValidatorCollectionController(net)
    web = NopEdgeController(net)
    topology.initialize(vnm, web)
    return topology


class SimController(object):
    def __init__(self, n_mag, ledger_type='poet0'):
        self.n_mag = n_mag
        self.node_controller = None
        self.edge_controller = None
        self._initialized = False

    def initialize(self, node_controller, edge_controller):
        assert isinstance(node_controller, NodeController)
        assert isinstance(edge_controller, EdgeController)
        assert node_controller.get_mag() == edge_controller.get_mag()
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

    def get_validator_configuration(self, idx):
        assert self._initialized
        return self.node_controller.configuration(idx)

    def set_validator_configuration(self, idx, cfg):
        assert self._initialized
        self.node_controller.set_validator_configuration(idx, cfg)

    def urls(self):
        assert self._initialized
        return self.node_controller.urls()

    def shutdown(self, **kwargs):
        if self._initialized:
            self.node_controller.shutdown(**kwargs)
            self.edge_controller.shutdown(**kwargs)

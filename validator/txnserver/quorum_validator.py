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

import logging
from twisted.internet import reactor
from txnserver import validator
from gossip.topology import quorum as quorum_topology

logger = logging.getLogger(__name__)


class QuorumValidator(validator.Validator):

    def start(self):
        if self.GenesisLedger:
            self.start_ledger()

            def nop():
                pass

            reactor.callLater(2.0, self.initialize_ledger_topology, nop)
            return
        self.initialize_ledger_connection()

    def initialize_ledger_connection(self):
        """
        Connect the ledger to the rest of the network.
        """
        self.status = 'waiting for initial connections'
        reactor.callLater(2.0, self.initialize_ledger_topology,
                          self.start_journal_transfer)

    def initialize_ledger_topology(self, callback):
        """
        Kick off the quorum topology generation protocol.
        """
        logger.debug('initialize ledger topology')
        self._connectionattempts = 0
        topology = self.Config.get("TopologyAlgorithm", "")
        if topology != "Quorum":
            logger.error("unknown topology protocol %s", topology)
            self.shutdown()
            return
        if 'TargetConnectivity' in self.Config:
            quorum_topology.TargetConnectivity = self.Config[
                'TargetConnectivity']
        if 'MinimumConnectivity' in self.Config:
            quorum_topology.MinimumConnectivity = self.Config[
                'MinimumConnectivity']
        self.quorum_initialization(callback)

    def quorum_initialization(self, callback):
        logger.info("ledger connections using Quorum topology")
        quorum_topology.start_topology_update(self.Ledger,
                                              callback)

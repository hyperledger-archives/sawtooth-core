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

import time
import os
import json
import unittest

from sawtooth.manage.node import NodeArguments
from sawtooth.manage.subproc import SubprocessNodeController
from sawtooth.manage.wrap import WrappedNodeController
from txnintegration.utils import Progress
from txnintegration.utils import TimeOut
from txnintegration.utils import sit_rep
from txnintegration.utils import is_convergent
from sawtooth.exceptions import MessageException


class SawtoothTestSuite(unittest.TestCase):
    def _do_setup(self, cfg, node_count=5):
        # give defaults to teardown vars
        self._node_ctrl = None
        print('creating', str(self.__class__.__name__))
        # set up our nodes (suite-internal interface)
        self._node_ctrl = WrappedNodeController(SubprocessNodeController())
        temp_dir = self._node_ctrl.get_data_dir()
        file_name = os.path.join(temp_dir, "config.js")
        with open(file_name, 'w') as config:
            config.write(json.dumps(cfg))
        self._nodes = [
            NodeArguments('v%s' % i, 8800 + i, 9000 + i,
                          config_files=[file_name],
                          ledger_type=cfg["LedgerType"])
            for i in range(node_count)]
        # set up our urls (external interface)
        self.urls = ['http://localhost:%s' % x.http_port for x in self._nodes]
        # Make genesis block
        print('creating genesis block...')
        self._nodes[0].genesis = True
        self._node_ctrl.create_genesis_block(self._nodes[0])
        # Launch network (node zero will trigger bootstrapping)
        print('launching network...')
        for x in self._nodes:
            self._node_ctrl.start(x)

    def _do_teardown(self):
        print('destroying', str(self.__class__.__name__))
        if hasattr(self, '_node_ctrl') and self._node_ctrl is not None:
            # Shut down the network
            with Progress("terminating network") as p:
                for node_name in self._node_ctrl.get_node_names():
                    self._node_ctrl.stop(node_name)
                to = TimeOut(16)
                while len(self._node_ctrl.get_node_names()) > 0:
                    if to.is_timed_out():
                        break
                    time.sleep(1)
                    p.step()
            # force kill anything left over
            for node_name in self._node_ctrl.get_node_names():
                try:
                    print("%s still 'up'; sending kill..." % node_name)
                    self._node_ctrl.kill(node_name)
                except Exception as e:
                    print(e.message)
            self._node_ctrl.archive(self.__class__.__name__)
            self._node_ctrl.clean()

    def _poll_for_convergence(self, timeout=256, tolerance=2, standard=5):
        convergent = False
        with Progress('awaiting convergence') as p:
            to = TimeOut(timeout)
            while convergent is False:
                self.assertFalse(to.is_timed_out(),
                                 'timed out awaiting convergence')
                p.step()
                time.sleep(4)
                try:
                    convergent = is_convergent(self.urls, standard=standard,
                                               tolerance=tolerance)
                except MessageException:
                    pass
        sit_rep(self.urls, verbosity=1)
        return convergent

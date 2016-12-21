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
import time
import os
import json
import traceback
import unittest

from sawtooth.manage.node import NodeArguments
from sawtooth.manage.subproc import SubprocessNodeController
from sawtooth.manage.wrap import WrappedNodeController
from sawtooth.exceptions import MessageException
from txnintegration.utils import Progress
from txnintegration.utils import TimeOut
from txnintegration.utils import is_convergent
from txnintegration.utils import sit_rep
from integration.test_all_transactions import TestAllTransactions
from integration.test_cp_scenarios import TestCommercialPaperScenarios
from integration.test_smoke import TestSmoke

LOGGER = logging.getLogger(__name__)


class DevModeMktTestSuite(unittest.TestCase):
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

    def _do_teardown(self):
        print 'destroying', str(self.__class__.__name__)
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
                    print "%s still 'up'; sending kill..." % node_name
                    self._node_ctrl.kill(node_name)
                except Exception as e:
                    print e.message
            self._node_ctrl.archive(self.__class__.__name__)
            self._node_ctrl.clean()

    def _do_setup(self):
        # give defaults to teardown vars
        self._node_ctrl = None
        print 'creating', str(self.__class__.__name__)
        # set up our nodes (suite-internal interface)
        self._node_ctrl = WrappedNodeController(SubprocessNodeController())
        cfg = {"LedgerType": "dev_mode",
               'InitialWaitTime': 1,
               'TargetWaitTime': 1,
               "TransactionFamilies": ["ledger.transaction.integer_key",
                                       "mktplace.transactions.market_place"],
               "DevModePublisher": True}
        temp_dir = self._node_ctrl.get_data_dir()
        file_name = os.path.join(temp_dir, "config.js")
        with open(file_name, 'w') as config:
            config.write(json.dumps(cfg))

        self._nodes = [
            NodeArguments('v%s' % 0, 8800 , 9000,
                          config_files=[file_name],
                          ledger_type="dev_mode")]
        # set up our urls (external interface)
        self.urls = ['http://localhost:%s' % x.http_port for x in self._nodes]
        # Make genesis block
        print 'creating genesis block...'
        self._nodes[0].genesis = True

        self._node_ctrl.create_genesis_block(self._nodes[0])
        # Launch network (node zero will trigger bootstrapping)
        print 'launching network...'
        for x in self._nodes:
            self._node_ctrl.start(x)
        time.sleep(20)

    def test_suite(self):
        success = False
        try:
            self._do_setup()
            urls = self.urls
            suite = unittest.TestSuite()
            suite.addTest(TestSmoke('test_mktplace_load', urls,
                                    self._node_ctrl.get_data_dir()))
            # suite.addTest(TestCommercialPaperScenarios('test_scenario_setup'))
            # suite.addTest(TestCommercialPaperScenarios('test_scenario_a'))
            # suite.addTest(TestCommercialPaperScenarios('test_scenario_b'))
            # suite.addTest(TestCommercialPaperScenarios('test_scenario_c'))
            # suite.addTest(TestCommercialPaperScenarios('test_scenario_d'))
            suite.addTest(TestAllTransactions('test_all_transactions', urls))
            runner = unittest.TextTestRunner(verbosity=2)
            result = runner.run(suite)
            if len(result.failures) == 0 and len(result.errors) == 0:
                success = True
        except:
            traceback.print_exc()
            raise
        finally:
            self._do_teardown()
            if success is False:
                self.fail(self.__class__.__name__)

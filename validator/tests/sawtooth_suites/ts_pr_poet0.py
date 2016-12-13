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

from integration.test_smoke import TestSmoke
from integration.test_convergence import TestConvergence
from integration.test_local_validation import TestLocalValidationErrors
from integration.test_web_api import TestWebApi
from integration.test_genesis_util import TestGenesisUtil
from sawtooth.manage.node import NodeArguments
from sawtooth.manage.subproc import SubprocessNodeController
from sawtooth.manage.wrap import WrappedNodeController
from txnintegration.utils import Progress
from txnintegration.utils import TimeOut


LOGGER = logging.getLogger(__name__)


class Poet0TestSuite(unittest.TestCase):
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
        cfg = {"LedgerType": "poet0",
               "TransactionFamilies": ["ledger.transaction.integer_key"]}
        temp_dir = self._node_ctrl.get_data_dir()
        file_name = os.path.join(temp_dir, "config.js")
        with open(file_name, 'w') as config:
            config.write(json.dumps(cfg))

        self._nodes = [
            NodeArguments('v%s' % i, 8800 + i, 9000 + i,
                          config_files=[file_name], ledger_type="poet0")
                          for i in range(5)]
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

    def test_suite(self):
        success = False
        try:
            suite = unittest.TestSuite(unittest.makeSuite(TestGenesisUtil))
            runner = unittest.TextTestRunner(verbosity=2)
            result = runner.run(suite)
            if len(result.failures) == 0 and len(result.errors) == 0:
                success = True
            self._do_setup()
            urls = self.urls
            suite = unittest.TestSuite(unittest.makeSuite(TestWebApi))
            # test_bootstrap will allow the validators to all come on line
            # before other tries to connect to the validators.
            suite.addTest(TestConvergence('test_bootstrap', urls))
            suite.addTest(TestSmoke('test_intkey_load_poet0', urls))
            suite.addTest(
                TestLocalValidationErrors('test_local_validation_errors',
                                          urls))
            result = runner.run(suite)
            if len(result.failures) == 0 and len(result.errors) == 0 and \
                success == True:
                success = True
        except:
            traceback.print_exc()
            raise
        finally:
            self._do_teardown()
            if success is False:
                self.fail(self.__class__.__name__)

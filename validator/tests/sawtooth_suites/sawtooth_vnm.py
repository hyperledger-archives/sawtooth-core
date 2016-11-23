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
import os
import shutil
import sys
import tempfile
import time
import traceback
import unittest

from integration.test_convergence import TestConvergence
from sawtooth.manage.node import NodeArguments
from sawtooth.manage.subproc import SubprocessNodeController
from txnintegration.utils import Progress
from txnintegration.utils import TimeOut

LOGGER = logging.getLogger(__name__)

class SawtoothVnmTestSuite(unittest.TestCase):
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
        # Clean temp dir
        print 'deleting temp directory'
        tmp_dir = hasattr(self, '_currency_home')
        tmp_dir = None if tmp_dir is False else self._currency_home
        if tmp_dir is not None and os.path.isdir(tmp_dir):
            shutil.rmtree(tmp_dir)
        # Restore environmental vars
        if hasattr(self, '_old_currency_home'):
            print 'restoring environmental variables'
            if self._old_currency_home is None:
                os.unsetenv('CURRENCYHOME')
            else:
                os.environ['CURRENCYHOME'] = self._old_currency_home

    def _do_setup(self):
        # give defaults to teardown vars
        self._node_ctrl = None
        self._currency_home = None
        self._old_currency_home = os.getenv('CURRENCYHOME')
        print 'creating', str(self.__class__.__name__)
        # We're not wrapped, so set up a temp CURRENCYHOME we can delete
        self._currency_home = tempfile.mkdtemp()
        for directory in ['data', 'keys', 'logs']:
            os.makedirs(os.path.join(self._currency_home, directory))
        os.environ['CURRENCYHOME'] = self._currency_home
        # set up our nodes (suite-internal interface)
        self._nodes = [
            NodeArguments('v%s' % i, 8800 + i, 9000 + i) for i in range(2)
        ]
        # set up our urls (external interface)
        self.urls = ['http://localhost:%s' % x.http_port for x in self._nodes]
        # Make genesis block
        print 'creating genesis block...'
        self._nodes[0].genesis = True
        self._node_ctrl = SubprocessNodeController()
        self._node_ctrl.do_genesis(self._nodes[0])
        # Launch network (node zero will trigger bootstrapping)
        print 'launching network...'
        for x in self._nodes:
            self._node_ctrl.start(x)

    def test_suite(self):
        success = False
        try:
            print
            self._do_setup()
            urls = self.urls
            suite = unittest.TestSuite()
            suite.addTest(TestConvergence('test_bootstrap', urls))
            runner = unittest.TextTestRunner()
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

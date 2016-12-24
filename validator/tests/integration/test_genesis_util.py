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
import os
import time
import unittest

from sawtooth.cli.admin_sub.genesis_common import genesis_info_file_name
from sawtooth.exceptions import MessageException
from sawtooth.manage.node import NodeArguments
from sawtooth.manage.subproc import SubprocessNodeController
from sawtooth.manage.wrap import WrappedNodeController
from txnintegration.utils import get_blocklists
from txnintegration.utils import is_convergent
from txnintegration.utils import Progress
from txnintegration.utils import TimeOut

LOGGER = logging.getLogger(__name__)

RUN_TEST_SUITES = True \
    if os.environ.get("RUN_TEST_SUITES", False) == "1" else False

DISABLE_POET1_SGX = True \
    if os.environ.get("DISABLE_POET1_SGX", False) == "1" else False


@unittest.skipUnless(RUN_TEST_SUITES, "Must be run in a test suites")
class TestGenesisUtil(unittest.TestCase):
    def extend_genesis_util(self, overrides):
        print()
        try:
            self._node_ctrl = None
            print('creating', str(self.__class__.__name__))
            # set up our nodes (suite-internal interface)
            self._node_ctrl = WrappedNodeController(SubprocessNodeController())
            cfg = overrides
            temp_dir = self._node_ctrl.get_data_dir()
            file_name = os.path.join(temp_dir, "config.js")
            with open(file_name, 'w') as config:
                config.write(json.dumps(cfg))
            data_dir = os.path.join(temp_dir, "data")
            gblock_file = genesis_info_file_name(data_dir)

            self._nodes = [
                NodeArguments('v%s' % i, 8800 + i, 9000 + i,
                              config_files=[file_name],
                              ledger_type=overrides["LedgerType"])
                for i in range(2)]
            # set up our urls (external interface)
            self.urls = [
                'http://localhost:%s' % x.http_port for x in self._nodes]
            # Make genesis block
            print('creating genesis block...')
            self.assertFalse(os.path.exists(gblock_file))
            self._nodes[0].genesis = True
            self._node_ctrl.create_genesis_block(self._nodes[0])

            # Test genesis util
            self.assertTrue(os.path.exists(gblock_file))
            genesis_dat = None
            with open(gblock_file, 'r') as f:
                genesis_dat = json.load(f)
            self.assertTrue('GenesisId' in genesis_dat.keys())
            head = genesis_dat['GenesisId']
            # Verify genesis tool efficacy on a minimal network
            # Launch network (node zero will trigger bootstrapping)
            print('launching network...')
            for x in self._nodes:
                self._node_ctrl.start(x)

            # wait a second for the node start the listening service to avoid
            # client operation failed: connection refused
            time.sleep(1)
            # ...verify validator is extending tgt_block
            to = TimeOut(64)
            blk_lists = None
            prog_str = 'testing root extension (expect root: %s)' % head
            with Progress(prog_str) as p:
                print()
                while not to.is_timed_out() and blk_lists is None:
                    p.step()
                    try:
                        blk_lists = get_blocklists(['http://localhost:8800'])
                        print('block_lists: %s' % blk_lists)
                        if len(blk_lists) < 1 or len(blk_lists[0]) < 2:
                            blk_lists = None
                    except MessageException as e:
                        pass
                    time.sleep(2)
            self.assertIsNotNone(blk_lists)
            root = blk_lists[0][0]
            self.assertEqual(head, root)
            # ...verify general convergence
            to = TimeOut(32)
            with Progress('testing root convergence') as p:
                print()
                while (is_convergent(self.urls, tolerance=1, standard=1)
                       is False and not to.is_timed_out()):
                    time.sleep(2)
                    p.step()
            # ...verify convergence on the genesis block
            blk_lists = get_blocklists(['http://localhost:8800'])
            root = blk_lists[0][0]
            self.assertEqual(head, root)
            print('network converged on root: %s' % root)
        finally:
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

    def test_dev_mode_genesis(self):
        self.extend_genesis_util({'LedgerType': 'dev_mode',
                                  'DevModePublisher': True})

    def test_poet0_genesis(self):
        self.extend_genesis_util({'LedgerType': 'poet0'})

    @unittest.skipIf(DISABLE_POET1_SGX, 'SGX currently behind simulator')
    def test_poet1_genesis(self):
        self.extend_genesis_util({'LedgerType': 'poet1'})

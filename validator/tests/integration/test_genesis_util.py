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
import json
import logging
import os
import time
import unittest

from sawtooth.cli.admin_sub.poet0_genesis import get_genesis_block_id_file_name
from sawtooth.exceptions import MessageException
from txnintegration.utils import get_blocklists
from txnintegration.utils import Progress
from txnintegration.utils import sawtooth_cli_intercept
from txnintegration.utils import TimeOut

from txnintegration.simcontroller import get_default_sim_controller

LOGGER = logging.getLogger(__name__)


class TestGenesisUtil(unittest.TestCase):

    def test_genesis_util(self):
        print
        top = None
        try:
            # Get config and resources for a ValidatorManager compliant node
            top = get_default_sim_controller(1)
            cfg = top.get_configuration(0)
            data_dir = cfg['DataDirectory']
            # Test admin poet0-genesis tool
            fname = get_genesis_block_id_file_name(data_dir)
            self.assertFalse(os.path.exists(fname))
            config_file = top.write_configuration(0)
            cli_args = 'admin poet0-genesis --config %s' % config_file
            sawtooth_cli_intercept(cli_args)
            self.assertTrue(os.path.exists(fname))
            genesis_dat = None
            with open(fname, 'r') as f:
                genesis_dat = json.load(f)
            self.assertTrue('GenesisId' in genesis_dat.keys())
            tgt_block = genesis_dat['GenesisId']
            # Verify genesis tool (also tests blockchain restoration)
            # ...initial connectivity must be zero for the initial validator
            cfg['InitialConnectivity'] = 0
            top.set_configuration(0, cfg)
            # ...launch validator
            top.node_controller.activate(0, probe_seconds=32)
            # ...verify validator is extending tgt_block
            to = TimeOut(64)
            blk_lists = None
            prog_str = 'TEST ROOT RESTORATION (expect %s)' % tgt_block
            with Progress(prog_str) as p:
                print
                while not to.is_timed_out() and blk_lists is None:
                    try:
                        blk_lists = get_blocklists(['http://localhost:8800'])
                        print 'block_lists: %s' % blk_lists
                        if len(blk_lists) < 1 or len(blk_lists[0]) < 2:
                            blk_lists = None
                    except MessageException as e:
                        pass
                    time.sleep(1)
                    p.step()
            self.assertIsNotNone(blk_lists)
            root = blk_lists[0][0]
            self.assertEqual(tgt_block, root)

        finally:
            if top is not None:
                top.shutdown()

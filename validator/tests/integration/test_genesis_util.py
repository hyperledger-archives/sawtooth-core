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

from sawtooth.cli.admin_sub.genesis_common import genesis_info_file_name
from sawtooth.exceptions import MessageException
from txnintegration.utils import get_blocklists
from txnintegration.utils import is_convergent
from txnintegration.utils import Progress
from txnintegration.utils import TimeOut

from txnintegration.simcontroller import get_default_sim_controller

LOGGER = logging.getLogger(__name__)

DISABLE_POET1_SGX = True \
    if os.environ.get("DISABLE_POET1_SGX", False) == "1" else False


class TestGenesisUtil(unittest.TestCase):
    def extend_genesis_util(self, overrides):
        print
        top = None
        try:
            top = get_default_sim_controller(2, overrides=overrides)
            # Test genesis util
            cfg = top.get_configuration(0)
            ledger_type = cfg['LedgerType']
            gblock_file = genesis_info_file_name(cfg['DataDirectory'])
            self.assertFalse(os.path.exists(gblock_file))
            top.do_genesis()
            self.assertTrue(os.path.exists(gblock_file))
            genesis_dat = None
            with open(gblock_file, 'r') as f:
                genesis_dat = json.load(f)
            self.assertTrue('GenesisId' in genesis_dat.keys())
            head = genesis_dat['GenesisId']
            # Verify genesis tool efficacy on a minimal network
            top.launch()
            # ...verify validator is extending tgt_block
            to = TimeOut(64)
            blk_lists = None
            prog_str = 'testing root extension (expect root: %s)' % head
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
                    time.sleep(2)
                    p.step()
            self.assertIsNotNone(blk_lists)
            root = blk_lists[0][0]
            self.assertEqual(head, root)
            # ...verify general convergence
            to = TimeOut(32)
            with Progress('testing root convergence') as p:
                print
                while (is_convergent(top.urls(), tolerance=1, standard=1)
                       is False and not to.is_timed_out()):
                    time.sleep(2)
                    p.step()
            # ...verify convergence on the genesis block
            blk_lists = get_blocklists(['http://localhost:8800'])
            root = blk_lists[0][0]
            self.assertEqual(head, root)
            print 'network converged on root: %s' % root
        finally:
            if top is not None:
                archive_name = 'Test%sGenesisResults' % ledger_type.upper()
                top.shutdown(archive_name=archive_name)

    def test_dev_mode_genesis(self):
        self.extend_genesis_util({'LedgerType': 'dev_mode'})

    def test_poet0_genesis(self):
        self.extend_genesis_util({})

    @unittest.skipIf(DISABLE_POET1_SGX, 'SGX currently behind simulator')
    def test_poet1_genesis(self):
        self.extend_genesis_util({'LedgerType': 'poet1'})

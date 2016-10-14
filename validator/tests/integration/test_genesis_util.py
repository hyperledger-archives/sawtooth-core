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
import shutil
import tempfile
import time
import unittest

from sawtooth.cli.admin_sub.poet0_genesis import get_genesis_block_id_file_name
from sawtooth.cli.main import main as entry_point
from sawtooth.exceptions import MessageException
from sawtooth.validator_config import get_validator_configuration
from txnintegration.netconfig import NetworkConfig
from txnintegration.utils import find_txn_validator
from txnintegration.utils import get_blocklists
from txnintegration.utils import Progress
from txnintegration.utils import TimeOut
from txnintegration.validator_collection_controller \
    import ValidatorCollectionController

LOGGER = logging.getLogger(__name__)


class TestGenesisUtil(unittest.TestCase):

    def test_genesis_util(self):
        print
        old_home = os.getenv('CURRENCYHOME')
        tmp_home = tempfile.mkdtemp()
        vcc = None
        try:
            # Set up env and config
            v_file = find_txn_validator()
            os.environ['CURRENCYHOME'] = tmp_home
            cfg = get_validator_configuration([], {})
            # ...rewire for ValidatorManager compatibility
            cfg['KeyDirectory'] = tmp_home
            cfg['DataDirectory'] = tmp_home
            cfg['LogDirectory'] = tmp_home

            # En route, test keygen client via main
            key_name = cfg['NodeName']
            key_dir = cfg['KeyDirectory']
            cmd = 'keygen %s --key-dir %s' % (key_name, key_dir)
            entry_point(args=cmd.split(), with_loggers=False)
            base_name = key_dir + os.path.sep + key_name
            self.assertTrue(os.path.exists('%s.wif' % base_name))
            self.assertTrue(os.path.exists('%s.addr' % base_name))
            cfg['KeyFile'] = '%s.wif' % base_name

            # Test admin poet0-genesis tool
            fname = get_genesis_block_id_file_name(cfg['DataDirectory'])
            self.assertFalse(os.path.exists(fname))
            config_file = tmp_home + os.path.sep + 'cfg.json'
            with open(config_file, 'w') as f:
                f.write(json.dumps(cfg, indent=4) + '\n')
            cmd = 'admin poet0-genesis --config %s' % config_file
            entry_point(args=cmd.split(), with_loggers=False)
            self.assertTrue(os.path.exists(fname))
            dat = None
            with open(fname, 'r') as f:
                dat = json.load(f)
            self.assertTrue('GenesisId' in dat.keys())
            tgt_block = dat['GenesisId']

            # Verify genesis tool (also tests blockchain restoration)
            # ...initial connectivity must be zero for the initial validator
            cfg['InitialConnectivity'] = 0
            # ...launch validator
            net_cfg = NetworkConfig.from_config_list([cfg])
            vcc = ValidatorCollectionController(net_cfg, data_dir=tmp_home,
                                                txnvalidator=v_file)
            vcc.activate(0, probe_seconds=120)
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
            # Shut down validator
            if vcc is not None:
                vcc.shutdown()
            # Restore environmental vars
            if old_home is None:
                os.unsetenv('CURRENCYHOME')
            else:
                os.environ['CURRENCYHOME'] = old_home
            # Delete temp dir
            if os.path.exists(tmp_home):
                shutil.rmtree(tmp_home)

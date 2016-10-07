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
import argparse
import json
import logging
import os
import shutil
import subprocess
import tempfile
import time
import traceback
import unittest

from sawtooth.cli.admin_sub.poet0_genesis import do_poet0_genesis
from sawtooth.cli.keygen import do_keygen
from sawtooth.exceptions import MessageException
from sawtooth.validator_config import get_validator_configuration
from txnintegration.utils import find_txn_validator
from txnintegration.utils import get_blocklists
from txnintegration.utils import Progress
from txnintegration.utils import TimeOut

LOGGER = logging.getLogger(__name__)


class TestGenesisUtil(unittest.TestCase):
    def test_genesis_util(self):
        old_home = os.getenv('CURRENCYHOME')
        tmp_home = tempfile.mkdtemp()
        proc = None
        try:
            # set up env and config
            os.environ['CURRENCYHOME'] = tmp_home
            cfg = get_validator_configuration([], {})
            config_file = tmp_home + os.path.sep + 'cfg.cfg'
            with open(config_file, 'w') as f:
                f.write(json.dumps(cfg, indent=4) + '\n')
            self.assertEqual(False, os.path.exists(cfg['KeyDirectory']))
            os.makedirs(cfg['KeyDirectory'])
            os.makedirs(cfg['DataDirectory'])
            os.makedirs(cfg['LogDirectory'])

            # en route, test keygen client
            ns = argparse.Namespace()
            ns.key_dir = cfg['KeyDirectory']
            ns.key_name = cfg['NodeName']
            ns.force = True
            ns.quiet = False
            do_keygen(ns)
            base_name = ns.key_dir + os.path.sep + ns.key_name
            self.assertEqual(True, os.path.exists('%s.wif' % base_name))
            self.assertEqual(True, os.path.exists('%s.addr' % base_name))

            # test admin poet0-genesis tool
            ns = argparse.Namespace()
            ns.admin_cmd = 'poet0-genesis'
            ns.config = [config_file]
            (bid, clen) = do_poet0_genesis(ns)

            # verify genesis tool (also tests restore)
            # ...hack the cfg to restore w/o peering and rewrite
            cfg['Restore'] = True
            cfg['LedgerURL'] = []
            cfg['InitialConnectivity'] = 0
            with open(config_file, 'w') as f:
                f.write(json.dumps(cfg, indent=4) + '\n')
            # ...test inputs to cmd (before passing to popen)
            validator_file = find_txn_validator()
            if not os.path.isfile(validator_file):
                raise RuntimeError('%s is not a file' % validator_file)
            if not os.path.isfile(config_file):
                raise RuntimeError('%s is not a file' % config_file)
            cmd = '%s -vv --config %s' % (validator_file, config_file)
            # ...spawn validator using our new genesis block
            proc = subprocess.Popen(cmd.split(),
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    env=os.environ.copy())
            # ...demonstrate that validator is building on our new block
            expected = 'operation failed: [Errno 111] Connection refused'
            to = TimeOut(64)
            blk_lists = None
            with Progress('TEST ROOT RESTORATION (expect %s)\n' % bid) as p:
                while not to.is_timed_out() and blk_lists is None:
                    try:
                        blk_lists = get_blocklists(['http://localhost:8800'])
                        print 'block_lists: %s' % blk_lists
                        if len(blk_lists) < 1 or len(blk_lists[0]) < 2:
                            blk_lists = None
                    except MessageException as e:
                        if e.message != expected:
                            raise
                    time.sleep(1)
                    p.step()
            root = blk_lists[0][0]
            self.assertEqual(bid, root)

        finally:
            if proc is not None:
                proc.kill()
            if old_home is None:
                os.unsetenv('CURRENCYHOME')
            else:
                os.environ['CURRENCYHOME'] = old_home
            if os.path.exists(tmp_home):
                shutil.rmtree(tmp_home)

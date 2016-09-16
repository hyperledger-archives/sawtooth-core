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
import copy
import logging
import math
import os
import time
import traceback
import unittest

from sawtooth.client import SawtoothClient
from txnintegration.netconfig import gen_dfl_cfg_poet0
from txnintegration.netconfig import NetworkConfig
from txnintegration.simcontroller import NopEdgeController
from txnintegration.simcontroller import SimController
from txnintegration.validator_collection_controller import \
    ValidatorCollectionController
from txnintegration.integer_key_client import IntegerKeyClient
from txnintegration.utils import is_convergent
from txnintegration.utils import sit_rep
from txnintegration.utils import generate_private_key as gen_pk


logger = logging.getLogger(__name__)

ENABLE_INTEGRATION_TESTS = False
if os.environ.get("ENABLE_INTEGRATION_TESTS", False) == "1":
    ENABLE_INTEGRATION_TESTS = True


class TestPartitionRecovery(unittest.TestCase):

    def _get_blocklists(self, urls):
        ret = [(SawtoothClient(base_url=u)).get_block_list() for u in urls]
        for (i, arr) in enumerate(ret):
            arr.reverse()
            ret[i] = [hsh[:4] for hsh in arr]
        return ret

    def _validate_blocklists(self, blocklists, verbose=True, strict=False):
        if verbose:
            print 'validating block lists....'
        reference = blocklists[0]
        valid = True
        for (i, x) in enumerate(blocklists):
            if strict:
                self.assertEqual(reference, x,
                                 'validator %s blocklist is divergent' % i)
            if reference != x:
                valid = False
        if verbose and valid:
            print '....block lists have converged'

    def _do_work(self, ik_client, off, n_mag):
        for i in range(off, off + n_mag):
            ik_client.set(key=str(i), value=math.pow(2, i))
            ik_client.waitforcommit()

    def test_two_clique(self):
        # this topology forms 2 exclusive cliques when n2 is severed
        vulnerable_mat = [
            [1, 1, 0, 0, 0],
            [1, 1, 1, 0, 0],
            [0, 1, 1, 1, 0],
            [0, 0, 1, 1, 1],
            [0, 0, 0, 1, 1],
        ]
        two_clique_mat = copy.deepcopy(vulnerable_mat)
        two_clique_mat[2][2] = 0
        n = len(vulnerable_mat)
        top = SimController(n)
        print
        try:
            print 'phase 0: build vulnerably connected 5-net:'
            net_cfg = NetworkConfig(gen_dfl_cfg_poet0(), n)
            net_cfg.set_nodes(vulnerable_mat)
            net_cfg.set_peers(vulnerable_mat)
            net_cfg.set_blacklist()
            vnm = ValidatorCollectionController(net_cfg)
            web = NopEdgeController(net_cfg)
            top.initialize(vnm, web)
            print 'phase 1: launch vulnerably connected 5-net:'
            top.do_genesis(probe_seconds=0)
            top.launch(probe_seconds=0)
            print 'phase 2: validate state across 5-net:'
            sit_rep(top.urls(), verbosity=2)
            print 'phase 3: morph 5-net into two exclusive 2-net cliques:'
            top.update(node_mat=two_clique_mat, probe_seconds=0, reg_seconds=0)
            print 'providing time for convergence (likely partial)...'
            time.sleep(32)
            sit_rep(top.urls())
            print 'phase 4: generate chain-ext A on clique {0, 1}:'
            url = top.urls()[0]
            print 'sending transactions to %s...' % (url)
            ikcA = IntegerKeyClient(baseurl=url, keystring=gen_pk())
            self._do_work(ikcA, 5, 2)
            print 'providing time for partial convergence...'
            time.sleep(8)
            sit_rep(top.urls())
            print 'phase 5: generate chain-ext B on clique {3, 4}, |B| = 2|A|:'
            url = top.urls()[-1]
            print 'sending transactions to %s...' % (url)
            ikcB = IntegerKeyClient(baseurl=url, keystring=gen_pk())
            self._do_work(ikcB, 1, 4)
            print 'providing time for partial convergence...'
            time.sleep(8)
            sit_rep(top.urls())
            print 'TEST 1: asserting network is forked'
            self.assertEquals(False, is_convergent(top.urls(), standard=3))
            print 'phase 6: reconnect 5-net:'
            print 'rezzing validator-2 with InitialConnectivity = |Peers|...'
            cfg = top.get_validator_configuration(2)
            cfg['InitialConnectivity'] = 2
            top.set_validator_configuration(2, cfg)
            top.update(node_mat=vulnerable_mat, probe_seconds=0, reg_seconds=0)
            print 'phase 7: validate state across 5-net:'
            print 'providing time for global convergence...'
            time.sleep(64)
            sit_rep(top.urls())
            print 'TEST 2: asserting network is convergent'
            self.assertEquals(True, is_convergent(top.urls(), standard=4))
        except Exception as e:
            print 'Exception encountered: %s' % (e.message)
            traceback.print_exc()
            sit_rep(top.urls())
        finally:
            top.shutdown(archive_name="TestPartitionRecoveryResults")

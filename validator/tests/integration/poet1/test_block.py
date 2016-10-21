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
import pybitcointools
import time
import unittest

from gossip.common import NullIdentifier
from journal.consensus.poet1.poet_enclave_simulator \
    import poet_enclave_simulator
from journal.consensus.poet1.signup_info import SignupInfo
from journal.consensus.poet1.wait_certificate import WaitTimer
from journal.consensus.poet1.wait_certificate import WaitCertificate

LOGGER = logging.getLogger(__name__)


class TestBlocks(unittest.TestCase):
    def test_block_generation(self):
        # Initialize poet enclave simulator
        SignupInfo.poet_enclave = poet_enclave_simulator
        WaitTimer.poet_enclave = poet_enclave_simulator
        # ...set WT so tests go fast w/o compromising local mean?
        WaitCertificate.poet_enclave = poet_enclave_simulator
        poet_enclave_simulator.initialize()
        # ...init in a journal (keys need to persist for/as v0)
        OSK = pybitcointools.random_key()
        OPK = pybitcointools.privtopub(OSK)
        s_info = SignupInfo.create_signup_info(
            originator_public_key=OPK,
            validator_network_basename="PoET1_TestNet",
            most_recent_wait_certificate_id=NullIdentifier)
        # Create VR transaction seed with s_info
        seed = [s_info]  # stub for now
        # Create block g_block including seed
        g_block = [seed]  # stub for now
        # block_digest = sha256(block)_OSK
        block_digest = str(g_block)  # stub for now
        print 'block digest: %s' % block_digest
        # Create Wait Timer, and wait for it
        WT = WaitTimer.create_wait_timer([])
        t0 = time.time()
        print 'WT: %s' % WT
        print 'waiting %ss (expires in %ss):' % (WT.duration, WT._expires - t0)
        while time.time() < t0 + WT.duration:
            # WT._expires seems too tight...'
            # duration checking not implemented yet...'
            break  # breaking till dur is checked for fast dev cycles
            time.sleep(1)
        # Create Wait Certificate
        WC = WaitCertificate.create_wait_certificate(block_digest)
        self.assertIsNotNone(WC)
        print 'WC: %s' % WC
        # Commit block with WC and shut down ledger
        # Initialize v0 on genesis block, and verify extension
